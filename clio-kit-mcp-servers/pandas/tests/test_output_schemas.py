"""Verify pandas tools declare real MCP output semantics (2026-07-28 protocol).

Every tool's registration must advertise a real, field-level ``outputSchema``
— not the useless generic ``{"type": "object", "additionalProperties": true}``
FastMCP derives from a bare ``-> dict`` return annotation. This drives the
server through an in-memory ``fastmcp.Client``, so it exercises exactly what
a real MCP client sees on the wire (mirrors plot_mcp's
``test_tools_list_advertises_real_output_schemas``).

Uses ``asyncio.run`` rather than ``@pytest.mark.asyncio``: this server's dev
dependency group does not carry a pytest asyncio plugin (unlike some sibling
servers), and pytest silently skips async def tests it cannot run rather than
failing loudly, so a marker-based test could pass by doing nothing. Driving
the event loop explicitly keeps the assertion honest without adding a new dev
dependency just for this test.
"""

import asyncio

from fastmcp import Client

from pandas_mcp.server import mcp

# All 16 pandas tools. Every one of them returns a "success" dict (traced
# from the real implementation code, not docstrings) -- none of them use a
# "status" field the way the plot server's tools do.
ALL_TOOL_NAMES = {
    "load_data",
    "save_data",
    "statistical_summary",
    "correlation_analysis",
    "hypothesis_testing",
    "handle_missing_data",
    "clean_data",
    "groupby_operations",
    "merge_datasets",
    "pivot_table",
    "time_series_operations",
    "validate_data",
    "filter_data",
    "optimize_memory",
    "profile_data",
    "profile_csv",
}

# Fields grounded from the actual `return {...}` statements in each tool's
# implementation function (see src/pandas_mcp/implementation/*.py). Every
# tool's outputSchema must advertise at least these always-present fields.
EXPECTED_TOP_LEVEL_FIELDS = {
    "load_data": {"success", "file_path", "file_format", "data", "total_rows", "info"},
    "save_data": {
        "success",
        "file_path",
        "file_format",
        "file_size_bytes",
        "file_size_mb",
        "rows_saved",
        "columns_saved",
    },
    "statistical_summary": {
        "success",
        "file_path",
        "shape",
        "basic_statistics",
        "additional_statistics",
        "categorical_statistics",
        "missing_data",
    },
    "correlation_analysis": {
        "success",
        "file_path",
        "method",
        "correlation_matrix",
        "high_correlations",
        "analyzed_columns",
    },
    "hypothesis_testing": {"success", "file_path", "test_info", "results"},
    "handle_missing_data": {
        "success",
        "file_path",
        "original_shape",
        "missing_data_info",
    },
    "clean_data": {"success", "file_path", "output_file", "cleaning_results"},
    "groupby_operations": {
        "success",
        "file_path",
        "output_file",
        "group_info",
        "results",
    },
    "merge_datasets": {
        "success",
        "left_file",
        "right_file",
        "output_file",
        "merge_stats",
        "merged_data",
    },
    "pivot_table": {"success", "file_path", "output_file", "pivot_info", "pivot_table"},
    "time_series_operations": {
        "success",
        "file_path",
        "output_file",
        "operation_info",
        "results",
    },
    "validate_data": {
        "success",
        "file_path",
        "validation_summary",
        "validation_results",
    },
    "filter_data": {
        "success",
        "file_path",
        "output_file",
        "filter_stats",
        "filtered_data",
    },
    "optimize_memory": {
        "success",
        "file_path",
        "output_file",
        "system_memory",
        "optimization_results",
        "column_memory_usage",
        "optimization_log",
        "recommendations",
    },
    "profile_data": {
        "success",
        "file_path",
        "basic_info",
        "summary",
        "missing_data",
        "column_analysis",
        "quality_checks",
    },
    "profile_csv": {
        "success",
        "file_path",
        "size_bytes",
        "columns",
        "column_count",
        "row_count",
        "rows_profiled",
        "dtypes",
        "null_counts",
        "numeric_summary",
        "sample_rows",
    },
}


def _list_tools():
    async def _run():
        async with Client(mcp) as client:
            return await client.list_tools()

    return asyncio.run(_run())


def test_tools_list_advertises_real_output_schemas() -> None:
    """tools/list must show a field-level outputSchema for every pandas tool."""
    tools = {tool.name: tool for tool in _list_tools()}

    missing = ALL_TOOL_NAMES - set(tools)
    assert not missing, f"tools missing from tools/list: {missing}"

    for name in ALL_TOOL_NAMES:
        schema = tools[name].output_schema
        assert schema is not None, f"{name} has no outputSchema"
        assert schema.get("type") == "object", f"{name} outputSchema is not an object"
        properties = schema.get("properties")
        assert properties, f"{name} outputSchema has no real field properties: {schema}"

        # Every pandas tool reports "success" on its structured result.
        assert "success" in properties, f"{name} outputSchema missing 'success' field"


def test_output_schemas_expose_the_known_fields() -> None:
    """Each tool's outputSchema must expose the fields grounded from its
    implementation's actual success-path return statement, not a subset that
    happens to satisfy a generic {"type": "object"} check."""
    tools = {tool.name: tool for tool in _list_tools()}

    for name, expected_fields in EXPECTED_TOP_LEVEL_FIELDS.items():
        schema = tools[name].output_schema
        assert schema is not None, f"{name} has no outputSchema"
        properties = set(schema.get("properties", {}))
        missing = expected_fields - properties
        assert not missing, f"{name} outputSchema missing known fields: {missing}"


def test_no_tool_uses_the_generic_bare_dict_schema() -> None:
    """Guard against regressing back to FastMCP's useless generic schema for
    a bare `-> dict` annotation: {"type": "object", "additionalProperties": True}
    with no real `properties`."""
    tools = {tool.name: tool for tool in _list_tools()}

    generic = {
        name
        for name in ALL_TOOL_NAMES
        if not (tools[name].output_schema or {}).get("properties")
    }
    assert not generic, f"tools still advertising a generic bare-dict schema: {generic}"
