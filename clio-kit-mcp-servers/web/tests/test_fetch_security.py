"""Security + fallback-chain coverage for ``fetch``.

SSRF guard (direct + per-redirect-hop), redirect provenance, the extractor downgrade signal,
and content-sniff for a missing content-type. All network is mocked via pytest-httpx.
"""

from __future__ import annotations

import pytest
from fastmcp import Client
from pytest_httpx import HTTPXMock

from web_mcp import server
from web_mcp.server import REASON_BINARY_NOT_INLINED, REASON_BLOCKED_HOST, mcp

from .helpers import parse_result

_HTML = (
    "<html><head><title>T</title></head><body><article>"
    "<p>Real body content here, several words long so extraction succeeds.</p>"
    "</article></body></html>"
)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "url",
    [
        "http://169.254.169.254/latest/meta-data/iam/security-credentials/",  # cloud metadata
        "http://127.0.0.1:8080/internal",
        "http://10.0.0.5/admin",
        "http://192.168.1.1/",
        "http://localhost/secret",
        "http://[::1]/",
    ],
)
async def test_fetch_blocks_private_and_metadata_hosts(url: str) -> None:
    """A literal loopback/private/link-local host (or localhost) is refused before any request."""
    async with Client(mcp) as client:
        with pytest.raises(Exception) as excinfo:
            await client.call_tool("fetch", {"url": url})
    assert REASON_BLOCKED_HOST in str(excinfo.value)


@pytest.mark.asyncio
async def test_fetch_blocks_redirect_into_metadata(httpx_mock: HTTPXMock) -> None:
    """A public url that 302-redirects to the metadata IP is blocked at the hop (redirect SSRF)."""
    httpx_mock.add_response(
        url="https://public.test/go",
        status_code=302,
        headers={"location": "http://169.254.169.254/latest/meta-data/"},
    )
    async with Client(mcp) as client:
        with pytest.raises(Exception) as excinfo:
            await client.call_tool("fetch", {"url": "https://public.test/go"})
    assert REASON_BLOCKED_HOST in str(excinfo.value)


@pytest.mark.asyncio
async def test_fetch_allow_private_hosts_config_opens_the_guard(
    httpx_mock: HTTPXMock, monkeypatch: pytest.MonkeyPatch
) -> None:
    """With allow_private_hosts=True the guard is off (deliberate internal fetcher)."""
    monkeypatch.setattr(server.settings, "allow_private_hosts", True)
    httpx_mock.add_response(
        url="http://127.0.0.1:9000/health",
        content=b"OK",
        headers={"content-type": "text/plain"},
    )
    async with Client(mcp) as client:
        result = await client.call_tool("fetch", {"url": "http://127.0.0.1:9000/health"})
    assert parse_result(result)["content"] == "OK"


@pytest.mark.asyncio
async def test_fetch_follows_redirect_and_reports_final_url(httpx_mock: HTTPXMock) -> None:
    """A public->public redirect is followed; url stays verbatim, final_url is the resolved hop."""
    httpx_mock.add_response(
        url="https://a.test/start",
        status_code=302,
        headers={"location": "https://b.test/end"},
    )
    httpx_mock.add_response(
        url="https://b.test/end", content=b"done", headers={"content-type": "text/plain"}
    )
    async with Client(mcp) as client:
        result = await client.call_tool("fetch", {"url": "https://a.test/start"})
    data = parse_result(result)
    assert data["url"] == "https://a.test/start"  # verbatim source
    assert data["final_url"] == "https://b.test/end"  # resolved after redirect
    assert data["content"] == "done"


@pytest.mark.asyncio
async def test_fetch_reports_extractor_trafilatura(httpx_mock: HTTPXMock) -> None:
    """A normal HTML page names the trafilatura extractor (downgrade is visible)."""
    httpx_mock.add_response(
        url="https://x.test/a", content=_HTML.encode(), headers={"content-type": "text/html"}
    )
    async with Client(mcp) as client:
        data = parse_result(await client.call_tool("fetch", {"url": "https://x.test/a"}))
    assert data["extractor"] == "trafilatura"


@pytest.mark.asyncio
async def test_fetch_reports_readability_downgrade(
    httpx_mock: HTTPXMock, monkeypatch: pytest.MonkeyPatch
) -> None:
    """When trafilatura yields nothing, readability runs AND is named (no silent downgrade)."""
    monkeypatch.setattr(server.trafilatura, "extract", lambda *a, **k: None)
    httpx_mock.add_response(
        url="https://x.test/b", content=_HTML.encode(), headers={"content-type": "text/html"}
    )
    async with Client(mcp) as client:
        data = parse_result(await client.call_tool("fetch", {"url": "https://x.test/b"}))
    assert data["extractor"] == "readability"
    assert data["content"] and "body content" in data["content"].lower()


@pytest.mark.asyncio
async def test_fetch_reports_plaintext_downgrade(
    httpx_mock: HTTPXMock, monkeypatch: pytest.MonkeyPatch
) -> None:
    """When both trafilatura and readability fail, the plaintext rung runs and is named."""
    monkeypatch.setattr(server.trafilatura, "extract", lambda *a, **k: None)

    def _boom(*_a: object, **_k: object) -> object:
        raise RuntimeError("readability down")

    monkeypatch.setattr(server, "ReadabilityDocument", _boom)
    httpx_mock.add_response(
        url="https://x.test/c", content=_HTML.encode(), headers={"content-type": "text/html"}
    )
    async with Client(mcp) as client:
        data = parse_result(await client.call_tool("fetch", {"url": "https://x.test/c"}))
    assert data["extractor"] == "plaintext"
    assert data["content"] and "body content" in data["content"].lower()


@pytest.mark.asyncio
async def test_fetch_no_content_type_text_is_sniffed_and_returned(httpx_mock: HTTPXMock) -> None:
    """A text body served with NO content-type is sniffed as text and returned, not withheld."""
    httpx_mock.add_response(url="https://x.test/raw", content=b"plain api response, no header")
    async with Client(mcp) as client:
        data = parse_result(await client.call_tool("fetch", {"url": "https://x.test/raw"}))
    assert data["content"] == "plain api response, no header"


@pytest.mark.asyncio
async def test_fetch_no_content_type_binary_stays_a_typed_note(httpx_mock: HTTPXMock) -> None:
    """A binary body with NO content-type is still withheld with the typed note (never junk)."""
    httpx_mock.add_response(url="https://x.test/bin", content=b"\x00\x01\x02\x03binary\x00blob")
    async with Client(mcp) as client:
        data = parse_result(await client.call_tool("fetch", {"url": "https://x.test/bin"}))
    assert data.get("content") is None
    assert data["reason"] == REASON_BINARY_NOT_INLINED
