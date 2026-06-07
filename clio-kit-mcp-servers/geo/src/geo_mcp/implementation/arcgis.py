"""Retrieve features from an ArcGIS FeatureServer layer as GeoJSON.

A generic geospatial RETRIEVAL helper: given an ArcGIS FeatureServer service,
layer, or query URL plus an optional lon/lat bbox and SQL ``where`` clause, it
queries the layer and writes a native GeoJSON FeatureCollection (ArcGIS
``f=geojson``) to a local file so any downstream renderer or geometry op can
consume it. The implementation is domain-neutral: it operates on generic ArcGIS
inputs and makes no assumptions about what the features represent.
"""

from __future__ import annotations

import asyncio
import json
import os
import re
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import httpx

# Network timeouts (seconds) for the FeatureServer query.
_HTTP_CONNECT_TIMEOUT_S = 8.0
_HTTP_READ_TIMEOUT_S = 30.0
# Upper bound that keeps tool payloads small enough for agent traces.
_MAX_ARCGIS_FEATURES = 200


class ArcGISQueryError(ValueError):
    """Raised when an ArcGIS FeatureServer query cannot be completed."""


def artifacts_root() -> Path:
    """Return the writable root for generated GeoJSON artifacts.

    Configurable via the ``CLIO_KIT_ARTIFACTS`` environment variable; otherwise a
    stable per-user temp directory is used. No agent-specific paths are hardcoded.
    """
    configured = os.environ.get("CLIO_KIT_ARTIFACTS", "").strip()
    if configured:
        root = Path(configured).expanduser()
    else:
        root = Path(tempfile.gettempdir()) / "clio-kit-geo-artifacts"
    root.mkdir(parents=True, exist_ok=True)
    return root.resolve()


def _validate_output_path(candidate: str | Path, *, default_name: str) -> Path:
    """Resolve an output path, confining writes to the configurable artifacts root.

    A relative path, bare filename, or any path outside the artifacts root is
    relocated under the artifacts root using only its filename. This is the
    standalone allowed-root check (no external file-policy dependency).
    """
    root = artifacts_root()
    raw = Path(str(candidate)).expanduser() if candidate else Path(default_name)
    name = raw.name or default_name
    if raw.is_absolute():
        try:
            resolved = raw.resolve()
            resolved.relative_to(root)
            resolved.parent.mkdir(parents=True, exist_ok=True)
            return resolved
        except (ValueError, OSError):
            pass
    target = (root / name).resolve()
    target.parent.mkdir(parents=True, exist_ok=True)
    return target


def _clean_optional_text(value: str | None) -> str | None:
    """Normalize empty strings to absent optional values."""
    if value is None:
        return None
    cleaned = str(value).strip()
    return cleaned or None


def _arcgis_layer_query_url(feature_service_url: str, layer_id: int | str | None) -> str:
    """Return an ArcGIS FeatureServer query URL for a service or layer URL."""
    base = feature_service_url.strip().rstrip("/")
    if not base.lower().startswith(("http://", "https://")):
        raise ValueError("feature_service_url must be HTTP(S)")
    if base.lower().endswith("/query"):
        return base
    tail = base.rsplit("/", 1)[-1]
    if tail.isdigit():
        return f"{base}/query"
    selected_layer = str(layer_id if layer_id not in (None, "") else 0).strip()
    if not selected_layer.isdigit():
        raise ValueError("layer_id must be numeric when querying a FeatureServer root")
    return f"{base}/{selected_layer}/query"


def _arcgis_bbox_geometry(
    *,
    min_lon: float | str | None,
    min_lat: float | str | None,
    max_lon: float | str | None,
    max_lat: float | str | None,
) -> dict[str, Any]:
    """Build ArcGIS envelope query params from optional lon/lat bbox values."""
    values = [min_lon, min_lat, max_lon, max_lat]
    if any(value in (None, "") for value in values):
        return {}
    try:
        xmin, ymin, xmax, ymax = (float(str(value)) for value in values)
    except (TypeError, ValueError) as exc:
        raise ValueError("bbox values must be numeric longitude/latitude values") from exc
    if xmin >= xmax or ymin >= ymax:
        raise ValueError("bbox must satisfy min_lon < max_lon and min_lat < max_lat")
    return {
        "geometry": json.dumps(
            {
                "xmin": xmin,
                "ymin": ymin,
                "xmax": xmax,
                "ymax": ymax,
                "spatialReference": {"wkid": 4326},
            }
        ),
        "geometryType": "esriGeometryEnvelope",
        "inSR": 4326,
        "spatialRel": "esriSpatialRelIntersects",
    }


