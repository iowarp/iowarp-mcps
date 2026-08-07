"""Every tool the geo MCP server registers must carry a compact display title.

The consuming UI reads `Tool.title` (falling back to `annotations.title`, then
`name`) to render a compact register of plain Title Case names — e.g. `Geocode`.
Parens are injected by the UI around the call's arguments, not part of the
title. This asserts every tool advertises one, and that it fits the compact
register's length budget.
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


@pytest.mark.asyncio
async def test_titles_have_no_parentheses() -> None:
    """Titles are plain Title Case names; parens are a UI-injected call-arg
    decoration, not part of the tool's display title (2.7.1 rename)."""
    async with Client(mcp) as client:
        tools = await client.list_tools()

    with_parens = [tool.name for tool in tools if tool.title and "(" in tool.title]
    assert not with_parens, f"Tools with parens in title: {with_parens}"
