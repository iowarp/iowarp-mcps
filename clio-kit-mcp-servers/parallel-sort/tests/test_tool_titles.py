"""Tests asserting every Parallel Sort MCP tool exposes a compact, non-empty title.

Titles populate `Tool.title` on the wire, which UI surfaces read first (falling
back to `annotations.title`, then `name`). See `@mcp.tool(..., title=...)` in
`parallel_sort_mcp/server.py`.
"""

import pytest
from fastmcp import Client

from parallel_sort_mcp.server import mcp

MAX_TITLE_LENGTH = 24


@pytest.mark.asyncio
async def test_all_tools_have_non_empty_titles() -> None:
    """Every registered tool must expose a short, non-empty title."""
    async with Client(mcp) as client:
        tools = await client.list_tools()

    assert tools, "expected at least one tool to be registered"

    missing_titles = []
    too_long = []
    for tool in tools:
        if not tool.title:
            missing_titles.append(tool.name)
        elif len(tool.title) > MAX_TITLE_LENGTH:
            too_long.append((tool.name, tool.title))

    assert not missing_titles, f"tools missing a title: {missing_titles}"
    assert not too_long, f"tools with title over {MAX_TITLE_LENGTH} chars: {too_long}"


@pytest.mark.asyncio
async def test_expected_tool_count_has_titles() -> None:
    """The full curated set of 13 Parallel Sort tools should all carry titles."""
    async with Client(mcp) as client:
        tools = await client.list_tools()

    titled = {t.name: t.title for t in tools if t.title}
    assert len(titled) == len(tools) == 13
