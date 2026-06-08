"""Unit + in-memory tests for the generic distance-filter tool.

All tests use synthetic temp files only — no real network or external data.
"""

from __future__ import annotations

import json

import pytest
from fastmcp import Client
from fastmcp.exceptions import ToolError
from geo_mcp.implementation import (
    ProximityError,
    filter_points_by_radius,
    haversine_km,
)
from geo_mcp.server import mcp

# Reference center: downtown Los Angeles area.
CENTER_LAT = 34.05
CENTER_LON = -118.25

# Three nearby points (increasing distance) and one clearly far point.
NEAR = (34.06, -118.26, "near")  # ~1.4 km
MID = (34.10, -118.30, "mid")  # ~7 km
FAR_IN = (34.20, -118.40, "far_in")  # ~21 km
OUT = (40.71, -74.01, "out")  # New York, thousands of km


def _write_csv(path, *, lat_header="latitude", lon_header="longitude", id_header="name"):
    lines = [f"{id_header},{lat_header},{lon_header}"]
    for lat, lon, name in (NEAR, MID, FAR_IN, OUT):
        lines.append(f"{name},{lat},{lon}")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


# --------------------------------------------------------------------------- #
# haversine
# --------------------------------------------------------------------------- #


def test_haversine_zero_distance():
    assert haversine_km(34.0, -118.0, 34.0, -118.0) == pytest.approx(0.0, abs=1e-9)


def test_haversine_known_distance():
    # LA to NYC is roughly 3936 km.
    d = haversine_km(34.05, -118.25, 40.71, -74.01)
    assert d == pytest.approx(3936, rel=0.02)


# --------------------------------------------------------------------------- #
# within-radius selection + distance sort
# --------------------------------------------------------------------------- #


def test_within_radius_selection(tmp_path):
    csv_path = _write_csv(tmp_path / "pts.csv")
    result = filter_points_by_radius(str(csv_path), CENTER_LAT, CENTER_LON, 25.0)
    assert result["ok"] is True
    names = [p["name"] for p in result["points"]]
    assert names == ["near", "mid", "far_in"]  # OUT excluded, sorted ascending
    assert result["within_radius_count"] == 3
    assert result["count"] == 3
    assert result["total_points"] == 4


def test_distance_sort_ascending(tmp_path):
    csv_path = _write_csv(tmp_path / "pts.csv")
    result = filter_points_by_radius(str(csv_path), CENTER_LAT, CENTER_LON, 25.0)
    distances = [p["distance_km"] for p in result["points"]]
    assert distances == sorted(distances)
    assert all("distance_km" in p for p in result["points"])


def test_radius_excludes_outside(tmp_path):
    csv_path = _write_csv(tmp_path / "pts.csv")
    result = filter_points_by_radius(str(csv_path), CENTER_LAT, CENTER_LON, 5.0)
    assert [p["name"] for p in result["points"]] == ["near"]
    assert result["within_radius_count"] == 1


def test_limit_caps_results_after_sort(tmp_path):
    csv_path = _write_csv(tmp_path / "pts.csv")
    result = filter_points_by_radius(str(csv_path), CENTER_LAT, CENTER_LON, 25.0, limit=2)
    assert result["count"] == 2
    assert result["within_radius_count"] == 3  # reports full count before cap
    assert [p["name"] for p in result["points"]] == ["near", "mid"]


def test_center_echoed_and_radius(tmp_path):
    csv_path = _write_csv(tmp_path / "pts.csv")
    result = filter_points_by_radius(str(csv_path), CENTER_LAT, CENTER_LON, 25.0)
    assert result["center"] == {"lat": CENTER_LAT, "lon": CENTER_LON}
    assert result["radius_km"] == 25.0


# --------------------------------------------------------------------------- #
# auto-detected columns + explicit overrides
# --------------------------------------------------------------------------- #


def test_autodetect_latitude_longitude(tmp_path):
    csv_path = _write_csv(tmp_path / "pts.csv", lat_header="latitude", lon_header="longitude")
    result = filter_points_by_radius(str(csv_path), CENTER_LAT, CENTER_LON, 25.0)
    assert result["lat_column"] == "latitude"
    assert result["lon_column"] == "longitude"


def test_autodetect_lat_lon_long_aliases(tmp_path):
    csv_path = _write_csv(tmp_path / "pts.csv", lat_header="LAT", lon_header="Long")
    result = filter_points_by_radius(str(csv_path), CENTER_LAT, CENTER_LON, 25.0)
    assert result["lat_column"] == "LAT"
    assert result["lon_column"] == "Long"


def test_explicit_columns(tmp_path):
    path = tmp_path / "pts.csv"
    path.write_text(
        "site,yy,xx\nnear,34.06,-118.26\nout,40.71,-74.01\n",
        encoding="utf-8",
    )
    result = filter_points_by_radius(
        str(path), CENTER_LAT, CENTER_LON, 25.0, lat_column="yy", lon_column="xx"
    )
    assert result["lat_column"] == "yy"
    assert [p["site"] for p in result["points"]] == ["near"]


def test_id_column_surfaced(tmp_path):
    csv_path = _write_csv(tmp_path / "pts.csv")
    result = filter_points_by_radius(str(csv_path), CENTER_LAT, CENTER_LON, 25.0, id_column="name")
    assert result["points"][0]["id"] == "near"