def _compact_arcgis_geometry(geometry: Any) -> dict[str, Any]:
    """Summarize an ArcGIS geometry for compact agent-facing payloads."""
    if not isinstance(geometry, dict):
        return {}
    if "x" in geometry and "y" in geometry:
        return {"x": geometry.get("x"), "y": geometry.get("y")}
    rings = geometry.get("rings")
    if isinstance(rings, list):
        xs: list[float] = []
        ys: list[float] = []
        for ring in rings[:3]:
            if not isinstance(ring, list):
                continue
            for point in ring[:250]:
                if isinstance(point, list | tuple) and len(point) >= 2:
                    try:
                        xs.append(float(point[0]))
                        ys.append(float(point[1]))
                    except (TypeError, ValueError):
                        continue
        if xs and ys:
            return {"bbox": [min(xs), min(ys), max(xs), max(ys)], "point_count_sampled": len(xs)}
    return {"geometry_keys": sorted(str(key) for key in geometry)[:8]}


def _arcgis_epoch_to_iso(value: Any) -> str | None:
    """Return an ISO UTC timestamp for plausible ArcGIS epoch values."""
    if isinstance(value, bool):
        return None
    try:
        numeric = float(value)
    except (TypeError, ValueError):
        return None
    if numeric <= 0:
        return None
    seconds = numeric / 1000 if numeric > 10_000_000_000 else numeric
    if not 946_684_800 <= seconds <= 4_102_444_800:
        return None
    return datetime.fromtimestamp(seconds, tz=timezone.utc).isoformat().replace("+00:00", "Z")


def _is_arcgis_date_field(name: str) -> bool:
    lowered = name.lower()
    return any(token in lowered for token in ("date", "time", "start", "end", "updated", "expires"))


def _normalize_arcgis_attributes(attributes: Any) -> dict[str, Any]:
    """Add ISO companions for ArcGIS date/time fields while preserving raw values."""
    if not isinstance(attributes, dict):
        return {}
    normalized = dict(attributes)
    for key, value in attributes.items():
        key_text = str(key)
        if not _is_arcgis_date_field(key_text):
            continue
        iso_value = _arcgis_epoch_to_iso(value)
        if iso_value:
            normalized[f"{key_text}_iso"] = iso_value
    return normalized


def _arcgis_feature_collection(features: list[dict[str, Any]]) -> dict[str, Any]:
    """Convert ArcGIS feature rows into a compact GeoJSON-like feature collection."""
    rows: list[dict[str, Any]] = []
    for feature in features:
        if not isinstance(feature, dict):
            continue
        rows.append(
            {
                "type": "Feature",
                "properties": _normalize_arcgis_attributes(feature.get("attributes")),
                "geometry": _compact_arcgis_geometry(feature.get("geometry")),
            }
        )
    return {"type": "FeatureCollection", "features": rows}


