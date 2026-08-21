"""Standard-library GeoJSON document inspection.

Reads, validates, summarizes and measures GeoJSON documents using only
``json`` and ``math`` -- no geopandas or shapely. That matters: these
functions report what a document literally contains, including features
whose geometry a geometry engine would reject, which is exactly what an
inspection tool must do. The shapely/geopandas paths in ``overlap.py``
answer the different question of what the *valid* geometry covers.

Ported from the standalone geojson MCP server when it merged into geo
(clio-kit #357).
"""

from __future__ import annotations

import json
import math
from collections import Counter
from pathlib import Path
from typing import Any

# A GeoJSON ``coordinates`` leaf is at minimum a [longitude, latitude] pair, but
# may carry a third (and per some producers a fourth) ordinate (e.g. elevation).
_MIN_POSITION_LEN = 2

# The seven GeoJSON geometry types defined by RFC 7946 section 1.4.
_GEOMETRY_TYPES = frozenset(
    {
        "Point",
        "MultiPoint",
        "LineString",
        "MultiLineString",
        "Polygon",
        "MultiPolygon",
        "GeometryCollection",
    }
)


class GeoJSONError(ValueError):
    """Raised when GeoJSON cannot be loaded or is structurally unusable."""


def _is_number(value: Any) -> bool:
    """Return ``True`` for a real, finite number (excludes ``bool`` and NaN/inf)."""
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


def load_geojson(source: Any) -> dict[str, Any] | list[Any]:
    """Load GeoJSON from a file path or inline value into a Python object.

    Args:
        source: A path to a JSON/GeoJSON file, a JSON string, or an
            already-parsed ``dict``/``list``.

    Returns:
        The parsed GeoJSON object (a ``dict`` for objects, a ``list`` for a
        bare list of features/geometries).

    Raises:
        GeoJSONError: If the source cannot be read or parsed as JSON, or is
            not an object/array at the top level.
    """
    if isinstance(source, (dict, list)):
        return source

    if not isinstance(source, str):
        raise GeoJSONError(f"Unsupported GeoJSON source type: {type(source).__name__}")

    text = source.strip()
    if not text:
        raise GeoJSONError("Empty GeoJSON source")

    # Treat values that begin with JSON object/array markers as inline JSON;
    # everything else is treated as a filesystem path.
    if text[0] in "{[":
        try:
            parsed = json.loads(text)
        except json.JSONDecodeError as exc:
            raise GeoJSONError(f"Invalid GeoJSON: {exc}") from exc
    else:
        path = Path(text)
        if not path.is_file():
            raise GeoJSONError(f"GeoJSON file not found: {text}")
        try:
            parsed = json.loads(path.read_text(encoding="utf-8"))
        except OSError as exc:
            raise GeoJSONError(f"Cannot read GeoJSON file '{text}': {exc}") from exc
        except json.JSONDecodeError as exc:
            raise GeoJSONError(f"Invalid GeoJSON in '{text}': {exc}") from exc

    if not isinstance(parsed, (dict, list)):
        raise GeoJSONError("GeoJSON must be a JSON object or array at the top level")
    return parsed


def iter_features(payload: dict[str, Any] | list[Any]) -> list[dict[str, Any]]:
    """Normalize any GeoJSON payload into a list of Feature-like dicts.

    Accepts a FeatureCollection, a single Feature, a bare geometry, or a list
    of any of those, and returns a list of dicts each shaped like a Feature
    (``{"type": "Feature", "geometry": ..., "properties": ...}``). Items that
    are not understandable as features are wrapped or skipped rather than
    raising, so callers can report counts without crashing on partial data.
    """
    if isinstance(payload, list):
        features: list[dict[str, Any]] = []
        for item in payload:
            features.extend(iter_features(item))
        return features

    obj_type = payload.get("type")
    if obj_type == "FeatureCollection":
        raw = payload.get("features")
        if not isinstance(raw, list):
            return []
        return [f for f in raw if isinstance(f, dict)]
    if obj_type == "Feature":
        return [payload]
    if obj_type in _GEOMETRY_TYPES:
        # A bare geometry: wrap it so callers see a uniform feature shape.
        return [{"type": "Feature", "properties": {}, "geometry": payload}]
    # Unknown object: surface it as a single feature so counts/validation can
    # report on it instead of silently dropping it.
    return [payload]


