"""Spatial overlap: which points fall within (or near) polygons.

Used to ground impact decisions — e.g. which AirNow monitors lie inside the
forecast smoke footprint. Takes GeoJSON points and polygons (inline or file
paths) and returns the matching points with their properties.
"""

from __future__ import annotations

from typing import Any

import geopandas as gpd
from shapely.geometry import shape

from .map_render import _coerce_feature_collection  # reuse GeoJSON loader

WGS84 = 4326
# Rough degrees-per-km at mid latitudes for an optional buffer (good enough for
# a "near the smoke" margin; not a geodesic calculation).
_DEG_PER_KM = 1.0 / 111.0


def points_in_polygons(
    points_geojson: Any,
    polygons_geojson: Any,
    *,
    buffer_km: float = 0.0,
    point_label_fields: list[str] | None = None,
) -> dict[str, Any]:
    """Return the points that fall within (optionally buffered) polygons.

    Args:
        points_geojson: GeoJSON points (FeatureCollection/Feature/list/JSON/path).
        polygons_geojson: GeoJSON polygons (same accepted forms).
        buffer_km: Optional margin added to the polygons (degrees-approx) so
            "just downwind" points count. 0 = strict containment.
        point_label_fields: Property names to surface per matched point.

    Returns:
        Dict with ``status``, ``points_total``, ``polygons_total``,
        ``matched_count``, and ``matched`` (each: index, lon, lat, properties).
    """
    pts = _coerce_feature_collection(points_geojson)
    polys = _coerce_feature_collection(polygons_geojson)
    if not pts:
        return {
            "status": "success",
            "points_total": 0,
            "polygons_total": len(polys),
            "matched_count": 0,
            "matched": [],
        }
    if not polys:
        return {
            "status": "success",
            "points_total": len(pts),
            "polygons_total": 0,
            "matched_count": 0,
            "matched": [],
        }

    poly_geoms = []
    for feat in polys:
        try:
            geom = shape(feat["geometry"])
        except (KeyError, TypeError, ValueError, AttributeError):
            continue
        if not geom.is_empty:
            poly_geoms.append(geom)
    if not poly_geoms:
        return {
            "status": "success",
            "points_total": len(pts),
            "polygons_total": 0,
            "matched_count": 0,
            "matched": [],
        }

    region = gpd.GeoSeries(poly_geoms, crs=WGS84).union_all()
    if buffer_km and buffer_km > 0:
        region = region.buffer(buffer_km * _DEG_PER_KM)

    matched: list[dict[str, Any]] = []
    for index, feat in enumerate(pts):
        try:
            geom = shape(feat["geometry"])
        except (KeyError, TypeError, ValueError, AttributeError):
            continue
        if geom.is_empty or not region.contains(geom):
            continue
        props = feat.get("properties") or {}
        if point_label_fields:
            props = {k: props.get(k) for k in point_label_fields}
        x, y = (geom.x, geom.y) if geom.geom_type == "Point" else (geom.centroid.x, geom.centroid.y)
        matched.append({"index": index, "lon": x, "lat": y, "properties": props})

    return {
        "status": "success",
        "points_total": len(pts),
        "polygons_total": len(poly_geoms),
        "matched_count": len(matched),
        "matched": matched,
    }


def bounding_box(geojson: Any, *, pad_km: float = 0.0) -> dict[str, Any]:
    """Compute the bounding box of GeoJSON features, optionally padded.

    A deterministic geometry op (models are unreliable at deriving bboxes from
    perimeter geometry). Returns ``bbox = [min_lon, min_lat, max_lon, max_lat]``.
    """
    feats = _coerce_feature_collection(geojson)
    geoms = []
    for feat in feats:
        try:
            geom = shape(feat["geometry"])
        except (KeyError, TypeError, ValueError, AttributeError):
            continue
        if not geom.is_empty:
            geoms.append(geom)
    if not geoms:
        return {"status": "empty", "bbox": None, "feature_count": 0}
    minx, miny, maxx, maxy = gpd.GeoSeries(geoms, crs=WGS84).total_bounds
    pad = (pad_km or 0.0) * _DEG_PER_KM
    return {
        "status": "success",
        "feature_count": len(geoms),
        "bbox": [
            round(minx - pad, 4),
            round(miny - pad, 4),
            round(maxx + pad, 4),
            round(maxy + pad, 4),
        ],
    }
