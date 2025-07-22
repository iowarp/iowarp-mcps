#!/usr/bin/env python3
"""
Darshan MCP Server for analyzing I/O profiler trace files.
Provides tools to load, explore, and analyze Darshan log files to understand I/O patterns and performance.
"""
import os
import sys
from mcp.server.fastmcp import FastMCP
from dotenv import load_dotenv
import logging
from typing import List, Optional

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Ensure project root is on path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Load environment variables
load_dotenv()

from darshan_mcp.capabilities import darshan_parser

# Initialize MCP server
mcp = FastMCP("DarshanMCP")

@mcp.tool(
    name="load_darshan_log",
    description="Load and parse a Darshan log file to extract I/O performance metrics and metadata. Returns basic information about the trace file including job details, file access patterns, and available modules."
)
async def load_darshan_log_tool(log_file_path: str) -> dict:
    """
    Load and parse a Darshan log file to extract metadata and basic I/O information.

    Args:
        log_file_path (str): Absolute path to the .darshan log file

    Returns:
        dict: Dictionary with job information, modules detected, and file count statistics.
    """
    return await darshan_parser.load_darshan_log(log_file_path)

@mcp.tool(
    name="get_job_summary",
    description="Get comprehensive job-level summary from a loaded Darshan log including execution time, number of processes, total I/O volume, and performance metrics."
)
async def get_job_summary_tool(log_file_path: str) -> dict:
    """
    Get comprehensive job-level summary including runtime statistics and I/O performance overview.

    Args:
        log_file_path (str): Path to the Darshan log file

    Returns:
        dict: Dictionary with runtime metrics, process information, and I/O volume statistics.
    """
    return await darshan_parser.get_job_summary(log_file_path)

@mcp.tool(
    name="analyze_file_access_patterns",
    description="Analyze file access patterns from the trace including which files were accessed, access types (read/write), sequential vs random access patterns, and file size distributions."
)
async def analyze_file_access_patterns_tool(log_file_path: str, file_pattern: Optional[str] = None) -> dict:
    """
    Analyze file access patterns to understand application I/O behavior and optimization opportunities.

    Args:
        log_file_path (str): Path to the Darshan log file
        file_pattern (str, optional): Filter files by pattern (e.g., '*.dat', '/scratch/*')

    Returns:
        dict: Dictionary with access pattern analysis including sequential vs random access statistics.
    """
    return await darshan_parser.analyze_file_access_patterns(log_file_path, file_pattern)

@mcp.tool(
    name="get_io_performance_metrics",
    description="Extract detailed I/O performance metrics including bandwidth, IOPS, average request sizes, and timing information for read and write operations."
)
async def get_io_performance_metrics_tool(log_file_path: str) -> dict:
    """
    Extract detailed I/O performance metrics including bandwidth, IOPS, and request size analysis.

    Args:
        log_file_path (str): Path to the Darshan log file

    Returns:
        dict: Dictionary with comprehensive performance metrics and throughput analysis.
    """
    return await darshan_parser.get_io_performance_metrics(log_file_path)

@mcp.tool(
    name="analyze_posix_operations",
    description="Analyze POSIX I/O operations from the trace including read/write system calls, file operations (open, close, seek), and their frequency and timing patterns."
)
async def analyze_posix_operations_tool(log_file_path: str) -> dict:
    """
    Analyze POSIX system call patterns including open, read, write, and seek operations.

    Args:
        log_file_path (str): Path to the Darshan log file

    Returns:
        dict: Dictionary with POSIX operation statistics and system call analysis.
    """
    return await darshan_parser.analyze_posix_operations(log_file_path)

@mcp.tool(
    name="analyze_mpiio_operations",
    description="Analyze MPI-IO operations if present in the trace, including collective vs independent operations, file view usage, and MPI-IO specific performance metrics."
)
async def analyze_mpiio_operations_tool(log_file_path: str) -> dict:
    """
    Analyze MPI-IO operations including collective vs independent I/O patterns and performance.

    Args:
        log_file_path (str): Path to the Darshan log file

    Returns:
        dict: Dictionary with MPI-IO operation analysis and collective I/O performance metrics.
    """
    return await darshan_parser.analyze_mpiio_operations(log_file_path)

@mcp.tool(
    name="identify_io_bottlenecks",
    description="Identify potential I/O performance bottlenecks by analyzing access patterns, file system usage, small vs large I/O operations, and synchronization patterns."
)
async def identify_io_bottlenecks_tool(log_file_path: str) -> dict:
    """
    Automatically identify potential I/O performance bottlenecks and optimization opportunities.

    Args:
        log_file_path (str): Path to the Darshan log file

    Returns:
        dict: Dictionary with identified performance issues and recommended optimizations.
    """
    return await darshan_parser.identify_io_bottlenecks(log_file_path)

@mcp.tool(
    name="get_timeline_analysis",
    description="Generate timeline analysis showing I/O activity over time, including peak I/O periods, idle times, and temporal patterns in file access."
)
async def get_timeline_analysis_tool(log_file_path: str, time_resolution: str = "1s") -> dict:
    """
    Generate temporal analysis of I/O activity to understand performance patterns over time.

    Args:
        log_file_path (str): Path to the Darshan log file
        time_resolution (str): Time resolution for analysis (e.g., '1s', '100ms')

    Returns:
        dict: Dictionary with timeline analysis and temporal I/O patterns.
    """
    return await darshan_parser.get_timeline_analysis(log_file_path, time_resolution)

@mcp.tool(
    name="compare_darshan_logs",
    description="Compare two Darshan log files to identify differences in I/O patterns, performance changes, and behavioral variations between different runs or configurations."
)
async def compare_darshan_logs_tool(log_file_1: str, log_file_2: str, comparison_metrics: List[str] = None) -> dict:
    """
    Compare two Darshan log files to identify performance differences and optimization results.

    Args:
        log_file_1 (str): Path to the first log file
        log_file_2 (str): Path to the second log file
        comparison_metrics (list): List of metrics to compare ['bandwidth', 'iops', 'file_count']

    Returns:
        dict: Dictionary with comparative analysis and performance delta identification.
    """
    if comparison_metrics is None:
        comparison_metrics = ['bandwidth', 'iops', 'file_count']
    return await darshan_parser.compare_darshan_logs(log_file_1, log_file_2, comparison_metrics)

@mcp.tool(
    name="generate_io_summary_report",
    description="Generate a comprehensive I/O summary report combining all analysis results into a human-readable format with key findings, performance insights, and recommendations."
)
async def generate_io_summary_report_tool(log_file_path: str, include_visualizations: bool = False) -> dict:
    """
    Generate comprehensive I/O analysis report with detailed metrics and recommendations.

    Args:
        log_file_path (str): Path to the Darshan log file
        include_visualizations (bool): Whether to include visualization data in the report

    Returns:
        dict: Dictionary with complete I/O analysis report and performance insights.
    """
    return await darshan_parser.generate_io_summary_report(log_file_path, include_visualizations)

def main():
    """Main entry point for the server."""
    import asyncio
    
    # Run the FastMCP server
    asyncio.run(mcp.run())

if __name__ == "__main__":
    main()