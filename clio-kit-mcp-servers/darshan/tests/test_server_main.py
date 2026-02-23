"""Tests for server main entry point and additional edge cases."""

import pytest
from unittest.mock import patch

from darshan_mcp import server


def test_main_function():
    """Test the main function calls mcp.run with default transport."""
    with patch.object(server.mcp, "run", return_value=None) as mock_run:
        with patch("argparse.ArgumentParser.parse_args") as mock_args:
            mock_args.return_value = type(
                "Args", (), {"transport": None, "host": "0.0.0.0", "port": 8000}
            )()
            server.main()
            mock_run.assert_called_once_with(transport="stdio")


def test_main_function_callable():
    """Test that the main function is callable and properly configured."""
    with patch.object(server.mcp, "run", return_value=None) as mock_run:
        with patch("argparse.ArgumentParser.parse_args") as mock_args:
            mock_args.return_value = type(
                "Args", (), {"transport": "http", "host": "127.0.0.1", "port": 9000}
            )()
            server.main()
            mock_run.assert_called_once_with(
                transport="http", host="127.0.0.1", port=9000
            )


@pytest.mark.asyncio
async def test_load_darshan_log_tool_integration():
    """Test load_darshan_log_tool with actual integration."""
    with patch("darshan_mcp.capabilities.darshan_parser.load_darshan_log") as mock_load:
        mock_load.return_value = {"success": True, "job_id": "12345"}
        result = await server.load_darshan_log_tool("/test/file.darshan")
        assert result["success"] is True
        mock_load.assert_called_once_with("/test/file.darshan")


@pytest.mark.asyncio
async def test_get_job_summary_tool_integration():
    """Test get_job_summary_tool with actual integration."""
    with patch(
        "darshan_mcp.capabilities.darshan_parser.get_job_summary"
    ) as mock_summary:
        mock_summary.return_value = {"success": True, "runtime": 300}
        result = await server.get_job_summary_tool("/test/file.darshan")
        assert result["success"] is True
        mock_summary.assert_called_once_with("/test/file.darshan")


@pytest.mark.asyncio
async def test_analyze_file_access_patterns_tool_integration():
    """Test analyze_file_access_patterns_tool with actual integration."""
    with patch(
        "darshan_mcp.capabilities.darshan_parser.analyze_file_access_patterns"
    ) as mock_analyze:
        mock_analyze.return_value = {"success": True, "patterns": []}
        result = await server.analyze_file_access_patterns_tool(
            "/test/file.darshan", "*.dat"
        )
        assert result["success"] is True
        mock_analyze.assert_called_once_with("/test/file.darshan", "*.dat")


@pytest.mark.asyncio
async def test_get_io_performance_metrics_tool_integration():
    """Test get_io_performance_metrics_tool with actual integration."""
    with patch(
        "darshan_mcp.capabilities.darshan_parser.get_io_performance_metrics"
    ) as mock_metrics:
        mock_metrics.return_value = {"success": True, "bandwidth_mbps": 1000}
        result = await server.get_io_performance_metrics_tool("/test/file.darshan")
        assert result["success"] is True
        mock_metrics.assert_called_once_with("/test/file.darshan")


@pytest.mark.asyncio
async def test_analyze_posix_operations_tool_integration():
    """Test analyze_posix_operations_tool with actual integration."""
    with patch(
        "darshan_mcp.capabilities.darshan_parser.analyze_posix_operations"
    ) as mock_posix:
        mock_posix.return_value = {"success": True, "operations": {}}
        result = await server.analyze_posix_operations_tool("/test/file.darshan")
        assert result["success"] is True
        mock_posix.assert_called_once_with("/test/file.darshan")


@pytest.mark.asyncio
async def test_analyze_mpiio_operations_tool_integration():
    """Test analyze_mpiio_operations_tool with actual integration."""
    with patch(
        "darshan_mcp.capabilities.darshan_parser.analyze_mpiio_operations"
    ) as mock_mpiio:
        mock_mpiio.return_value = {"success": True, "operations": {}}
        result = await server.analyze_mpiio_operations_tool("/test/file.darshan")
        assert result["success"] is True
        mock_mpiio.assert_called_once_with("/test/file.darshan")


@pytest.mark.asyncio
async def test_identify_io_bottlenecks_tool_integration():
    """Test identify_io_bottlenecks_tool with actual integration."""
    with patch(
        "darshan_mcp.capabilities.darshan_parser.identify_io_bottlenecks"
    ) as mock_bottlenecks:
        mock_bottlenecks.return_value = {"success": True, "issues": []}
        result = await server.identify_io_bottlenecks_tool("/test/file.darshan")
        assert result["success"] is True
        mock_bottlenecks.assert_called_once_with("/test/file.darshan")


@pytest.mark.asyncio
async def test_get_timeline_analysis_tool_integration():
    """Test get_timeline_analysis_tool with actual integration."""
    with patch(
        "darshan_mcp.capabilities.darshan_parser.get_timeline_analysis"
    ) as mock_timeline:
        mock_timeline.return_value = {"success": True, "timeline": []}
        result = await server.get_timeline_analysis_tool("/test/file.darshan", "100ms")
        assert result["success"] is True
        mock_timeline.assert_called_once_with("/test/file.darshan", "100ms")


@pytest.mark.asyncio
async def test_compare_darshan_logs_tool_integration():
    """Test compare_darshan_logs_tool with actual integration."""
    with patch(
        "darshan_mcp.capabilities.darshan_parser.compare_darshan_logs"
    ) as mock_compare:
        mock_compare.return_value = {"success": True, "differences": []}
        result = await server.compare_darshan_logs_tool(
            "/test/file1.darshan", "/test/file2.darshan", ["bandwidth", "iops"]
        )
        assert result["success"] is True
        mock_compare.assert_called_once_with(
            "/test/file1.darshan", "/test/file2.darshan", ["bandwidth", "iops"]
        )


@pytest.mark.asyncio
async def test_generate_io_summary_report_tool_integration():
    """Test generate_io_summary_report_tool with actual integration."""
    with patch(
        "darshan_mcp.capabilities.darshan_parser.generate_io_summary_report"
    ) as mock_report:
        mock_report.return_value = {"success": True, "report": "Summary"}
        result = await server.generate_io_summary_report_tool(
            "/test/file.darshan", True
        )
        assert result["success"] is True
        mock_report.assert_called_once_with("/test/file.darshan", True)