def test_skips_unparseable_rows(tmp_path):
    path = tmp_path / "pts.csv"
    path.write_text(
        "name,latitude,longitude\nnear,34.06,-118.26\nbad,not_a_num,-118.0\n",
        encoding="utf-8",
    )
    result = filter_points_by_radius(str(path), CENTER_LAT, CENTER_LON, 25.0)
    assert result["count"] == 1
    assert result["skipped_invalid"] == 1


# --------------------------------------------------------------------------- #
# GeoJSON points input
# --------------------------------------------------------------------------- #


def test_geojson_points_input(tmp_path):
    fc = {
        "type": "FeatureCollection",
        "features": [
            {
                "type": "Feature",
                "properties": {"name": "near"},
                "geometry": {"type": "Point", "coordinates": [-118.26, 34.06]},
            },
            {
                "type": "Feature",
                "properties": {"name": "out"},
                "geometry": {"type": "Point", "coordinates": [-74.01, 40.71]},
            },
        ],
    }
    path = tmp_path / "pts.geojson"
    path.write_text(json.dumps(fc), encoding="utf-8")
    result = filter_points_by_radius(str(path), CENTER_LAT, CENTER_LON, 25.0)
    assert result["source_format"] == "geojson"
    assert [p["name"] for p in result["points"]] == ["near"]
    assert "distance_km" in result["points"][0]


# --------------------------------------------------------------------------- #
# ProximityError paths
# --------------------------------------------------------------------------- #


def test_error_missing_file():
    with pytest.raises(ProximityError, match="not found"):
        filter_points_by_radius("/no/such/file.csv", CENTER_LAT, CENTER_LON, 10.0)


def test_error_bad_latitude(tmp_path):
    csv_path = _write_csv(tmp_path / "pts.csv")
    with pytest.raises(ProximityError, match="center_lat"):
        filter_points_by_radius(str(csv_path), 999.0, CENTER_LON, 10.0)


def test_error_bad_longitude(tmp_path):
    csv_path = _write_csv(tmp_path / "pts.csv")
    with pytest.raises(ProximityError, match="center_lon"):
        filter_points_by_radius(str(csv_path), CENTER_LAT, 999.0, 10.0)


def test_error_nonpositive_radius(tmp_path):
    csv_path = _write_csv(tmp_path / "pts.csv")
    with pytest.raises(ProximityError, match="radius_km"):
        filter_points_by_radius(str(csv_path), CENTER_LAT, CENTER_LON, 0.0)


def test_error_bad_limit(tmp_path):
    csv_path = _write_csv(tmp_path / "pts.csv")
    with pytest.raises(ProximityError, match="limit"):
        filter_points_by_radius(str(csv_path), CENTER_LAT, CENTER_LON, 10.0, limit=0)


def test_error_undetectable_columns(tmp_path):
    path = tmp_path / "pts.csv"
    path.write_text("name,foo,bar\nnear,1,2\n", encoding="utf-8")
    with pytest.raises(ProximityError, match="auto-detect"):
        filter_points_by_radius(str(path), CENTER_LAT, CENTER_LON, 10.0)


def test_error_explicit_column_missing(tmp_path):
    csv_path = _write_csv(tmp_path / "pts.csv")
    with pytest.raises(ProximityError, match="not found"):
        filter_points_by_radius(str(csv_path), CENTER_LAT, CENTER_LON, 10.0, lat_column="nope")


def test_error_empty_file(tmp_path):
    path = tmp_path / "empty.csv"
    path.write_text("   \n", encoding="utf-8")
    with pytest.raises(ProximityError, match="empty"):
        filter_points_by_radius(str(path), CENTER_LAT, CENTER_LON, 10.0)


def test_error_geojson_no_points(tmp_path):
    path = tmp_path / "pts.geojson"
    path.write_text(json.dumps({"type": "FeatureCollection", "features": []}), encoding="utf-8")
    with pytest.raises(ProximityError, match="no usable Point"):
        filter_points_by_radius(str(path), CENTER_LAT, CENTER_LON, 10.0)


# --------------------------------------------------------------------------- #
# in-memory MCP tool surface
# --------------------------------------------------------------------------- #


@pytest.mark.asyncio
async def test_tool_registered():
    async with Client(mcp) as client:
        tools = {t.name for t in await client.list_tools()}
    assert "filter_points_by_radius" in tools


@pytest.mark.asyncio
async def test_tool_runs_in_memory(tmp_path):
    csv_path = _write_csv(tmp_path / "pts.csv")
    async with Client(mcp) as client:
        result = await client.call_tool(
            "filter_points_by_radius",
            {
                "data_path": str(csv_path),
                "center_lat": CENTER_LAT,
                "center_lon": CENTER_LON,
                "radius_km": 25.0,
            },
        )
    assert result.data["ok"] is True
    assert [p["name"] for p in result.data["points"]] == ["near", "mid", "far_in"]


@pytest.mark.asyncio
async def test_tool_raises_toolerror(tmp_path):
    async with Client(mcp) as client:
        with pytest.raises(ToolError):
            await client.call_tool(
                "filter_points_by_radius",
                {
                    "data_path": "/no/such/file.csv",
                    "center_lat": CENTER_LAT,
                    "center_lon": CENTER_LON,
                    "radius_km": 25.0,
                },
            )
