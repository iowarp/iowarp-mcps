"""The ported GeoJSON tools must surface failures as ToolError, not raw exceptions.

An MCP tool that lets a domain exception escape gives the agent a stack trace
instead of something it can act on, so both paths are pinned here: a GeoJSON
problem the implementation recognises, and an unexpected failure underneath it.
"""

from __future__ import annotations

from unittest.mock import patch

import pytest
from fastmcp.exceptions import ToolError
from geo_mcp import server

PORTED_TOOLS = (
    ("inspect_geojson_tool", "inspect_geojson", "GeoJSON inspection failed"),
    ("validate_geojson_tool", "validate_geojson", "GeoJSON validation failed"),
    ("summarize_geojson_tool", "summarize_geojson", "GeoJSON summary failed"),
    ("feature_bbox_tool", "feature_bbox", "GeoJSON bounding box failed"),
)


@pytest.mark.asyncio
@pytest.mark.parametrize("tool_name,_impl,_prefix", PORTED_TOOLS)
async def test_unreadable_source_becomes_a_tool_error(
    tool_name: str, _impl: str, _prefix: str, tmp_path
) -> None:
    """A GeoJSONError from the implementation reaches the agent as ToolError."""
    tool = getattr(server, tool_name)

    with pytest.raises(ToolError):
        await tool(source=str(tmp_path / "absent.geojson"))


@pytest.mark.asyncio
@pytest.mark.parametrize("tool_name,impl,prefix", PORTED_TOOLS)
async def test_unexpected_failure_is_wrapped_with_context(
    tool_name: str, impl: str, prefix: str
) -> None:
    """An unexpected exception is labelled rather than leaking bare."""
    tool = getattr(server, tool_name)

    with patch.object(server, impl, side_effect=RuntimeError("disk exploded")):
        with pytest.raises(ToolError, match=prefix):
            await tool(source="anything")
