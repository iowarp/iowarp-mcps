"""Tests for the ``search`` tool and its provider abstraction.

DuckDuckGo is exercised by stubbing the ``ddgs.DDGS`` class; Brave/Tavily by
mocking their HTTP endpoints. No real network occurs in this suite.
"""

from __future__ import annotations

from typing import Any, Literal

import pytest
from fastmcp import Client
from pytest_httpx import HTTPXMock

from web_mcp import server
from web_mcp.server import Settings, create_mcp, mcp

from .helpers import parse_result


class _FakeDDGS:
    """Context-manager stand-in for ``ddgs.DDGS``."""

    def __enter__(self) -> _FakeDDGS:
        return self

    def __exit__(self, *args: Any) -> Literal[False]:
        return False

    def text(self, query: str, max_results: int) -> list[dict[str, str]]:
        del query
        rows = [
            {"title": "First", "href": "https://a.example", "body": "first snippet"},
            {"title": "Second", "href": "https://b.example", "body": "second snippet"},
            {"title": "Third", "href": "https://c.example", "body": "third snippet"},
        ]
        return rows[:max_results]


@pytest.mark.asyncio
async def test_search_ddg_default(monkeypatch: pytest.MonkeyPatch) -> None:
    """The keyless DDG provider is used by default and results are mapped."""
    monkeypatch.setattr(server, "settings", Settings(search_provider="ddg"))
    monkeypatch.setattr("ddgs.DDGS", _FakeDDGS)

    async with Client(mcp) as client:
        result = await client.call_tool("search", {"query": "storm plains", "count": 2})
    data = parse_result(result)

    assert data["ok"] is True
    assert data["provider"] == "ddg"
    assert data["query"] == "storm plains"
    assert data["count"] == 2
    assert data["results"][0] == {
        "title": "First",
        "url": "https://a.example",
        "snippet": "first snippet",
    }


@pytest.mark.asyncio
async def test_search_brave_with_key(
    monkeypatch: pytest.MonkeyPatch, httpx_mock: HTTPXMock
) -> None:
    """Brave is selectable with a key and its response is mapped."""
    monkeypatch.setattr(server, "settings", Settings(search_provider="brave", brave_api_key="k"))
    httpx_mock.add_response(
        json={
            "web": {
                "results": [
                    {
                        "title": "Brave Hit",
                        "url": "https://brave.example/1",
                        "description": "brave snippet",
                    }
                ]
            }
        }
    )
    async with Client(mcp) as client:
        result = await client.call_tool("search", {"query": "anything"})
    data = parse_result(result)
    assert data["provider"] == "brave"
    assert data["results"][0]["title"] == "Brave Hit"
    assert data["results"][0]["url"] == "https://brave.example/1"
    assert data["results"][0]["snippet"] == "brave snippet"


@pytest.mark.asyncio
async def test_search_tavily_with_key(
    monkeypatch: pytest.MonkeyPatch, httpx_mock: HTTPXMock
) -> None:
    """Tavily is selectable with a key and its response is mapped."""
    monkeypatch.setattr(server, "settings", Settings(search_provider="tavily", tavily_api_key="t"))
    httpx_mock.add_response(
        json={
            "results": [
                {
                    "title": "Tavily Hit",
                    "url": "https://tavily.example/1",
                    "content": "tavily snippet",
                }
            ]
        }
    )
    async with Client(mcp) as client:
        result = await client.call_tool("search", {"query": "anything"})
    data = parse_result(result)
    assert data["provider"] == "tavily"
    assert data["results"][0]["title"] == "Tavily Hit"
    assert data["results"][0]["snippet"] == "tavily snippet"


@pytest.mark.asyncio
async def test_search_brave_without_key_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    """Selecting Brave with no key is a typed error, never a silent DDG fallback."""
    monkeypatch.setattr(server, "settings", Settings(search_provider="brave"))
    async with Client(mcp) as client:
        with pytest.raises(Exception) as excinfo:
            await client.call_tool("search", {"query": "anything"})
    assert "WEB_BRAVE_API_KEY" in str(excinfo.value)


@pytest.mark.asyncio
async def test_search_tavily_without_key_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    """Selecting Tavily with no key is a typed error naming the missing config."""
    monkeypatch.setattr(server, "settings", Settings(search_provider="tavily"))
    async with Client(mcp) as client:
        with pytest.raises(Exception) as excinfo:
            await client.call_tool("search", {"query": "anything"})
    assert "WEB_TAVILY_API_KEY" in str(excinfo.value)


