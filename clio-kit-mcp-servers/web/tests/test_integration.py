"""Real-network integration tests (opt-in, skipped by default).

These hit the live internet and are therefore excluded from the default suite.
Run explicitly with::

    WEB_MCP_LIVE=1 uv run pytest -m integration
"""

from __future__ import annotations

import os

import pytest
from fastmcp import Client

from web_mcp.server import Settings, create_mcp, mcp

from .helpers import parse_result

_LIVE = os.getenv("WEB_MCP_LIVE") == "1"
_SEARXNG_URL = os.getenv("WEB_SEARXNG_BASE_URL")

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(not _LIVE, reason="set WEB_MCP_LIVE=1 to run real-network tests"),
]


@pytest.mark.asyncio
async def test_live_fetch_example_com() -> None:
    """Fetch a real, stable page and confirm content comes back."""
    async with Client(mcp) as client:
        result = await client.call_tool("fetch", {"target": "https://example.com/"})
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


@pytest.mark.skipif(
    not _SEARXNG_URL,
    reason="set WEB_SEARXNG_BASE_URL to run the live SearXNG integration test",
)
@pytest.mark.asyncio
async def test_live_search_searxng() -> None:
    """Exercise category and engine selectors against the deployed instance."""
    searxng_mcp = create_mcp(
        Settings(search_provider="searxng", searxng_base_url=_SEARXNG_URL),
    )
    async with Client(searxng_mcp) as client:
        result = await client.call_tool(
            "search",
            {
                "query": "parallel I/O",
                "count": 3,
                "category": "science",
                "engines": ["arxiv", "crossref"],
                "language": "en",
                "safesearch": 0,
            },
        )
    data = parse_result(result)
    assert data["ok"] is True
    assert data["provider"] == "searxng"
    assert data["count"] > 0
    assert data["results"]
    assert "engines_answered" in data
    assert "unresponsive_engines" in data
