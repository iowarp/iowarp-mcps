#!/usr/bin/env python3
"""Darshan MCP Server for analyzing I/O profiler trace files."""

import os
import logging
from typing import Optional

from fastmcp import FastMCP
from fastmcp.exceptions import ToolError
from fastmcp.prompts import Message
from dotenv import load_dotenv

from darshan_mcp.capabilities import darshan_parser

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

# Initialize MCP server
mcp: FastMCP = FastMCP(
    "darshan",
    instructions=(
        "Analyzes I/O performance logs from Darshan profiler. "
        "Open log files, examine module data, analyze counters, and generate performance insights."
    ),
    list_page_size=10,
)


_READ_ONLY_ANNOTATIONS = {
    "readOnlyHint": True,
    "destructiveHint": False,
    "idempotentHint": True,
}


@mcp.tool(
    name="load_darshan_log",
    title="load(log)",
    description="Load and parse a Darshan log file to extract I/O performance metrics and metadata.",
    annotations=_READ_ONLY_ANNOTATIONS,
    tags={"darshan", "io-analysis"},
)
async def load_darshan_log_tool(log_file_path: str) -> dict:
    """Load and parse a Darshan log file to extract metadata and basic I/O information.

    Args:
        log_file_path: Absolute path to the .darshan log file.

    Returns:
        Dictionary with job information, modules detected, and file count statistics.
    """
    result = await darshan_parser.load_darshan_log(log_file_path)
    if not result.get("success", False):
        raise ToolError(result.get("error", "Failed to load Darshan log"))
    return result


@mcp.tool(
    name="get_job_summary",
    title="get(job summary)",
    description="Get job-level summary from a Darshan log including runtime, process count, and I/O volume.",
    annotations=_READ_ONLY_ANNOTATIONS,
    tags={"darshan", "io-analysis"},
)
async def get_job_summary_tool(log_file_path: str) -> dict:
    """Get comprehensive job-level summary including runtime statistics and I/O performance overview.

    Args:
        log_file_path: Path to the Darshan log file.

    Returns:
        Dictionary with runtime metrics, process information, and I/O volume statistics.
    """
    result = await darshan_parser.get_job_summary(log_file_path)
    if not result.get("success", False):
        raise ToolError(result.get("error", "Failed to get job summary"))
    return result


@mcp.tool(
    name="analyze_file_access_patterns",
    title="analyze(access)",
    description="Analyze file access patterns including read/write types and sequential vs random access.",
    annotations=_READ_ONLY_ANNOTATIONS,
    tags={"darshan", "io-analysis"},
)
async def analyze_file_access_patterns_tool(
    log_file_path: str, file_pattern: Optional[str] = None
) -> dict:
    """Analyze file access patterns to understand application I/O behavior.

    Args:
        log_file_path: Path to the Darshan log file.
        file_pattern: Filter files by pattern (e.g., '*.dat', '/scratch/*').

    Returns:
        Dictionary with access pattern analysis including sequential vs random access statistics.
    """
    result = await darshan_parser.analyze_file_access_patterns(
        log_file_path, file_pattern
    )
    if not result.get("success", False):
        raise ToolError(result.get("error", "Failed to analyze file access patterns"))
    return result


@mcp.tool(
    name="get_io_performance_metrics",
    title="get(io metrics)",
    description="Extract I/O performance metrics including bandwidth, IOPS, and request sizes.",
    annotations=_READ_ONLY_ANNOTATIONS,
    tags={"darshan", "performance"},
)
async def get_io_performance_metrics_tool(log_file_path: str) -> dict:
    """Extract detailed I/O performance metrics including bandwidth, IOPS, and request size analysis.

    Args:
        log_file_path: Path to the Darshan log file.

    Returns:
        Dictionary with comprehensive performance metrics and throughput analysis.
    """
    result = await darshan_parser.get_io_performance_metrics(log_file_path)
    if not result.get("success", False):
        raise ToolError(result.get("error", "Failed to get I/O performance metrics"))
    return result


@mcp.tool(
    name="analyze_posix_operations",
    title="analyze(posix)",
    description="Analyze POSIX I/O operations including read/write system calls and their frequency.",
    annotations=_READ_ONLY_ANNOTATIONS,
    tags={"darshan", "io-analysis"},
)
async def analyze_posix_operations_tool(log_file_path: str) -> dict:
    """Analyze POSIX system call patterns including open, read, write, and seek operations.

    Args:
        log_file_path: Path to the Darshan log file.

    Returns:
        Dictionary with POSIX operation statistics and system call analysis.
    """
    result = await darshan_parser.analyze_posix_operations(log_file_path)
    if not result.get("success", False):
        raise ToolError(result.get("error", "Failed to analyze POSIX operations"))
    return result


