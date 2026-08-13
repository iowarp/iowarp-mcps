"""Web MCP server: curated ``fetch`` + ``search`` tools for agentic web access.

This is a proper v1 web-tooling surface for CLIO. Two tools are exposed:

* ``fetch`` -- retrieve an HTTP(S) URL with a streamed size cap and timeout,
  convert HTML to Markdown (trafilatura -> readability -> plain-text strip),
  and either return the content inline or write it to a local file.
* ``search`` -- query a configurable web-search provider (keyless DuckDuckGo by
  default, self-hosted SearXNG, or optional BYO-key Brave / Tavily).

Documented extension points (NOT implemented in v1 -- honest, typed gaps, never
a silent fallback):

* Headless-browser escalation (Playwright) for JS-rendered / Anubis-walled
  pages. When HTML extraction yields nothing, ``fetch`` returns a typed note
  ``reason="js_render_required_browser_unavailable"`` instead of silently
  handing back junk.
* ``(url, prompt)`` small-model extraction. An MCP server has no model access,
  so page-specific extraction stays the agent's job: use ``to_file=True`` and
  let the agent pipe the saved file through its own model.
"""

from __future__ import annotations

import asyncio
import json
import os
from pathlib import Path
from typing import Annotated, Any, Literal
from urllib.parse import urlparse

import httpx
from dotenv import load_dotenv
from fastmcp import FastMCP
from fastmcp.exceptions import ToolError
from fastmcp.prompts import Message
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

from web_mcp.document_service import (
    convert_document,
    is_convertible_document,
    resolve_doi,
)
from web_mcp.fetch_utils import REASON_BLOCKED_HOST as REASON_BLOCKED_HOST
from web_mcp.fetch_utils import (
    assert_allowed_url,
    decode,
    derive_filename,
    download,
    extract_title,
    html_to_markdown,
    is_html,
    is_text,
    looks_like_text,
    split_content_type,
    validate_output_path,
)
from web_mcp.searxng import search_searxng

# Environment setup
load_dotenv()


# ---------------------------------------------------------------------------
# Configuration (single source of truth; tests vary CONFIG, not ambient env)
# ---------------------------------------------------------------------------


class Settings(BaseSettings):
    """Runtime configuration for the web MCP server.

    All fields are overridable via ``WEB_``-prefixed environment variables
    (e.g. ``WEB_SEARCH_PROVIDER``, ``WEB_BRAVE_API_KEY``, ``WEB_MAX_BYTES``) or
    a ``.env`` file, but tests should construct ``Settings(...)`` directly so
    behavior is driven by config rather than the ambient environment.
    """

    model_config = SettingsConfigDict(env_prefix="WEB_", env_file=".env", extra="ignore")

    # Search provider selection. Keyless "ddg" is the default so search works
    # out of the box; self-hosted "searxng" requires its deployment URL, while
    # "brave"/"tavily" are opt-in and require their own key.
    search_provider: Literal["ddg", "searxng", "brave", "tavily"] = "ddg"
    searxng_base_url: str | None = None
    document_service_url: str | None = None
    brave_api_key: str | None = None
    tavily_api_key: str | None = None

    # Fetch limits.
    max_bytes: int = 5 * 1024 * 1024
    max_document_bytes: int = 50 * 1024 * 1024
    connect_timeout_s: float = 5.0
    read_timeout_s: float = 30.0
    conversion_wait_s: float = 25.0
    conversion_poll_s: float = 1.0

    # Default writable root for ``to_file`` output. ``None`` -> current working
    # directory, so a caller that launches the server from a chosen directory
    # controls where artifacts land.
    artifacts_root: str | None = None

    # SSRF guard: when False (default), fetch refuses URLs whose host is a
    # loopback / private / link-local / reserved LITERAL IP (or a localhost
    # name) -- on the initial URL AND every redirect hop -- so the tool is not a
    # confused deputy reaching the cloud-metadata endpoint (169.254.169.254) or
    # an internal service on behalf of injected content. Set True for a
    # deliberately internal fetcher. Deeper DNS-rebinding (a public name that
    # resolves private) is caught at the sandbox egress layer, not here: the
    # confined tool routes through a proxy and must NOT resolve DNS itself
    # (Linux-fence DNS is proxy-only), so the guard is literal-address-based.
    allow_private_hosts: bool = False