def iter_positions(geometry: Any) -> list[tuple[float, ...]]:
    """Return every coordinate position contained in a GeoJSON geometry.

    Handles all geometry types including nested ``GeometryCollection``. Each
    returned position is a tuple of numeric ordinates (``lon, lat[, ...]``).
    Non-numeric or malformed coordinate leaves are ignored.
    """
    if not isinstance(geometry, dict):
        return []

    geom_type = geometry.get("type")
    if geom_type == "GeometryCollection":
        positions: list[tuple[float, ...]] = []
        for child in geometry.get("geometries") or []:
            positions.extend(iter_positions(child))
        return positions

    def walk(value: Any) -> list[tuple[float, ...]]:
        if (
            isinstance(value, list)
            and len(value) >= _MIN_POSITION_LEN
            and all(_is_number(v) for v in value)
        ):
            return [tuple(float(v) for v in value)]
        points: list[tuple[float, ...]] = []
        if isinstance(value, list):
            for item in value:
                points.extend(walk(item))
        return points

    return walk(geometry.get("coordinates"))


def compute_bbox(payload: dict[str, Any] | list[Any]) -> list[float] | None:
    """Compute the overall bounding box of all positions in a GeoJSON payload.

    This is the single shared bbox helper reused by every public tool.

    Returns:
        ``[min_lon, min_lat, max_lon, max_lat]`` over all coordinate positions,
        or ``None`` when the payload contains no usable positions.
    """
    lons: list[float] = []
    lats: list[float] = []
    for feature in iter_features(payload):
        geometry = feature.get("geometry") if isinstance(feature, dict) else None
        for position in iter_positions(geometry):
            lons.append(position[0])
            lats.append(position[1])
    if not lons:
        return None
    return [min(lons), min(lats), max(lons), max(lats)]


def _extract_crs(payload: dict[str, Any] | list[Any]) -> str | None:
    """Extract a CRS identifier from a (pre-RFC7946) ``crs`` member, if present.

    RFC 7946 drops the ``crs`` member (everything is assumed WGS84), but many
    real-world files still carry one. This returns the named CRS string (e.g.
    ``"urn:ogc:def:crs:OGC:1.3:CRS84"``) when available, else ``None``.
    """
    if not isinstance(payload, dict):
        return None
    crs = payload.get("crs")
    if not isinstance(crs, dict):
        return None
    props = crs.get("properties")
    if isinstance(props, dict):
        name = props.get("name")
        if isinstance(name, str) and name:
            return name
    return None


def inspect_geojson(source: Any, max_sample_features: int = 5) -> dict[str, Any]:
    """Inspect GeoJSON and report structure, schema, extent, and vertex totals.

    Args:
        source: GeoJSON path or inline GeoJSON (string/dict/list).
        max_sample_features: Number of representative feature property samples
            to include (clamped to 0..50).

    Returns:
        A dict with ``geojson_type``, ``feature_count``, ``geometry_types``
        (type -> count), ``property_keys`` (sorted schema), ``bbox``
        (``[min_lon, min_lat, max_lon, max_lat]`` or ``None``), ``crs`` (or
        ``None``), ``total_vertices``, and ``sample_features``.

    Raises:
        GeoJSONError: If the source cannot be loaded.
    """
    payload = load_geojson(source)
    max_sample_features = max(0, min(int(max_sample_features), 50))

    features = iter_features(payload)
    geometry_counts: Counter[str] = Counter()
    property_keys: Counter[str] = Counter()
    total_vertices = 0
    samples: list[dict[str, Any]] = []

    for index, feature in enumerate(features):
        if not isinstance(feature, dict):
            continue
        geometry = feature.get("geometry")
        properties = feature.get("properties")
        if not isinstance(properties, dict):
            properties = {}
        geom_type = "null"
        if isinstance(geometry, dict):
            geom_type = str(geometry.get("type") or "Unknown")
        elif geometry is None:
            geom_type = "null"
        geometry_counts[geom_type] += 1
        property_keys.update(str(key) for key in properties)
        vertex_count = len(iter_positions(geometry))
        total_vertices += vertex_count
        if len(samples) < max_sample_features:
            samples.append(
                {
                    "index": index,
                    "geometry_type": geom_type,
                    "vertex_count": vertex_count,
                    "properties": {key: properties[key] for key in sorted(properties)[:10]},
                }
            )

    geojson_type = payload.get("type") if isinstance(payload, dict) else "List"
    return {
        "geojson_type": str(geojson_type or ""),
        "feature_count": len(features),
        "geometry_types": dict(geometry_counts),
        "property_keys": sorted(property_keys),
        "bbox": compute_bbox(payload),
        "crs": _extract_crs(payload),
        "total_vertices": total_vertices,
        "sample_features": samples,
    }


