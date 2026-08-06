"""Every tool the pandas MCP server registers must carry a compact display title.

The consuming UI reads `Tool.title` (falling back to `annotations.title`, then
`name`) to render a small-title register — e.g. `filter(data)`. This asserts
every tool advertises one, and that it fits the compact register's length budget.

Uses `asyncio.run` rather than `@pytest.mark.asyncio` / anyio markers: this
server's dev dependency group does not carry a pytest asyncio plugin (unlike
some sibling servers), and pytest silently skips async def tests it cannot
run rather than failing loudly, so a marker-based test could pass by doing
nothing. Driving the event loop explicitly keeps the assertion honest without
adding a new dev dependency just for this test.
"""

import asyncio

from fastmcp import Client
from pandas_mcp.server import mcp

MAX_TITLE_LENGTH = 24


def _list_tools():
    async def _run():
        async with Client(mcp) as client:
            return await client.list_tools()

    return asyncio.run(_run())


def test_every_tool_has_a_title() -> None:
    tools = _list_tools()
    assert tools, "expected at least one registered tool"
    missing = [t.name for t in tools if not t.title]
    assert not missing, f"tools missing a title: {missing}"


def test_titles_fit_the_compact_register() -> None:
    tools = _list_tools()
    too_long = {
        t.name: t.title for t in tools if t.title and len(t.title) > MAX_TITLE_LENGTH
    }
    assert not too_long, f"titles exceed {MAX_TITLE_LENGTH} chars: {too_long}"
