"""Tests for Darshan MCP server."""

import pytest
from unittest.mock import patch, AsyncMock
import sys
import os

# Add the src directory to the path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from darshan_mcp.server import (
    load_darshan_log_tool,
    get_job_summary_tool,
    analyze_file_access_patterns_tool,
    get_io_performance_metrics_tool,
    analyze_posix_operations_tool,
    analyze_mpiio_operations_tool,
    identify_io_bottlenecks_tool,
    get_timeline_analysis_tool,
    compare_darshan_logs_tool,
    generate_io_summary_report_tool,
)


@pytest.mark.asyncio
async def test_load_darshan_log_tool():
    """Test load_darshan_log tool."""
    mock_result = {
        "success": True,
        "log_file": "/test/file.darshan",
        "job_info": {"job_id": "12345", "nprocs": 64},
        "modules": ["POSIX", "MPIIO"],
        "file_count": 10,
    }

    with patch(
        "darshan_mcp.server.darshan_parser.load_darshan_log", new_callable=AsyncMock
    ) as mock_handler:
        mock_handler.return_value = mock_result

        result = await load_darshan_log_tool("/test/file.darshan")

        assert result == mock_result
        mock_handler.assert_called_once_with("/test/file.darshan")


@pytest.mark.asyncio
async def test_get_job_summary_tool():
    """Test get_job_summary tool."""
    mock_result = {
        "success": True,
        "job_id": "12345",
        "nprocs": 64,
        "runtime_seconds": 3600,
        "total_io_volume": 1000000000,
        "total_bandwidth_mbps": 200,
    }

    with patch(
        "darshan_mcp.server.darshan_parser.get_job_summary", new_callable=AsyncMock
    ) as mock_handler:
        mock_handler.return_value = mock_result

        result = await get_job_summary_tool("/test/file.darshan")

        assert result == mock_result
        mock_handler.assert_called_once_with("/test/file.darshan")


@pytest.mark.asyncio
async def test_analyze_file_access_patterns_tool():
    """Test analyze_file_access_patterns tool."""
    mock_result = {
        "success": True,
        "file_count": 5,
        "read_only_files": 2,
        "write_only_files": 2,
        "read_write_files": 1,
        "sequential_access": 3,
        "random_access": 2,
    }

    with patch(
        "darshan_mcp.server.darshan_parser.analyze_file_access_patterns",
        new_callable=AsyncMock,
    ) as mock_handler:
        mock_handler.return_value = mock_result

        result = await analyze_file_access_patterns_tool("/test/file.darshan", "*.dat")

        assert result == mock_result
        mock_handler.assert_called_once_with("/test/file.darshan", "*.dat")


@pytest.mark.asyncio
async def test_analyze_file_access_patterns_tool_no_pattern():
    """Test analyze_file_access_patterns tool without pattern."""
    mock_result = {"success": True, "file_count": 10, "filter_pattern": None}

    with patch(
        "darshan_mcp.server.darshan_parser.analyze_file_access_patterns",
        new_callable=AsyncMock,
    ) as mock_handler:
        mock_handler.return_value = mock_result

        result = await analyze_file_access_patterns_tool("/test/file.darshan")

        assert result == mock_result
        mock_handler.assert_called_once_with("/test/file.darshan", None)


@pytest.mark.asyncio
async def test_get_io_performance_metrics_tool():
    """Test get_io_performance_metrics tool."""
    mock_result = {
        "success": True,
        "read_metrics": {"total_bytes": 1000000, "bandwidth_mbps": 100, "iops": 1000},
        "write_metrics": {"total_bytes": 500000, "bandwidth_mbps": 50, "iops": 500},
        "overall_metrics": {"total_bandwidth_mbps": 150, "total_iops": 1500},
    }

    with patch(
        "darshan_mcp.server.darshan_parser.get_io_performance_metrics",
        new_callable=AsyncMock,
    ) as mock_handler:
        mock_handler.return_value = mock_result

        result = await get_io_performance_metrics_tool("/test/file.darshan")

        assert result == mock_result
        mock_handler.assert_called_once_with("/test/file.darshan")


@pytest.mark.asyncio
async def test_analyze_posix_operations_tool():
    """Test analyze_posix_operations tool."""
    mock_result = {
        "success": True,
        "operations": {
            "opens": 10,
            "closes": 10,
            "reads": 1000,
            "writes": 500,
            "seeks": 100,
        },
    }

    with patch(
        "darshan_mcp.server.darshan_parser.analyze_posix_operations",
        new_callable=AsyncMock,
    ) as mock_handler:
        mock_handler.return_value = mock_result

        result = await analyze_posix_operations_tool("/test/file.darshan")

        assert result == mock_result
        mock_handler.assert_called_once_with("/test/file.darshan")


@pytest.mark.asyncio
async def test_analyze_mpiio_operations_tool():
    """Test analyze_mpiio_operations tool."""
    mock_result = {
        "success": True,
        "collective_operations": {"reads": 50, "writes": 25},
        "independent_operations": {"reads": 200, "writes": 100},
    }

    with patch(
        "darshan_mcp.server.darshan_parser.analyze_mpiio_operations",
        new_callable=AsyncMock,
    ) as mock_handler:
        mock_handler.return_value = mock_result

        result = await analyze_mpiio_operations_tool("/test/file.darshan")

        assert result == mock_result
        mock_handler.assert_called_once_with("/test/file.darshan")


