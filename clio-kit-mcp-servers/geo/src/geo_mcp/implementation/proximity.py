"""Generic distance filtering: rank/filter a table of points by proximity.

Domain-neutral helper that reads a CSV (or GeoJSON points) of locations,
computes the haversine (great-circle) distance from a center coordinate to
each row, and returns the rows that fall within a radius, sorted ascending by
distance and annotated with ``distance_km``.

No domain semantics: any table of points (sensors, sites, cities, samples,
events) works as long as it carries latitude/longitude columns. Common
lat/lon column names are auto-detected when not supplied.
"""

from __future__ import annotations

import csv
import json
import math
from pathlib import Path
from typing import Any

# Mean Earth radius in kilometers (used by the haversine formula).
_EARTH_RADIUS_KM = 6371.0088

# Candidate column names tried (case-insensitively) when auto-detecting the
# latitude / longitude fields. Ordered by preference.
_LAT_CANDIDATES = ("latitude", "lat", "lat_deg", "y", "ycoord", "y_coord")
_LON_CANDIDATES = (
    "longitude",
    "lon",
    "long",
    "lng",
    "lon_deg",
    "x",
    "xcoord",
    "x_coord",
)


class ProximityError(Exception):
    """Raised when distance filtering fails on bad input."""


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Great-circle distance in kilometers between two lat/lon points.

    Args:
        lat1: Latitude of the first point in decimal degrees.
        lon1: Longitude of the first point in decimal degrees.
        lat2: Latitude of the second point in decimal degrees.
        lon2: Longitude of the second point in decimal degrees.

    Returns:
        The haversine distance between the two points in kilometers.
    """
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    d_phi = math.radians(lat2 - lat1)
    d_lambda = math.radians(lon2 - lon1)
    a = math.sin(d_phi / 2.0) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(d_lambda / 2.0) ** 2
    c = 2.0 * math.asin(min(1.0, math.sqrt(a)))
    return _EARTH_RADIUS_KM * c


def _to_float(value: Any) -> float | None:
    """Best-effort float coercion; returns None for missing/unparseable values."""
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _validate_coordinate(value: float, *, name: str, low: float, high: float) -> float:
    """Coerce ``value`` to a float in [low, high] or raise ProximityError."""
    try:
        out = float(value)
    except (TypeError, ValueError) as exc:
        raise ProximityError(f"{name} must be a number, got {value!r}.") from exc
    if math.isnan(out) or math.isinf(out):
        raise ProximityError(f"{name} must be a finite number, got {value!r}.")
    if not (low <= out <= high):
        raise ProximityError(f"{name} must be between {low} and {high}, got {out}.")
    return out


def _pick_column(fieldnames: list[str], candidates: tuple[str, ...]) -> str | None:
    """Return the first column whose lowercased name matches a candidate."""
    lookup = {name.strip().lower(): name for name in fieldnames if name is not None}
    for candidate in candidates:
        if candidate in lookup:
            return lookup[candidate]
    return None


def _resolve_column(
    fieldnames: list[str],
    explicit: str | None,
    candidates: tuple[str, ...],
    *,
    axis: str,
) -> str:
    """Resolve a lat/lon column name, using an explicit value or auto-detection."""
    if explicit is not None:
        if explicit not in fieldnames:
            raise ProximityError(
                f"{axis} column {explicit!r} not found. Available columns: {fieldnames}"
            )
        return explicit
    detected = _pick_column(fieldnames, candidates)
    if detected is None:
        raise ProximityError(
            f"Could not auto-detect a {axis} column. Tried {list(candidates)}; "
            f"available columns: {fieldnames}. Pass {axis}_column explicitly."
        )
    return detected


def _read_csv_rows(text: str) -> tuple[list[dict[str, Any]], list[str]]:
    """Parse CSV text into a list of row dicts and the header field names."""
    reader = csv.DictReader(text.splitlines())
    if reader.fieldnames is None:
        raise ProximityError("CSV input has no header row.")
    fieldnames = [name for name in reader.fieldnames if name is not None]
    if not fieldnames:
        raise ProximityError("CSV input has no header row.")
    rows = [dict(row) for row in reader]
    return rows, fieldnames


def _geojson_rows(text: str) -> tuple[list[dict[str, Any]], list[str]]:
    """Parse GeoJSON points into row dicts with synthetic lat/lon columns.

    Each point Feature becomes a row composed of its ``properties`` plus
    ``latitude`` / ``longitude`` columns derived from the point geometry, so the
    same column-resolution and distance logic applies as for CSV input.
    """
    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        raise ProximityError(f"Input is not valid JSON/GeoJSON: {exc}") from exc

    if isinstance(data, dict) and data.get("type") == "FeatureCollection":
        features = data.get("features") or []
    elif isinstance(data, dict) and data.get("type") == "Feature":
        features = [data]
    elif isinstance(data, list):
        features = data
    else:
        raise ProximityError(
            "GeoJSON input must be a FeatureCollection, Feature, or list of Features."
        )

    rows: list[dict[str, Any]] = []
    for feat in features:
        if not isinstance(feat, dict):
            continue
        geometry = feat.get("geometry") or {}
        if geometry.get("type") != "Point":
            continue
        coords = geometry.get("coordinates")
        if not isinstance(coords, (list, tuple)) or len(coords) < 2:
            continue
        lon, lat = coords[0], coords[1]
        props = feat.get("properties") or {}
        row: dict[str, Any] = dict(props) if isinstance(props, dict) else {}
        row["longitude"] = lon
        row["latitude"] = lat
        rows.append(row)

    if not rows:
        raise ProximityError("GeoJSON input contained no usable Point features.")
    # latitude/longitude are always present on synthesized rows.
    fieldnames = list(rows[0].keys())
    return rows, fieldnames


def _load_points(data_path: str) -> tuple[list[dict[str, Any]], list[str], str]:
    """Load points from a CSV or GeoJSON file into rows + header + format tag."""
    if not isinstance(data_path, str) or not data_path.strip():
        raise ProximityError("data_path must be a non-empty file path.")
    path = Path(data_path).expanduser()
    if not path.is_file():
        raise ProximityError(f"data_path not found: {data_path}")
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise ProximityError(f"Could not read data_path {data_path}: {exc}") from exc
    if not text.strip():
        raise ProximityError(f"data_path is empty: {data_path}")

    suffix = path.suffix.lower()
    if suffix in {".geojson", ".json"}:
        rows, fieldnames = _geojson_rows(text)
        return rows, fieldnames, "geojson"
    rows, fieldnames = _read_csv_rows(text)
    return rows, fieldnames, "csv"


def filter_points_by_radius(
    data_path: str,
    center_lat: float,
    center_lon: float,
    radius_km: float,
    *,
    lat_column: str | None = None,
    lon_column: str | None = None,
    id_column: str | None = None,
    limit: int | None = None,
    compact: bool = False,
) -> dict[str, Any]:
    """Filter a table of points to those within ``radius_km`` of a center.

    Reads a CSV (or GeoJSON points) of locations, computes the haversine
    distance from ``(center_lat, center_lon)`` to each row, keeps the rows
    within ``radius_km``, and returns them sorted ascending by distance with a
    ``distance_km`` annotation. Latitude/longitude columns are auto-detected
    from common names when not supplied. Domain-neutral: no station/catalog
    semantics.

    Args:
        data_path: Path to a CSV or GeoJSON file of points.
        center_lat: Center latitude in decimal degrees ([-90, 90]).
        center_lon: Center longitude in decimal degrees ([-180, 180]).
        radius_km: Radius in kilometers (must be > 0).
        lat_column: Latitude column name; auto-detected when None.
        lon_column: Longitude column name; auto-detected when None.
        id_column: Optional column whose value is surfaced as ``id`` per point.
        limit: Optional cap on the number of returned points (after sorting).

    Returns:
        ``{ok, count, within_radius_count, points, center, radius_km, ...}``
        where ``points`` is the within-radius rows sorted by ``distance_km``.

    Raises:
        ProximityError: On any bad input (missing file, bad coordinates,
            unresolvable columns, non-positive radius, invalid limit).
    """
    center_lat = _validate_coordinate(center_lat, name="center_lat", low=-90.0, high=90.0)
    center_lon = _validate_coordinate(center_lon, name="center_lon", low=-180.0, high=180.0)

    try:
        radius = float(radius_km)
    except (TypeError, ValueError) as exc:
        raise ProximityError(f"radius_km must be a number, got {radius_km!r}.") from exc
    if math.isnan(radius) or math.isinf(radius) or radius <= 0:
        raise ProximityError(f"radius_km must be a positive finite number, got {radius_km!r}.")

    resolved_limit: int | None = None
    if limit is not None:
        try:
            resolved_limit = int(limit)
        except (TypeError, ValueError) as exc:
            raise ProximityError(f"limit must be an integer, got {limit!r}.") from exc
        if resolved_limit <= 0:
            raise ProximityError(f"limit must be a positive integer, got {limit!r}.")

    rows, fieldnames, source_format = _load_points(data_path)

    lat_col = _resolve_column(fieldnames, lat_column, _LAT_CANDIDATES, axis="lat")
    lon_col = _resolve_column(fieldnames, lon_column, _LON_CANDIDATES, axis="lon")
    if id_column is not None and id_column not in fieldnames:
        raise ProximityError(f"id_column {id_column!r} not found. Available columns: {fieldnames}")

    total = len(rows)
    within: list[dict[str, Any]] = []
    skipped = 0
    for row in rows:
        lat = _to_float(row.get(lat_col))
        lon = _to_float(row.get(lon_col))
        if lat is None or lon is None:
            skipped += 1
            continue
        if math.isnan(lat) or math.isnan(lon) or math.isinf(lat) or math.isinf(lon):
            skipped += 1
            continue
        if not (-90.0 <= lat <= 90.0 and -180.0 <= lon <= 180.0):
            skipped += 1
            continue
        distance = haversine_km(center_lat, center_lon, lat, lon)
        if distance > radius:
            continue
        point: dict[str, Any]
        if compact:
            # Lean projection: only the id + distance_km a ranker needs. Keeps the
            # result small so a many-row table (or many repeated calls) does not
            # flood a small-context agent's trajectory with full rows it discards.
            point = {"distance_km": round(distance, 4)}
            if id_column is not None:
                point["id"] = row.get(id_column)
                point[id_column] = row.get(id_column)
        else:
            point = dict(row)
            point["distance_km"] = round(distance, 4)
            if id_column is not None:
                point["id"] = row.get(id_column)
        within.append(point)

    within.sort(key=lambda item: item["distance_km"])
    within_count = len(within)
    if resolved_limit is not None:
        within = within[:resolved_limit]

    return {
        "ok": True,
        "count": len(within),
        "within_radius_count": within_count,
        "total_points": total,
        "skipped_invalid": skipped,
        "source_format": source_format,
        "lat_column": lat_col,
        "lon_column": lon_col,
        "center": {"lat": center_lat, "lon": center_lon},
        "radius_km": radius,
        "points": within,
    }
