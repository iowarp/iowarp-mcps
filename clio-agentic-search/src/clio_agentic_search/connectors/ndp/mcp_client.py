"""NDP-MCP client: CLIO talks to the NDP MCP server as an MCP client.

This is how CLIO integrates with the NDP-MCP server from clio-kit:
  - CLIO spawns ndp-mcp as a subprocess (stdio transport)
  - CLIO calls its tools via the MCP protocol (list_tools, call_tool)
  - CLIO processes the results through its own pipeline (profile, index, search)

This is the "correct" architecture: CLIO is the agentic layer that USES MCPs.
"""

from __future__ import annotations

import json
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


class NDPMCPClient:
    """MCP client that talks to the NDP-MCP server via stdio."""

    def __init__(self, ndp_mcp_binary: str = "ndp-mcp"):
        self.binary = ndp_mcp_binary
        self._session: ClientSession | None = None
        self._context = None

    @asynccontextmanager
    async def connect(self) -> AsyncIterator[NDPMCPClient]:
        """Connect to NDP-MCP server as a subprocess."""
        params = StdioServerParameters(
            command=self.binary,
            args=["--transport", "stdio"],
        )
        async with stdio_client(params) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                self._session = session
                try:
                    yield self
                finally:
                    self._session = None

    async def list_tools(self) -> list[str]:
        """List tools exposed by NDP-MCP."""
        if self._session is None:
            raise RuntimeError("Not connected")
        result = await self._session.list_tools()
        return [t.name for t in result.tools]

    async def search_datasets(
        self,
        search_terms: list[str],
        server: str = "global",
        limit: int = 20,
    ) -> list[dict[str, Any]]:
        """Call NDP-MCP's search_datasets tool."""
        if self._session is None:
            raise RuntimeError("Not connected")

        all_datasets: list[dict[str, Any]] = []
        seen_ids: set[str] = set()

        for term in search_terms:
            try:
                result = await self._session.call_tool(
                    "search_datasets",
                    arguments={
                        "search_terms": [term],
                        "server": server,
                        "limit": str(limit),
                    },
                )
                # result.content is a list of content blocks
                for block in result.content:
                    if hasattr(block, "text"):
                        try:
                            data = json.loads(block.text)
                            if isinstance(data, dict) and "datasets" in data:
                                for ds in data["datasets"]:
                                    if ds.get("id") not in seen_ids:
                                        all_datasets.append(ds)
                                        seen_ids.add(ds.get("id"))
                        except (json.JSONDecodeError, KeyError):
                            pass
            except Exception:
                pass

        return all_datasets

    async def list_organizations(self, server: str = "global") -> list[str]:
        """Call NDP-MCP's list_organizations tool."""
        if self._session is None:
            raise RuntimeError("Not connected")
        result = await self._session.call_tool("list_organizations", arguments={"server": server})
        for block in result.content:
            if hasattr(block, "text"):
                try:
                    data = json.loads(block.text)
                    if isinstance(data, dict) and "organizations" in data:
                        return data["organizations"]
                except json.JSONDecodeError:
                    pass
        return []
