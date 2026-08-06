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
from fastmcp.prompts import Message
from pydantic import Field

from .implementation import (
    ArcGISQueryError,
    GeocodeError,
    MapRenderError,
    ProximityError,
    bounding_box,
    filter_points_by_radius,
    geocode,
    points_in_polygons,
    query_arcgis_features,
    render_map,
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

load_dotenv()

mcp: FastMCP = FastMCP(
    "geo",
    instructions=(
        "Renders and retrieves geospatial vector data. Pass one or more layers of "
        "GeoJSON (polygons, lines, points) to render_feature_map and get back a PNG "
        "with an optional basemap. Use query_arcgis_features to pull features from an "
        "ArcGIS FeatureServer layer into a native GeoJSON file, points_in_polygons "
        "for spatial overlap, bounding_box to derive an analysis region from "
        "GeoJSON features, and filter_points_by_radius to rank/filter any CSV or "
        "GeoJSON table of points by great-circle distance to a center location."
    ),
)


@mcp.tool(
    name="render_feature_map",
    title="map(render)",
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
        Field(
            description=(
                "Ordered layers (later layers draw on top). Each: {'geojson': "
                "FeatureCollection|Feature|geometry|list|JSON-string|path, 'name': str, "
                "'style': {facecolor, edgecolor, alpha, linewidth, color, markersize, "
                "zorder, color_by, scale, category_colors, legend}}."
            )
        ),
    ],
    output_path: Annotated[str, Field(description="Destination PNG path.")] = "map.png",
    title: Annotated[str, Field(description="Figure title.")] = "",
    basemap: Annotated[
        bool, Field(description="Add a CartoDB Positron basemap (needs network).")
    ] = True,
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
    title="join(points)",
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
    points_geojson: Annotated[
        Any, Field(description="GeoJSON points (FeatureCollection/Feature/list/JSON/path).")
    ],
    polygons_geojson: Annotated[Any, Field(description="GeoJSON polygons (same accepted forms).")],
    buffer_km: Annotated[
        float,
        Field(description="Optional margin added to polygons so near points count. 0 = strict."),
    ] = 0.0,
    point_label_fields: Annotated[
        list[str] | None, Field(description="Property names to surface per matched point.")
    ] = None,
) -> dict[str, Any]:
    """Return the points that fall within (optionally buffered) polygons."""
    try:
        return points_in_polygons(
            points_geojson,
            polygons_geojson,
            buffer_km=buffer_km,
            point_label_fields=point_label_fields,
        )
    except Exception as exc:  # noqa: BLE001 - surface as tool error
        logger.exception("points_in_polygons failed")
        raise ToolError(f"Spatial overlap failed: {exc}") from exc


@mcp.tool(
    name="bounding_box",
    title="compute(bbox)",
    description=(
        "Compute the bounding box [min_lon, min_lat, max_lon, max_lat] of GeoJSON "
        "features (inline or file path), optionally padded by buffer_km. A "
        "deterministic geometry op for deriving an analysis region from a fire perimeter."
    ),
    annotations={"readOnlyHint": True, "destructiveHint": False, "idempotentHint": True},
    tags={"geospatial", "bbox", "region", "geojson"},
)
async def bounding_box_tool(
    geojson: Annotated[
        Any, Field(description="GeoJSON features (FeatureCollection/Feature/list/JSON/path).")
    ],
    pad_km: Annotated[float, Field(description="Optional padding in km added on each side.")] = 0.0,
) -> dict[str, Any]:
    """Return the (optionally padded) bounding box of GeoJSON features."""
    try:
        return bounding_box(geojson, pad_km=pad_km)
    except Exception as exc:  # noqa: BLE001
        logger.exception("bounding_box failed")
        raise ToolError(f"Bounding box failed: {exc}") from exc