def _validate_position(value: Any, path: str, errors: list[str]) -> None:
    """Append an error if ``value`` is not a valid GeoJSON position."""
    if not isinstance(value, list) or len(value) < _MIN_POSITION_LEN:
        errors.append(f"{path}: position must be a list of at least 2 numbers")
        return
    if not all(_is_number(v) for v in value):
        errors.append(f"{path}: position ordinates must be finite numbers")


def _validate_coordinates(geom_type: str, coords: Any, path: str, errors: list[str]) -> None:
    """Validate a geometry's ``coordinates`` against its declared type.

    Checks the nesting depth required by each geometry type and that every
    coordinate leaf is a valid numeric position. Records human-readable
    messages in ``errors`` instead of raising.
    """
    if geom_type == "Point":
        _validate_position(coords, path, errors)
    elif geom_type in ("MultiPoint", "LineString"):
        if not isinstance(coords, list):
            errors.append(f"{path}: coordinates must be a list of positions")
            return
        for i, pos in enumerate(coords):
            _validate_position(pos, f"{path}[{i}]", errors)
    elif geom_type in ("MultiLineString", "Polygon"):
        if not isinstance(coords, list):
            errors.append(f"{path}: coordinates must be a list of line/ring arrays")
            return
        for i, line in enumerate(coords):
            if not isinstance(line, list):
                errors.append(f"{path}[{i}]: must be a list of positions")
                continue
            for j, pos in enumerate(line):
                _validate_position(pos, f"{path}[{i}][{j}]", errors)
    elif geom_type == "MultiPolygon":
        if not isinstance(coords, list):
            errors.append(f"{path}: coordinates must be a list of polygons")
            return
        for i, poly in enumerate(coords):
            if not isinstance(poly, list):
                errors.append(f"{path}[{i}]: must be a list of rings")
                continue
            for j, ring in enumerate(poly):
                if not isinstance(ring, list):
                    errors.append(f"{path}[{i}][{j}]: must be a list of positions")
                    continue
                for k, pos in enumerate(ring):
                    _validate_position(pos, f"{path}[{i}][{j}][{k}]", errors)


def _validate_geometry(geometry: Any, path: str, errors: list[str]) -> None:
    """Validate a single GeoJSON geometry object (or ``null``)."""
    if geometry is None:
        return  # A null geometry is permitted on a Feature per RFC 7946.
    if not isinstance(geometry, dict):
        errors.append(f"{path}: geometry must be an object or null")
        return
    geom_type = geometry.get("type")
    if geom_type not in _GEOMETRY_TYPES:
        errors.append(f"{path}: unknown geometry type {geom_type!r}")
        return
    if geom_type == "GeometryCollection":
        geometries = geometry.get("geometries")
        if not isinstance(geometries, list):
            errors.append(f"{path}: GeometryCollection requires a 'geometries' list")
            return
        for i, child in enumerate(geometries):
            _validate_geometry(child, f"{path}.geometries[{i}]", errors)
        return
    if "coordinates" not in geometry:
        errors.append(f"{path}: geometry missing 'coordinates'")
        return
    _validate_coordinates(geom_type, geometry["coordinates"], f"{path}.coordinates", errors)


