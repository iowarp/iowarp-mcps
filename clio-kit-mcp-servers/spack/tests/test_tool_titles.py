"""Every spack tool exposes a short, human-readable title on the wire.

FastMCP's ``Tool.title`` is what the consuming UI reads first (falling back to
``annotations.title`` then ``name``), so every ``@mcp.tool(...)`` must set one
explicitly. This checks the full ``mcp`` instance before any per-profile
filtering (``apply_tool_profile``) removes the admin-only tool.
"""

from __future__ import annotations

import pytest
from fastmcp import Client

from spack_mcp.server import mcp

EXPECTED_TOOLS = {
    "spack_find",
    "spack_locate",
    "spack_search",
    "spack_info",
    "spack_install",
    "spack_environment",
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


@pytest.mark.asyncio
async def test_titles_have_no_parentheses() -> None:
    """Titles are plain Title Case names; parens are a UI-injected call-arg
    decoration, not part of the tool's display title (2.7.1 rename)."""
    async with Client(mcp) as client:
        tools = await client.list_tools()

    with_parens = [tool.name for tool in tools if tool.title and "(" in tool.title]
    assert not with_parens, f"Tools with parens in title: {with_parens}"
