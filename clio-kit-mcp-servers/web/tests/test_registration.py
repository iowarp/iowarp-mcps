"""The server registers a resource and a prompt (FastMCP 3.0 compliance + discovery)."""

from __future__ import annotations

import json

import pytest
from fastmcp import Client

from web_mcp import server
from web_mcp.server import Settings, mcp


@pytest.mark.asyncio
async def test_resource_and_prompt_are_registered() -> None:
    """web://providers resource and the research_web prompt are exposed."""
    async with Client(mcp) as client:
        resources = await client.list_resources()
        prompts = await client.list_prompts()
    assert any(str(r.uri) == "web://providers" for r in resources)
    assert any(p.name == "research_web" for p in prompts)


@pytest.mark.asyncio
async def test_providers_resource_reports_active_backend() -> None:
    """Reading web://providers returns the active + available search providers."""
    async with Client(mcp) as client:
        result = await client.read_resource("web://providers")
    payload = json.loads(result[0].text)  # resource contents expose .text (JSON)
    assert payload["active_provider"] == "ddg"  # keyless default
    assert "brave" in payload["available_providers"] and "tavily" in payload["available_providers"]
    assert "searxng" in payload["available_providers"]
    assert payload["searxng_configured"] is False


@pytest.mark.asyncio
async def test_providers_resource_reports_configured_searxng(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Discovery reports SearXNG readiness without exposing its deployment URL."""
    monkeypatch.setattr(
        server,
        "settings",
        Settings(
            search_provider="searxng",
            searxng_base_url="http://10.0.0.102:8088",
        ),
    )
    async with Client(mcp) as client:
        result = await client.read_resource("web://providers")
    payload = json.loads(result[0].text)
    assert payload["active_provider"] == "searxng"
    assert payload["searxng_configured"] is True
    assert "10.0.0.102" not in result[0].text
