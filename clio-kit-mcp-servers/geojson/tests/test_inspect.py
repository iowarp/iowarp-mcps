"""Unit tests for the stdlib GeoJSON inspection helpers."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from geojson_mcp.implementation import (
    GeoJSONError,
    compute_bbox,
    feature_bbox,
    inspect_geojson,
    load_geojson,
    summarize_geojson,
    validate_geojson,
)

from .conftest import FEATURE_COLLECTION, POINT_FEATURE


# ---------------------------------------------------------------------------
# load_geojson
# ---------------------------------------------------------------------------
def test_load_from_path(point_file: Path) -> None:
    loaded = load_geojson(str(point_file))
    assert loaded["type"] == "Feature"


def test_load_from_inline_dict() -> None:
    assert load_geojson(POINT_FEATURE)["type"] == "Feature"


def test_load_from_inline_json_string() -> None:
    assert load_geojson(json.dumps(POINT_FEATURE))["type"] == "Feature"


def test_load_missing_file_raises() -> None:
    with pytest.raises(GeoJSONError, match="not found"):
        load_geojson("/no/such/file.geojson")


def test_load_invalid_json_raises(invalid_json_file: Path) -> None:
    with pytest.raises(GeoJSONError, match="Invalid GeoJSON"):
        load_geojson(str(invalid_json_file))


def test_load_empty_raises() -> None:
    with pytest.raises(GeoJSONError, match="Empty"):
        load_geojson("   ")


# ---------------------------------------------------------------------------
# inspect_geojson
# ---------------------------------------------------------------------------
def test_inspect_point(point_file: Path) -> None:
    info = inspect_geojson(str(point_file))
    assert info["geojson_type"] == "Feature"
    assert info["feature_count"] == 1
    assert info["geometry_types"] == {"Point": 1}
    assert info["property_keys"] == ["name", "value"]
    assert info["bbox"] == [-118.25, 34.05, -118.25, 34.05]
    assert info["total_vertices"] == 1


def test_inspect_linestring(linestring_file: Path) -> None:
    info = inspect_geojson(str(linestring_file))
    assert info["geometry_types"] == {"LineString": 1}
    assert info["total_vertices"] == 3
    assert info["bbox"] == [-118.5, 34.0, -117.5, 35.0]


def test_inspect_polygon(polygon_file: Path) -> None:
    info = inspect_geojson(str(polygon_file))
    assert info["geometry_types"] == {"Polygon": 1}
    # The closing position repeats the first, so a 4-corner ring has 5 vertices.
    assert info["total_vertices"] == 5
    assert info["bbox"] == [-118.5, 34.0, -118.0, 34.5]


def test_inspect_feature_collection(collection_file: Path) -> None:
    info = inspect_geojson(str(collection_file))
    assert info["geojson_type"] == "FeatureCollection"
    assert info["feature_count"] == 3
    assert info["geometry_types"] == {"Point": 1, "LineString": 1, "Polygon": 1}
    assert info["bbox"] == [-118.5, 34.0, -117.5, 35.0]
    assert info["total_vertices"] == 1 + 3 + 5
    assert set(info["property_keys"]) >= {"name", "value", "length_km", "code"}


def test_inspect_sample_features_limit(collection_file: Path) -> None:
    info = inspect_geojson(str(collection_file), max_sample_features=1)
    assert len(info["sample_features"]) == 1
    assert info["sample_features"][0]["geometry_type"] == "Point"


def test_inspect_detects_crs() -> None:
    payload = {
        "type": "FeatureCollection",
        "crs": {"type": "name", "properties": {"name": "urn:ogc:def:crs:OGC:1.3:CRS84"}},
        "features": [POINT_FEATURE],
    }
    info = inspect_geojson(payload)
    assert info["crs"] == "urn:ogc:def:crs:OGC:1.3:CRS84"


def test_inspect_no_crs_returns_none(point_file: Path) -> None:
    assert inspect_geojson(str(point_file))["crs"] is None


def test_inspect_bare_geometry() -> None:
    info = inspect_geojson({"type": "Point", "coordinates": [1.0, 2.0]})
    assert info["feature_count"] == 1
    assert info["geometry_types"] == {"Point": 1}
    assert info["bbox"] == [1.0, 2.0, 1.0, 2.0]


# ---------------------------------------------------------------------------
# validate_geojson
# ---------------------------------------------------------------------------
def test_validate_point_ok(point_file: Path) -> None:
    result = validate_geojson(str(point_file))
    assert result == {"valid": True, "errors": []}


def test_validate_collection_ok(collection_file: Path) -> None:
    result = validate_geojson(str(collection_file))
    assert result["valid"] is True
    assert result["errors"] == []


def test_validate_all_geometry_types_ok() -> None:
    payload = {
        "type": "FeatureCollection",
        "features": [
            {"type": "Feature", "properties": {}, "geometry": g}
            for g in (
                {"type": "Point", "coordinates": [0, 0]},
                {"type": "MultiPoint", "coordinates": [[0, 0], [1, 1]]},
                {"type": "LineString", "coordinates": [[0, 0], [1, 1]]},
                {"type": "MultiLineString", "coordinates": [[[0, 0], [1, 1]]]},
                {"type": "Polygon", "coordinates": [[[0, 0], [1, 0], [1, 1], [0, 0]]]},
                {"type": "MultiPolygon", "coordinates": [[[[0, 0], [1, 0], [1, 1], [0, 0]]]]},
                {
                    "type": "GeometryCollection",
                    "geometries": [{"type": "Point", "coordinates": [0, 0]}],
                },
            )
        ],
    }
    assert validate_geojson(payload) == {"valid": True, "errors": []}


def test_validate_null_geometry_ok() -> None:
    payload = {"type": "Feature", "properties": {}, "geometry": None}
    assert validate_geojson(payload)["valid"] is True


def test_validate_malformed(malformed_file: Path) -> None:
    result = validate_geojson(str(malformed_file))
    assert result["valid"] is False
    assert len(result["errors"]) >= 2
    assert any("coordinates" in e for e in result["errors"])


def test_validate_unknown_type() -> None:
    result = validate_geojson({"type": "Banana", "coordinates": [0, 0]})
    assert result["valid"] is False
    assert "Banana" in result["errors"][0]


def test_validate_feature_collection_missing_features() -> None:
    result = validate_geojson({"type": "FeatureCollection"})
    assert result["valid"] is False
    assert any("features" in e for e in result["errors"])


def test_validate_non_finite_coordinate() -> None:
    # NaN survives json round-trips via Python's json module; ensure it is rejected.
    result = validate_geojson({"type": "Point", "coordinates": [float("nan"), 1.0]})
    assert result["valid"] is False


# ---------------------------------------------------------------------------
# summarize_geojson
# ---------------------------------------------------------------------------
def test_summarize_collection(collection_file: Path) -> None:
    result = summarize_geojson(str(collection_file))
    assert "3 feature(s)" in result["summary"]
    assert result["feature_count"] == 3
    assert result["bbox"] == [-118.5, 34.0, -117.5, 35.0]
    assert "bbox=" in result["summary"]


def test_summarize_empty_collection() -> None:
    result = summarize_geojson({"type": "FeatureCollection", "features": []})
    assert result["feature_count"] == 0
    assert result["bbox"] is None
    assert "bbox=none" in result["summary"]


# ---------------------------------------------------------------------------
# feature_bbox + shared helper
# ---------------------------------------------------------------------------
def test_feature_bbox(collection_file: Path) -> None:
    result = feature_bbox(str(collection_file))
    assert result["bbox"] == [-118.5, 34.0, -117.5, 35.0]
    assert result["feature_count"] == 3


def test_feature_bbox_empty() -> None:
    result = feature_bbox({"type": "FeatureCollection", "features": []})
    assert result["bbox"] is None
    assert result["feature_count"] == 0


def test_compute_bbox_matches_inspect(collection_file: Path) -> None:
    payload = load_geojson(str(collection_file))
    assert compute_bbox(payload) == inspect_geojson(str(collection_file))["bbox"]


def test_compute_bbox_handles_geometrycollection() -> None:
    payload = {
        "type": "GeometryCollection",
        "geometries": [
            {"type": "Point", "coordinates": [-10.0, -5.0]},
            {"type": "Point", "coordinates": [10.0, 5.0]},
        ],
    }
    assert compute_bbox(payload) == [-10.0, -5.0, 10.0, 5.0]


def test_list_of_features() -> None:
    info = inspect_geojson([POINT_FEATURE, FEATURE_COLLECTION])
    # 1 from the bare feature + 3 from the collection.
    assert info["feature_count"] == 4
