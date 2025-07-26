#!/usr/bin/env python3
"""
Parallel Sort MCP Server implementation using Model Context Protocol.
Provides log file sorting capabilities by timestamp.
"""

import os
import sys
import json
from typing import Optional
from fastmcp import FastMCP
from dotenv import load_dotenv
import logging
import mcp_handlers

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# Add current directory to path for relative imports
sys.path.insert(0, os.path.dirname(__file__))

# Load environment variables
load_dotenv()

# Initialize MCP server
mcp: FastMCP = FastMCP("ParallelSortMCP")


@mcp.tool(
    name="sort_log_by_timestamp",
    description="Sort log file lines by timestamps in YYYY-MM-DD HH:MM:SS format. Handles edge cases like empty files and invalid timestamps.",
)
async def sort_log_tool(
    log_file: str, output_file: Optional[str] = None, reverse: bool = False
) -> dict:
    """
    Sort log files by timestamp in chronological order with support for standard log formats.

    Args:
        log_file (str): Path to input log file
        output_file (str, optional): Path for sorted output file
        reverse (bool, optional): Sort in descending order (default: False)

    Returns:
        dict: Dictionary with sorting results, processed line count, and execution time.
    """
    logger.info(f"Sorting log file: {log_file}")
    return await mcp_handlers.sort_log_handler(log_file, output_file, reverse)


@mcp.tool(
    name="parallel_sort_large_file",
    description="Sort large log files using parallel processing with chunked approach for improved performance.",
)
async def parallel_sort_tool(
    log_file: str,
    output_file: str,
    chunk_size_mb: int = 100,
    num_workers: Optional[int] = None,
) -> dict:
    """
    Sort large log files using parallel processing with chunked approach for memory efficiency.

    Args:
        log_file (str): Path to large log file
        output_file (str): Path for sorted output file
        chunk_size_mb (int, optional): Chunk size in MB (default: 100)
        num_workers (int, optional): Number of worker processes (default: CPU count)

    Returns:
        dict: Dictionary with sorting results, performance metrics, and memory usage.
    """
    logger.info(f"Parallel sorting large file: {log_file}")
    return await mcp_handlers.parallel_sort_handler(
        log_file, output_file, chunk_size_mb, num_workers
    )


@mcp.tool(
    name="analyze_log_statistics",
    description="Generate comprehensive statistics and analysis for log files including temporal patterns, log levels, and quality metrics.",
)
async def analyze_statistics_tool(log_file: str, include_patterns: bool = True) -> dict:
    """
    Perform comprehensive statistical analysis of log files including temporal patterns and log levels.

    Args:
        log_file (str): Path to log file
        include_patterns (bool, optional): Include pattern analysis (default: True)

    Returns:
        dict: Dictionary with statistics, temporal analysis, log level distribution, and quality metrics.
    """
    logger.info(f"Analyzing log statistics: {log_file}")
    return await mcp_handlers.analyze_statistics_handler(log_file, include_patterns)


@mcp.tool(
    name="detect_log_patterns",
    description="Detect patterns in log files including anomalies, error clusters, trending issues, and repeated patterns.",
)
async def detect_patterns_tool(
    log_file: str,
    pattern_types: Optional[list] = None,
    sensitivity: Optional[str] = None,
) -> dict:
    """
    Detect patterns, anomalies, and trends in log files for proactive issue identification.

    Args:
        log_file (str): Path to log file
        pattern_types (list, optional): Types of patterns to detect
        sensitivity (str, optional): Detection sensitivity ('low', 'medium', 'high')

    Returns:
        dict: Dictionary with detected patterns, anomalies, error clusters, and trend analysis.
    """
    logger.info(f"Detecting patterns in: {log_file}")
    return await mcp_handlers.detect_patterns_handler(
        log_file, pattern_types, sensitivity
    )


@mcp.tool(
    name="filter_logs",
    description="Filter log entries based on multiple conditions with support for complex logical operations.",
)
async def filter_logs_tool(
    log_file: str,
    filters: list,
    logical_operator: Optional[str] = None,
    output_file: Optional[str] = None,
) -> dict:
    """
    Apply multiple filter conditions to log files with complex logical operations.

    Args:
        log_file (str): Path to log file
        filters (list): List of filter conditions
        logical_operator (str, optional): Logical operator between filters ('AND', 'OR')
        output_file (str, optional): Path for filtered output

    Returns:
        dict: Dictionary with filtered results and applied filter summary.
    """
    logger.info(f"Filtering logs: {log_file}")
    return await mcp_handlers.filter_logs_handler(
        log_file, filters, logical_operator, output_file
    )


@mcp.tool(
    name="filter_by_time_range",
    description="Filter log entries by time range using start and end timestamps.",
)
async def filter_time_range_tool(
    log_file: str, start_time: str, end_time: str, output_file: Optional[str] = None
) -> dict:
    """
    Filter log entries within a specific time range.

    Args:
        log_file (str): Path to log file
        start_time (str): Start timestamp (YYYY-MM-DD HH:MM:SS)
        end_time (str): End timestamp (YYYY-MM-DD HH:MM:SS)
        output_file (str, optional): Path for filtered output

    Returns:
        dict: Dictionary with filtered entries and time range statistics.
    """
    logger.info(f"Filtering by time range: {log_file}")
    return await mcp_handlers.filter_time_range_handler(
        log_file, start_time, end_time, output_file
    )


