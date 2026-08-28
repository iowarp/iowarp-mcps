"""Focused unit coverage for the self-hosted SearXNG adapter."""

from __future__ import annotations

from typing import Any

import httpx
import pytest
from fastmcp.exceptions import ToolError
from pytest_httpx import HTTPXMock

from web_mcp.searxng import (
    _normalize_unresponsive_engines,
    _search_endpoint,
    search_searxng,
)


async def _search(
    *, category: str | None = None
) -> tuple[list[dict[str, Any]], list[str], list[dict[str, str]]]:
    """Call the adapter with deterministic defaults."""
    return await search_searxng(
        "query",
        3,
        base_url="http://10.0.0.102:8088",
        connect_timeout_s=1.0,
        read_timeout_s=2.0,
        category=category,
        engines=None,
        language=None,
        time_range=None,
        pageno=1,
        safesearch=None,
    )


@pytest.mark.parametrize(
    ("url", "message"),
    [
        ("not-a-url", r"absolute http\(s\) URL"),
        ("http://10.0.0.102:8088?bad=1", "query string or fragment"),
    ],
)
def test_search_endpoint_rejects_invalid_roots(url: str, message: str) -> None:
    """The configured root must be an absolute URL without query state."""
    with pytest.raises(ToolError, match=message):
        _search_endpoint(url)


def test_normalize_unresponsive_engines_handles_dicts_and_other_values() -> None:
    """Dict-form failures are normalized and non-list payloads are ignored."""
    assert _normalize_unresponsive_engines(None) == []
    assert _normalize_unresponsive_engines(
        [{"engine": "arxiv"}, {"engine": "crossref", "reason": "timeout"}, {}]
    ) == [
        {"engine": "arxiv", "reason": "unknown"},
        {"engine": "crossref", "reason": "timeout"},
    ]


@pytest.mark.asyncio
async def test_search_category_maps_single_engine_and_skips_invalid_rows(
    httpx_mock: HTTPXMock,
) -> None:
    """Category-only calls are forwarded and alternate result fields are mapped."""
    httpx_mock.add_response(
        url=("http://10.0.0.102:8088/search?q=query&format=json&categories=it&pageno=1"),
        json={
            "results": [
                "invalid",
                {
                    "title": "Repository",
                    "url": "https://github.com/iowarp/clio-agent",
                    "snippet": "Fallback snippet.",
                    "engine": "github",
                },
            ]
        },
    )
    results, engines, unresponsive = await _search(category="it")
    assert results == [
        {
            "title": "Repository",
            "url": "https://github.com/iowarp/clio-agent",
            "snippet": "Fallback snippet.",
            "engines": ["github"],
        }
    ]
    assert engines == ["github"]
    assert unresponsive == []


@pytest.mark.asyncio
async def test_search_reports_transport_failure(httpx_mock: HTTPXMock) -> None:
    """Connection failures become typed SearXNG errors."""
    httpx_mock.add_exception(httpx.ConnectError("offline"))
    with pytest.raises(ToolError, match="Could not query SearXNG"):
        await _search()


@pytest.mark.asyncio
async def test_search_reports_non_403_http_failure(httpx_mock: HTTPXMock) -> None:
    """Non-403 HTTP failures retain the status code in a typed error."""
    httpx_mock.add_response(status_code=500)
    with pytest.raises(ToolError, match="HTTP 500"):
        await _search()


@pytest.mark.asyncio
async def test_search_reports_non_json_response(httpx_mock: HTTPXMock) -> None:
    """HTML or text responses cannot masquerade as a successful search."""
    httpx_mock.add_response(text="not json", headers={"content-type": "text/plain"})
    with pytest.raises(ToolError, match="did not return JSON"):
        await _search()


@pytest.mark.asyncio
async def test_search_reports_malformed_json(httpx_mock: HTTPXMock) -> None:
    """JSON without a result list is rejected explicitly."""
    httpx_mock.add_response(json={"results": {}})
    with pytest.raises(ToolError, match="malformed JSON"):
        await _search()