@pytest.mark.asyncio
async def test_search_searxng_maps_results_and_native_selectors(
    monkeypatch: pytest.MonkeyPatch, httpx_mock: HTTPXMock
) -> None:
    """SearXNG receives native selectors and exposes engine provenance."""
    searxng_mcp = create_mcp(
        Settings(search_provider="searxng", searxng_base_url="http://10.0.0.102:8088")
    )
    httpx_mock.add_response(
        url=(
            "http://10.0.0.102:8088/search?q=parallel+io&format=json"
            "&engines=arxiv%2Ccrossref&language=en"
            "&time_range=year&pageno=2&safesearch=0"
        ),
        json={
            "results": [
                {
                    "title": "Parallel I/O Paper",
                    "url": "https://example.org/paper",
                    "content": "A scientific result.",
                    "engines": ["arxiv", "crossref"],
                },
                {
                    "title": "Second Result",
                    "url": "https://example.org/second",
                    "content": "Not returned because count is one.",
                    "engine": "arxiv",
                },
            ],
            "unresponsive_engines": [["semantic scholar", "timeout"]],
        },
    )

    async with Client(searxng_mcp) as client:
        result = await client.call_tool(
            "search",
            {
                "query": "parallel io",
                "count": 1,
                "category": "science",
                "engines": ["arxiv", "crossref"],
                "language": "en",
                "time_range": "year",
                "pageno": 2,
                "safesearch": 0,
            },
        )
    data = parse_result(result)

    assert data["provider"] == "searxng"
    assert data["count"] == 1
    assert data["results"] == [
        {
            "title": "Parallel I/O Paper",
            "url": "https://example.org/paper",
            "snippet": "A scientific result.",
            "engines": ["arxiv", "crossref"],
        }
    ]
    assert data["engines_answered"] == ["arxiv", "crossref"]
    assert data["unresponsive_engines"] == [{"engine": "semantic scholar", "reason": "timeout"}]


@pytest.mark.asyncio
async def test_search_searxng_requires_base_url() -> None:
    """Selecting SearXNG without its deployment URL fails at startup."""
    with pytest.raises(ValueError, match="requires --address"):
        create_mcp(Settings(search_provider="searxng"))


@pytest.mark.asyncio
async def test_search_searxng_reports_disabled_json(
    monkeypatch: pytest.MonkeyPatch, httpx_mock: HTTPXMock
) -> None:
    """A 403 identifies the disabled SearXNG JSON API instead of falling back."""
    searxng_mcp = create_mcp(
        Settings(search_provider="searxng", searxng_base_url="http://10.0.0.102:8088")
    )
    httpx_mock.add_response(status_code=403)
    async with Client(searxng_mcp) as client:
        with pytest.raises(Exception) as excinfo:
            await client.call_tool("search", {"query": "anything"})
    assert "JSON" in str(excinfo.value)
    assert "403" in str(excinfo.value)


@pytest.mark.asyncio
@pytest.mark.asyncio
async def test_non_searxng_schema_omits_provider_and_native_selectors() -> None:
    """Provider choice is installation-time and irrelevant arguments are absent."""
    ddg_mcp = create_mcp(Settings(search_provider="ddg"))
    async with Client(ddg_mcp) as client:
        search_tool = next(tool for tool in await client.list_tools() if tool.name == "search")
    properties = search_tool.input_schema["properties"]
    assert set(properties) == {"query", "count"}


@pytest.mark.asyncio
async def test_searxng_schema_contains_native_selectors_and_exact_page_description() -> None:
    """Only the SearXNG installation exposes its native selector schema."""
    searxng_mcp = create_mcp(
        Settings(search_provider="searxng", searxng_base_url="http://10.0.0.102:8088")
    )
    async with Client(searxng_mcp) as client:
        search_tool = next(tool for tool in await client.list_tools() if tool.name == "search")
    properties = search_tool.input_schema["properties"]
    assert set(properties) == {
        "query",
        "count",
        "category",
        "engines",
        "language",
        "time_range",
        "pageno",
        "safesearch",
    }
    assert properties["pageno"]["description"] == (
        "SearXNG result page, bounded by this deployment to 1 through 3."
    )
