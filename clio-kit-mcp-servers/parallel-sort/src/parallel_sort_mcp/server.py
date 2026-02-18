#!/usr/bin/env python3
"""
Parallel Sort MCP Server implementation using Model Context Protocol.
Provides log file sorting capabilities by timestamp.
"""

import os
from typing import Optional
from fastmcp import FastMCP
from fastmcp.exceptions import ToolError
from fastmcp.prompts import Message
from dotenv import load_dotenv
import logging
from . import mcp_handlers

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

# Initialize MCP server
mcp: FastMCP = FastMCP(
    "parallel-sort",
    instructions=(
        "Sorts large files using parallel algorithms. "
        "Configure sort parameters, execute sorts with progress tracking, and verify results."
    ),
    list_page_size=10,
)


@mcp.resource("parallel-sort://capabilities")
def sort_capabilities() -> dict:
    """Parallel sort algorithms and configuration options."""
    return {
        "algorithms": ["merge sort", "quick sort", "radix sort"],
        "max_parallelism": "auto (CPU count)",
        "supported_data_types": ["numeric", "string", "binary"],
    }


@mcp.prompt()
def sort_large_file(file_path: str) -> list[Message]:
    """Guided workflow for sorting a large file with optimal settings."""
    return [
        Message(
            f"I need to sort the large file at {file_path}. "
            "Configure optimal sort parameters based on file size and available memory, "
            "execute the sort with progress tracking, and verify the output."
        ),
    ]


@mcp.tool(
    name="sort_log_by_timestamp",
    description="Sort log file lines by timestamps in YYYY-MM-DD HH:MM:SS format.",
    annotations={"readOnlyHint": False, "destructiveHint": False, "idempotentHint": False},
    tags={"sort", "execution"},
)
async def sort_log_tool(
    log_file: str, output_file: Optional[str] = None, reverse: bool = False
) -> dict:
    """Sort log files by timestamp in chronological order.

    Args:
        log_file: Path to input log file.
        output_file: Path for sorted output file.
        reverse: Sort in descending order (default: False).

    Returns:
        Dictionary with sorting results, processed line count, and execution time.
    """
    logger.info(f"Sorting log file: {log_file}")
    return await mcp_handlers.sort_log_handler(log_file, output_file, reverse)


@mcp.tool(
    name="parallel_sort_large_file",
    description="Sort large log files using parallel processing with chunked approach.",
    annotations={"readOnlyHint": False, "destructiveHint": False, "idempotentHint": False},
    tags={"sort", "execution"},
)
async def parallel_sort_tool(
    log_file: str,
    output_file: str,
    chunk_size_mb: int = 100,
    num_workers: Optional[int] = None,
) -> dict:
    """Sort large log files using parallel processing for memory efficiency.

    Args:
        log_file: Path to large log file.
        output_file: Path for sorted output file.
        chunk_size_mb: Chunk size in MB (default: 100).
        num_workers: Number of worker processes (default: CPU count).

    Returns:
        Dictionary with sorting results, performance metrics, and memory usage.
    """
    logger.info(f"Parallel sorting large file: {log_file}")
    return await mcp_handlers.parallel_sort_handler(
        log_file, output_file, chunk_size_mb, num_workers
    )


@mcp.tool(
    name="analyze_log_statistics",
    description="Generate statistics for log files including temporal patterns and log levels.",
    annotations={"readOnlyHint": True, "destructiveHint": False, "idempotentHint": True},
    tags={"sort", "monitoring"},
)
async def analyze_statistics_tool(log_file: str, include_patterns: bool = True) -> dict:
    """Perform statistical analysis of log files.

    Args:
        log_file: Path to log file.
        include_patterns: Include pattern analysis (default: True).

    Returns:
        Dictionary with statistics, temporal analysis, and quality metrics.
    """
    logger.info(f"Analyzing log statistics: {log_file}")
    return await mcp_handlers.analyze_statistics_handler(log_file, include_patterns)


