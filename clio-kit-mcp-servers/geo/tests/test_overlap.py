"""Unit tests for the geo points_in_polygons spatial-overlap tool."""

from __future__ import annotations

from geo_mcp.implementation import points_in_polygons

POLY = {
    "type": "FeatureCollection",
    "features": [
        {
            "type": "Feature",
            "properties": {"smoke": "3-25"},
            "geometry": {
                "type": "Polygon",
                "coordinates": [
                    [[-118.5, 34.0], [-118.0, 34.0], [-118.0, 34.5], [-118.5, 34.5], [-118.5, 34.0]]
                ],
            },
        }
    ],
}


def _pt(lon, lat, **props):
    return {
        "type": "Feature",
        "properties": props,
        "geometry": {"type": "Point", "coordinates": [lon, lat]},
    }


def test_matches_only_points_inside():
    pts = {
        "type": "FeatureCollection",
        "features": [
            _pt(-118.2, 34.2, AQI=168, name="in"),
            _pt(-117.0, 33.0, AQI=20, name="out"),
        ],
    }
    r = points_in_polygons(pts, POLY, point_label_fields=["AQI", "name"])
    assert r["matched_count"] == 1
    assert r["matched"][0]["properties"] == {"AQI": 168, "name": "in"}


def test_buffer_includes_near_points():
    near = {
        "type": "FeatureCollection",
        "features": [_pt(-117.95, 34.2, name="near")],
    }  # ~4-5km east of edge
    assert points_in_polygons(near, POLY)["matched_count"] == 0
    assert points_in_polygons(near, POLY, buffer_km=15)["matched_count"] == 1


def test_empty_inputs():
    assert (
        points_in_polygons({"type": "FeatureCollection", "features": []}, POLY)["matched_count"]
        == 0
    )
    assert (
        points_in_polygons(
            {"type": "FeatureCollection", "features": [_pt(-118.2, 34.2)]},
            {"type": "FeatureCollection", "features": []},
        )["matched_count"]
        == 0
    )


def test_accepts_path(tmp_path):
    import json

    pp = tmp_path / "pts.geojson"
    pp.write_text(
        json.dumps({"type": "FeatureCollection", "features": [_pt(-118.2, 34.2, name="in")]})
    )
    gp = tmp_path / "poly.geojson"
    gp.write_text(json.dumps(POLY))
    r = points_in_polygons(str(pp), str(gp))
    assert r["matched_count"] == 1