@mcp.tool(
    name="query_arcgis_features",
    title="query(arcgis)",
    description=(
        "Query an ArcGIS FeatureServer layer (with optional lon/lat bbox and where "
        "clause) and write the returned features to a local GeoJSON file. The saved "
        "FeatureCollection can be fed directly into render_feature_map, "
        "points_in_polygons, or bounding_box."
    ),
    annotations={"readOnlyHint": True, "destructiveHint": False, "idempotentHint": True},
    tags={"geospatial", "arcgis", "features", "geojson", "retrieval"},
)
async def query_arcgis_features_tool(
    feature_service_url: Annotated[
        str,
        Field(description="ArcGIS FeatureServer service, layer, or query URL (HTTP(S))."),
    ],
    layer_id: Annotated[
        int | str | None,
        Field(description="Numeric layer id when querying a FeatureServer root."),
    ] = None,
    where: Annotated[
        str,
        Field(description="ArcGIS SQL where clause (default '1=1')."),
    ] = "1=1",
    out_fields: Annotated[
        str,
        Field(description="Comma-separated output fields or '*' for all."),
    ] = "*",
    max_features: Annotated[
        int | str | None,
        Field(description="Maximum features to return (default 25, capped at 200)."),
    ] = 25,
    min_lon: Annotated[float | str | None, Field(description="Bbox minimum longitude.")] = None,
    min_lat: Annotated[float | str | None, Field(description="Bbox minimum latitude.")] = None,
    max_lon: Annotated[float | str | None, Field(description="Bbox maximum longitude.")] = None,
    max_lat: Annotated[float | str | None, Field(description="Bbox maximum latitude.")] = None,
    output_path: Annotated[
        str | None,
        Field(description="Output GeoJSON path; auto-named under the artifacts root if omitted."),
    ] = None,
) -> dict[str, Any]:
    """Query an ArcGIS FeatureServer layer and persist features as GeoJSON.

    Returns ``{ok, output_path, feature_count, geometry_type, fields, features, ...}``
    and writes a native GeoJSON FeatureCollection (ArcGIS ``f=geojson``) to
    ``output_path``.
    """
    try:
        return await query_arcgis_features(
            feature_service_url,
            layer_id=layer_id,
            where=where,
            out_fields=out_fields,
            max_features=max_features,
            min_lon=min_lon,
            min_lat=min_lat,
            max_lon=max_lon,
            max_lat=max_lat,
            output_path=output_path,
        )
    except ArcGISQueryError as exc:
        raise ToolError(str(exc)) from exc
    except Exception as exc:  # noqa: BLE001 - surface query failures as tool errors
        logger.exception("query_arcgis_features failed")
        raise ToolError(f"ArcGIS feature query failed: {exc}") from exc


@mcp.tool(
    name="geocode",
    title="geocode(place)",
    description=(
        "Look up a free-text place name or location and return real coordinates "
        "from OpenStreetMap Nominatim (a lookup, not a model guess). Each match "
        "carries lat/lon, a [min_lon, min_lat, max_lon, max_lat] bbox, type, "
        "importance, and a provenance source so the region can be grounded and cited."
    ),
    annotations={"readOnlyHint": True, "destructiveHint": False, "idempotentHint": True},
    tags={"geocoding", "location", "coordinates"},
)
async def geocode_tool(
    query: Annotated[
        str,
        Field(description="Place name or free-text location to look up (e.g. 'Boulder, CO')."),
    ],
    limit: Annotated[
        int,
        Field(description="Maximum number of matches to return (default 1, capped at 50)."),
    ] = 1,
    countrycodes: Annotated[
        str | None,
        Field(
            description=(
                "Optional comma-separated ISO 3166-1 alpha-2 country codes to "
                "restrict results (e.g. 'us' or 'us,ca')."
            )
        ),
    ] = None,
) -> list[dict[str, Any]]:
    """Geocode a place name into coordinates via OpenStreetMap Nominatim.

    Returns a list of matches, each with ``display_name``, ``lat``, ``lon``,
    ``bbox`` ([min_lon, min_lat, max_lon, max_lat]), ``type``, ``importance``,
    and ``provenance`` (the data source, e.g. ``"osm_nominatim"``).
    """
    try:
        return await geocode(query, limit=limit, countrycodes=countrycodes)
    except GeocodeError as exc:
        raise ToolError(str(exc)) from exc
    except Exception as exc:  # noqa: BLE001 - surface lookup failures as tool errors
        logger.exception("geocode failed")
        raise ToolError(f"Geocoding failed: {exc}") from exc


