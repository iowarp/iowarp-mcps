"""FastMCP registration and CLI for the CLIO Web MCP server."""

from __future__ import annotations

import os
from datetime import timedelta
from typing import Annotated, Any, Literal
from urllib.parse import urlparse

from dotenv import load_dotenv
from fastmcp import FastMCP
from fastmcp.prompts import Message
from fastmcp.server.context import Context
from fastmcp.utilities.tasks import TaskConfig
from pydantic import Field

from web_mcp.config import Settings
from web_mcp.fetch import (
    REASON_BINARY_NOT_INLINED as REASON_BINARY_NOT_INLINED,
)
from web_mcp.fetch import (
    REASON_JS_RENDER_REQUIRED as REASON_JS_RENDER_REQUIRED,
)
from web_mcp.fetch import fetch_event_log, fetch_target
from web_mcp.fetch_utils import REASON_BLOCKED_HOST as REASON_BLOCKED_HOST
from web_mcp.search import search_common, search_searxng_provider
from web_mcp.task_runtime import build_tasks_extension

load_dotenv()
settings = Settings()


def _new_mcp() -> FastMCP:
    """Create an unregistered Web MCP instance."""

    return FastMCP(
        "web",
        instructions=(
            "Use search to discover sources and fetch to read HTTP(S), DOI, HTML, text, "
            "PDF, and structured-document targets. Fetch is a durable task; query it for "
            "progress and cancel it when continued work is no longer useful."
        ),
        list_page_size=10,
    )


async def fetch(
    ctx: Context,
    target: Annotated[
        str,
        Field(description="An http(s) URL or DOI (bare, doi: prefix, or doi.org URL) to fetch."),
    ],
    to_file: Annotated[
        bool,
        Field(
            description=(
                "Write content to a local file and return local_path instead of inline content."
            )
        ),
    ] = False,
    output_dir: Annotated[
        str | None,
        Field(description="Destination directory when to_file=True."),
    ] = None,
    max_bytes: Annotated[
        int | None,
        Field(description="Override the configured response size cap in bytes."),
    ] = None,
    timeout: Annotated[
        float | None,
        Field(description="Override the configured per-request read timeout in seconds."),
    ] = None,
) -> dict[str, Any]:
    """Fetch a URL or DOI as a queryable, cancellable MCP task."""

    return await fetch_target(
        settings,
        ctx,
        target,
        to_file=to_file,
        output_dir=output_dir,
        max_bytes=max_bytes,
        timeout=timeout,
    )


async def fetch_events(
    conversion_id: Annotated[
        str,
        Field(description="Backend conversion ID reported by fetch task progress."),
    ],
    after_sequence: Annotated[
        int,
        Field(description="Return events after this sequence cursor.", ge=0),
    ] = 0,
    limit: Annotated[
        int,
        Field(description="Maximum ordered events to return.", ge=1, le=500),
    ] = 100,
) -> dict[str, Any]:
    """Query the full durable event log for one document conversion."""

    return await fetch_event_log(
        settings,
        conversion_id,
        after_sequence=after_sequence,
        limit=limit,
    )


async def _search_common(
    query: Annotated[str, Field(description="The search query.")],
    count: Annotated[int, Field(description="Maximum number of results to return.")] = 5,
) -> dict[str, Any]:
    """Search the fixed DDG, Brave, or Tavily provider."""

    return await search_common(settings, query, count)


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
        int,
        Field(
            description="SearXNG result page, bounded by this deployment to 1 through 3.",
            ge=1,
            le=3,
        ),
    ] = 1,
    safesearch: Annotated[
        int | None,
        Field(description="SearXNG safe-search level, 0 through 2.", ge=0, le=2),
    ] = None,
) -> dict[str, Any]:
    """Search the fixed SearXNG provider with its native selectors."""

    return await search_searxng_provider(
        settings,
        query,
        count,
        category,
        engines,
        language,
        time_range,
        pageno,
        safesearch,
    )


