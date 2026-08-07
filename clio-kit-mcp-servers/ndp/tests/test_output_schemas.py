"""Verify NDP tools declare real MCP output semantics (2026-07-28 protocol).

Every NDP tool's registration must advertise a real, field-level
``outputSchema`` — not the generic ``{"type": "object"}`` a bare
``-> dict[str, Any]`` return annotation would produce.

These tests drive the server through an in-memory ``fastmcp.Client``, so they
exercise exactly what a real MCP client sees on the wire.
"""

import pytest
from fastmcp import Client

from ndp_mcp.server import mcp

ALL_TOOL_NAMES = {
    "list_organizations",
    "search_datasets",
    "get_dataset_details",
    "stage_resource",
}

# Field names that must always be present in each tool's outputSchema
# properties, regardless of which runtime branch produced the result.
EXPECTED_FIELDS = {
    "list_organizations": {"organizations", "count", "server", "name_filter"},
    "search_datasets": {"datasets", "count", "total_found", "server", "search_parameters"},
    "get_dataset_details": {"dataset", "identifier_used", "server", "resource_count"},
    "stage_resource": {"ok", "local_path", "size_bytes", "content_type", "url", "method"},
}


@pytest.mark.asyncio
async def test_tools_list_advertises_real_output_schemas() -> None:
    """tools/list must show a field-level outputSchema for every NDP tool."""
    async with Client(mcp) as client:
        tools = {tool.name: tool for tool in await client.list_tools()}

    missing = ALL_TOOL_NAMES - set(tools)
    assert not missing, f"tools missing from tools/list: {missing}"

    for name in ALL_TOOL_NAMES:
        schema = tools[name].output_schema
        assert schema is not None, f"{name} has no outputSchema"
        assert schema.get("type") == "object", f"{name} outputSchema is not an object"
        properties = schema.get("properties")
        assert properties, f"{name} outputSchema has no real field properties: {schema}"

        expected = EXPECTED_FIELDS[name]
        missing_fields = expected - set(properties)
        assert not missing_fields, (
            f"{name} outputSchema missing expected fields {missing_fields}: {schema}"
        )


@pytest.mark.asyncio
async def test_list_organizations_schema_is_not_generic() -> None:
    """The bare-dict fallback schema ({"type": "object", "additionalProperties":
    true} with no real "properties") must not survive for list_organizations."""
    async with Client(mcp) as client:
        tools = {tool.name: tool for tool in await client.list_tools()}

    schema = tools["list_organizations"].output_schema
    assert schema is not None
    assert "organizations" in schema["properties"]
    assert schema["properties"]["count"].get("type") == "integer"


@pytest.mark.asyncio
async def test_search_datasets_schema_has_nested_search_parameters() -> None:
    """search_parameters must be a real nested object schema, not a bare dict."""
    async with Client(mcp) as client:
        tools = {tool.name: tool for tool in await client.list_tools()}

    schema = tools["search_datasets"].output_schema
    assert schema is not None
    search_parameters = schema["properties"]["search_parameters"]
    # Resolve a top-level $ref (e.g. "#/$defs/SearchParameters") if present.
    if "$ref" in search_parameters:
        ref = search_parameters["$ref"].removeprefix("#/")
        target: dict = schema
        for segment in ref.split("/"):
            target = target[segment]
        search_parameters = target
    assert search_parameters.get("properties"), (
        f"search_parameters has no field-level schema: {search_parameters}"
    )
    assert "dataset_name" in search_parameters["properties"]


@pytest.mark.asyncio
async def test_stage_resource_schema_covers_both_success_paths() -> None:
    """stage_resource is reachable via HTTP and OSDF/Pelican paths; the
    outputSchema must cover the fields common to both, truthfully."""
    async with Client(mcp) as client:
        tools = {tool.name: tool for tool in await client.list_tools()}

    schema = tools["stage_resource"].output_schema
    assert schema is not None
    properties = schema["properties"]
    for field in ("ok", "local_path", "size_bytes", "content_type", "url", "method"):
        assert field in properties, f"stage_resource outputSchema missing '{field}': {schema}"

    required = set(schema.get("required", []))
    # Path-specific fields must not be forced required on both branches.
    assert "transport" not in required
    assert "_meta" not in required