@mcp.tool(
    name="detect_log_patterns",
    description="Detect patterns in log files including anomalies and error clusters.",
    annotations={"readOnlyHint": True, "destructiveHint": False, "idempotentHint": True},
    tags={"sort", "monitoring"},
)
async def detect_patterns_tool(
    log_file: str,
    pattern_types: Optional[list] = None,
    sensitivity: Optional[str] = None,
) -> dict:
    """Detect patterns, anomalies, and trends in log files.

    Args:
        log_file: Path to log file.
        pattern_types: Types of patterns to detect.
        sensitivity: Detection sensitivity ('low', 'medium', 'high').

    Returns:
        Dictionary with detected patterns, anomalies, and trend analysis.
    """
    logger.info(f"Detecting patterns in: {log_file}")
    return await mcp_handlers.detect_patterns_handler(
        log_file, pattern_types, sensitivity
    )


@mcp.tool(
    name="filter_logs",
    description="Filter log entries based on multiple conditions with logical operations.",
    annotations={"readOnlyHint": False, "destructiveHint": False, "idempotentHint": False},
    tags={"sort", "execution"},
)
async def filter_logs_tool(
    log_file: str,
    filters: list,
    logical_operator: Optional[str] = None,
    output_file: Optional[str] = None,
) -> dict:
    """Apply multiple filter conditions to log files.

    Args:
        log_file: Path to log file.
        filters: List of filter conditions.
        logical_operator: Logical operator between filters ('AND', 'OR').
        output_file: Path for filtered output.

    Returns:
        Dictionary with filtered results and applied filter summary.
    """
    logger.info(f"Filtering logs: {log_file}")
    return await mcp_handlers.filter_logs_handler(
        log_file, filters, logical_operator, output_file
    )


@mcp.tool(
    name="filter_by_time_range",
    description="Filter log entries by time range using start and end timestamps.",
    annotations={"readOnlyHint": False, "destructiveHint": False, "idempotentHint": False},
    tags={"sort", "execution"},
)
async def filter_time_range_tool(
    log_file: str, start_time: str, end_time: str, output_file: Optional[str] = None
) -> dict:
    """Filter log entries within a specific time range.

    Args:
        log_file: Path to log file.
        start_time: Start timestamp (YYYY-MM-DD HH:MM:SS).
        end_time: End timestamp (YYYY-MM-DD HH:MM:SS).
        output_file: Path for filtered output.

    Returns:
        Dictionary with filtered entries and time range statistics.
    """
    logger.info(f"Filtering by time range: {log_file}")
    return await mcp_handlers.filter_time_range_handler(
        log_file, start_time, end_time, output_file
    )


@mcp.tool(
    name="filter_by_log_level",
    description="Filter log entries by log level (ERROR, WARN, INFO, DEBUG, etc.).",
    annotations={"readOnlyHint": False, "destructiveHint": False, "idempotentHint": False},
    tags={"sort", "execution"},
)
async def filter_level_tool(
    log_file: str, log_levels: list, output_file: Optional[str] = None
) -> dict:
    """Filter log entries by log level.

    Args:
        log_file: Path to log file.
        log_levels: List of log levels to include.
        output_file: Path for filtered output.

    Returns:
        Dictionary with filtered entries and log level distribution.
    """
    logger.info(f"Filtering by level: {log_file}")
    return await mcp_handlers.filter_level_handler(log_file, log_levels, output_file)


@mcp.tool(
    name="filter_by_keyword",
    description="Filter log entries by keywords with support for multiple keywords and logical operations.",
    annotations={"readOnlyHint": False, "destructiveHint": False, "idempotentHint": False},
    tags={"sort", "execution"},
)
async def filter_keyword_tool(
    log_file: str,
    keywords: list,
    case_sensitive: bool = False,
    logical_operator: Optional[str] = None,
    output_file: Optional[str] = None,
) -> dict:
    """Filter log entries containing specific keywords.

    Args:
        log_file: Path to log file.
        keywords: List of keywords to search for.
        case_sensitive: Case sensitive matching (default: False).
        logical_operator: Operator between keywords ('AND', 'OR').
        output_file: Path for filtered output.

    Returns:
        Dictionary with filtered entries and keyword match statistics.
    """
    logger.info(f"Filtering by keywords: {log_file}")
    return await mcp_handlers.filter_keyword_handler(
        log_file, keywords, case_sensitive, logical_operator, output_file
    )


