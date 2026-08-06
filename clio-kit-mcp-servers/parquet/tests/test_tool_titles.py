"""Every parquet tool exposes a short, human-readable title on the wire.

FastMCP's ``Tool.title`` is what the consuming UI reads first (falling back to
``annotations.title`` then ``name``), so every ``@mcp.tool(...)`` must set one
explicitly.
"""

from __future__ import annotations

import pytest
from fastmcp import Client
from parquet_mcp.server import mcp

EXPECTED_TOOLS = {
    "summarize_tool",
    "read_slice_tool",
    "get_column_preview_tool",
    "aggregate_column_tool",
}


@pytest.mark.asyncio
async def test_every_tool_has_a_short_title() -> None:
    async with Client(mcp) as client:
        tools = await client.list_tools()
    names = {tool.name for tool in tools}
    assert EXPECTED_TOOLS <= names
    for tool in tools:
        assert tool.title, f"{tool.name} is missing a title"
        assert len(tool.title) <= 24, f"{tool.name} title too long: {tool.title!r}"
