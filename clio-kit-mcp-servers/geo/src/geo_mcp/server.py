#!/usr/bin/env python3
"""Geo MCP server.

Renders GeoJSON vector layers into map images. Any tool that produces GeoJSON
features (catalog feature queries, file inspection, analysis output) can be
visualized as a layered map with an optional web-tile basemap.
"""

import logging
from typing import Annotated, Any, Literal, cast

from dotenv import load_dotenv
from fastmcp import FastMCP
from fastmcp.exceptions import ToolError
from fastmcp.prompts import Message
from pydantic import Field
from typing_extensions import NotRequired, TypedDict

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

# --- Structured result shapes (drive real MCP outputSchema declarations) ----


class MapLayerSummary(TypedDict):
    """Per-layer feature/geometry summary within a rendered map result.

    ``skipped`` is present only when the layer had no usable geometries;
    ``geometry`` is present only when it did — the two are mutually
    exclusive, but both are optional so one TypedDict covers both outcomes.
    """

    name: str
    features: int
    geometry: NotRequired[list[str]]
    skipped: NotRequired[Literal["no features"]]


class MapBounds(TypedDict):
    """WGS84 bounding box merged across every rendered layer."""

    min_lon: float
    min_lat: float
    max_lon: float
    max_lat: float


class RenderFeatureMapResult(TypedDict):
    """Structured result for a successful render_feature_map call."""

    status: Literal["success"]
    output_path: str
    size_bytes: int
    bounds: MapBounds
    basemap: bool
    layers: list[MapLayerSummary]


class MatchedPoint(TypedDict):
    """One point that fell within the (optionally buffered) query polygons."""

    index: int
    lon: float
    lat: float
    properties: dict[str, Any]


class PointsInPolygonsResult(TypedDict):
    """Structured result for a successful points_in_polygons call.

    Every return path in the implementation (no input points, no input
    polygons, or a normal overlap) produces this exact same shape — only the
    counts and ``matched`` contents vary — so one TypedDict covers all of
    them; no discriminated union is needed here.
    """

    status: Literal["success"]
    points_total: int
    polygons_total: int
    matched_count: int
    matched: list[MatchedPoint]


class BoundingBoxResult(TypedDict):
    """Structured result for a bounding_box call.

    ``status`` is ``"empty"`` when the input GeoJSON had no usable
    geometries — ``bbox`` is then ``None`` and ``feature_count`` is 0.
    Otherwise ``status`` is ``"success"`` and ``bbox`` carries
    ``[min_lon, min_lat, max_lon, max_lat]``.

    Modeled as one TypedDict with a two-value ``status`` Literal rather than
    a ``Field(discriminator=...)`` union: a discriminated union's JSON Schema
    root is a bare ``oneOf``/``discriminator`` object with no ``type: object``
    key, which trips FastMCP's non-object-output-schema auto-wrap
    (``x-fastmcp-wrap-result``) and would silently change this tool's
    structured_content from a bare dict to ``{"result": {...}}``.
    """

    status: Literal["success", "empty"]
    feature_count: int
    bbox: list[float] | None


class ArcGISFeature(TypedDict):
    """One GeoJSON-like feature returned by an ArcGIS FeatureServer query.

    ``geometry`` is a compact summary, not raw ArcGIS geometry: a point
    ``{x, y}``, a sampled ring ``{bbox, point_count_sampled}``, or a
    last-resort ``{geometry_keys}`` fallback — genuinely freeform.
    """

    type: Literal["Feature"]
    properties: dict[str, Any]
    geometry: dict[str, Any]


class QueryArcGISFeaturesResult(TypedDict):
    """Structured result for a successful query_arcgis_features call."""

    ok: Literal[True]
    status: Literal["success"]
    source_url: str
    query_url: str
    output_path: str
    output_size_bytes: int
    feature_count: int
    geometry_type: str | None
    fields: list[str]
    features: list[ArcGISFeature]
    features_truncated: bool


class GeocodeMatch(TypedDict):
    """One geocoded location match from OpenStreetMap Nominatim."""

    display_name: str | None
    lat: float
    lon: float
    bbox: list[float] | None
    type: str | None
    importance: float | None
    provenance: Literal["osm_nominatim"]


class DistanceFilterCenter(TypedDict):
    """Center coordinate used for a filter_points_by_radius query."""

    lat: float
    lon: float


