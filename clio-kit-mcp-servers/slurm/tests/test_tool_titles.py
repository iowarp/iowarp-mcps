"""Verify every Slurm MCP tool declares a compact, wire-visible title.

The consuming UI reads ``Tool.title`` first (falling back to
``annotations.title`` then ``name``), so every tool registered on the server
— both the compact user-facing surface and the legacy granular surface —
must set a non-empty, short ``title`` via the ``@mcp.tool(...)`` decorator.
"""

import importlib

import pytest
from fastmcp import Client
from slurm_mcp import server as slurm_server

EXPECTED_TOOL_COUNT = 18
MAX_TITLE_LENGTH = 24


@pytest.fixture
def mcp():
    """Reload the server module for a pristine, unfiltered tool registry.

    Other tests in this suite (``test_server_tools.py``) call ``server.main()``
    repeatedly with only ``mcp.run`` mocked, so ``apply_tool_profile`` runs for
    real and permanently strips the legacy tool surface from the shared
    ``slurm_mcp.server.mcp`` singleton for the remainder of the test session.
    Reloading gives this test its own clean FastMCP instance with the full
    18-tool registry, independent of prior test execution order.
    """
    importlib.reload(slurm_server)
    return slurm_server.mcp


@pytest.mark.asyncio
async def test_all_tools_have_titles(mcp) -> None:
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
async def test_titles_are_distinct_within_server(mcp) -> None:
    """Curated and legacy tools cover overlapping verbs/objects; titles must
    still be non-redundant within this one server file."""
    async with Client(mcp) as client:
        tools = await client.list_tools()

    titles = [tool.title for tool in tools]
    assert len(titles) == len(set(titles)), "Duplicate titles found within slurm server"


@pytest.mark.asyncio
async def test_titles_have_no_parentheses(mcp) -> None:
    """Titles are plain Title Case names; parens are a UI-injected call-arg
    decoration, not part of the tool's display title (2.7.1 rename)."""
    async with Client(mcp) as client:
        tools = await client.list_tools()

    with_parens = [tool.name for tool in tools if tool.title and "(" in tool.title]
    assert not with_parens, f"Tools with parens in title: {with_parens}"
