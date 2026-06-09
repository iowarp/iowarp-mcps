"""Tests for the NDP resource-staging tool.

``stage_resource`` is exercised through the in-memory FastMCP client with all
network access mocked, so no real HTTP/OSDF traffic occurs.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
from fastmcp import Client

from ndp_mcp import server
from ndp_mcp.server import mcp


def _parse_result(result: Any) -> dict[str, Any]:
    data = result.data
    if isinstance(data, dict):
        return data
    if isinstance(data, str):
        return json.loads(data)
    return {"raw": str(data)}


@pytest.fixture(autouse=True)
def _artifacts_root(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Confine all artifact writes to the pytest temp dir."""
    root = tmp_path / "artifacts"
    monkeypatch.setenv("CLIO_KIT_ARTIFACTS", str(root))
    return root


# ---------------------------------------------------------------------------
# artifacts_root precedence
# ---------------------------------------------------------------------------


def test_artifacts_root_explicit_output_dir_wins(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """An explicit output_dir takes precedence over env and CWD."""
    monkeypatch.setenv("CLIO_KIT_ARTIFACTS", str(tmp_path / "env"))
    explicit = tmp_path / "explicit"
    assert server.artifacts_root(explicit) == explicit.resolve()


def test_artifacts_root_env_overrides_cwd(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """CLIO_KIT_ARTIFACTS is used when no explicit output_dir is supplied."""
    env_root = tmp_path / "env"
    monkeypatch.setenv("CLIO_KIT_ARTIFACTS", str(env_root))
    monkeypatch.chdir(tmp_path)
    assert server.artifacts_root() == env_root.resolve()


def test_artifacts_root_defaults_to_cwd(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """With no output_dir and no env var, the fallback is the process CWD.

    A caller that launches the server from a chosen working directory gets
    artifacts written there by default.
    """
    monkeypatch.delenv("CLIO_KIT_ARTIFACTS", raising=False)
    monkeypatch.chdir(tmp_path)
    assert server.artifacts_root() == tmp_path.resolve()


# ---------------------------------------------------------------------------
# stage_resource
# ---------------------------------------------------------------------------


class _FakeStreamResponse:
    """Minimal async stand-in for an httpx streaming response."""

    def __init__(self, *, chunks: list[bytes], headers: dict[str, str]) -> None:
        self._chunks = chunks
        self.headers = headers
        self.url = "https://example.test/sample.csv"

    async def __aenter__(self) -> _FakeStreamResponse:
        return self

    async def __aexit__(self, *args: Any) -> None:
        return None

    def raise_for_status(self) -> None:
        return None

    async def aiter_bytes(self, chunk_size: int):
        del chunk_size
        for chunk in self._chunks:
            yield chunk


class _FakeAsyncClient:
    """Async client stub returning a preconfigured streaming response."""

    def __init__(self, response: _FakeStreamResponse) -> None:
        self._response = response

    async def __aenter__(self) -> _FakeAsyncClient:
        return self

    async def __aexit__(self, *args: Any) -> None:
        return None

    def stream(self, method: str, url: str):
        del method, url
        return self._response


@pytest.mark.asyncio
async def test_stage_resource_http_writes_file_and_shape(
    monkeypatch: pytest.MonkeyPatch,
    _artifacts_root: Path,
) -> None:
    """An HTTP(S) resource is streamed to a local file with the expected shape."""
    payload = b"time,east,north,up\n1,0.1,0.2,0.3\n"
    response = _FakeStreamResponse(
        chunks=[payload],
        headers={"content-length": str(len(payload)), "content-type": "text/csv"},
    )

    def fake_client(*args: Any, **kwargs: Any) -> _FakeAsyncClient:
        return _FakeAsyncClient(response)

    monkeypatch.setattr(server.httpx, "AsyncClient", fake_client)

    async with Client(mcp) as client:
        result = await client.call_tool(
            "stage_resource",
            {"url": "https://example.test/sample.csv"},
        )

    data = _parse_result(result)
    assert data["ok"] is True
    assert data["content_type"] == "text/csv"
    assert data["size_bytes"] == len(payload)
    assert data["method"] == "http"
    local_path = Path(data["local_path"])
    assert local_path.exists()
    assert local_path.read_bytes() == payload
    # File must live under the configured artifacts root, not a hardcoded path.
    assert str(local_path).startswith(str(_artifacts_root.resolve()))
    assert local_path.name == "sample.csv"


@pytest.mark.asyncio
async def test_stage_resource_http_size_cap_raises(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Advertised content-length over max_bytes raises a ToolError (no partial file)."""
    response = _FakeStreamResponse(
        chunks=[b"x" * 100],
        headers={"content-length": "100"},
    )

    def fake_client(*args: Any, **kwargs: Any) -> _FakeAsyncClient:
        return _FakeAsyncClient(response)

    monkeypatch.setattr(server.httpx, "AsyncClient", fake_client)

    async with Client(mcp) as client:
        with pytest.raises(Exception) as excinfo:
            await client.call_tool(
                "stage_resource",
                {"url": "https://example.test/big.bin", "max_bytes": 10},
            )

    assert "staging limit" in str(excinfo.value)


@pytest.mark.asyncio
async def test_stage_resource_rejects_unsupported_scheme() -> None:
    """Non HTTP(S)/OSDF URLs are rejected."""
    async with Client(mcp) as client:
        with pytest.raises(Exception) as excinfo:
            await client.call_tool("stage_resource", {"url": "ftp://example.test/x"})
    assert "Unsupported resource URL scheme" in str(excinfo.value)


@pytest.mark.asyncio
async def test_stage_resource_osdf_requires_pelican(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """OSDF resources fail clearly when the pelican CLI is unavailable."""
    monkeypatch.setattr(server.shutil, "which", lambda name: None)

    async with Client(mcp) as client:
        with pytest.raises(Exception) as excinfo:
            await client.call_tool(
                "stage_resource",
                {"url": "osdf:///ndp/public/data/object.bin"},
            )
    assert "pelican" in str(excinfo.value).lower()
