"""Geocode a free-text place name into real coordinates via a lookup.

A generic, domain-neutral geocoding helper: given a place name or free-text
location, it queries a real geocoding service and returns matching locations
with coordinates, a bounding box, and a ``provenance`` field naming the data
source. The point is to GROUND a region from an authoritative lookup instead of
relying on a model's geographic prior, so callers can cite a real source.

The default data source is OpenStreetMap Nominatim. Nominatim returns each
match's bounding box as ``[min_lat, max_lat, min_lon, max_lon]``; this module
REORDERS it to the conventional ``[min_lon, min_lat, max_lon, max_lat]`` used
throughout the geo server. No domain assumptions are made about what a place is.
"""

from __future__ import annotations

import asyncio
from typing import Any

import httpx

# OpenStreetMap Nominatim search endpoint.
_NOMINATIM_SEARCH_URL = "https://nominatim.openstreetmap.org/search"
# Nominatim mandates a descriptive, identifying User-Agent on every request.
_USER_AGENT = "clio-kit-geo-mcp/1.0 (+https://github.com/iowarp/clio-kit)"
# Provenance label written onto every match so callers can cite the source.
_PROVENANCE = "osm_nominatim"

# Network timeouts (seconds) for the geocoding query.
_HTTP_CONNECT_TIMEOUT_S = 8.0
_HTTP_READ_TIMEOUT_S = 30.0
# Upper bound that keeps tool payloads small enough for agent traces.
_MAX_RESULTS = 50


class GeocodeError(ValueError):
    """Raised when a geocoding lookup cannot be completed."""


def _clean_optional_text(value: str | None) -> str | None:
    """Normalize empty strings to absent optional values."""
    if value is None:
        return None
    cleaned = str(value).strip()
    return cleaned or None


def _reorder_bbox(boundingbox: Any) -> list[float] | None:
    """Reorder a Nominatim boundingbox to ``[min_lon, min_lat, max_lon, max_lat]``.

    Nominatim returns ``boundingbox`` as ``[min_lat, max_lat, min_lon, max_lon]``
    (four numeric strings). Returns ``None`` when the value is missing or
    malformed so a single bad match does not fail the whole lookup.
    """
    if not isinstance(boundingbox, (list, tuple)) or len(boundingbox) != 4:
        return None
    try:
        min_lat, max_lat, min_lon, max_lon = (float(value) for value in boundingbox)
    except (TypeError, ValueError):
        return None
    return [min_lon, min_lat, max_lon, max_lat]


def _map_match(entry: Any) -> dict[str, Any] | None:
    """Map a single Nominatim result object to the generic match schema.

    Returns ``None`` when the entry lacks usable coordinates so it can be
    skipped without failing the entire lookup.
    """
    if not isinstance(entry, dict):
        return None
    try:
        lat = float(entry["lat"])
        lon = float(entry["lon"])
    except (KeyError, TypeError, ValueError):
        return None
    importance_raw = entry.get("importance")
    try:
        importance = float(importance_raw) if importance_raw is not None else None
    except (TypeError, ValueError):
        importance = None
    return {
        "display_name": entry.get("display_name"),
        "lat": lat,
        "lon": lon,
        "bbox": _reorder_bbox(entry.get("boundingbox")),
        "type": entry.get("type"),
        "importance": importance,
        "provenance": _PROVENANCE,
    }


async def geocode(
    query: str,
    *,
    limit: int = 1,
    countrycodes: str | None = None,
) -> list[dict[str, Any]]:
    """Geocode a free-text place name into coordinates via OpenStreetMap Nominatim.

    Performs a real lookup against the Nominatim search API and returns the
    matching locations. Each match grounds the place in an authoritative source
    (recorded as ``provenance``) rather than a model's geographic prior.

    Args:
        query: Place name or free-text location to look up (e.g. ``"Boulder, CO"``).
        limit: Maximum number of matches to return (default 1, capped at 50).
        countrycodes: Optional comma-separated ISO 3166-1 alpha-2 country codes to
            restrict results (e.g. ``"us"`` or ``"us,ca"``).

    Returns:
        A list of match dicts, each with ``display_name``, ``lat`` (float),
        ``lon`` (float), ``bbox`` (``[min_lon, min_lat, max_lon, max_lat]`` or
        ``None``), ``type``, ``importance``, and ``provenance``.

    Raises:
        GeocodeError: On a blank query, HTTP error, invalid JSON, or when the
            lookup returns no usable matches.
    """
    cleaned_query = _clean_optional_text(query)
    if not cleaned_query:
        raise GeocodeError("query must be a non-empty place name or location string")

    bounded_limit = max(1, min(int(limit), _MAX_RESULTS))
    params: dict[str, Any] = {
        "format": "json",
        "q": cleaned_query,
        "limit": bounded_limit,
        "addressdetails": 0,
    }
    country_filter = _clean_optional_text(countrycodes)
    if country_filter:
        params["countrycodes"] = country_filter

    headers = {"User-Agent": _USER_AGENT}
    timeout = httpx.Timeout(_HTTP_READ_TIMEOUT_S, connect=_HTTP_CONNECT_TIMEOUT_S)
    try:
        async with httpx.AsyncClient(timeout=timeout, follow_redirects=True) as client:
            response = await client.get(_NOMINATIM_SEARCH_URL, params=params, headers=headers)
            response.raise_for_status()
            decoded = response.json()
    except (httpx.HTTPError, ValueError) as exc:
        raise GeocodeError(f"Could not complete the geocoding lookup: {exc}") from exc

    if not isinstance(decoded, list):
        raise GeocodeError("Geocoding service returned an unexpected response shape.")

    matches = [match for match in (_map_match(entry) for entry in decoded) if match is not None]
    if not matches:
        raise GeocodeError(f"No matching location found for query: {cleaned_query!r}")
    return matches


def geocode_sync(
    query: str,
    *,
    limit: int = 1,
    countrycodes: str | None = None,
) -> list[dict[str, Any]]:
    """Synchronous wrapper around :func:`geocode` for non-async callers."""
    return asyncio.run(geocode(query, limit=limit, countrycodes=countrycodes))