class FilterPointsByRadiusResult(TypedDict):
    """Structured result for a successful filter_points_by_radius call.

    ``points`` entries carry the source row's own (freeform) columns plus an
    always-present ``distance_km`` and, when ``id_column`` was given, an
    ``id`` field — the base columns are genuinely open-ended, so each point
    stays ``dict[str, Any]``.
    """

    ok: Literal[True]
    count: int
    within_radius_count: int
    total_points: int
    skipped_invalid: int
    source_format: Literal["csv", "geojson"]
    lat_column: str
    lon_column: str
    center: DistanceFilterCenter
    radius_km: float
    points: list[dict[str, Any]]


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
    title="Render Map",
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
) -> RenderFeatureMapResult:
    """Render GeoJSON layers to a map PNG. See tool description for the layer schema."""
    try:
        return cast(
            RenderFeatureMapResult,
            render_map(layers, output_path, title=title, basemap=basemap, bbox=bbox),
        )
    except MapRenderError as exc:
        raise ToolError(str(exc)) from exc
    except Exception as exc:  # noqa: BLE001 - surface rendering failures as tool errors
        logger.exception("render_feature_map failed")
        raise ToolError(f"Map render failed: {exc}") from exc


@mcp.tool(
    name="points_in_polygons",
    title="Points In Polygons",
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
) -> PointsInPolygonsResult:
    """Return the points that fall within (optionally buffered) polygons."""
    try:
        return cast(
            PointsInPolygonsResult,
            points_in_polygons(
                points_geojson,
                polygons_geojson,
                buffer_km=buffer_km,
                point_label_fields=point_label_fields,
            ),
        )
    except Exception as exc:  # noqa: BLE001 - surface as tool error
        logger.exception("points_in_polygons failed")
        raise ToolError(f"Spatial overlap failed: {exc}") from exc


@mcp.tool(
    name="bounding_box",
    title="Bounding Box",
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
) -> BoundingBoxResult:
    """Return the (optionally padded) bounding box of GeoJSON features."""
    try:
        return cast(BoundingBoxResult, bounding_box(geojson, pad_km=pad_km))
    except Exception as exc:  # noqa: BLE001
        logger.exception("bounding_box failed")
        raise ToolError(f"Bounding box failed: {exc}") from exc


@mcp.tool(
    name="query_arcgis_features",
    title="Query ArcGIS",
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
) -> QueryArcGISFeaturesResult:
    """Query an ArcGIS FeatureServer layer and persist features as GeoJSON.

    Returns ``{ok, output_path, feature_count, geometry_type, fields, features, ...}``
    and writes a native GeoJSON FeatureCollection (ArcGIS ``f=geojson``) to
    ``output_path``.
    """
    try:
        return cast(
            QueryArcGISFeaturesResult,
            await query_arcgis_features(
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
            ),
        )
    except ArcGISQueryError as exc:
        raise ToolError(str(exc)) from exc
    except Exception as exc:  # noqa: BLE001 - surface query failures as tool errors
        logger.exception("query_arcgis_features failed")
        raise ToolError(f"ArcGIS feature query failed: {exc}") from exc


@mcp.tool(
    name="geocode",
    title="Geocode",
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
) -> list[GeocodeMatch]:
    """Geocode a place name into coordinates via OpenStreetMap Nominatim.

    Returns a list of matches, each with ``display_name``, ``lat``, ``lon``,
    ``bbox`` ([min_lon, min_lat, max_lon, max_lat]), ``type``, ``importance``,
    and ``provenance`` (the data source, e.g. ``"osm_nominatim"``).
    """
    try:
        return cast(
            list[GeocodeMatch], await geocode(query, limit=limit, countrycodes=countrycodes)
        )
    except GeocodeError as exc:
        raise ToolError(str(exc)) from exc
    except Exception as exc:  # noqa: BLE001 - surface lookup failures as tool errors
        logger.exception("geocode failed")
        raise ToolError(f"Geocoding failed: {exc}") from exc


@mcp.tool(
    name="filter_points_by_radius",
    title="Filter By Radius",
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
) -> FilterPointsByRadiusResult:
    """Return the points within radius_km of the center, sorted by distance.

    Returns ``{ok, count, within_radius_count, points:[{..., distance_km}],
    center, radius_km, lat_column, lon_column, ...}``. Domain-neutral; no
    station/catalog semantics.
    """
    try:
        return cast(
            FilterPointsByRadiusResult,
            filter_points_by_radius(
                data_path,
                center_lat,
                center_lon,
                radius_km,
                lat_column=lat_column,
                lon_column=lon_column,
                id_column=id_column,
                limit=limit,
            ),
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