@mcp.tool(
    name="analyze_mpiio_operations",
    title="analyze(mpiio)",
    description="Analyze MPI-IO operations including collective vs independent operations.",
    annotations=_READ_ONLY_ANNOTATIONS,
    tags={"darshan", "io-analysis"},
)
async def analyze_mpiio_operations_tool(log_file_path: str) -> dict:
    """Analyze MPI-IO operations including collective vs independent I/O patterns.

    Args:
        log_file_path: Path to the Darshan log file.

    Returns:
        Dictionary with MPI-IO operation analysis and collective I/O performance metrics.
    """
    result = await darshan_parser.analyze_mpiio_operations(log_file_path)
    if not result.get("success", False):
        raise ToolError(result.get("error", "Failed to analyze MPI-IO operations"))
    return result


@mcp.tool(
    name="identify_io_bottlenecks",
    title="find(bottlenecks)",
    description="Identify I/O performance bottlenecks by analyzing access patterns and operations.",
    annotations=_READ_ONLY_ANNOTATIONS,
    tags={"darshan", "performance"},
)
async def identify_io_bottlenecks_tool(log_file_path: str) -> dict:
    """Identify potential I/O performance bottlenecks and optimization opportunities.

    Args:
        log_file_path: Path to the Darshan log file.

    Returns:
        Dictionary with identified performance issues and recommended optimizations.
    """
    result = await darshan_parser.identify_io_bottlenecks(log_file_path)
    if not result.get("success", False):
        raise ToolError(result.get("error", "Failed to identify I/O bottlenecks"))
    return result


@mcp.tool(
    name="get_timeline_analysis",
    title="get(timeline)",
    description="Generate timeline analysis showing I/O activity over time and temporal patterns.",
    annotations=_READ_ONLY_ANNOTATIONS,
    tags={"darshan", "performance"},
)
async def get_timeline_analysis_tool(
    log_file_path: str, time_resolution: str = "1s"
) -> dict:
    """Generate temporal analysis of I/O activity to understand performance patterns over time.

    Args:
        log_file_path: Path to the Darshan log file.
        time_resolution: Time resolution for analysis (e.g., '1s', '100ms').

    Returns:
        Dictionary with timeline analysis and temporal I/O patterns.
    """
    result = await darshan_parser.get_timeline_analysis(log_file_path, time_resolution)
    if not result.get("success", False):
        raise ToolError(result.get("error", "Failed to get timeline analysis"))
    return result


@mcp.tool(
    name="compare_darshan_logs",
    title="compare(logs)",
    description="Compare two Darshan log files to identify performance differences between runs.",
    annotations=_READ_ONLY_ANNOTATIONS,
    tags={"darshan", "performance"},
)
async def compare_darshan_logs_tool(
    log_file_1: str, log_file_2: str, comparison_metrics: Optional[list[str]] = None
) -> dict:
    """Compare two Darshan log files to identify performance differences.

    Args:
        log_file_1: Path to the first log file.
        log_file_2: Path to the second log file.
        comparison_metrics: List of metrics to compare ['bandwidth', 'iops', 'file_count'].

    Returns:
        Dictionary with comparative analysis and performance delta identification.
    """
    if comparison_metrics is None:
        comparison_metrics = ["bandwidth", "iops", "file_count"]
    result = await darshan_parser.compare_darshan_logs(
        log_file_1, log_file_2, comparison_metrics
    )
    if not result.get("success", False):
        raise ToolError(result.get("error", "Failed to compare Darshan logs"))
    return result


@mcp.tool(
    name="generate_io_summary_report",
    title="generate(report)",
    description="Generate a comprehensive I/O summary report with findings and recommendations.",
    annotations=_READ_ONLY_ANNOTATIONS,
    tags={"darshan", "performance"},
)
async def generate_io_summary_report_tool(
    log_file_path: str, include_visualizations: bool = False
) -> dict:
    """Generate comprehensive I/O analysis report with detailed metrics and recommendations.

    Args:
        log_file_path: Path to the Darshan log file.
        include_visualizations: Whether to include visualization data in the report.

    Returns:
        Dictionary with complete I/O analysis report and performance insights.
    """
    result = await darshan_parser.generate_io_summary_report(
        log_file_path, include_visualizations
    )
    if not result.get("success", False):
        raise ToolError(result.get("error", "Failed to generate I/O summary report"))
    return result


@mcp.resource("darshan://capabilities")
def darshan_capabilities() -> dict:
    """Darshan I/O profiling analysis capabilities."""
    return {
        "supported_formats": ["darshan log files (.darshan)"],
        "analysis_types": [
            "module counters",
            "file records",
            "I/O patterns",
            "performance summary",
        ],
    }


@mcp.prompt()
def analyze_io_performance(log_path: str) -> list[Message]:
    """Guided workflow for analyzing I/O performance from a Darshan log."""
    return [
        Message(
            f"I need to analyze the I/O performance in the Darshan log at {log_path}. "
            "Open the log, list available modules, show key counters, and provide a performance summary."
        ),
    ]


def main() -> None:
    """Main entry point for the Darshan MCP server."""
    import argparse

    parser = argparse.ArgumentParser(description="Darshan MCP Server")
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
