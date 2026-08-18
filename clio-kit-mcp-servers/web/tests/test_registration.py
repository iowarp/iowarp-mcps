"""The server registers a resource and a prompt (FastMCP 3.0 compliance + discovery)."""

from __future__ import annotations

import json

import pytest
from fastmcp import Client
from mcp.types import TextResourceContents

from web_mcp.server import Settings, create_mcp, mcp


@pytest.mark.asyncio
async def test_resource_and_prompt_are_registered() -> None:
    """web://capabilities resource and the research_web prompt are exposed."""
    async with Client(mcp) as client:
        resources = await client.list_resources()
        prompts = await client.list_prompts()
    assert any(str(r.uri) == "web://capabilities" for r in resources)
    assert any(p.name == "research_web" for p in prompts)


@pytest.mark.asyncio
async def test_capabilities_resource_reports_only_active_backend() -> None:
    """Discovery describes this installation rather than alternate providers."""
    async with Client(mcp) as client:
        result = await client.read_resource("web://capabilities")
    contents = result[0]
    assert isinstance(contents, TextResourceContents)
    payload = json.loads(contents.text)
    assert payload["active_provider"] == "ddg"  # keyless default
    assert payload["search_parameters"] == ["query", "count"]
    assert "available_providers" not in payload


@pytest.mark.asyncio
async def test_capabilities_resource_reports_configured_searxng() -> None:
    """Discovery reports SearXNG selectors without exposing its deployment URL."""
    searxng_mcp = create_mcp(
        Settings(
            search_provider="searxng",
            searxng_base_url="http://10.0.0.102:8088",
        ),
    )
    async with Client(searxng_mcp) as client:
        result = await client.read_resource("web://capabilities")
    contents = result[0]
    assert isinstance(contents, TextResourceContents)
    payload = json.loads(contents.text)
    assert payload["active_provider"] == "searxng"
    assert "pageno" in payload["search_parameters"]
    assert "10.0.0.102" not in contents.text
