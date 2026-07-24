"""Real-network integration tests (opt-in, skipped by default).

These hit the live internet and are therefore excluded from the default suite.
Run explicitly with::

    WEB_MCP_LIVE=1 uv run pytest -m integration
"""

from __future__ import annotations

import os

import pytest
from fastmcp import Client

from web_mcp.server import mcp

from .helpers import parse_result

_LIVE = os.getenv("WEB_MCP_LIVE") == "1"

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(not _LIVE, reason="set WEB_MCP_LIVE=1 to run real-network tests"),
]


@pytest.mark.asyncio
async def test_live_fetch_example_com() -> None:
    """Fetch a real, stable page and confirm content comes back."""
    async with Client(mcp) as client:
        result = await client.call_tool("fetch", {"url": "https://example.com/"})
    data = parse_result(result)
    assert data["ok"] is True
    assert data["url"] == "https://example.com/"
    assert data["content"]


@pytest.mark.asyncio
async def test_live_search_ddg() -> None:
    """Run a real keyless DuckDuckGo search."""
    async with Client(mcp) as client:
        result = await client.call_tool("search", {"query": "iowarp clio", "count": 3})
    data = parse_result(result)
    assert data["ok"] is True
    assert data["provider"] == "ddg"
