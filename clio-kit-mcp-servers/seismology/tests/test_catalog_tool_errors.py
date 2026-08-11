"""The ported catalog tools must surface failures as ToolError, not raw exceptions.

An MCP tool that lets a domain exception escape gives the agent a stack trace
instead of something it can act on, so both paths are pinned here: a catalog
problem the implementation recognises, and an unexpected failure underneath it.
"""

from __future__ import annotations

from unittest.mock import patch

import pytest
from fastmcp.exceptions import ToolError
from seismology_mcp import server

PORTED_TOOLS = (
    ("analyze_sequence_tool", "analyze_sequence", "Could not analyze sequence"),
    ("plot_sequence_tool", "plot_sequence", "Could not plot sequence"),
)


@pytest.mark.asyncio
@pytest.mark.parametrize("tool_name,_impl,_prefix", PORTED_TOOLS)
async def test_unreadable_catalog_becomes_a_tool_error(
    tool_name: str, _impl: str, _prefix: str, tmp_path
) -> None:
    """A CatalogError from the implementation reaches the agent as ToolError."""
    tool = getattr(server, tool_name)

    with pytest.raises(ToolError):
        await tool(catalog_path=str(tmp_path / "absent.geojson"))


@pytest.mark.asyncio
@pytest.mark.parametrize("tool_name,impl,prefix", PORTED_TOOLS)
async def test_unexpected_failure_is_wrapped_with_context(
    tool_name: str, impl: str, prefix: str
) -> None:
    """An unexpected exception is labelled rather than leaking bare."""
    tool = getattr(server, tool_name)

    with patch.object(server, impl, side_effect=RuntimeError("disk exploded")):
        with pytest.raises(ToolError, match=prefix):
            await tool(catalog_path="anything")
