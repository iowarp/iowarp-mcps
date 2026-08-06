"""Every tool exposed by the server must carry a short, compact ``title``."""

import pytest

try:
    from chronomcp.server import mcp

    HAS_DEPENDENCIES = True
except ImportError:
    HAS_DEPENDENCIES = False

pytestmark = pytest.mark.skipif(
    not HAS_DEPENDENCIES,
    reason="ChronoLog system dependencies not available",
)


@pytest.mark.asyncio
async def test_all_tools_have_compact_titles() -> None:
    from fastmcp import Client

    async with Client(mcp) as client:
        tools = await client.list_tools()

    assert len(tools) == 4
    for tool in tools:
        assert tool.title, f"{tool.name} is missing a title"
        assert len(tool.title) <= 24, f"{tool.name} title too long: {tool.title!r}"
