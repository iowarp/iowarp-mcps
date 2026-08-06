"""Verify geo tools declare real MCP output semantics (2026-07-28 protocol).

Every geo tool's registration must advertise a real, field-level
``outputSchema`` — not the generic ``{"type": "object",
"additionalProperties": true}`` a bare ``-> dict`` / ``-> dict[str, Any]``
return annotation would produce. These tests drive the server through an
in-memory ``fastmcp.Client``, so they exercise exactly what a real MCP client
sees on the wire, and spot-check that a couple of tools' actual
structured_content matches the advertised schema's field names.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from fastmcp import Client

from geo_mcp.server import mcp

ALL_TOOL_NAMES = {
    "render_feature_map",
    "points_in_polygons",
    "bounding_box",
    "query_arcgis_features",
    "geocode",
    "filter_points_by_radius",
}

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


def _pt(lon: float, lat: float, **props: object) -> dict:
    return {
        "type": "Feature",
        "properties": props,
        "geometry": {"type": "Point", "coordinates": [lon, lat]},
    }


@pytest.mark.asyncio
async def test_tools_list_advertises_real_output_schemas() -> None:
    """tools/list must show a field-level outputSchema for every geo tool."""
    async with Client(mcp) as client:
        tools = {tool.name: tool for tool in await client.list_tools()}

    missing = ALL_TOOL_NAMES - set(tools)
    assert not missing, f"tools missing from tools/list: {missing}"

    for name in ALL_TOOL_NAMES:
        schema = tools[name].output_schema
        assert schema is not None, f"{name} has no outputSchema"
        assert schema.get("type") == "object", f"{name} outputSchema is not an object"
        properties = schema.get("properties")
        assert properties, f"{name} outputSchema has no real field properties: {schema}"


@pytest.mark.asyncio
async def test_bounding_box_schema_covers_both_status_values() -> None:
    """bounding_box unifies the empty/success outcomes into one schema whose
    ``status`` property enumerates both values (no info lost by not using a
    discriminated union)."""
    async with Client(mcp) as client:
        tools = {tool.name: tool for tool in await client.list_tools()}

    status_schema = tools["bounding_box"].output_schema["properties"]["status"]
    assert set(status_schema.get("enum", [])) == {"success", "empty"}


@pytest.mark.asyncio
async def test_bounding_box_empty_result_matches_schema_fields() -> None:
    async with Client(mcp) as client:
        result = await client.call_tool(
            "bounding_box", {"geojson": {"type": "FeatureCollection", "features": []}}
        )
    structured = result.structured_content
    assert structured == {"status": "empty", "bbox": None, "feature_count": 0}


@pytest.mark.asyncio
async def test_bounding_box_success_result_matches_schema_fields() -> None:
    async with Client(mcp) as client:
        result = await client.call_tool("bounding_box", {"geojson": POLY})
    structured = result.structured_content
    assert structured is not None
    assert structured["status"] == "success"
    assert structured["feature_count"] == 1
    assert structured["bbox"] == [-118.5, 34.0, -118.0, 34.5]


@pytest.mark.asyncio
async def test_points_in_polygons_result_matches_schema_fields() -> None:
    points = {
        "type": "FeatureCollection",
        "features": [
            _pt(-118.2, 34.2, AQI=168, name="in"),
            _pt(-117.0, 33.0, AQI=20, name="out"),
        ],
    }
    async with Client(mcp) as client:
        result = await client.call_tool(
            "points_in_polygons",
            {
                "points_geojson": points,
                "polygons_geojson": POLY,
                "point_label_fields": ["AQI", "name"],
            },
        )
    structured = result.structured_content
    assert structured is not None
    assert structured["status"] == "success"
    assert structured["points_total"] == 2
    assert structured["matched_count"] == 1
    assert structured["matched"][0]["properties"] == {"AQI": 168, "name": "in"}


@pytest.mark.asyncio
async def test_filter_points_by_radius_result_matches_schema_fields(tmp_path: Path) -> None:
    csv_path = tmp_path / "points.csv"
    csv_path.write_text(
        "name,latitude,longitude\nnear,34.05,-118.25\nfar,0.0,0.0\n", encoding="utf-8"
    )
    async with Client(mcp) as client:
        result = await client.call_tool(
            "filter_points_by_radius",
            {
                "data_path": str(csv_path),
                "center_lat": 34.05,
                "center_lon": -118.25,
                "radius_km": 10,
            },
        )
    structured = result.structured_content
    assert structured is not None
    assert structured["ok"] is True
    assert structured["count"] == 1
    assert structured["source_format"] == "csv"
    assert structured["center"] == {"lat": 34.05, "lon": -118.25}
    assert structured["points"][0]["name"] == "near"
    assert "distance_km" in structured["points"][0]


@pytest.mark.asyncio
async def test_render_feature_map_result_matches_schema_fields(tmp_path: Path) -> None:
    out = tmp_path / "map.png"
    async with Client(mcp) as client:
        result = await client.call_tool(
            "render_feature_map",
            {
                "layers": [{"name": "region", "geojson": POLY, "style": {"facecolor": "red"}}],
                "output_path": str(out),
                "basemap": False,
            },
        )
    structured = result.structured_content
    assert structured is not None
    assert structured["status"] == "success"
    assert structured["basemap"] is False
    assert structured["layers"][0] == {"name": "region", "features": 1, "geometry": ["Polygon"]}
    assert out.is_file()


@pytest.mark.asyncio
async def test_render_feature_map_skipped_layer_matches_schema_fields(tmp_path: Path) -> None:
    """A layer with no usable geometries carries ``skipped`` instead of
    ``geometry`` — both are modeled as optional fields on one TypedDict."""
    out = tmp_path / "map.png"
    async with Client(mcp) as client:
        result = await client.call_tool(
            "render_feature_map",
            {
                "layers": [
                    {"name": "empty", "geojson": {"type": "FeatureCollection", "features": []}},
                    {"name": "region", "geojson": POLY, "style": {"facecolor": "red"}},
                ],
                "output_path": str(out),
                "basemap": False,
            },
        )
    structured = result.structured_content
    assert structured is not None
    assert structured["layers"][0] == {"name": "empty", "features": 0, "skipped": "no features"}
    assert structured["layers"][1] == {"name": "region", "features": 1, "geometry": ["Polygon"]}