def validate_geojson(source: Any) -> dict[str, Any]:
    """Validate the structural well-formedness of a GeoJSON document.

    Checks that the top-level ``type`` is recognized and that every geometry's
    type/coordinates are well-formed (correct nesting depth, numeric finite
    positions). Does not enforce semantic rules like closed/right-hand-rule
    polygon rings.

    Args:
        source: GeoJSON path or inline GeoJSON.

    Returns:
        ``{"valid": bool, "errors": list[str]}``.

    Raises:
        GeoJSONError: If the source cannot be loaded/parsed at all.
    """
    payload = load_geojson(source)
    errors: list[str] = []

    if isinstance(payload, list):
        errors.append("Top-level GeoJSON should be an object, not a bare array")
        for i, item in enumerate(payload):
            _validate_geometry(
                item.get("geometry") if isinstance(item, dict) else item, f"[{i}]", errors
            )
        return {"valid": not errors, "errors": errors}

    obj_type = payload.get("type")
    if obj_type not in (_GEOMETRY_TYPES | {"Feature", "FeatureCollection"}):
        errors.append(f"Unknown top-level GeoJSON type {obj_type!r}")
        return {"valid": False, "errors": errors}

    if obj_type == "FeatureCollection":
        raw = payload.get("features")
        if not isinstance(raw, list):
            errors.append("FeatureCollection requires a 'features' list")
        else:
            for i, feature in enumerate(raw):
                if not isinstance(feature, dict):
                    errors.append(f"features[{i}]: must be a Feature object")
                    continue
                if feature.get("type") != "Feature":
                    errors.append(f"features[{i}]: type must be 'Feature'")
                _validate_geometry(feature.get("geometry"), f"features[{i}].geometry", errors)
    elif obj_type == "Feature":
        _validate_geometry(payload.get("geometry"), "geometry", errors)
    else:
        # Bare geometry at the top level.
        _validate_geometry(payload, "geometry", errors)

    return {"valid": not errors, "errors": errors}


def summarize_geojson(source: Any, max_sample_features: int = 3) -> dict[str, Any]:
    """Produce a compact, human-readable summary of a GeoJSON document.

    Args:
        source: GeoJSON path or inline GeoJSON.
        max_sample_features: Number of sample feature property sets to include.

    Returns:
        A dict with a one-line ``summary`` string plus the structured fields it
        was built from: ``feature_count``, ``geometry_types``, ``bbox``,
        ``property_keys``, and ``sample_features``.

    Raises:
        GeoJSONError: If the source cannot be loaded.
    """
    info = inspect_geojson(source, max_sample_features=max_sample_features)
    geom_summary = ", ".join(
        f"{count} {gtype}" for gtype, count in sorted(info["geometry_types"].items())
    )
    bbox = info["bbox"]
    bbox_text = (
        f"bbox=[{bbox[0]:.4f}, {bbox[1]:.4f}, {bbox[2]:.4f}, {bbox[3]:.4f}]"
        if bbox is not None
        else "bbox=none"
    )
    summary = (
        f"{info['geojson_type'] or 'GeoJSON'} with {info['feature_count']} feature(s) "
        f"({geom_summary or 'no geometries'}); {bbox_text}; "
        f"{len(info['property_keys'])} property key(s); "
        f"{info['total_vertices']} total vertices"
    )
    return {
        "summary": summary,
        "feature_count": info["feature_count"],
        "geometry_types": info["geometry_types"],
        "bbox": bbox,
        "property_keys": info["property_keys"],
        "sample_features": info["sample_features"],
    }


def feature_bbox(source: Any) -> dict[str, Any]:
    """Return the overall bounding box of all features in a GeoJSON document.

    Uses the shared :func:`compute_bbox` helper.

    Args:
        source: GeoJSON path or inline GeoJSON.

    Returns:
        ``{"bbox": [min_lon, min_lat, max_lon, max_lat] | None,
        "feature_count": int}``.

    Raises:
        GeoJSONError: If the source cannot be loaded.
    """
    payload = load_geojson(source)
    return {
        "bbox": compute_bbox(payload),
        "feature_count": len(iter_features(payload)),
    }
