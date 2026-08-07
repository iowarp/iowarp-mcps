"""Every tool exposed by the server must carry a short, compact ``title``.

NOTE: unlike the other test modules in this directory, this one DOES import
``hdf5_mcp.server`` (needed to reach the ``mcp`` instance). A prior hang here
was traced to a module-level ``ThreadPoolExecutor`` plus lifespan file
discovery; both were verified interactively (``uv run python -c ...``) to
complete quickly and shut down cleanly before this test was added.
"""

import pytest
from fastmcp import Client

from hdf5_mcp.server import mcp


@pytest.mark.asyncio
async def test_all_tools_have_compact_titles() -> None:
    async with Client(mcp) as client:
        tools = await client.list_tools()

    assert len(tools) == 27
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
