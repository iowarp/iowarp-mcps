"""MCP-level tests for the GeoJSON document tools ported from the geojson server.

Also pins the distinction between the two bounding-box tools, which is the one
thing an agent could plausibly get wrong now that both live on the same server.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from fastmcp import Client
from geo_mcp.server import mcp

PORTED_TOOLS = {
    "inspect_geojson",
    "validate_geojson",
    "summarize_geojson",
    "feature_bbox",
}


@pytest.mark.asyncio
async def test_ported_geojson_tools_are_registered() -> None:
    """Every tool the geojson server exposed still exists, under its old name."""
    async with Client(mcp) as client:
        tools = {t.name for t in await client.list_tools()}
    assert PORTED_TOOLS <= tools


@pytest.mark.asyncio
async def test_inspect_tool_runs(collection_file: Path) -> None:
    async with Client(mcp) as client:
        result = await client.call_tool("inspect_geojson", {"source": str(collection_file)})
    data = result.data
    assert data["feature_count"] == 3
    assert data["geometry_types"] == {"Point": 1, "LineString": 1, "Polygon": 1}
    assert data["bbox"] == [-118.5, 34.0, -117.5, 35.0]


@pytest.mark.asyncio
async def test_validate_tool_runs(collection_file: Path) -> None:
    async with Client(mcp) as client:
        result = await client.call_tool("validate_geojson", {"source": str(collection_file)})
    assert result.data["valid"] is True
    assert result.data["errors"] == []


@pytest.mark.asyncio
async def test_summarize_tool_runs(collection_file: Path) -> None:
    async with Client(mcp) as client:
        result = await client.call_tool("summarize_geojson", {"source": str(collection_file)})
    assert result.data["feature_count"] == 3


@pytest.mark.asyncio
async def test_feature_bbox_tool_runs(collection_file: Path) -> None:
    async with Client(mcp) as client:
        result = await client.call_tool("feature_bbox", {"source": str(collection_file)})
    assert result.data["bbox"] == [-118.5, 34.0, -117.5, 35.0]
    assert result.data["feature_count"] == 3


@pytest.mark.asyncio
async def test_the_two_bbox_tools_answer_different_questions() -> None:
    """feature_bbox reports the document; bounding_box reports valid geometry.

    They are not duplicates: given a feature whose geometry a geometry engine
    rejects, feature_bbox still counts it and includes its coordinates, while
    bounding_box skips it. Each tool's description must point at the other so an
    agent picks deliberately rather than by coin flip.
    """
    async with Client(mcp) as client:
        tools = {t.name: t for t in await client.list_tools()}

    assert "feature_bbox" in tools["bounding_box"].description
    assert "bounding_box" in tools["feature_bbox"].description
    assert tools["bounding_box"].title != tools["feature_bbox"].title