# Module-level settings instance. Tests monkeypatch ``server.settings`` with a
# freshly constructed ``Settings(...)`` to exercise alternate configuration.
settings = Settings()


# Search-provider HTTP endpoints (keyed providers).
_BRAVE_ENDPOINT = "https://api.search.brave.com/res/v1/web/search"
_TAVILY_ENDPOINT = "https://api.tavily.com/search"

# Typed extension-point signals (honest gaps, never silent fallbacks).
REASON_JS_RENDER_REQUIRED = "js_render_required_browser_unavailable"
REASON_BINARY_NOT_INLINED = "binary_content_not_inlined"
REASON_CONVERSION_PENDING = "document_conversion_pending"

# Bounds. Redirects are followed manually so each hop is SSRF-checked before the
# connection; search results are capped so a caller can't request an unbounded page.
_MAX_SEARCH_COUNT = 25


def _new_mcp() -> FastMCP:
    """Create an unregistered Web MCP instance."""

    return FastMCP(
        "web",
        instructions=(
            "Provides agentic web access. Use search to discover candidate sources and fetch "
            "to read HTTP(S), DOI, HTML, text, PDF, and structured-document targets. The search "
            "provider is fixed when this MCP installation starts."
        ),
        list_page_size=10,
    )


# ---------------------------------------------------------------------------
# Tool 1: fetch
# ---------------------------------------------------------------------------


def _validate_output_path(
    candidate: str | Path, *, default_name: str, output_dir: str | Path | None = None
) -> Path:
    """Confine a requested output path to this installation's artifact root."""
    return validate_output_path(
        candidate,
        default_name=default_name,
        output_dir=output_dir,
        configured_root=settings.artifacts_root,
    )


def _assert_allowed_url(url: str) -> None:
    """Apply this installation's private-host policy to a target URL."""
    assert_allowed_url(url, allow_private_hosts=settings.allow_private_hosts)


async def _download(
    url: str, *, max_bytes: int, max_document_bytes: int, timeout: httpx.Timeout
) -> tuple[bytes, str | None, int, str]:
    """Download through the shared redirect, SSRF, and size-limit implementation."""
    return await download(
        url,
        max_bytes=max_bytes,
        max_document_bytes=max_document_bytes,
        timeout=timeout,
        allow_private_hosts=settings.allow_private_hosts,
    )


