"""Tests for the ``fetch`` tool.

All network access is mocked via pytest-httpx; the tool is driven through the
in-memory FastMCP client. No real HTTP occurs in this suite.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from fastmcp import Client
from pytest_httpx import HTTPXMock, IteratorStream

from web_mcp import server
from web_mcp.server import REASON_BINARY_NOT_INLINED, REASON_JS_RENDER_REQUIRED, mcp

from .helpers import parse_result

_HTML = (
    "<html><head><title>Weather Report</title></head>"
    "<body><article><h1>Storm Watch</h1>"
    "<p>A powerful storm system is moving across the plains this week, "
    "bringing heavy rain and strong winds to the region. Residents should "
    "prepare for possible flooding along low-lying roads.</p>"
    '<p>See the <a href="https://noaa.example/alerts">NOAA alerts</a> page '
    "for the latest advisories and evacuation guidance.</p>"
    "</article></body></html>"
)


@pytest.mark.asyncio
async def test_fetch_html_to_markdown(httpx_mock: HTTPXMock) -> None:
    """HTML is converted to Markdown/text and the title is extracted."""
    httpx_mock.add_response(
        url="https://example.test/report",
        content=_HTML.encode("utf-8"),
        headers={"content-type": "text/html; charset=utf-8"},
    )
    async with Client(mcp) as client:
        result = await client.call_tool("fetch", {"url": "https://example.test/report"})
    data = parse_result(result)

    assert data["ok"] is True
    assert data["method"] == "http"
    assert data["status"] == 200
    assert data["title"] == "Weather Report"
    assert data["content"] is not None
    assert "storm" in data["content"].lower()


@pytest.mark.asyncio
async def test_fetch_url_round_trips_verbatim(httpx_mock: HTTPXMock) -> None:
    """The fetched source URL is returned verbatim (provenance keys off it)."""
    url = "https://example.test/path?a=1&b=2"
    httpx_mock.add_response(
        url=url,
        content=b"hello",
        headers={"content-type": "text/plain"},
    )
    async with Client(mcp) as client:
        result = await client.call_tool("fetch", {"url": url})
    data = parse_result(result)
    assert data["url"] == url


@pytest.mark.asyncio
async def test_fetch_text_passthrough(httpx_mock: HTTPXMock) -> None:
    """Non-HTML text is returned as-is."""
    httpx_mock.add_response(
        url="https://example.test/data.txt",
        content=b"plain body text",
        headers={"content-type": "text/plain"},
    )
    async with Client(mcp) as client:
        result = await client.call_tool("fetch", {"url": "https://example.test/data.txt"})
    data = parse_result(result)
    assert data["content"] == "plain body text"
    assert data["content_type"] == "text/plain"
    assert data["title"] is None


@pytest.mark.asyncio
async def test_fetch_rejects_non_http_scheme() -> None:
    """A non-http(s) URL raises a ToolError before any network call."""
    async with Client(mcp) as client:
        with pytest.raises(Exception) as excinfo:
            await client.call_tool("fetch", {"url": "ftp://example.test/x"})
    assert "http(s)" in str(excinfo.value)


@pytest.mark.asyncio
async def test_fetch_size_cap_content_length(httpx_mock: HTTPXMock) -> None:
    """An advertised content-length over the cap raises a ToolError."""
    httpx_mock.add_response(
        url="https://example.test/big.bin",
        content=b"x" * 100,
        headers={"content-type": "text/plain"},
    )
    async with Client(mcp) as client:
        with pytest.raises(Exception) as excinfo:
            await client.call_tool(
                "fetch", {"url": "https://example.test/big.bin", "max_bytes": 10}
            )
    assert "exceeds the fetch size limit" in str(excinfo.value)


@pytest.mark.asyncio
async def test_fetch_size_cap_mid_stream(httpx_mock: HTTPXMock) -> None:
    """A body that exceeds the cap mid-stream (no content-length) raises."""
    httpx_mock.add_response(
        url="https://example.test/stream",
        stream=IteratorStream([b"a" * 8, b"b" * 8]),
        headers={"content-type": "text/plain"},
    )
    async with Client(mcp) as client:
        with pytest.raises(Exception) as excinfo:
            await client.call_tool("fetch", {"url": "https://example.test/stream", "max_bytes": 10})
    assert "while downloading" in str(excinfo.value)


@pytest.mark.asyncio
async def test_fetch_to_file_writes_and_returns_path(httpx_mock: HTTPXMock, tmp_path: Path) -> None:
    """to_file writes the content to disk and returns local_path (no inline content)."""
    httpx_mock.add_response(
        url="https://example.test/notes.txt",
        content=b"saved body",
        headers={"content-type": "text/plain"},
    )
    out = tmp_path / "out"
    async with Client(mcp) as client:
        result = await client.call_tool(
            "fetch",
            {
                "url": "https://example.test/notes.txt",
                "to_file": True,
                "output_dir": str(out),
            },
        )
    data = parse_result(result)
    assert "content" not in data
    local_path = Path(data["local_path"])
    assert local_path.exists()
    assert local_path.read_text(encoding="utf-8") == "saved body"
    assert str(local_path).startswith(str(out.resolve()))


@pytest.mark.asyncio
async def test_fetch_binary_without_to_file_is_typed_note(httpx_mock: HTTPXMock) -> None:
    """Binary content is not inlined; a typed reason is returned instead."""
    httpx_mock.add_response(
        url="https://example.test/image.png",
        content=b"\x89PNG\r\n\x1a\n\x00\x00",
        headers={"content-type": "image/png"},
    )
    async with Client(mcp) as client:
        result = await client.call_tool("fetch", {"url": "https://example.test/image.png"})
    data = parse_result(result)
    assert data["content"] is None
    assert data["reason"] == REASON_BINARY_NOT_INLINED


@pytest.mark.asyncio
async def test_fetch_binary_to_file_writes_raw_bytes(httpx_mock: HTTPXMock, tmp_path: Path) -> None:
    """Binary content with to_file=True is written raw to disk."""
    blob = b"\x89PNG\r\n\x1a\n\x00\x01\x02\x03"
    httpx_mock.add_response(
        url="https://example.test/image.png",
        content=blob,
        headers={"content-type": "image/png"},
    )
    out = tmp_path / "bin"
    async with Client(mcp) as client:
        result = await client.call_tool(
            "fetch",
            {"url": "https://example.test/image.png", "to_file": True, "output_dir": str(out)},
        )
    data = parse_result(result)
    local_path = Path(data["local_path"])
    assert local_path.read_bytes() == blob


@pytest.mark.asyncio
async def test_fetch_empty_html_signals_js_render(httpx_mock: HTTPXMock) -> None:
    """HTML with no extractable content returns the headless-browser reason."""
    empty_js_page = (
        "<html><head><title>App</title></head><body>"
        "<div id='root'></div>"
        "<script>window.__data=1;</script></body></html>"
    )
    httpx_mock.add_response(
        url="https://example.test/spa",
        content=empty_js_page.encode("utf-8"),
        headers={"content-type": "text/html"},
    )
    async with Client(mcp) as client:
        result = await client.call_tool("fetch", {"url": "https://example.test/spa"})
    data = parse_result(result)
    assert data["content"] is None
    assert data["reason"] == REASON_JS_RENDER_REQUIRED


@pytest.mark.asyncio
async def test_fetch_max_bytes_default_from_settings(
    httpx_mock: HTTPXMock, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The size cap defaults to Settings.max_bytes when not overridden."""
    monkeypatch.setattr(server, "settings", server.Settings(max_bytes=5))
    httpx_mock.add_response(
        url="https://example.test/toobig",
        content=b"x" * 50,
        headers={"content-type": "text/plain"},
    )
    async with Client(mcp) as client:
        with pytest.raises(Exception) as excinfo:
            await client.call_tool("fetch", {"url": "https://example.test/toobig"})
    assert "exceeds the fetch size limit" in str(excinfo.value)