def capabilities() -> dict[str, Any]:
    """Return the active installation's search, fetch, and task capabilities."""

    search_parameters = ["query", "count"]
    if settings.search_provider == "searxng":
        search_parameters.extend(
            ["category", "engines", "language", "time_range", "pageno", "safesearch"]
        )
    durable_backend = bool(settings.remote_url or settings.task_backend_url)
    return {
        "active_provider": settings.search_provider,
        "search_parameters": search_parameters,
        "document_enrichment": bool((settings.effective_document_service_url or "").strip()),
        "fetch_task_mode": "required",
        "search_task_mode": "forbidden",
        "task_backend": "valkey" if durable_backend else "memory",
        "max_bytes": settings.max_bytes,
        "max_document_bytes": settings.max_document_bytes,
        "allow_private_hosts": settings.allow_private_hosts,
    }


def research_web(topic: str) -> list[Message]:
    """Provide a guided search-then-fetch research workflow."""

    return [
        Message(
            f"Research '{topic}' on the web. Use search to find relevant pages, then fetch "
            "the strongest sources and synthesize the findings with source URLs."
        )
    ]


def _validate_startup(configured: Settings) -> None:
    """Reject invalid selected-provider configuration before serving tools."""

    if configured.search_provider == "searxng":
        value = (configured.effective_searxng_url or "").strip()
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
    instance.add_extension(build_tasks_extension(settings))
    instance.tool(
        name="fetch",
        title="Fetch Target",
        description=(
            "Fetch an HTTP(S) URL or DOI as a durable task. HTML and text are read locally; "
            "supported documents use CLIO Web Search conversion when configured."
        ),
        annotations={"readOnlyHint": True, "destructiveHint": False, "idempotentHint": True},
        tags={"web", "fetch", "http", "documents"},
        task=TaskConfig(mode="required", poll_interval=timedelta(seconds=1)),
    )(fetch)
    instance.tool(
        name="fetch_events",
        title="Get Fetch Events",
        description="Query the full ordered backend event log for a document fetch conversion.",
        annotations={"readOnlyHint": True, "destructiveHint": False, "idempotentHint": True},
        tags={"web", "fetch", "documents", "progress"},
        task=TaskConfig(mode="forbidden"),
    )(fetch_events)
    search_function = (
        _search_searxng_tool if settings.search_provider == "searxng" else _search_common
    )
    search_description = (
        "Search the configured self-hosted SearXNG deployment with native selectors."
        if settings.search_provider == "searxng"
        else f"Search the web using this installation's fixed {settings.search_provider} provider."
    )
    instance.tool(
        name="search",
        title="Search Web",
        description=search_description,
        annotations={"readOnlyHint": True, "destructiveHint": False, "idempotentHint": False},
        tags={"web", "search"},
        task=TaskConfig(mode="forbidden"),
    )(search_function)
    instance.resource("web://capabilities")(capabilities)
    instance.prompt()(research_web)
    return instance


mcp = create_mcp()


def main() -> None:
    """Run the Web MCP over stdio or HTTP."""

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
        help="Legacy SearXNG or CLIO Web Search root URL.",
    )
    parser.add_argument(
        "--document-address",
        help="Legacy CLIO Web Search root URL for DOI and document enrichment.",
    )
    parser.add_argument(
        "--remote-url",
        "--remote_url",
        dest="remote_url",
        help="Unified CLIO Web Search URL for search, documents, and task discovery.",
    )
    parser.add_argument("--transport", choices=["stdio", "http"], default=None)
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--port", type=int, default=8000)
    args = parser.parse_args()
    selected = args.provider or ("searxng" if args.remote_url else settings.search_provider)
    configured = Settings(
        search_provider=selected,
        searxng_base_url=args.address or settings.searxng_base_url,
        document_service_url=(
            args.document_address
            or settings.document_service_url
            or (args.address if selected == "searxng" else None)
        ),
        remote_url=args.remote_url or settings.remote_url,
        remote_token=settings.remote_token,
        brave_api_key=settings.brave_api_key,
        tavily_api_key=settings.tavily_api_key,
        max_bytes=settings.max_bytes,
        max_document_bytes=settings.max_document_bytes,
        connect_timeout_s=settings.connect_timeout_s,
        read_timeout_s=settings.read_timeout_s,
        conversion_poll_s=settings.conversion_poll_s,
        progress_heartbeat_s=settings.progress_heartbeat_s,
        artifacts_root=settings.artifacts_root,
        allow_private_hosts=settings.allow_private_hosts,
        state_dir=settings.state_dir,
        task_backend_url=settings.task_backend_url,
        task_queue_name=settings.task_queue_name,
        task_concurrency=settings.task_concurrency,
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