async def fetch(
    target: Annotated[
        str,
        Field(description="An http(s) URL or DOI (bare, doi: prefix, or doi.org URL) to fetch."),
    ],
    to_file: Annotated[
        bool,
        Field(
            description=(
                "Write the (converted) content to a local file and return "
                "local_path instead of inline content. Use for large or binary "
                "resources so raw pages never bloat context; the agent can then "
                "pipe the saved file through its own model for (url, prompt) "
                "extraction."
            )
        ),
    ] = False,
    output_dir: Annotated[
        str | None,
        Field(
            description=(
                "Destination directory when to_file=True. Defaults to the "
                "configured artifacts_root or the current working directory."
            )
        ),
    ] = None,
    max_bytes: Annotated[
        int | None,
        Field(description="Override the size cap in bytes (default from config: 5 MiB)."),
    ] = None,
    timeout: Annotated[
        float | None,
        Field(description="Override the read timeout in seconds (default from config)."),
    ] = None,
) -> dict[str, Any]:
    """Fetch a URL or DOI and return Markdown, structure, or a saved artifact.

    An MCP server has no model access, so page-specific ``(url, prompt)``
    extraction is intentionally left to the agent: fetch to a file and pipe it
    through the agent's own model.
    """
    requested_target = (target or "").strip()
    if not requested_target:
        raise ToolError("fetch requires a non-empty URL or DOI target.")

    cap = max_bytes if max_bytes and max_bytes > 0 else settings.max_bytes
    read_timeout = timeout if timeout and timeout > 0 else settings.read_timeout_s
    timeout_cfg = httpx.Timeout(read_timeout, connect=settings.connect_timeout_s)

    doi: str | None = None
    doi_resolution: dict[str, Any] | None = None
    download_targets: list[str]
    parsed_target = urlparse(requested_target)
    is_doi_url = (
        parsed_target.scheme in {"http", "https"}
        and (parsed_target.hostname or "").lower() in {"doi.org", "dx.doi.org"}
        and bool(parsed_target.path.strip("/"))
    )
    if is_doi_url or not requested_target.lower().startswith(("http://", "https://")):
        if "://" in requested_target and not is_doi_url:
            raise ToolError(
                f"fetch only supports http(s) URLs or DOI targets; got: {requested_target!r}"
            )
        doi = parsed_target.path.strip("/") if is_doi_url else requested_target
        doi_resolution = await resolve_doi(
            doi,
            service_url=settings.document_service_url,
            timeout=timeout_cfg,
        )
        doi = str(doi_resolution["doi"])
        download_targets = [
            str(candidate["url"])
            for candidate in doi_resolution["candidates"]
            if isinstance(candidate, dict) and candidate.get("url")
        ]
        if not download_targets:
            raise ToolError(f"CLIO Search found no lawful retrieval candidate for DOI {doi}.")
    else:
        download_targets = [requested_target]

    download_target = ""
    failures: list[str] = []
    for candidate in download_targets:
        _assert_allowed_url(candidate)
        try:
            body, raw_content_type, status, final_url = await _download(
                candidate,
                max_bytes=cap,
                max_document_bytes=settings.max_document_bytes,
                timeout=timeout_cfg,
            )
            download_target = candidate
            break
        except (ToolError, httpx.HTTPError) as exc:
            failures.append(f"{candidate}: {exc}")
    else:
        summary = "; ".join(failures)
        raise ToolError(f"Could not fetch {requested_target}: {summary}")

    size_bytes = len(body)
    mime, charset = split_content_type(raw_content_type)
    is_html_content = is_html(mime)
    # A response with NO content-type is content-sniffed: decodable-as-UTF-8 text is treated as
    # text (returned), not withheld as binary. Only genuinely undecodable bytes stay binary.
    is_text_content = is_text(mime) or is_html_content or (mime == "" and looks_like_text(body))
    is_binary = not is_text_content

    result: dict[str, Any] = {
        "ok": True,
        "target": requested_target,
        "url": download_target,
        "size_bytes": size_bytes,
        "content_type": raw_content_type,
        "status": status,
        "title": None,
        "method": "http",
    }
    if doi_resolution is not None:
        result["doi"] = doi
        result["doi_resolution"] = doi_resolution
    if final_url and final_url != download_target:
        result["final_url"] = final_url  # the resolved URL after redirects (url stays verbatim)

    content: str | None
    if is_html_content:
        html = decode(body, charset)
        result["title"] = extract_title(html)
        content, extractor = html_to_markdown(html)
        result["extractor"] = extractor  # which extractor ran (downgrade is visible)
        if content is None:
            # Extraction produced nothing usable: almost always a JS-rendered
            # or challenge-walled page. Signal the headless-browser extension
            # point instead of returning junk.
            result["content"] = None
            result["reason"] = REASON_JS_RENDER_REQUIRED
            result["note"] = (
                "HTML extraction yielded no content; the page likely requires a "
                "JavaScript-capable headless browser, which is not available in v1."
            )
            return result
    elif (
        is_binary
        and settings.document_service_url
        and is_convertible_document(body, raw_content_type, final_url)
    ):
        filename = derive_filename(final_url, is_html=False, is_binary=True)
        conversion = await convert_document(
            body,
            filename=filename,
            content_type=raw_content_type,
            source_url=final_url,
            doi=doi,
            service_url=settings.document_service_url,
            timeout=timeout_cfg,
            wait_s=settings.conversion_wait_s,
            poll_s=settings.conversion_poll_s,
        )
        if conversion.get("status") != "complete":
            result.update(
                {
                    "content": None,
                    "reason": REASON_CONVERSION_PENDING,
                    "conversion_id": conversion.get("id"),
                    "retry_after_s": conversion.get("retry_after_s", 2),
                }
            )
            return result
        converted = conversion.get("result")
        if not isinstance(converted, dict):
            raise ToolError("CLIO Search completed conversion without a result payload.")
        content = str(converted.get("markdown") or "")
        result["method"] = "clio-search"
        result["extractor"] = "document-service"
        document = converted.get("document")
        if isinstance(document, dict):
            inline_document = dict(document)
            structure = inline_document.pop("structure", None)
            if structure is not None:
                inline_document["structure_available"] = True
                if isinstance(structure, dict):
                    inline_document["structure_summary"] = {
                        key: len(value)
                        for key, value in structure.items()
                        if isinstance(value, (dict, list))
                    }
            result["document"] = inline_document
        else:
            result["document"] = document
        result["conversion_id"] = conversion.get("id")
        if to_file:
            output_path = _validate_output_path(
                f"{Path(filename).stem}.md", default_name="document.md", output_dir=output_dir
            )
            output_path.write_text(content, encoding="utf-8")
            metadata_path = output_path.with_suffix(".json")
            metadata_path.write_text(
                json.dumps(document, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
            result["local_path"] = str(output_path)
            result["metadata_path"] = str(metadata_path)
            if isinstance(document, dict) and "structure" in document:
                result["structure_saved_to"] = str(metadata_path)
            return result
        result["content"] = content
        return result
    elif is_binary:
        if not to_file:
            # Never inline a giant binary blob; hand back a typed note.
            result["content"] = None
            result["reason"] = REASON_BINARY_NOT_INLINED
            result["note"] = (
                "Binary content is not inlined. Re-call fetch with to_file=True to "
                "save it to a local file."
            )
            return result
        content = None  # binary is written raw below
    else:
        content = decode(body, charset)

    if to_file:
        filename = derive_filename(final_url, is_html=is_html_content, is_binary=is_binary)
        output_path = _validate_output_path(filename, default_name="page", output_dir=output_dir)
        if is_binary:
            output_path.write_bytes(body)
        else:
            output_path.write_text(content or "", encoding="utf-8")
        result["local_path"] = str(output_path)
    else:
        result["content"] = content

    return result


# ---------------------------------------------------------------------------
# Tool 2: search (provider abstraction, config-selected)
# ---------------------------------------------------------------------------


def _ddgs_search(query: str, count: int) -> list[dict[str, str]]:
    """Keyless DuckDuckGo search via the ``ddgs`` package (sync)."""
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


async def _search_ddg(query: str, count: int) -> list[dict[str, str]]:
    """Run the synchronous DDG search off the event loop."""
    return await asyncio.to_thread(_ddgs_search, query, count)


async def _search_brave(query: str, count: int) -> list[dict[str, str]]:
    """BYO-key Brave Search adapter."""
    if not settings.brave_api_key:
        raise ToolError(
            "search provider 'brave' requires an API key. Set WEB_BRAVE_API_KEY "
            "(Settings.brave_api_key) or choose a different provider."
        )
    headers = {"X-Subscription-Token": settings.brave_api_key, "Accept": "application/json"}
    params: dict[str, str | int] = {"q": query, "count": count}
    async with httpx.AsyncClient(timeout=httpx.Timeout(settings.read_timeout_s)) as client:
        response = await client.get(_BRAVE_ENDPOINT, headers=headers, params=params)
        response.raise_for_status()
        payload = response.json()
    web = payload.get("web") or {}
    results: list[dict[str, str]] = []
    for item in (web.get("results") or [])[:count]:
        results.append(
            {
                "title": str(item.get("title") or ""),
                "url": str(item.get("url") or ""),
                "snippet": str(item.get("description") or ""),
            }
        )
    return results


async def _search_tavily(query: str, count: int) -> list[dict[str, str]]:
    """BYO-key Tavily Search adapter."""
    if not settings.tavily_api_key:
        raise ToolError(
            "search provider 'tavily' requires an API key. Set WEB_TAVILY_API_KEY "
            "(Settings.tavily_api_key) or choose a different provider."
        )
    body = {
        "api_key": settings.tavily_api_key,
        "query": query,
        "max_results": count,
    }
    async with httpx.AsyncClient(timeout=httpx.Timeout(settings.read_timeout_s)) as client:
        response = await client.post(_TAVILY_ENDPOINT, json=body)
        response.raise_for_status()
        payload = response.json()
    results: list[dict[str, str]] = []
    for item in (payload.get("results") or [])[:count]:
        results.append(
            {
                "title": str(item.get("title") or ""),
                "url": str(item.get("url") or ""),
                "snippet": str(item.get("content") or ""),
            }
        )
    return results


async def _search_common(
    query: Annotated[str, Field(description="The search query.")],
    count: Annotated[int, Field(description="Maximum number of results to return.")] = 5,
) -> dict[str, Any]:
    """Search the fixed DDG, Brave, or Tavily provider."""

    text = (query or "").strip()
    if not text:
        raise ToolError("A non-empty query is required.")
    effective_count = min(count if count and count > 0 else 5, _MAX_SEARCH_COUNT)
    if settings.search_provider == "ddg":
        results = await _search_ddg(text, effective_count)
    elif settings.search_provider == "brave":
        results = await _search_brave(text, effective_count)
    elif settings.search_provider == "tavily":
        results = await _search_tavily(text, effective_count)
    else:
        raise ToolError("The active search provider requires the SearXNG search schema.")
    return {
        "ok": True,
        "provider": settings.search_provider,
        "query": text,
        "results": results,
        "count": len(results),
    }


async def _search_searxng_tool(
    query: Annotated[str, Field(description="The search query.")],
    count: Annotated[int, Field(description="Maximum number of results to return.")] = 5,
    category: Annotated[
        Literal["general", "science", "it"] | None,
        Field(description="SearXNG category: general, science, or it."),
    ] = None,
    engines: Annotated[
        list[str] | None,
        Field(description="Exact SearXNG engines; takes precedence over category."),
    ] = None,
    language: Annotated[str | None, Field(description="SearXNG result language.")] = None,
    time_range: Annotated[
        Literal["day", "month", "year"] | None,
        Field(description="SearXNG recency: day, month, or year."),
    ] = None,
    pageno: Annotated[
        int | None,
        Field(
            description="SearXNG result page, bounded by this deployment to 1 through 3.",
            ge=1,
            le=3,
        ),
    ] = None,
    safesearch: Annotated[
        int | None,
        Field(description="SearXNG safe-search level, 0 through 2.", ge=0, le=2),
    ] = None,
) -> dict[str, Any]:
    """Search the fixed SearXNG provider with its native selectors."""

    text = (query or "").strip()
    if not text:
        raise ToolError("A non-empty query is required.")
    effective_count = min(count if count and count > 0 else 5, _MAX_SEARCH_COUNT)
    results, engines_answered, unresponsive_engines = await search_searxng(
        text,
        effective_count,
        base_url=settings.searxng_base_url,
        connect_timeout_s=settings.connect_timeout_s,
        read_timeout_s=settings.read_timeout_s,
        category=category,
        engines=engines,
        language=language,
        time_range=time_range,
        pageno=pageno or 1,
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


def capabilities() -> dict[str, Any]:
    """Return only the active installation's search and fetch capabilities."""

    search_parameters = ["query", "count"]
    if settings.search_provider == "searxng":
        search_parameters.extend(
            ["category", "engines", "language", "time_range", "pageno", "safesearch"]
        )
    return {
        "active_provider": settings.search_provider,
        "search_parameters": search_parameters,
        "document_enrichment": bool((settings.document_service_url or "").strip()),
        "max_bytes": settings.max_bytes,
        "max_document_bytes": settings.max_document_bytes,
        "allow_private_hosts": settings.allow_private_hosts,
    }


def research_web(topic: str) -> list[Message]:
    """Guided search then fetch workflow for researching a topic on the web."""
    return [
        Message(
            f"Research '{topic}' on the web. Use search to find the most relevant pages, "
            "then fetch the top results (to_file=True for long pages so raw content stays "
            "out of context) and synthesize the findings, citing each source URL."
        )
    ]


def _validate_startup(configured: Settings) -> None:
    """Reject invalid selected-provider configuration before serving tools."""

    if configured.search_provider == "searxng":
        value = (configured.searxng_base_url or "").strip()
        parsed = urlparse(value)
        if parsed.scheme not in {"http", "https"} or not parsed.hostname:
            raise ValueError("provider 'searxng' requires --address with an absolute HTTP(S) URL")
    if configured.search_provider == "brave" and not configured.brave_api_key:
        raise ValueError("provider 'brave' requires WEB_BRAVE_API_KEY")
    if configured.search_provider == "tavily" and not configured.tavily_api_key:
        raise ValueError("provider 'tavily' requires WEB_TAVILY_API_KEY")


def create_mcp(configured: Settings | None = None) -> FastMCP:
    """Create the provider-specific MCP schema for one installation."""

    global settings
    if configured is not None:
        settings = configured
    _validate_startup(settings)
    instance = _new_mcp()
    instance.tool(
        name="fetch",
        title="Fetch Target",
        description=(
            "Fetch an HTTP(S) URL or DOI. HTML and text are read locally; supported PDFs and "
            "structured documents use the optional CLIO Search document service."
        ),
        annotations={"readOnlyHint": True, "destructiveHint": False, "idempotentHint": True},
        tags={"web", "fetch", "http", "documents"},
    )(fetch)
    search_function = (
        _search_searxng_tool if settings.search_provider == "searxng" else _search_common
    )
    search_description = (
        "Search the configured self-hosted SearXNG deployment with native category, engine, "
        "language, time-range, page, and safe-search selectors."
        if settings.search_provider == "searxng"
        else f"Search the web using this installation's fixed {settings.search_provider} provider."
    )
    instance.tool(
        name="search",
        title="Search Web",
        description=search_description,
        annotations={"readOnlyHint": True, "destructiveHint": False, "idempotentHint": False},
        tags={"web", "search"},
    )(search_function)
    instance.resource("web://capabilities")(capabilities)
    instance.prompt()(research_web)
    return instance


mcp = create_mcp()


def main() -> None:
    """Main entry point for the web MCP server."""
    import argparse

    parser = argparse.ArgumentParser(description="Web MCP Server")
    parser.add_argument(
        "--provider",
        type=str.lower,
        choices=["ddg", "searxng", "brave", "tavily"],
        default=None,
        help="Search provider fixed for this MCP installation.",
    )
    parser.add_argument(
        "--address",
        help="SearXNG or CLIO Search root URL; required when --provider searxng.",
    )
    parser.add_argument(
        "--document-address",
        help="Optional CLIO Search root URL for DOI and document enrichment.",
    )
    parser.add_argument("--transport", choices=["stdio", "http"], default=None)
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--port", type=int, default=8000)
    args = parser.parse_args()
    selected = args.provider or settings.search_provider
    configured = Settings(
        search_provider=selected,
        searxng_base_url=args.address or settings.searxng_base_url,
        document_service_url=(
            args.document_address
            or settings.document_service_url
            or (args.address if selected == "searxng" else None)
        ),
        brave_api_key=settings.brave_api_key,
        tavily_api_key=settings.tavily_api_key,
        max_bytes=settings.max_bytes,
        max_document_bytes=settings.max_document_bytes,
        connect_timeout_s=settings.connect_timeout_s,
        read_timeout_s=settings.read_timeout_s,
        conversion_wait_s=settings.conversion_wait_s,
        conversion_poll_s=settings.conversion_poll_s,
        artifacts_root=settings.artifacts_root,
        allow_private_hosts=settings.allow_private_hosts,
    )
    try:
        server = create_mcp(configured)
    except ValueError as exc:
        parser.error(str(exc))
    transport = args.transport or os.getenv("MCP_TRANSPORT", "stdio")
    if transport == "http":
        server.run(transport="http", host=args.host, port=args.port)
    else:
        server.run(transport="stdio")


if __name__ == "__main__":
    main()
