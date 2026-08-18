"""Provider-specific search adapters behind the stable Web MCP contract."""

from __future__ import annotations

import asyncio
from typing import Any, Literal

import httpx
from fastmcp.exceptions import ToolError

from web_mcp.config import Settings
from web_mcp.searxng import search_searxng

_BRAVE_ENDPOINT = "https://api.search.brave.com/res/v1/web/search"
_TAVILY_ENDPOINT = "https://api.tavily.com/search"
_MAX_SEARCH_COUNT = 25


async def search_common(configured: Settings, query: str, count: int = 5) -> dict[str, Any]:
    """Search the configured DDG, Brave, or Tavily provider."""

    text = (query or "").strip()
    if not text:
        raise ToolError("A non-empty query is required.")
    effective_count = min(count if count and count > 0 else 5, _MAX_SEARCH_COUNT)
    if configured.search_provider == "ddg":
        results = await _search_ddg(text, effective_count)
    elif configured.search_provider == "brave":
        results = await _search_brave(configured, text, effective_count)
    elif configured.search_provider == "tavily":
        results = await _search_tavily(configured, text, effective_count)
    else:
        raise ToolError("The active search provider requires the SearXNG search schema.")
    return {
        "ok": True,
        "provider": configured.search_provider,
        "query": text,
        "results": results,
        "count": len(results),
    }


async def search_searxng_provider(
    configured: Settings,
    query: str,
    count: int = 5,
    category: Literal["general", "science", "it"] | None = None,
    engines: list[str] | None = None,
    language: str | None = None,
    time_range: Literal["day", "month", "year"] | None = None,
    pageno: int = 1,
    safesearch: int | None = None,
) -> dict[str, Any]:
    """Search the configured SearXNG provider with native selectors."""

    text = (query or "").strip()
    if not text:
        raise ToolError("A non-empty query is required.")
    effective_count = min(count if count and count > 0 else 5, _MAX_SEARCH_COUNT)
    results, engines_answered, unresponsive_engines = await search_searxng(
        text,
        effective_count,
        base_url=configured.effective_searxng_url,
        connect_timeout_s=configured.connect_timeout_s,
        read_timeout_s=configured.read_timeout_s,
        category=category,
        engines=engines,
        language=language,
        time_range=time_range,
        pageno=pageno,
        safesearch=safesearch,
    )
    return {
        "ok": True,
        "provider": "searxng",
        "query": text,
        "results": results,
        "count": len(results),
        "engines_answered": engines_answered,
        "unresponsive_engines": unresponsive_engines,
    }


async def _search_ddg(query: str, count: int) -> list[dict[str, str]]:
    return await asyncio.to_thread(_ddgs_search, query, count)


def _ddgs_search(query: str, count: int) -> list[dict[str, str]]:
    from ddgs import DDGS

    results: list[dict[str, str]] = []
    with DDGS() as ddgs:
        for item in ddgs.text(query, max_results=count):
            results.append(
                {
                    "title": str(item.get("title") or ""),
                    "url": str(item.get("href") or item.get("url") or ""),
                    "snippet": str(item.get("body") or item.get("snippet") or ""),
                }
            )
    return results


async def _search_brave(configured: Settings, query: str, count: int) -> list[dict[str, str]]:
    if not configured.brave_api_key:
        raise ToolError(
            "search provider 'brave' requires an API key. Set WEB_BRAVE_API_KEY "
            "or choose a different provider."
        )
    headers = {
        "X-Subscription-Token": configured.brave_api_key,
        "Accept": "application/json",
    }
    async with httpx.AsyncClient(timeout=httpx.Timeout(configured.read_timeout_s)) as client:
        response = await client.get(
            _BRAVE_ENDPOINT, headers=headers, params={"q": query, "count": count}
        )
        response.raise_for_status()
        payload = response.json()
    return [
        {
            "title": str(item.get("title") or ""),
            "url": str(item.get("url") or ""),
            "snippet": str(item.get("description") or ""),
        }
        for item in ((payload.get("web") or {}).get("results") or [])[:count]
    ]


async def _search_tavily(configured: Settings, query: str, count: int) -> list[dict[str, str]]:
    if not configured.tavily_api_key:
        raise ToolError(
            "search provider 'tavily' requires an API key. Set WEB_TAVILY_API_KEY "
            "or choose a different provider."
        )
    body = {
        "api_key": configured.tavily_api_key,
        "query": query,
        "max_results": count,
    }
    async with httpx.AsyncClient(timeout=httpx.Timeout(configured.read_timeout_s)) as client:
        response = await client.post(_TAVILY_ENDPOINT, json=body)
        response.raise_for_status()
        payload = response.json()
    return [
        {
            "title": str(item.get("title") or ""),
            "url": str(item.get("url") or ""),
            "snippet": str(item.get("content") or ""),
        }
        for item in (payload.get("results") or [])[:count]
    ]
