"""Every tool exposed by the server must carry a short, compact ``title``."""

import pytest
from fastmcp import Client

from web_mcp.server import mcp


@pytest.mark.asyncio
async def test_all_tools_have_compact_titles() -> None:
    async with Client(mcp) as client:
        tools = await client.list_tools()

    assert len(tools) == 2
    for tool in tools:
        assert tool.title, f"{tool.name} is missing a title"
        assert len(tool.title) <= 24, f"{tool.name} title too long: {tool.title!r}"