@mcp.tool(
    name="filter_by_log_level",
    description="Filter log entries by log level (ERROR, WARN, INFO, DEBUG, etc.).",
)
async def filter_level_tool(
    log_file: str, log_levels: list, output_file: Optional[str] = None
) -> dict:
    """
    Filter log entries by log level (ERROR, WARN, INFO, DEBUG, etc.).

    Args:
        log_file (str): Path to log file
        log_levels (list): List of log levels to include
        output_file (str, optional): Path for filtered output

    Returns:
        dict: Dictionary with filtered entries and log level distribution.
    """
    logger.info(f"Filtering by level: {log_file}")
    return await mcp_handlers.filter_level_handler(log_file, log_levels, output_file)


@mcp.tool(
    name="filter_by_keyword",
    description="Filter log entries by keywords in the message content with support for multiple keywords and logical operations.",
)
async def filter_keyword_tool(
    log_file: str,
    keywords: list,
    case_sensitive: bool = False,
    logical_operator: Optional[str] = None,
    output_file: Optional[str] = None,
) -> dict:
    """
    Filter log entries containing specific keywords with advanced matching options.

    Args:
        log_file (str): Path to log file
        keywords (list): List of keywords to search for
        case_sensitive (bool, optional): Case sensitive matching (default: False)
        logical_operator (str, optional): Operator between keywords ('AND', 'OR')
        output_file (str, optional): Path for filtered output

    Returns:
        dict: Dictionary with filtered entries and keyword match statistics.
    """
    logger.info(f"Filtering by keywords: {log_file}")
    return await mcp_handlers.filter_keyword_handler(
        log_file, keywords, case_sensitive, logical_operator, output_file
    )


@mcp.tool(
    name="apply_filter_preset",
    description="Apply predefined filter presets like 'errors_only', 'warnings_and_errors', 'connection_issues', etc.",
)
async def filter_preset_tool(
    log_file: str, preset_name: str, output_file: Optional[str] = None
) -> dict:
    """
    Apply predefined filter presets for common log analysis scenarios.

    Args:
        log_file (str): Path to log file
        preset_name (str): Preset name ('errors_only', 'warnings_and_errors', 'connection_issues', etc.)
        output_file (str, optional): Path for filtered output

    Returns:
        dict: Dictionary with filtered results and preset configuration details.
    """
    logger.info(f"Applying filter preset '{preset_name}': {log_file}")
    return await mcp_handlers.filter_preset_handler(log_file, preset_name, output_file)


@mcp.tool(
    name="export_to_json",
    description="Export log processing results to JSON format with optional metadata.",
)
async def export_json_tool(data: dict, include_metadata: bool = True) -> dict:
    """
    Export results to JSON format.

    Args:
        data: Processing results to export
        include_metadata: Whether to include processing metadata

    Returns:
        Dictionary with JSON export results
    """
    logger.info("Exporting to JSON format")
    return await mcp_handlers.export_json_handler(data, include_metadata)


@mcp.tool(
    name="export_to_csv",
    description="Export log entries to CSV format with structured columns for timestamp, level, and message.",
)
async def export_csv_tool(data: dict, include_headers: bool = True) -> dict:
    """
    Export results to CSV format.

    Args:
        data: Processing results to export
        include_headers: Whether to include CSV headers

    Returns:
        Dictionary with CSV export results
    """
    logger.info("Exporting to CSV format")
    return await mcp_handlers.export_csv_handler(data, include_headers)


@mcp.tool(
    name="export_to_text",
    description="Export log entries to plain text format with optional processing summary.",
)
async def export_text_tool(data: dict, include_summary: bool = True) -> dict:
    """
    Export results to text format.

    Args:
        data: Processing results to export
        include_summary: Whether to include processing summary

    Returns:
        Dictionary with text export results
    """
    logger.info("Exporting to text format")
    return await mcp_handlers.export_text_handler(data, include_summary)


@mcp.tool(
    name="generate_summary_report",
    description="Generate a comprehensive summary report of log processing results with statistics and analysis.",
)
async def summary_report_tool(data: dict) -> dict:
    """
    Generate a summary report.

    Args:
        data: Processing results to summarize

    Returns:
        Dictionary with summary report
    """
    logger.info("Generating summary report")
    return await mcp_handlers.summary_report_handler(data)


def main():
    """
    Main entry point for the Parallel Sort MCP server.
    Supports both stdio and SSE transports based on environment variables.
    """
    try:
        logger.info("Starting Parallel Sort MCP Server")

        # Determine which transport to use
        transport = os.getenv("MCP_TRANSPORT", "stdio").lower()
        if transport == "sse":
            # SSE transport for web-based clients
            host = os.getenv("MCP_SSE_HOST", "0.0.0.0")
            port = int(os.getenv("MCP_SSE_PORT", "8000"))
            logger.info(f"Starting SSE transport on {host}:{port}")
            print(
                json.dumps({"message": f"Starting SSE on {host}:{port}"}),
                file=sys.stderr,
            )
            mcp.run(transport="sse", host=host, port=port)
        else:
            # Default stdio transport
            logger.info("Starting stdio transport")
            print(json.dumps({"message": "Starting stdio transport"}), file=sys.stderr)
            mcp.run(transport="stdio")

    except Exception as e:
        logger.error(f"Server error: {e}")
        print(json.dumps({"error": str(e)}), file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
