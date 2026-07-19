"""FastMCP surface for operator-owned scientific dataset discovery."""

from __future__ import annotations

import argparse
import os
from pathlib import Path
from threading import Lock
from typing import Annotated

from fastmcp import FastMCP
from fastmcp.exceptions import ToolError
from fastmcp.prompts import Message
from pydantic import Field

from .backend import CatalogError, CatalogStore
from .models import DatasetDescribeResult, DatasetSearchResult

mcp: FastMCP = FastMCP(
    "scientific-catalog",
    instructions=(
        "Discover operator-registered scientific datasets using intrinsic metadata. "
        "Use scientific_dataset_search to find an identity, then "
        "scientific_dataset_describe to obtain the exact JARVIS dataset descriptor. "
        "This catalog contains no camera, colormap, filter, scheduler, or demo recipe semantics."
    ),
)

_STORE: CatalogStore | None = None
_STORE_LOCK = Lock()


def configure_catalog(path: Path) -> None:
    """Configure the exact operator-owned catalog file for this server process."""
    global _STORE
    store = CatalogStore(path)
    with _STORE_LOCK:
        _STORE = store


def _store() -> CatalogStore:
    with _STORE_LOCK:
        store = _STORE
    if store is None:
        configured = os.environ.get("SCIENTIFIC_CATALOG_FILE", "").strip()
        if not configured:
            raise ToolError(
                "scientific catalog is not configured; pass --catalog-file or set "
                "SCIENTIFIC_CATALOG_FILE"
            )
        try:
            configure_catalog(Path(configured))
        except CatalogError as exc:
            raise ToolError(str(exc)) from exc
        with _STORE_LOCK:
            store = _STORE
    assert store is not None
    return store


@mcp.tool(
    name="scientific_dataset_search",
    description=(
        "Search operator-registered scientific datasets and return bounded intrinsic summaries."
    ),
    annotations={
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": False,
    },
    tags={"scientific-data", "catalog", "user"},
)
def scientific_dataset_search_tool(
    query: str | None = None,
    tags: list[str] | None = None,
    kind: str | None = None,
    format: str | None = None,
    cursor: str | None = None,
    page_size: Annotated[int, Field(ge=1, le=100)] = 20,
) -> DatasetSearchResult:
    """Search titles, summaries, tags, and exact intrinsic format metadata."""
    try:
        return _store().search(
            query=query,
            tags=tags,
            kind=kind,
            format=format,
            cursor=cursor,
            page_size=page_size,
        )
    except CatalogError as exc:
        raise ToolError(str(exc)) from exc


@mcp.tool(
    name="scientific_dataset_describe",
    description=(
        "Return one exact operator catalog record plus a top-level dataset_descriptor. "
        "Pass dataset_descriptor unchanged as jarvis_add_step config.dataset_descriptor; "
        "do not pass the surrounding dataset record."
    ),
    annotations={
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": False,
    },
    tags={"scientific-data", "catalog", "user"},
)
def scientific_dataset_describe_tool(dataset_id: str) -> DatasetDescribeResult:
    """Resolve a stable dataset id and an explicit JARVIS-ready descriptor handoff."""
    try:
        return _store().describe(dataset_id)
    except CatalogError as exc:
        raise ToolError(str(exc)) from exc


@mcp.resource("scientific-catalog://capabilities")
def scientific_catalog_capabilities() -> dict[str, object]:
    """Describe the separation between discovery and runtime visualization."""
    return {
        "schema_version": "clio-kit.scientific-catalog-capabilities.v1",
        "operations": ["search", "describe"],
        "descriptor_schema": "jarvis.dataset-descriptor.v1",
        "runtime_owner": "jarvis",
        "desktop_transport_owner": "clio-relay",
        "visualization_owner": "vigil",
        "scene_semantics_in_catalog": False,
    }


@mcp.prompt()
def discover_scientific_dataset(query: str) -> list[Message]:
    """Guide an agent through catalog search and exact descriptor handoff."""
    return [
        Message(
            f"Find an operator-registered scientific dataset matching {query!r}. "
            "Call scientific_dataset_search with that query first. Use only dataset identifiers "
            "returned by the search, and report a no-match result before broadening the query. "
            "For the chosen dataset_id, call scientific_dataset_describe and pass only its "
            "top-level dataset_descriptor unchanged to JARVIS. Do not invent camera, colormap, "
            "filter, scheduler, or demo-recipe semantics."
        )
    ]


def main() -> None:
    """Run the scientific catalog MCP server over stdio or HTTP."""
    parser = argparse.ArgumentParser(description="Scientific Catalog MCP Server")
    parser.add_argument("--catalog-file", type=Path, default=None)
    parser.add_argument("--transport", choices=["stdio", "http"], default=None)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8000)
    args = parser.parse_args()
    if args.catalog_file is not None:
        try:
            configure_catalog(args.catalog_file)
        except CatalogError as exc:
            parser.error(str(exc))
    transport = args.transport or os.environ.get("MCP_TRANSPORT", "stdio")
    if transport == "http":
        mcp.run(transport="http", host=args.host, port=args.port)
    else:
        mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
