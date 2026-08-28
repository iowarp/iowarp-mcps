"""Self-hosted SearXNG JSON API adapter for the web MCP server."""

from __future__ import annotations

import re
from typing import Any
from urllib.parse import urlparse

import httpx
from fastmcp.exceptions import ToolError

_CITATION_COUNT_RE = re.compile(r"^(\d+)\s+citations?$", re.IGNORECASE)


def _string_list(value: Any) -> list[str]:
    """Normalize a SearXNG scalar/list metadata field to non-empty strings."""

    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    if isinstance(value, str) and value.strip():
        return [value.strip()]
    return []


def _citation_count(item: dict[str, Any]) -> int | None:
    """Parse only explicit SearXNG citation-count labels."""

    direct = item.get("citation_count")
    if isinstance(direct, int) and not isinstance(direct, bool) and direct >= 0:
        return direct
    for candidate in _string_list(item.get("comments")):
        match = _CITATION_COUNT_RE.fullmatch(candidate)
        if match:
            return int(match.group(1))
    return None


def _normalize_result(item: dict[str, Any]) -> dict[str, Any]:
    """Preserve useful standard and scholarly fields from one SearXNG result."""

    engines = _string_list(item.get("engines"))
    if not engines and item.get("engine"):
        engines = [str(item["engine"])]
    result: dict[str, Any] = {
        "title": str(item.get("title") or ""),
        "url": str(item.get("url") or ""),
        "snippet": str(item.get("content") or item.get("snippet") or ""),
        "engines": engines,
    }
    aliases: dict[str, tuple[str, ...]] = {
        "authors": ("authors", "author"),
        "doi": ("doi",),
        "published_at": ("published_at", "publishedDate", "published_date"),
        "journal": ("journal",),
        "publisher": ("publisher",),
        "document_type": ("document_type", "type"),
        "pdf_url": ("pdf_url",),
        "html_url": ("html_url",),
        "tags": ("tags",),
        "score": ("score",),
    }
    for output_name, source_names in aliases.items():
        value = next((item[name] for name in source_names if item.get(name) is not None), None)
        if value not in (None, "", []):
            result[output_name] = (
                _string_list(value) if output_name in {"authors", "tags"} else value
            )
    citation_count = _citation_count(item)
    if citation_count is not None:
        result["citation_count"] = citation_count
    return result


def _search_endpoint(base_url: str | None) -> str:
    """Return the configured SearXNG search endpoint or raise a typed error."""
    value = (base_url or "").strip()
    parsed = urlparse(value)
    if not value:
        raise ToolError(
            "search provider 'searxng' requires its deployment URL. "
            "Set WEB_SEARXNG_BASE_URL (Settings.searxng_base_url)."
        )
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        raise ToolError(f"WEB_SEARXNG_BASE_URL must be an absolute http(s) URL; got {value!r}.")
    if parsed.query or parsed.fragment:
        raise ToolError("WEB_SEARXNG_BASE_URL must not contain a query string or fragment.")
    return f"{value.rstrip('/')}/search"


def _normalize_unresponsive_engines(value: Any) -> list[dict[str, str]]:
    """Normalize SearXNG's ``[engine, reason]`` pairs for MCP callers."""
    if not isinstance(value, list):
        return []
    normalized: list[dict[str, str]] = []
    for item in value:
        if isinstance(item, (list, tuple)) and len(item) >= 2:
            normalized.append({"engine": str(item[0]), "reason": str(item[1])})
        elif isinstance(item, dict) and item.get("engine"):
            normalized.append(
                {
                    "engine": str(item["engine"]),
                    "reason": str(item.get("reason") or "unknown"),
                }
            )
    return normalized


async def search_searxng(
    query: str,
    count: int,
    *,
    base_url: str | None,
    connect_timeout_s: float,
    read_timeout_s: float,
    category: str | None,
    engines: list[str] | None,
    language: str | None,
    time_range: str | None,
    pageno: int,
    safesearch: int | None,
) -> tuple[list[dict[str, Any]], list[str], list[dict[str, str]]]:
    """Search a configured self-hosted SearXNG instance via its JSON API."""
    endpoint = _search_endpoint(base_url)
    params: dict[str, str | int] = {"q": query, "format": "json"}
    selected_engines = [name.strip() for name in engines or [] if name.strip()]
    if selected_engines:
        params["engines"] = ",".join(selected_engines)
    elif category:
        params["categories"] = category
    if language and language.strip():
        params["language"] = language.strip()
    if time_range:
        params["time_range"] = time_range
    params["pageno"] = pageno
    if safesearch is not None:
        params["safesearch"] = safesearch

    timeout = httpx.Timeout(read_timeout_s, connect=connect_timeout_s)
    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.get(endpoint, params=params)
    except httpx.HTTPError as exc:
        raise ToolError(f"Could not query SearXNG at {endpoint}: {exc}") from exc

    if response.status_code == 403:
        raise ToolError(
            "SearXNG returned HTTP 403 for its JSON API. Ensure 'json' is enabled "
            "under search.formats in settings.yml."
        )
    try:
        response.raise_for_status()
    except httpx.HTTPStatusError as exc:
        raise ToolError(
            f"SearXNG search failed with HTTP {response.status_code} at {endpoint}."
        ) from exc
    try:
        payload = response.json()
    except ValueError as exc:
        raise ToolError(
            "SearXNG did not return JSON. Ensure the JSON format is enabled and "
            "WEB_SEARXNG_BASE_URL points to the instance root."
        ) from exc
    if not isinstance(payload, dict) or not isinstance(payload.get("results"), list):
        raise ToolError("SearXNG returned malformed JSON: expected a results list.")

    results: list[dict[str, Any]] = []
    engines_answered: set[str] = set()
    for item in payload["results"]:
        if not isinstance(item, dict):
            continue
        item_engines = item.get("engines")
        if isinstance(item_engines, list):
            engines_answered.update(str(name) for name in item_engines if name)
        elif item.get("engine"):
            engines_answered.add(str(item["engine"]))
        results.append(_normalize_result(item))
        if len(results) >= count:
            break

    unresponsive = _normalize_unresponsive_engines(payload.get("unresponsive_engines"))
    return results, sorted(engines_answered), unresponsive