async def query_arcgis_features(
    feature_service_url: str,
    *,
    layer_id: int | str | None = None,
    where: str = "1=1",
    out_fields: str = "*",
    max_features: int | str | None = 25,
    min_lon: float | str | None = None,
    min_lat: float | str | None = None,
    max_lon: float | str | None = None,
    max_lat: float | str | None = None,
    output_path: str | None = None,
) -> dict[str, Any]:
    """Query an ArcGIS FeatureServer layer and persist features as GeoJSON.

    Args:
        feature_service_url: ArcGIS FeatureServer service, layer, or query URL.
        layer_id: Numeric layer id when querying a FeatureServer root.
        where: ArcGIS SQL where clause (default ``"1=1"``).
        out_fields: Comma-separated output fields or ``"*"`` for all.
        max_features: Maximum features to return (default 25, capped at 200).
        min_lon: Bbox minimum longitude (all four bbox values required together).
        min_lat: Bbox minimum latitude.
        max_lon: Bbox maximum longitude.
        max_lat: Bbox maximum latitude.
        output_path: Output GeoJSON path; auto-named under the artifacts root if
            omitted.

    Returns:
        Dict with ``ok``, ``source_url``, ``query_url``, ``output_path``,
        ``output_size_bytes``, ``feature_count``, ``geometry_type``, ``fields``,
        ``features``, and ``features_truncated``. Writes a native GeoJSON
        FeatureCollection (ArcGIS ``f=geojson``) to ``output_path``.
    """
    if not output_path and feature_service_url:
        # Auto-name the saved FeatureCollection from the service segment so it can
        # always be resolved downstream without depending on the caller passing one.
        segments = [s for s in str(feature_service_url).split("/") if s]
        service_name = ""
        for index, segment in enumerate(segments):
            if segment.lower() == "featureserver" and index > 0:
                service_name = segments[index - 1]
                break
        if not service_name:
            service_name = next(
                (s for s in reversed(segments) if s and not s.isdigit() and "." not in s),
                "features",
            )
        safe = re.sub(r"[^a-zA-Z0-9]+", "_", service_name).strip("_").lower() or "features"
        output_path = f"{safe}.geojson"

    geojson_name = Path(str(output_path)).name or "features.geojson"
    if not geojson_name.lower().endswith((".geojson", ".json")):
        geojson_name += ".geojson"
    resolved_output = _validate_output_path(geojson_name, default_name="features.geojson")

    try:
        limit = max(1, min(int(max_features or 25), _MAX_ARCGIS_FEATURES))
        params: dict[str, Any] = {
            "f": "json",
            "where": _clean_optional_text(where) or "1=1",
            "outFields": _clean_optional_text(out_fields) or "*",
            "returnGeometry": "true",
            "outSR": 4326,
            "resultRecordCount": limit,
        }
        params.update(
            _arcgis_bbox_geometry(
                min_lon=min_lon, min_lat=min_lat, max_lon=max_lon, max_lat=max_lat
            )
        )
        query_url = _arcgis_layer_query_url(feature_service_url, layer_id)
    except ValueError as exc:
        raise ArcGISQueryError(str(exc)) from exc

    timeout = httpx.Timeout(_HTTP_READ_TIMEOUT_S, connect=_HTTP_CONNECT_TIMEOUT_S)
    try:
        async with httpx.AsyncClient(timeout=timeout, follow_redirects=True) as client:
            response = await client.get(query_url, params=params)
            response.raise_for_status()
            decoded = response.json()
    except (httpx.HTTPError, ValueError) as exc:
        raise ArcGISQueryError(f"Could not query ArcGIS FeatureServer resource: {exc}") from exc

    if isinstance(decoded, dict) and decoded.get("error"):
        raise ArcGISQueryError(
            f"ArcGIS returned an error for the requested feature query: {decoded.get('error')}"
        )
    features = decoded.get("features") if isinstance(decoded, dict) else None
    if not isinstance(features, list):
        raise ArcGISQueryError("ArcGIS returned no feature list for the requested resource.")

    collection = _arcgis_feature_collection(features)
    # The compact collection above summarizes geometry for agent traces. For the
    # saved file fetch native GeoJSON so downstream renderers get real geometry.
    geo_collection: dict[str, Any] = collection
    try:
        async with httpx.AsyncClient(timeout=timeout, follow_redirects=True) as client:
            geo_resp = await client.get(query_url, params={**params, "f": "geojson"})
            geo_resp.raise_for_status()
            candidate = geo_resp.json()
            if isinstance(candidate, dict) and candidate.get("type") == "FeatureCollection":
                geo_collection = candidate
    except (httpx.HTTPError, ValueError):
        geo_collection = collection

    resolved_output.write_text(
        json.dumps(geo_collection, sort_keys=True, indent=2, default=str), encoding="utf-8"
    )

    raw_fields = decoded.get("fields") if isinstance(decoded, dict) else []
    fields = raw_fields if isinstance(raw_fields, list) else []
    return {
        "ok": True,
        "source_url": feature_service_url,
        "query_url": str(response.url),
        "output_path": str(resolved_output),
        "output_size_bytes": resolved_output.stat().st_size,
        "feature_count": len(collection["features"]),
        "geometry_type": decoded.get("geometryType") if isinstance(decoded, dict) else None,
        "fields": [
            str(field.get("name"))
            for field in fields
            if isinstance(field, dict) and field.get("name")
        ][:24],
        "features": collection["features"][: min(10, len(collection["features"]))],
        "features_truncated": len(collection["features"]) > 10,
        "status": "success",
    }


def query_arcgis_features_sync(
    feature_service_url: str,
    *,
    layer_id: int | str | None = None,
    where: str = "1=1",
    out_fields: str = "*",
    max_features: int | str | None = 25,
    min_lon: float | str | None = None,
    min_lat: float | str | None = None,
    max_lon: float | str | None = None,
    max_lat: float | str | None = None,
    output_path: str | None = None,
) -> dict[str, Any]:
    """Synchronous wrapper around :func:`query_arcgis_features` for non-async callers."""
    return asyncio.run(
        query_arcgis_features(
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
    )
