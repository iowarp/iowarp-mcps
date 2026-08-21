"""Saved earthquake-catalog loading (pure stdlib + numpy-free).

This module reads a catalog the caller already has on disk and normalizes it into
a list of event dicts. It retrieves nothing - acquisition is the job of a
separate retrieval MCP, not this server.

Two on-disk formats are accepted:

* **GeoJSON** (``.json`` / ``.geojson``): either a catalog-style
  ``FeatureCollection`` (events under ``features[].properties`` / ``geometry``,
  the common earthquake-catalog feed layout), or a saved wrapper
  ``{"events": [...]}`` whose ``events`` are already normalized event dicts.
* **CSV** (``.csv``): one event per row with columns ``mag``/``magnitude``,
  ``time``/``time_ms``, ``longitude``/``lon``, ``latitude``/``lat``,
  ``depth``/``depth_km``, and optional ``place``/``id``. Times may be epoch
  milliseconds, epoch seconds, or ISO-8601 timestamps.

The normalized event schema (the contract the analysis/plotting code reads):
``{"mag", "time_ms", "lon", "lat", "depth_km", "place", "id"}``.
"""

from __future__ import annotations

import csv
import json
from datetime import datetime
from pathlib import Path
from typing import Any


class CatalogError(Exception):
    """Raised when a saved catalog cannot be read or parsed."""


def resolve_read_path(catalog_path: str) -> Path:
    """Resolve and validate a readable catalog file path.

    Args:
        catalog_path: Path to a saved GeoJSON or CSV earthquake catalog.

    Returns:
        The resolved absolute path.

    Raises:
        CatalogError: If the path is empty, missing, or not a file.
    """
    text = str(catalog_path or "").strip()
    if not text:
        raise CatalogError("No catalog_path provided.")
    path = Path(text).expanduser().resolve()
    if not path.exists():
        raise CatalogError(f"Catalog does not exist: {path}")
    if not path.is_file():
        raise CatalogError(f"Catalog path is not a regular file: {path}")
    return path


def resolve_write_path(output_path: str) -> Path:
    """Resolve an output file path, creating parent directories.

    Args:
        output_path: Destination path for a generated artifact.

    Returns:
        The resolved absolute path with its parent directory ensured.

    Raises:
        CatalogError: If the path is empty or its parent cannot be created.
    """
    text = str(output_path or "").strip()
    if not text:
        raise CatalogError("No output_path provided.")
    path = Path(text).expanduser().resolve()
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        raise CatalogError(
            f"Could not create output directory {path.parent}: {exc}"
        ) from exc
    return path


# --- GeoJSON normalization (lifted verbatim from the source server) ----------


def _normalize_events(geojson: dict[str, Any]) -> list[dict[str, Any]]:
    events: list[dict[str, Any]] = []
    for feature in geojson.get("features", []):
        props = feature.get("properties") or {}
        geom = feature.get("geometry") or {}
        coords = geom.get("coordinates") or [None, None, None]
        mag = props.get("mag")
        if mag is None or props.get("type", "earthquake") != "earthquake":
            continue
        events.append(
            {
                "mag": float(mag),
                "time_ms": int(props["time"]),
                "lon": coords[0],
                "lat": coords[1],
                "depth_km": coords[2],
                "place": props.get("place", ""),
                "id": feature.get("id", ""),
            }
        )
    events.sort(key=lambda e: e["time_ms"])
    return events


# --- CSV normalization -------------------------------------------------------

_MAG_KEYS = ("mag", "magnitude", "mw", "ml")
_TIME_KEYS = ("time_ms", "time", "datetime", "date", "origin_time")
_LON_KEYS = ("lon", "longitude", "long")
_LAT_KEYS = ("lat", "latitude")
_DEPTH_KEYS = ("depth_km", "depth")
_PLACE_KEYS = ("place", "location", "region")
_ID_KEYS = ("id", "event_id", "eventid")


