"""Implementation helpers for the geo MCP server."""

from .arcgis import ArcGISQueryError, query_arcgis_features
from .geocode import GeocodeError, geocode
from .geojson_inspect import (
    GeoJSONError,
    compute_bbox,
    feature_bbox,
    inspect_geojson,
    load_geojson,
    summarize_geojson,
    validate_geojson,
)
from .map_render import MapRenderError, render_map
from .overlap import bounding_box, points_in_polygons
from .proximity import ProximityError, filter_points_by_radius, haversine_km

__all__ = [
    "MapRenderError",
    "render_map",
    "points_in_polygons",
    "bounding_box",
    "ArcGISQueryError",
    "query_arcgis_features",
    "GeocodeError",
    "geocode",
    "GeoJSONError",
    "compute_bbox",
    "feature_bbox",
    "inspect_geojson",
    "load_geojson",
    "summarize_geojson",
    "validate_geojson",
    "ProximityError",
    "filter_points_by_radius",
    "haversine_km",
]
