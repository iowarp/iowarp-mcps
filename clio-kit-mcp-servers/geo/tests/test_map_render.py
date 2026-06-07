"""Unit tests for geo map rendering.

These exercise the rendering state space: geometry coercion across GeoJSON
shapes, polygon/point/line layers, fixed and data-driven coloring, the EPA AQI
scale, bbox windows, malformed inputs, and on-disk output. Basemap tiles are
disabled so tests do not require network access.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from geo_mcp.implementation import MapRenderError, render_map

POLY = {
    "type": "Polygon",
    "coordinates": [
        [[-118.5, 34.0], [-118.0, 34.0], [-118.0, 34.5], [-118.5, 34.5], [-118.5, 34.0]]
    ],
}
POINT = {"type": "Point", "coordinates": [-118.25, 34.05]}


def _fc(*features: dict) -> dict:
    return {"type": "FeatureCollection", "features": list(features)}


def _feat(geom: dict, **props: object) -> dict:
    return {"type": "Feature", "geometry": geom, "properties": props}


def test_renders_polygon_layer(tmp_path: Path) -> None:
    out = tmp_path / "poly.png"
    res = render_map(
        [{"name": "region", "geojson": _fc(_feat(POLY)), "style": {"facecolor": "red"}}],
        str(out),
        basemap=False,
    )
    assert res["status"] == "success"
    assert out.is_file() and out.stat().st_size > 0
    assert res["layers"][0]["features"] == 1
    assert res["bounds"]["min_lon"] == pytest.approx(-118.5)


def test_renders_multiple_layers_and_points(tmp_path: Path) -> None:
    out = tmp_path / "multi.png"
    res = render_map(
        [
            {"name": "perimeter", "geojson": POLY, "style": {"facecolor": "red", "alpha": 0.5}},
            {
                "name": "stations",
                "geojson": _fc(
                    _feat(POINT), _feat({"type": "Point", "coordinates": [-118.1, 34.2]})
                ),
                "style": {"color": "blue", "markersize": 30},
            },
        ],
        str(out),
        basemap=False,
        title="Two layers",
    )
    assert res["layers"][0]["features"] == 1
    assert res["layers"][1]["features"] == 2
    assert out.stat().st_size > 0


def test_epa_aqi_scale_colors_points(tmp_path: Path) -> None:
    out = tmp_path / "aqi.png"
    feats = _fc(
        _feat({"type": "Point", "coordinates": [-118.2, 34.0]}, AQI=20),
        _feat({"type": "Point", "coordinates": [-118.1, 34.1]}, AQI=120),
        _feat({"type": "Point", "coordinates": [-118.0, 34.2]}, AQI=260),
        _feat({"type": "Point", "coordinates": [-117.9, 34.3]}, AQI=None),
    )
    res = render_map(
        [{"name": "air", "geojson": feats, "style": {"color_by": "AQI", "scale": "epa_aqi"}}],
        str(out),
        basemap=False,
    )
    assert res["layers"][0]["features"] == 4
    assert out.stat().st_size > 0


def test_category_colors(tmp_path: Path) -> None:
    out = tmp_path / "cat.png"
    feats = _fc(
        _feat(POLY, klass="3 - 25"),
        _feat(
            {
                "type": "Polygon",
                "coordinates": [[[-117.9, 34.0], [-117.5, 34.0], [-117.5, 34.4], [-117.9, 34.0]]],
            },
            klass="25 - 50",
        ),
    )
    res = render_map(
        [
            {
                "name": "smoke",
                "geojson": feats,
                "style": {
                    "color_by": "klass",
                    "category_colors": {"3 - 25": "#cccccc", "25 - 50": "#888888"},
                },
            }
        ],
        str(out),
        basemap=False,
    )
    assert res["layers"][0]["features"] == 2


def test_accepts_json_string_and_path(tmp_path: Path) -> None:
    out = tmp_path / "fromstr.png"
    res = render_map([{"geojson": json.dumps(POLY)}], str(out), basemap=False)
    assert res["status"] == "success"

    gj_path = tmp_path / "layer.geojson"
    gj_path.write_text(json.dumps(_fc(_feat(POINT))), encoding="utf-8")
    out2 = tmp_path / "frompath.png"
    res2 = render_map(
        [{"geojson": str(gj_path), "style": {"color": "green"}}], str(out2), basemap=False
    )
    assert res2["layers"][0]["features"] == 1


def test_bbox_window(tmp_path: Path) -> None:
    out = tmp_path / "bbox.png"
    res = render_map(
        [{"geojson": POLY, "style": {"facecolor": "orange"}}],
        str(out),
        basemap=False,
        bbox=[-119.0, 33.5, -117.5, 35.0],
    )
    assert res["status"] == "success"


def test_empty_layers_raises() -> None:
    with pytest.raises(MapRenderError):
        render_map([], "x.png", basemap=False)


def test_no_geometry_raises(tmp_path: Path) -> None:
    with pytest.raises(MapRenderError):
        render_map([{"geojson": _fc()}], str(tmp_path / "e.png"), basemap=False)


def test_bad_json_string_raises(tmp_path: Path) -> None:
    with pytest.raises(MapRenderError):
        render_map([{"geojson": "{not json"}], str(tmp_path / "e.png"), basemap=False)


def test_missing_path_raises(tmp_path: Path) -> None:
    with pytest.raises(MapRenderError):
        render_map(
            [{"geojson": str(tmp_path / "nope.geojson")}], str(tmp_path / "e.png"), basemap=False
        )


def test_bad_bbox_raises(tmp_path: Path) -> None:
    with pytest.raises(MapRenderError):
        render_map([{"geojson": POLY}], str(tmp_path / "e.png"), basemap=False, bbox=[1, 2, 3])


def test_creates_parent_dirs(tmp_path: Path) -> None:
    out = tmp_path / "nested" / "deep" / "map.png"
    res = render_map([{"geojson": POLY}], str(out), basemap=False)
    assert Path(res["output_path"]).is_file()
