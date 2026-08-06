"""Every tool the geo MCP server registers must carry a compact display title.

The consuming UI reads `Tool.title` (falling back to `annotations.title`, then
`name`) to render a small-title register — e.g. `geocode(place)`. This asserts
every tool advertises one, and that it fits the compact register's length budget.
"""

import pytest
from fastmcp import Client
from geo_mcp.server import mcp

MAX_TITLE_LENGTH = 24


@pytest.mark.asyncio
async def test_every_tool_has_a_title() -> None:
    async with Client(mcp) as client:
        tools = await client.list_tools()

    assert tools, "expected at least one registered tool"
    missing = [t.name for t in tools if not t.title]
    assert not missing, f"tools missing a title: {missing}"


@pytest.mark.asyncio
async def test_titles_fit_the_compact_register() -> None:
    async with Client(mcp) as client:
        tools = await client.list_tools()

    too_long = {t.name: t.title for t in tools if t.title and len(t.title) > MAX_TITLE_LENGTH}
    assert not too_long, f"titles exceed {MAX_TITLE_LENGTH} chars: {too_long}"
