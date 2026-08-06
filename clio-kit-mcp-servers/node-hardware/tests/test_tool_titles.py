"""Verify every Node Hardware MCP tool declares a compact, wire-visible title.

The consuming UI reads ``Tool.title`` first (falling back to
``annotations.title`` then ``name``), so every tool registered on the server
must set a non-empty, short ``title`` via the ``@mcp.tool(...)`` decorator.
"""

import pytest
from fastmcp import Client
from node_hardware_mcp.server import mcp

EXPECTED_TOOL_COUNT = 11
MAX_TITLE_LENGTH = 24


@pytest.mark.asyncio
async def test_all_tools_have_titles() -> None:
    async with Client(mcp) as client:
        tools = await client.list_tools()

    assert len(tools) == EXPECTED_TOOL_COUNT

    missing_titles = []
    too_long = []
    for tool in tools:
        if not tool.title:
            missing_titles.append(tool.name)
        elif len(tool.title) > MAX_TITLE_LENGTH:
            too_long.append((tool.name, tool.title))

    assert not missing_titles, f"Tools missing a title: {missing_titles}"
    assert not too_long, f"Tools with a title over {MAX_TITLE_LENGTH} chars: {too_long}"


@pytest.mark.asyncio
async def test_titles_are_distinct_within_server() -> None:
    async with Client(mcp) as client:
        tools = await client.list_tools()

    titles = [tool.title for tool in tools]
    assert len(titles) == len(set(titles)), (
        "Duplicate titles found within node-hardware server"
    )


@pytest.mark.asyncio
async def test_titles_have_no_parentheses() -> None:
    """Titles are plain Title Case names; parens are a UI-injected call-arg
    decoration, not part of the tool's display title (2.7.1 rename)."""
    async with Client(mcp) as client:
        tools = await client.list_tools()

    with_parens = [tool.name for tool in tools if tool.title and "(" in tool.title]
    assert not with_parens, f"Tools with parens in title: {with_parens}"
