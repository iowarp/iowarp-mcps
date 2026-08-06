#!/usr/bin/env python3
"""GeoJSON MCP server.

Domain-neutral GeoJSON inspection tooling. Reads, validates, summarizes, and
measures the extent of GeoJSON documents (FeatureCollection / Feature / bare
geometry) supplied either as a file path or inline GeoJSON. Implemented with
the Python standard library only (``json`` + ``math``) — no geopandas/shapely.
"""

import argparse
import logging
import os
from typing import Annotated, Any, Literal, cast

from fastmcp import FastMCP
from fastmcp.exceptions import ToolError
from fastmcp.prompts import Message
from pydantic import Field

from .implementation import (
    GeoJSONError,
    feature_bbox,
    inspect_geojson,
    summarize_geojson,
    validate_geojson,
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

mcp: FastMCP = FastMCP(
    "geojson",
    instructions=(
        "Inspect and validate GeoJSON documents without any heavy geospatial "
        "dependencies. Pass a path to a .geojson file or inline GeoJSON "
        "(FeatureCollection / Feature / bare geometry, as a JSON string or "
        "object). Use inspect_geojson for a full structural report (geometry "
        "type counts, feature count, property schema, bbox, CRS, total "
        "vertices); validate_geojson to check structural validity and get a "
        "list of errors; summarize_geojson for a compact human-readable "
        "summary; and feature_bbox for just the overall bounding box "
        "[min_lon, min_lat, max_lon, max_lat]. All coordinates are assumed "
        "lon/lat (WGS84) unless a crs member says otherwise."
    ),
)

# Shared type alias for the GeoJSON source argument accepted by every tool.
_SourceField = Annotated[
    str,
    Field(
        description=(
            "Path to a .geojson/JSON file, or inline GeoJSON as a JSON string "
            "(FeatureCollection / Feature / geometry)."
        )
    ),
]


@mcp.tool(
    name="inspect_geojson",
    title="Inspect",
    description=(
        "Inspect a GeoJSON document and report its geometry types and counts, "
        "feature count, property keys (schema), bounding box "
        "[min_lon, min_lat, max_lon, max_lat], CRS if present, and total vertex "
        "count. Accepts a file path or inline GeoJSON."
    ),
    annotations={"readOnlyHint": True, "destructiveHint": False, "idempotentHint": True},
    tags={"geojson", "inspection", "metadata", "schema"},
)
async def inspect_geojson_tool(
    source: _SourceField,
    max_sample_features: Annotated[
        int,
        Field(description="Number of representative feature property samples to include (0-50)."),
    ] = 5,
) -> dict[str, Any]:
    """Return a structural report for a GeoJSON document.

    Returns ``{geojson_type, feature_count, geometry_types, property_keys,
    bbox, crs, total_vertices, sample_features}``.
    """
    try:
        return inspect_geojson(source, max_sample_features=max_sample_features)
    except GeoJSONError as exc:
        raise ToolError(str(exc)) from exc
    except Exception as exc:  # noqa: BLE001 - surface as tool error
        logger.exception("inspect_geojson failed")
        raise ToolError(f"GeoJSON inspection failed: {exc}") from exc


@mcp.tool(
    name="validate_geojson",
    title="Validate",
    description=(
        "Validate the structural well-formedness of a GeoJSON document: that "
        "the top-level type is recognized and every geometry's type and "
        "coordinates are well-formed (correct nesting depth, finite numeric "
        "positions). Returns {valid, errors}."
    ),
    annotations={"readOnlyHint": True, "destructiveHint": False, "idempotentHint": True},
    tags={"geojson", "validation", "linting"},
)
async def validate_geojson_tool(source: _SourceField) -> dict[str, Any]:
    """Return ``{"valid": bool, "errors": list[str]}`` for a GeoJSON document."""
    try:
        return validate_geojson(source)
    except GeoJSONError as exc:
        raise ToolError(str(exc)) from exc
    except Exception as exc:  # noqa: BLE001 - surface as tool error
        logger.exception("validate_geojson failed")
        raise ToolError(f"GeoJSON validation failed: {exc}") from exc


@mcp.tool(
    name="summarize_geojson",
    title="Summarize",
    description=(
        "Produce a compact human-readable summary of a GeoJSON document: counts "
        "per geometry type, bounding box, property keys, and a few sample "
        "feature property sets. Accepts a file path or inline GeoJSON."
    ),
    annotations={"readOnlyHint": True, "destructiveHint": False, "idempotentHint": True},
    tags={"geojson", "summary", "inspection"},
)
async def summarize_geojson_tool(
    source: _SourceField,
    max_sample_features: Annotated[
        int,
        Field(description="Number of sample feature property sets to include (0-50)."),
    ] = 3,
) -> dict[str, Any]:
    """Return ``{summary, feature_count, geometry_types, bbox, property_keys, sample_features}``."""
    try:
        return summarize_geojson(source, max_sample_features=max_sample_features)
    except GeoJSONError as exc:
        raise ToolError(str(exc)) from exc
    except Exception as exc:  # noqa: BLE001 - surface as tool error
        logger.exception("summarize_geojson failed")
        raise ToolError(f"GeoJSON summary failed: {exc}") from exc


@mcp.tool(
    name="feature_bbox",
    title="Bounding Box",
    description=(
        "Compute the overall bounding box [min_lon, min_lat, max_lon, max_lat] "
        "of all features in a GeoJSON document. Accepts a file path or inline "
        "GeoJSON. Returns the bbox (or null when there are no coordinates) and "
        "the feature count."
    ),
    annotations={"readOnlyHint": True, "destructiveHint": False, "idempotentHint": True},
    tags={"geojson", "bbox", "region"},
)
async def feature_bbox_tool(source: _SourceField) -> dict[str, Any]:
    """Return ``{"bbox": [min_lon, min_lat, max_lon, max_lat] | None, "feature_count": int}``."""
    try:
        return feature_bbox(source)
    except GeoJSONError as exc:
        raise ToolError(str(exc)) from exc
    except Exception as exc:  # noqa: BLE001 - surface as tool error
        logger.exception("feature_bbox failed")
        raise ToolError(f"GeoJSON bounding box failed: {exc}") from exc


@mcp.resource("geojson://capabilities")
def capabilities() -> dict[str, Any]:
    """Describe what the geojson MCP server can do."""
    return {
        "tools": [
            "inspect_geojson",
            "validate_geojson",
            "summarize_geojson",
            "feature_bbox",
        ],
        "accepts": "GeoJSON file path or inline GeoJSON (FeatureCollection/Feature/geometry/JSON)",
        "outputs": [
            "structural report (geometry types, counts, schema, bbox, CRS, vertices)",
            "structural validity {valid, errors}",
            "compact human-readable summary",
            "overall bounding box",
        ],
        "crs": "EPSG:4326 (lon/lat) assumed unless a crs member is present",
        "dependencies": "Python standard library only (json + math)",
        "description": (
            "Domain-neutral GeoJSON inspection: report geometry types and "
            "counts, feature counts, property schema, bounding box, CRS, and "
            "total vertices; validate structural well-formedness; summarize; "
            "and compute bounding boxes — all without geopandas/shapely."
        ),
    }


@mcp.prompt()
def inspect_workflow(source: str) -> list[Message]:
    """Guided workflow: validate, then inspect and summarize a GeoJSON document."""
    return [
        Message(
            f"Inspect the GeoJSON at '{source}'. First call validate_geojson to "
            "confirm it is structurally well-formed and review any errors. Then "
            "call inspect_geojson for the geometry type counts, feature count, "
            "property schema, bounding box, CRS, and total vertices. Finish with "
            "summarize_geojson for a compact human-readable overview, and report "
            "whether the data looks analysis-ready."
        ),
    ]


def main() -> None:
    """Entry point for the geojson MCP server."""
    parser = argparse.ArgumentParser(description="GeoJSON inspection MCP server")
    parser.add_argument("--transport", choices=["stdio", "http"], default=None)
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--port", type=int, default=8000)
    args = parser.parse_args()
    transport = cast(
        Literal["stdio", "http"], args.transport or os.getenv("MCP_TRANSPORT", "stdio")
    )
    mcp.run(transport=transport, host=args.host, port=args.port)


if __name__ == "__main__":
    main()
