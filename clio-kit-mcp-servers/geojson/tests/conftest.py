"""Shared pytest fixtures: small temporary .geojson files for the geojson MCP."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

POINT_FEATURE: dict[str, Any] = {
    "type": "Feature",
    "properties": {"name": "origin", "value": 1},
    "geometry": {"type": "Point", "coordinates": [-118.25, 34.05]},
}

LINESTRING_FEATURE: dict[str, Any] = {
    "type": "Feature",
    "properties": {"name": "path", "length_km": 12.3},
    "geometry": {
        "type": "LineString",
        "coordinates": [[-118.5, 34.0], [-118.0, 34.5], [-117.5, 35.0]],
    },
}

POLYGON_FEATURE: dict[str, Any] = {
    "type": "Feature",
    "properties": {"name": "region", "code": "A1"},
    "geometry": {
        "type": "Polygon",
        "coordinates": [
            [[-118.5, 34.0], [-118.0, 34.0], [-118.0, 34.5], [-118.5, 34.5], [-118.5, 34.0]]
        ],
    },
}

FEATURE_COLLECTION: dict[str, Any] = {
    "type": "FeatureCollection",
    "features": [POINT_FEATURE, LINESTRING_FEATURE, POLYGON_FEATURE],
}

# A structurally malformed document: declared Polygon but coordinates are a flat
# list of numbers instead of an array of rings, and one position is non-numeric.
MALFORMED: dict[str, Any] = {
    "type": "FeatureCollection",
    "features": [
        {
            "type": "Feature",
            "properties": {},
            "geometry": {"type": "Polygon", "coordinates": [-118.5, 34.0]},
        },
        {
            "type": "Feature",
            "properties": {},
            "geometry": {"type": "Point", "coordinates": ["not-a-number", 34.0]},
        },
    ],
}


def _write(tmp_path: Path, name: str, payload: dict[str, Any]) -> Path:
    path = tmp_path / name
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


@pytest.fixture
def point_file(tmp_path: Path) -> Path:
    """A single Point Feature on disk."""
    return _write(tmp_path, "point.geojson", POINT_FEATURE)


@pytest.fixture
def linestring_file(tmp_path: Path) -> Path:
    """A single LineString Feature on disk."""
    return _write(tmp_path, "line.geojson", LINESTRING_FEATURE)


@pytest.fixture
def polygon_file(tmp_path: Path) -> Path:
    """A single Polygon Feature on disk."""
    return _write(tmp_path, "polygon.geojson", POLYGON_FEATURE)


@pytest.fixture
def collection_file(tmp_path: Path) -> Path:
    """A FeatureCollection (Point + LineString + Polygon) on disk."""
    return _write(tmp_path, "collection.geojson", FEATURE_COLLECTION)


@pytest.fixture
def malformed_file(tmp_path: Path) -> Path:
    """A structurally malformed GeoJSON document on disk."""
    return _write(tmp_path, "malformed.geojson", MALFORMED)


@pytest.fixture
def invalid_json_file(tmp_path: Path) -> Path:
    """A file whose contents are not valid JSON at all."""
    path = tmp_path / "broken.geojson"
    path.write_text("{ this is not json", encoding="utf-8")
    return path