@mcp.tool(
    name="apply_filter_preset",
    description="Apply predefined filter presets like 'errors_only' or 'connection_issues'.",
    annotations={"readOnlyHint": False, "destructiveHint": False, "idempotentHint": False},
    tags={"sort", "execution"},
)
async def filter_preset_tool(
    log_file: str, preset_name: str, output_file: Optional[str] = None
) -> dict:
    """Apply predefined filter presets for common log analysis scenarios.

    Args:
        log_file: Path to log file.
        preset_name: Preset name ('errors_only', 'warnings_and_errors', etc.).
        output_file: Path for filtered output.

    Returns:
        Dictionary with filtered results and preset configuration details.
    """
    logger.info(f"Applying filter preset '{preset_name}': {log_file}")
    return await mcp_handlers.filter_preset_handler(log_file, preset_name, output_file)


@mcp.tool(
    name="export_to_json",
    description="Export log processing results to JSON format.",
    annotations={"readOnlyHint": False, "destructiveHint": False, "idempotentHint": True},
    tags={"sort", "configuration"},
)
async def export_json_tool(data: dict, include_metadata: bool = True) -> dict:
    """Export results to JSON format.

    Args:
        data: Processing results to export.
        include_metadata: Whether to include processing metadata.

    Returns:
        Dictionary with JSON export results.
    """
    logger.info("Exporting to JSON format")
    return await mcp_handlers.export_json_handler(data, include_metadata)


@mcp.tool(
    name="export_to_csv",
    description="Export log entries to CSV format with structured columns.",
    annotations={"readOnlyHint": False, "destructiveHint": False, "idempotentHint": True},
    tags={"sort", "configuration"},
)
async def export_csv_tool(data: dict, include_headers: bool = True) -> dict:
    """Export results to CSV format.

    Args:
        data: Processing results to export.
        include_headers: Whether to include CSV headers.

    Returns:
        Dictionary with CSV export results.
    """
    logger.info("Exporting to CSV format")
    return await mcp_handlers.export_csv_handler(data, include_headers)


@mcp.tool(
    name="export_to_text",
    description="Export log entries to plain text format.",
    annotations={"readOnlyHint": False, "destructiveHint": False, "idempotentHint": True},
    tags={"sort", "configuration"},
)
async def export_text_tool(data: dict, include_summary: bool = True) -> dict:
    """Export results to text format.

    Args:
        data: Processing results to export.
        include_summary: Whether to include processing summary.

    Returns:
        Dictionary with text export results.
    """
    logger.info("Exporting to text format")
    return await mcp_handlers.export_text_handler(data, include_summary)


@mcp.tool(
    name="generate_summary_report",
    description="Generate a summary report of log processing results with statistics.",
    annotations={"readOnlyHint": True, "destructiveHint": False, "idempotentHint": True},
    tags={"sort", "monitoring"},
)
async def summary_report_tool(data: dict) -> dict:
    """Generate a summary report.

    Args:
        data: Processing results to summarize.

    Returns:
        Dictionary with summary report.
    """
    logger.info("Generating summary report")
    return await mcp_handlers.summary_report_handler(data)


def main() -> None:
    """Main entry point for the Parallel Sort MCP server."""
    import argparse

    parser = argparse.ArgumentParser(description="Parallel Sort MCP Server")
    parser.add_argument("--transport", choices=["stdio", "http"], default=None)
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--port", type=int, default=8000)
    args = parser.parse_args()
    transport = args.transport or os.getenv("MCP_TRANSPORT", "stdio")
    if transport == "http":

        mcp.run(transport=transport, host=args.host, port=args.port)

    else:

        mcp.run(transport=transport)


if __name__ == "__main__":
    main()