def _first(row: dict[str, Any], keys: tuple[str, ...]) -> Any:
    for key in keys:
        if key in row and row[key] not in (None, ""):
            return row[key]
    return None


def _to_time_ms(value: Any) -> int:
    """Coerce a time cell into epoch milliseconds.

    Accepts epoch milliseconds, epoch seconds, or an ISO-8601 timestamp.
    """
    if isinstance(value, (int, float)):
        number = float(value)
    else:
        text = str(value).strip()
        try:
            number = float(text)
        except ValueError:
            iso = text.replace("Z", "+00:00")
            try:
                parsed = datetime.fromisoformat(iso)
            except ValueError as exc:
                raise CatalogError(f"Unparseable time value: {value!r}") from exc
            return int(parsed.timestamp() * 1000)
    # Heuristic: values below ~10^11 are epoch seconds, not milliseconds.
    if number < 1e11:
        number *= 1000.0
    return int(number)


def _to_float(value: Any) -> float | None:
    if value in (None, ""):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _events_from_csv(path: Path) -> list[dict[str, Any]]:
    events: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        if reader.fieldnames is None:
            raise CatalogError("CSV catalog has no header row.")
        normalized_field = {name: name.strip().lower() for name in reader.fieldnames}
        for raw_row in reader:
            row = {normalized_field.get(key, key): val for key, val in raw_row.items()}
            mag = _to_float(_first(row, _MAG_KEYS))
            time_raw = _first(row, _TIME_KEYS)
            if mag is None or time_raw is None:
                continue
            events.append(
                {
                    "mag": mag,
                    "time_ms": _to_time_ms(time_raw),
                    "lon": _to_float(_first(row, _LON_KEYS)),
                    "lat": _to_float(_first(row, _LAT_KEYS)),
                    "depth_km": _to_float(_first(row, _DEPTH_KEYS)),
                    "place": _first(row, _PLACE_KEYS) or "",
                    "id": _first(row, _ID_KEYS) or "",
                }
            )
    events.sort(key=lambda e: e["time_ms"])
    return events


def load_catalog(catalog_path: str) -> tuple[Path, list[dict[str, Any]]]:
    """Load a saved catalog into normalized event dicts.

    Args:
        catalog_path: Path to a GeoJSON (``.json``/``.geojson``) or CSV
            (``.csv``) earthquake catalog already staged on disk.

    Returns:
        A ``(resolved_path, events)`` tuple. ``events`` is a time-sorted list of
        dicts with keys ``mag``, ``time_ms``, ``lon``, ``lat``, ``depth_km``,
        ``place``, and ``id``. An empty list is a valid result (a quiet region).

    Raises:
        CatalogError: If the file cannot be read, has an unsupported extension,
            or cannot be parsed into events.
    """
    path = resolve_read_path(catalog_path)
    suffix = path.suffix.lower()
    if suffix == ".csv":
        try:
            return path, _events_from_csv(path)
        except CatalogError:
            raise
        except (OSError, ValueError) as exc:
            raise CatalogError(f"Could not parse CSV catalog: {exc}") from exc

    if suffix in (".json", ".geojson"):
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise CatalogError(f"Could not parse JSON catalog: {exc}") from exc
        if not isinstance(payload, dict):
            raise CatalogError("JSON catalog must be an object.")
        # Saved wrapper with already-normalized events.
        if isinstance(payload.get("events"), list):
            return path, sorted(payload["events"], key=lambda e: e.get("time_ms", 0))
        # Catalog-style GeoJSON FeatureCollection (the common feed layout).
        if "features" in payload:
            return path, _normalize_events(payload)
        raise CatalogError(
            "JSON catalog must be a GeoJSON FeatureCollection or an "
            "{'events': [...]} wrapper."
        )

    raise CatalogError(
        f"Unsupported catalog extension {suffix!r}; use .geojson, .json, or .csv."
    )