@pytest.mark.asyncio
async def test_identify_io_bottlenecks_tool():
    """Test identify_io_bottlenecks tool."""
    mock_result = {
        "success": True,
        "identified_issues": [
            {
                "type": "small_reads",
                "description": "Small read operations detected",
                "severity": "medium",
            },
            {
                "type": "random_access",
                "description": "Random access pattern detected",
                "severity": "high",
            },
        ],
        "recommendations": [
            "Use larger buffer sizes",
            "Consider data layout optimization",
        ],
        "severity_score": 5,
    }

    with patch(
        "darshan_mcp.server.darshan_parser.identify_io_bottlenecks",
        new_callable=AsyncMock,
    ) as mock_handler:
        mock_handler.return_value = mock_result

        result = await identify_io_bottlenecks_tool("/test/file.darshan")

        assert result == mock_result
        mock_handler.assert_called_once_with("/test/file.darshan")


@pytest.mark.asyncio
async def test_get_timeline_analysis_tool():
    """Test get_timeline_analysis tool."""
    mock_result = {
        "success": True,
        "time_resolution": "100ms",
        "analysis": {
            "total_duration": 3600,
            "peak_periods": [{"start": 100, "end": 200, "peak_bandwidth": 500}],
            "idle_periods": [{"start": 0, "end": 50}],
        },
    }

    with patch(
        "darshan_mcp.server.darshan_parser.get_timeline_analysis",
        new_callable=AsyncMock,
    ) as mock_handler:
        mock_handler.return_value = mock_result

        result = await get_timeline_analysis_tool("/test/file.darshan", "100ms")

        assert result == mock_result
        mock_handler.assert_called_once_with("/test/file.darshan", "100ms")


@pytest.mark.asyncio
async def test_get_timeline_analysis_tool_default_resolution():
    """Test get_timeline_analysis tool with default resolution."""
    mock_result = {"success": True, "time_resolution": "1s"}

    with patch(
        "darshan_mcp.server.darshan_parser.get_timeline_analysis",
        new_callable=AsyncMock,
    ) as mock_handler:
        mock_handler.return_value = mock_result

        result = await get_timeline_analysis_tool("/test/file.darshan")

        assert result == mock_result
        mock_handler.assert_called_once_with("/test/file.darshan", "1s")


@pytest.mark.asyncio
async def test_compare_darshan_logs_tool():
    """Test compare_darshan_logs tool."""
    mock_result = {
        "success": True,
        "log_file_1": "/test/file1.darshan",
        "log_file_2": "/test/file2.darshan",
        "differences": {
            "bandwidth": {
                "log_1": 100,
                "log_2": 150,
                "difference": 50,
                "percent_change": 50.0,
            },
            "iops": {
                "log_1": 1000,
                "log_2": 1200,
                "difference": 200,
                "percent_change": 20.0,
            },
        },
    }

    with patch(
        "darshan_mcp.server.darshan_parser.compare_darshan_logs", new_callable=AsyncMock
    ) as mock_handler:
        mock_handler.return_value = mock_result

        result = await compare_darshan_logs_tool(
            "/test/file1.darshan", "/test/file2.darshan", ["bandwidth", "iops"]
        )

        assert result == mock_result
        mock_handler.assert_called_once_with(
            "/test/file1.darshan", "/test/file2.darshan", ["bandwidth", "iops"]
        )


@pytest.mark.asyncio
async def test_compare_darshan_logs_tool_default_metrics():
    """Test compare_darshan_logs tool with default metrics."""
    mock_result = {
        "success": True,
        "comparison_metrics": ["bandwidth", "iops", "file_count"],
    }

    with patch(
        "darshan_mcp.server.darshan_parser.compare_darshan_logs", new_callable=AsyncMock
    ) as mock_handler:
        mock_handler.return_value = mock_result

        result = await compare_darshan_logs_tool(
            "/test/file1.darshan", "/test/file2.darshan"
        )

        assert result == mock_result
        mock_handler.assert_called_once_with(
            "/test/file1.darshan",
            "/test/file2.darshan",
            ["bandwidth", "iops", "file_count"],
        )


@pytest.mark.asyncio
async def test_generate_io_summary_report_tool():
    """Test generate_io_summary_report tool."""
    mock_result = {
        "success": True,
        "log_file": "/test/file.darshan",
        "executive_summary": {
            "total_io_volume_gb": 1.5,
            "runtime_minutes": 60,
            "process_count": 64,
            "avg_bandwidth_mbps": 200,
        },
        "detailed_analysis": {},
        "key_findings": ["Small I/O operations detected"],
        "recommendations": ["Use larger buffer sizes"],
    }

    with patch(
        "darshan_mcp.server.darshan_parser.generate_io_summary_report",
        new_callable=AsyncMock,
    ) as mock_handler:
        mock_handler.return_value = mock_result

        result = await generate_io_summary_report_tool("/test/file.darshan", True)

        assert result == mock_result
        mock_handler.assert_called_once_with("/test/file.darshan", True)


@pytest.mark.asyncio
async def test_generate_io_summary_report_tool_default_visualizations():
    """Test generate_io_summary_report tool with default visualization setting."""
    mock_result = {"success": True, "include_visualizations": False}

    with patch(
        "darshan_mcp.server.darshan_parser.generate_io_summary_report",
        new_callable=AsyncMock,
    ) as mock_handler:
        mock_handler.return_value = mock_result

        result = await generate_io_summary_report_tool("/test/file.darshan")

        assert result == mock_result
        mock_handler.assert_called_once_with("/test/file.darshan", False)
