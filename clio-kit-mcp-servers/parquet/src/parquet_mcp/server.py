"""FastMCP server for Apache Parquet files."""

import json
from typing import Optional, List, Union
from fastmcp import FastMCP
from fastmcp.exceptions import ToolError
from fastmcp.prompts import Message
from parquet_mcp.capabilities.parquet_handler import (
    summarize,
    read_slice,
    get_column_preview,
    aggregate_column,
)


def _check_error(result: str) -> str:
    """Check handler result for error status and raise ToolError if found."""
    try:
        parsed = json.loads(result)
        if isinstance(parsed, dict) and parsed.get("status") == "error":
            raise ToolError(parsed.get("message", "Unknown error"))
    except (json.JSONDecodeError, TypeError):
        pass
    return result


mcp = FastMCP(
    "parquet",
    instructions=(
        "Reads and analyzes Apache Parquet files. "
        "Use summarize_tool for file overview, read_slice_tool for row access, "
        "get_column_preview_tool for column samples, aggregate_column_tool for statistics."
    ),
)


@mcp.tool(
    title="summarize(parquet)",
    description="Return Parquet schema, row count, and file size.",
    annotations={
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
    },
    tags={"parquet", "data-analysis"},
)
async def summarize_tool(file_path: str) -> str:
    """Summarize a Parquet file's structure and metadata.

    Args:
        file_path: Path to the Parquet file

    Returns:
        JSON string with schema, row count, row groups, and file size
    """
    return _check_error(await summarize(file_path))


@mcp.tool(
    title="read(slice)",
    description="Read a row slice from a Parquet file with optional column projection and filtering.",
    annotations={
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
    },
    tags={"parquet", "data-analysis"},
)
async def read_slice_tool(
    file_path: str,
    start_row: int,
    end_row: int,
    columns: Optional[List[str]] = None,
    filter_json: Optional[str] = None,
) -> str:
    """Read a specific range of rows from a Parquet file.

    Args:
        file_path: Path to the Parquet file
        start_row: Starting row index (inclusive, 0-based)
        end_row: Ending row index (exclusive)
        columns: Optional list of column names to include (all columns if None)
        filter_json: Optional JSON string with filter specification
                     Example: '{"column": "zenith", "op": "less", "value": 0.5}'

    Returns:
        JSON string with status, schema, data, and shape information
    """
    return _check_error(
        await read_slice(file_path, start_row, end_row, columns, filter_json)
    )


@mcp.tool(
    title="preview(column)",
    description="Preview values from a specific column with pagination.",
    annotations={
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
    },
    tags={"parquet", "data-analysis"},
)
async def get_column_preview_tool(
    file_path: str, column_name: str, start_index: int = 0, max_items: int = 100
) -> str:
    """Get a preview of values from a named column in a Parquet file.

    Args:
        file_path: Path to the Parquet file
        column_name: Name of the column to preview
        start_index: Starting index for pagination (default: 0)
        max_items: Maximum number of items to return (default: 100, max: 100)

    Returns:
        JSON string with column values, type info, and pagination metadata
    """
    return _check_error(
        await get_column_preview(file_path, column_name, start_index, max_items)
    )


@mcp.tool(
    title="aggregate(column)",
    description="Compute aggregate statistics (min, max, mean, etc.) on a Parquet column.",
    annotations={
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
    },
    tags={"parquet", "data-analysis", "statistics"},
)
async def aggregate_column_tool(
    file_path: str,
    column_name: str,
    operation: str,
    filter_json: Optional[str] = None,
    start_row: Optional[Union[int, float]] = None,
    end_row: Optional[Union[int, float]] = None,
) -> str:
    """Compute aggregate statistics on a column with optional filtering and range bounds.

    Args:
        file_path: Path to the Parquet file
        column_name: Name of the column to aggregate
        operation: Aggregation operation (min, max, mean, sum, count, std, count_distinct)
        filter_json: Optional JSON string with filter specification
                     Example: '{"column": "batch_id", "op": "equal", "value": 1}'
        start_row: Optional starting row index for range constraint
        end_row: Optional ending row index for range constraint

    Returns:
        JSON string with aggregation result and metadata
    """
    return _check_error(
        await aggregate_column(
            file_path, column_name, operation, filter_json, start_row, end_row
        )
    )


@mcp.resource("parquet://formats")
def supported_formats() -> dict:
    """Supported Parquet features and capabilities."""
    return {
        "read_formats": ["parquet"],
        "compression_codecs": ["snappy", "gzip", "lz4", "zstd", "brotli"],
        "features": ["column pruning", "row group filtering", "schema inspection"],
    }


@mcp.prompt()
def analyze_parquet(file_path: str) -> list[Message]:
    """Guided workflow for analyzing a Parquet file."""
    return [
        Message(
            f"I need to analyze the Parquet file at {file_path}. "
            "First summarize its schema and row count, then preview the first few columns, "
            "and compute basic statistics on numeric columns."
        ),
    ]


def main() -> None:
    """Main entry point for the Parquet MCP server."""
    import os
    import argparse

    parser = argparse.ArgumentParser(description="Parquet MCP Server")
    parser.add_argument("--transport", choices=["stdio", "http"], default=None)
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--port", type=int, default=8000)
    args = parser.parse_args()
    transport = args.transport or os.getenv("MCP_TRANSPORT", "stdio")
    if transport == "http":
        mcp.run(transport="http", host=args.host, port=args.port)
    else:
        mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
