"""Tests for the ``search`` tool and its provider abstraction.

DuckDuckGo is exercised by stubbing the ``ddgs.DDGS`` class; Brave/Tavily by
mocking their HTTP endpoints. No real network occurs in this suite.
"""

from __future__ import annotations

from typing import Any

import pytest
from fastmcp import Client
from pytest_httpx import HTTPXMock

from web_mcp import server
from web_mcp.server import Settings, mcp

from .helpers import parse_result


class _FakeDDGS:
    """Context-manager stand-in for ``ddgs.DDGS``."""

    def __enter__(self) -> _FakeDDGS:
        return self

    def __exit__(self, *args: Any) -> bool:
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
async def test_search_provider_override_beats_config(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """An explicit provider argument overrides the configured default."""
    monkeypatch.setattr(server, "settings", Settings(search_provider="ddg"))
    async with Client(mcp) as client:
        with pytest.raises(Exception) as excinfo:
            await client.call_tool("search", {"query": "x", "provider": "brave"})
    assert "WEB_BRAVE_API_KEY" in str(excinfo.value)


@pytest.mark.asyncio
async def test_search_unknown_provider_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    """An unknown provider is rejected with a typed error."""
    monkeypatch.setattr(server, "settings", Settings(search_provider="bing"))
    async with Client(mcp) as client:
        with pytest.raises(Exception) as excinfo:
            await client.call_tool("search", {"query": "x"})
    assert "Unknown search provider" in str(excinfo.value)
