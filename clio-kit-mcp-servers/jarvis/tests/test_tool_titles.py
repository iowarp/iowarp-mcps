"""Every jarvis tool exposes a short, human-readable title on the wire.

FastMCP's ``Tool.title`` is what the consuming UI reads first (falling back to
``annotations.title`` then ``name``), so every ``@mcp.tool(...)`` must set one
explicitly. This server registers 36 tools across the legacy pipeline
surface, the package tools, the curated ``jarvis_*`` surface, and the
``jm_*`` JarvisManager surface -- this test just checks metadata, so it needs
no real Jarvis-CD/Spack backend to pass.

This module reloads ``jarvis_mcp.server`` to get a tool registry unaffected
by other tests. ``main()`` calls ``apply_tool_profile(profile)`` against the
real module-level ``mcp`` singleton, and several existing tests (e.g.
``test_server.py::TestMainFunction``, ``test_server_direct.py::
TestMainFunctionDirect``) call ``main()`` for real while only patching
``mcp.run`` -- ``apply_tool_profile`` still runs for real and permanently
removes the 30 ``ADMIN_TOOLS`` from the shared singleton for the rest of the
pytest session. Reloading (as ``spack_mcp``'s tests already do for the
analogous profile filtering) gives this test a clean, full 36-tool registry
regardless of test order, and leaves a fresh instance behind afterward.
"""

from __future__ import annotations

import importlib

import pytest
from fastmcp import Client

from jarvis_mcp import server

EXPECTED_TOOL_COUNT = 36


@pytest.mark.asyncio
async def test_every_tool_has_a_short_title() -> None:
    fresh_server = importlib.reload(server)
    try:
        async with Client(fresh_server.mcp) as client:
            tools = await client.list_tools()
        assert len(tools) == EXPECTED_TOOL_COUNT, sorted(tool.name for tool in tools)
        for tool in tools:
            assert tool.title, f"{tool.name} is missing a title"
            assert len(tool.title) <= 24, f"{tool.name} title too long: {tool.title!r}"
    finally:
        importlib.reload(server)
