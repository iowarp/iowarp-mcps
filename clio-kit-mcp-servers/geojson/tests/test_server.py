"""MCP-level tests: the geojson server exposes its tools and runs in-memory."""

from __future__ import annotations

from pathlib import Path

import pytest
from fastmcp import Client
from fastmcp.exceptions import ToolError
from geojson_mcp.server import mcp

EXPECTED_TOOLS = {
    "inspect_geojson",
    "validate_geojson",
    "summarize_geojson",
    "feature_bbox",
}


@pytest.mark.asyncio
async def test_all_tools_registered() -> None:
    async with Client(mcp) as client:
        tools = {t.name for t in await client.list_tools()}
    assert EXPECTED_TOOLS <= tools


@pytest.mark.asyncio
async def test_tools_have_annotations_and_tags() -> None:
    # The server-side Tool objects carry annotations and tags directly.
    tools = await mcp.list_tools()
    for tool in tools:
        assert tool.annotations is not None, tool.name
        assert tool.tags, tool.name


@pytest.mark.asyncio
async def test_inspect_tool_runs(collection_file: Path) -> None:
    async with Client(mcp) as client:
        result = await client.call_tool("inspect_geojson", {"source": str(collection_file)})
    data = result.data
    assert data["feature_count"] == 3
    assert data["geometry_types"] == {"Point": 1, "LineString": 1, "Polygon": 1}
    assert data["bbox"] == [-118.5, 34.0, -117.5, 35.0]


@pytest.mark.asyncio
async def test_validate_tool_ok(point_file: Path) -> None:
    async with Client(mcp) as client:
        result = await client.call_tool("validate_geojson", {"source": str(point_file)})
    assert result.data == {"valid": True, "errors": []}


@pytest.mark.asyncio
async def test_validate_tool_malformed(malformed_file: Path) -> None:
    async with Client(mcp) as client:
        result = await client.call_tool("validate_geojson", {"source": str(malformed_file)})
    assert result.data["valid"] is False
    assert result.data["errors"]


@pytest.mark.asyncio
async def test_summarize_tool_runs(collection_file: Path) -> None:
    async with Client(mcp) as client:
        result = await client.call_tool("summarize_geojson", {"source": str(collection_file)})
    assert "3 feature(s)" in result.data["summary"]


@pytest.mark.asyncio
async def test_feature_bbox_tool_runs(polygon_file: Path) -> None:
    async with Client(mcp) as client:
        result = await client.call_tool("feature_bbox", {"source": str(polygon_file)})
    assert result.data["bbox"] == [-118.5, 34.0, -118.0, 34.5]
    assert result.data["feature_count"] == 1


@pytest.mark.asyncio
async def test_inline_json_string(point_file: Path) -> None:
    inline = point_file.read_text(encoding="utf-8")
    async with Client(mcp) as client:
        result = await client.call_tool("inspect_geojson", {"source": inline})
    assert result.data["feature_count"] == 1


@pytest.mark.asyncio
async def test_missing_file_raises_tool_error() -> None:
    async with Client(mcp) as client:
        with pytest.raises(ToolError):
            await client.call_tool("inspect_geojson", {"source": "/no/such/file.geojson"})


@pytest.mark.asyncio
async def test_invalid_json_raises_tool_error(invalid_json_file: Path) -> None:
    async with Client(mcp) as client:
        with pytest.raises(ToolError):
            await client.call_tool("validate_geojson", {"source": str(invalid_json_file)})
