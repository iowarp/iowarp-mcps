"""Tests for the geojson server resource and prompt surface."""

from __future__ import annotations

import pytest
from fastmcp import Client
from geojson_mcp.server import mcp


@pytest.mark.asyncio
async def test_capabilities_resource() -> None:
    async with Client(mcp) as client:
        resources = {str(r.uri) for r in await client.list_resources()}
    assert "geojson://capabilities" in resources


@pytest.mark.asyncio
async def test_capabilities_content() -> None:
    async with Client(mcp) as client:
        result = await client.read_resource("geojson://capabilities")
    import json

    payload = json.loads(result[0].text)
    assert "inspect_geojson" in payload["tools"]
    assert "validate_geojson" in payload["tools"]
    assert "summarize_geojson" in payload["tools"]
    assert "feature_bbox" in payload["tools"]


@pytest.mark.asyncio
async def test_inspect_workflow_prompt_registered() -> None:
    async with Client(mcp) as client:
        prompts = {p.name for p in await client.list_prompts()}
    assert "inspect_workflow" in prompts


@pytest.mark.asyncio
async def test_inspect_workflow_prompt_renders() -> None:
    async with Client(mcp) as client:
        result = await client.get_prompt("inspect_workflow", {"source": "/data/sample.geojson"})
    assert result.messages
    assert "/data/sample.geojson" in result.messages[0].content.text


def test_instructions_set() -> None:
    assert mcp.instructions
