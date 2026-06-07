#!/usr/bin/env python3
"""Geo MCP server.

Renders GeoJSON vector layers into map images. Any tool that produces GeoJSON
features (catalog feature queries, file inspection, analysis output) can be
visualized as a layered map with an optional web-tile basemap.
"""

import logging
from typing import Annotated, Any

from dotenv import load_dotenv
from fastmcp import FastMCP
from fastmcp.exceptions import ToolError
from pydantic import Field

from .implementation import MapRenderError, render_map

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

load_dotenv()

mcp: FastMCP = FastMCP(
    "geo",
    instructions=(
        "Renders geospatial vector data into map images. Pass one or more layers "
        "of GeoJSON (polygons, lines, points) and get back a PNG with an optional "
        "basemap. Use render_feature_map to visualize fire perimeters, smoke "
        "polygons, monitoring stations, regions, or any GeoJSON features on one map."
    ),
)


@mcp.tool(
    name="render_feature_map",
    description=(
        "Render one or more GeoJSON layers (polygons/lines/points) onto a single "
        "map PNG with an optional basemap. Each layer accepts a style with fixed "
        "colors or data-driven coloring (color_by + category_colors, an 'epa_aqi' "
        "AQI scale, or a matplotlib colormap). Returns the output path and bounds."
    ),
    annotations={"readOnlyHint": False, "destructiveHint": True, "idempotentHint": True},
    tags={"geospatial", "map", "visualization", "geojson"},
)
async def render_feature_map_tool(
    layers: Annotated[
        list[dict[str, Any]],
        Field(description=(
            "Ordered layers (later layers draw on top). Each: {'geojson': "
            "FeatureCollection|Feature|geometry|list|JSON-string|path, 'name': str, "
            "'style': {facecolor, edgecolor, alpha, linewidth, color, markersize, "
            "zorder, color_by, scale, category_colors, legend}}."
        )),
    ],
    output_path: Annotated[str, Field(description="Destination PNG path.")] = "map.png",
    title: Annotated[str, Field(description="Figure title.")] = "",
    basemap: Annotated[bool, Field(description="Add a CartoDB Positron basemap (needs network).")] = True,
    bbox: Annotated[
        list[float] | None,
        Field(description="Optional view window [min_lon, min_lat, max_lon, max_lat]."),
    ] = None,
) -> dict[str, Any]:
    """Render GeoJSON layers to a map PNG. See tool description for the layer schema."""
    try:
        return render_map(layers, output_path, title=title, basemap=basemap, bbox=bbox)
    except MapRenderError as exc:
        raise ToolError(str(exc)) from exc
    except Exception as exc:  # noqa: BLE001 - surface rendering failures as tool errors
        logger.exception("render_feature_map failed")
        raise ToolError(f"Map render failed: {exc}") from exc


@mcp.tool(
    name="points_in_polygons",
    description=(
        "Spatial overlap: return which GeoJSON points fall within (optionally "
        "buffered) GeoJSON polygons — e.g. which AirNow monitors lie inside the "
        "smoke footprint. Accepts inline GeoJSON or file paths. Returns the "
        "matched points with their properties and a matched_count."
    ),
    annotations={"readOnlyHint": True, "destructiveHint": False, "idempotentHint": True},
    tags={"geospatial", "overlap", "spatial-join", "geojson"},
)
async def points_in_polygons_tool(
    points_geojson: Annotated[Any, Field(description="GeoJSON points (FeatureCollection/Feature/list/JSON/path).")],
    polygons_geojson: Annotated[Any, Field(description="GeoJSON polygons (same accepted forms).")],
    buffer_km: Annotated[float, Field(description="Optional margin added to polygons so near points count. 0 = strict.")] = 0.0,
    point_label_fields: Annotated[
        list[str] | None, Field(description="Property names to surface per matched point.")
    ] = None,
) -> dict[str, Any]:
    """Return the points that fall within (optionally buffered) polygons."""
    try:
        return points_in_polygons(
            points_geojson, polygons_geojson, buffer_km=buffer_km, point_label_fields=point_label_fields
        )
    except Exception as exc:  # noqa: BLE001 - surface as tool error
        logger.exception("points_in_polygons failed")
        raise ToolError(f"Spatial overlap failed: {exc}") from exc


def main() -> None:
    """Entry point for the geo MCP server."""
    mcp.run()


if __name__ == "__main__":
    main()