@mcp.tool(
    name="filter_points_by_radius",
    title="filter(radius)",
    description=(
        "Filter/rank any table of points by great-circle distance to a center. "
        "Reads a CSV (or GeoJSON points) of locations, computes the haversine "
        "distance from (center_lat, center_lon) to each row, and returns the rows "
        "within radius_km sorted ascending by distance, each annotated with "
        "distance_km. Latitude/longitude columns are auto-detected from common "
        "names (latitude/lat, longitude/lon/long) when not given. Domain-neutral: "
        "works for sensors, sites, cities, samples, or any lon/lat table."
    ),
    annotations={"readOnlyHint": True, "destructiveHint": False, "idempotentHint": True},
    tags={"geospatial", "distance", "filter", "haversine", "proximity"},
)
async def filter_points_by_radius_tool(
    data_path: Annotated[
        str,
        Field(description="Path to a CSV or GeoJSON file of points to filter."),
    ],
    center_lat: Annotated[
        float, Field(description="Center latitude in decimal degrees ([-90, 90]).")
    ],
    center_lon: Annotated[
        float, Field(description="Center longitude in decimal degrees ([-180, 180]).")
    ],
    radius_km: Annotated[
        float, Field(description="Radius in kilometers; only points within are kept (> 0).")
    ],
    lat_column: Annotated[
        str | None,
        Field(description="Latitude column name; auto-detected (latitude/lat/y) when omitted."),
    ] = None,
    lon_column: Annotated[
        str | None,
        Field(
            description="Longitude column name; auto-detected (longitude/lon/long/x) when omitted."
        ),
    ] = None,
    id_column: Annotated[
        str | None,
        Field(description="Optional column whose value is surfaced as 'id' on each point."),
    ] = None,
    limit: Annotated[
        int | None,
        Field(description="Optional cap on the number of returned points (after sorting)."),
    ] = None,
) -> dict[str, Any]:
    """Return the points within radius_km of the center, sorted by distance.

    Returns ``{ok, count, within_radius_count, points:[{..., distance_km}],
    center, radius_km, lat_column, lon_column, ...}``. Domain-neutral; no
    station/catalog semantics.
    """
    try:
        return filter_points_by_radius(
            data_path,
            center_lat,
            center_lon,
            radius_km,
            lat_column=lat_column,
            lon_column=lon_column,
            id_column=id_column,
            limit=limit,
        )
    except ProximityError as exc:
        raise ToolError(str(exc)) from exc
    except Exception as exc:  # noqa: BLE001 - surface as tool error
        logger.exception("filter_points_by_radius failed")
        raise ToolError(f"Distance filtering failed: {exc}") from exc


@mcp.resource("geo://capabilities")
def capabilities() -> dict[str, Any]:
    """Describe what the geo MCP server can do."""
    return {
        "tools": [
            "render_feature_map",
            "points_in_polygons",
            "bounding_box",
            "query_arcgis_features",
            "geocode",
            "filter_points_by_radius",
        ],
        "accepts": (
            "GeoJSON (FeatureCollection/Feature/geometry/list/JSON-string/path); "
            "CSV or GeoJSON point tables for distance filtering"
        ),
        "outputs": [
            "map PNG",
            "GeoJSON FeatureCollection file",
            "spatial-overlap matches",
            "bbox",
            "geocoded location matches",
            "distance-filtered points sorted by distance_km",
        ],
        "crs": "EPSG:4326 (lon/lat)",
        "description": (
            "Render GeoJSON vector layers to maps, retrieve ArcGIS FeatureServer "
            "features as GeoJSON, run point-in-polygon overlap, compute bounding "
            "boxes, geocode place names into coordinates via OpenStreetMap "
            "Nominatim, and filter/rank any CSV or GeoJSON table of points by "
            "great-circle (haversine) distance to a center location."
        ),
    }


@mcp.prompt()
def map_arcgis_layer(feature_service_url: str) -> list[Message]:
    """Guided workflow: retrieve an ArcGIS layer and render it on a map."""
    return [
        Message(
            f"Retrieve features from the ArcGIS FeatureServer at '{feature_service_url}' "
            "with query_arcgis_features, then render the saved GeoJSON onto a map with "
            "render_feature_map. Report the feature count and the output paths."
        ),
    ]


def main() -> None:
    """Entry point for the geo MCP server."""
    mcp.run()


if __name__ == "__main__":
    main()
