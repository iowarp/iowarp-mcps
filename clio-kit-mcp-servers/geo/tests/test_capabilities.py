"""Smoke tests that the MCP server exposes the expected tool surface."""

import pytest
from fastmcp import Client
from geo_mcp.server import mcp


@pytest.mark.asyncio
async def test_render_tool_registered() -> None:
    async with Client(mcp) as client:
        tools = {t.name for t in await client.list_tools()}
    assert "render_feature_map" in tools


@pytest.mark.asyncio
async def test_render_tool_runs_in_memory(tmp_path) -> None:
    poly = {
        "type": "Polygon",
        "coordinates": [[[-118.5, 34.0], [-118.0, 34.0], [-118.0, 34.5], [-118.5, 34.0]]],
    }
    out = tmp_path / "tool.png"
    async with Client(mcp) as client:
        result = await client.call_tool(
            "render_feature_map",
            {
                "layers": [{"geojson": poly, "style": {"facecolor": "red"}}],
                "output_path": str(out),
                "basemap": False,
            },
        )
    assert out.is_file() and out.stat().st_size > 0
    assert result.data["status"] == "success"
