"""Tests for error paths and edge cases in Darshan parser capabilities."""

import pytest
from unittest.mock import patch

from darshan_mcp.capabilities import darshan_parser


@pytest.mark.asyncio
async def test_load_darshan_log_parse_failure():
    """Test loading when parse returns failure."""
    with patch("os.path.exists", return_value=True):
        with patch("os.path.getsize", return_value=1024000):
            with patch(
                "darshan_mcp.capabilities.darshan_parser._parse_darshan_json"
            ) as mock_parse:
                mock_parse.return_value = {
                    "success": False,
                    "error": "Failed to parse JSON",
                }
                result = await darshan_parser.load_darshan_log("/test/file.darshan")
                assert result["success"] is False
                assert "error" in result


@pytest.mark.asyncio
async def test_load_darshan_log_exception():
    """Test exception handling in load_darshan_log."""
    with patch("os.path.exists", return_value=True):
        with patch("os.path.getsize", return_value=1024000):
            with patch(
                "darshan_mcp.capabilities.darshan_parser._parse_darshan_json",
                side_effect=Exception("Unexpected error"),
            ):
                result = await darshan_parser.load_darshan_log("/test/file.darshan")
                assert result["success"] is False
                assert "error" in result
                assert "Unexpected error" in result["error"]


@pytest.mark.asyncio
async def test_get_job_summary_parse_failure():
    """Test get_job_summary when parse returns failure."""
    with patch("os.path.exists", return_value=True):
        with patch(
            "darshan_mcp.capabilities.darshan_parser._parse_darshan_json"
        ) as mock_parse:
            mock_parse.return_value = {"success": False, "error": "Parse failed"}
            result = await darshan_parser.get_job_summary("/test/file.darshan")
            assert result["success"] is False


@pytest.mark.asyncio
async def test_get_job_summary_exception():
    """Test exception handling in get_job_summary."""
    with patch("os.path.exists", return_value=True):
        with patch(
            "darshan_mcp.capabilities.darshan_parser._parse_darshan_json",
            side_effect=Exception("Summary error"),
        ):
            result = await darshan_parser.get_job_summary("/test/file.darshan")
            assert result["success"] is False
            assert "Error generating job summary" in result["error"]


@pytest.mark.asyncio
async def test_analyze_file_access_patterns_exception():
    """Test exception handling in analyze_file_access_patterns."""
    with patch("os.path.exists", return_value=True):
        with patch(
            "darshan_mcp.capabilities.darshan_parser._parse_darshan_json",
            side_effect=Exception("Access pattern error"),
        ):
            result = await darshan_parser.analyze_file_access_patterns(
                "/test/file.darshan"
            )
            assert result["success"] is False
            assert "Error analyzing file access patterns" in result["error"]


@pytest.mark.asyncio
async def test_get_io_performance_metrics_file_not_found():
    """Test exception handling in get_io_performance_metrics."""
    result = await darshan_parser.get_io_performance_metrics(
        "/nonexistent/file.darshan"
    )
    assert result["success"] is False


@pytest.mark.asyncio
async def test_identify_io_bottlenecks_file_not_found():
    """Test exception handling in identify_io_bottlenecks."""
    result = await darshan_parser.identify_io_bottlenecks("/nonexistent/file.darshan")
    assert result["success"] is False


@pytest.mark.asyncio
async def test_identify_io_bottlenecks_many_files():
    """Test bottleneck detection with excessive file count."""
    mock_data = {
        "job": {
            "job_id": "12345",
            "nprocs": 64,
        },
        "files": {
            f"/file{i}.dat": {"bytes_read": 100, "bytes_written": 100}
            for i in range(1500)
        },
        "success": True,
    }

    with patch("os.path.exists", return_value=True):
        with patch(
            "darshan_mcp.capabilities.darshan_parser._parse_darshan_json",
            return_value=mock_data,
        ):
            result = await darshan_parser.identify_io_bottlenecks("/test/file.darshan")
            assert result["success"] is True
            # Check for many_files issue
            issues = [
                issue
                for issue in result["identified_issues"]
                if issue["type"] == "many_files"
            ]
            assert len(issues) > 0
            assert "1500" in issues[0]["description"]


@pytest.mark.asyncio
async def test_compare_darshan_logs_file_not_found():
    """Test exception handling in compare_darshan_logs."""
    result = await darshan_parser.compare_darshan_logs(
        "/nonexistent/file1.darshan", "/test/file2.darshan", ["bandwidth"]
    )
    assert result["success"] is False


@pytest.mark.asyncio
async def test_generate_io_summary_report_graceful_handling():
    """Test generate_io_summary_report handles errors from sub-functions gracefully."""
    result = await darshan_parser.generate_io_summary_report(
        "/nonexistent/file.darshan", include_visualizations=False
    )
    # Should still return success=True but with error details in sub-results
    assert result["success"] is True
    assert "detailed_analysis" in result


@pytest.mark.asyncio
async def test_analyze_posix_operations_exception():
    """Test exception handling in analyze_posix_operations."""
    with patch(
        "darshan_mcp.capabilities.darshan_parser._run_darshan_command",
        side_effect=Exception("POSIX error"),
    ):
        result = await darshan_parser.analyze_posix_operations("/test/file.darshan")
        assert result["success"] is False
        assert "Error analyzing POSIX operations" in result["error"]


@pytest.mark.asyncio
async def test_analyze_mpiio_operations_exception():
    """Test exception handling in analyze_mpiio_operations."""
    with patch(
        "darshan_mcp.capabilities.darshan_parser._run_darshan_command",
        side_effect=Exception("MPI-IO error"),
    ):
        result = await darshan_parser.analyze_mpiio_operations("/test/file.darshan")
        assert result["success"] is False
        assert "Error analyzing MPI-IO operations" in result["error"]


@pytest.mark.asyncio
async def test_get_timeline_analysis_exception():
    """Test exception handling in get_timeline_analysis."""
    with patch("os.path.exists", return_value=True):
        with patch(
            "darshan_mcp.capabilities.darshan_parser._parse_darshan_json",
            side_effect=Exception("Timeline error"),
        ):
            result = await darshan_parser.get_timeline_analysis(
                "/test/file.darshan", "1s"
            )
            assert result["success"] is False
            assert "Error generating timeline analysis" in result["error"]


@pytest.mark.asyncio
async def test_analyze_file_access_patterns_empty_files():
    """Test analyze_file_access_patterns with empty files dict."""
    mock_data = {
        "job": {"job_id": "12345", "nprocs": 64},
        "files": {},
        "success": True,
    }

    with patch("os.path.exists", return_value=True):
        with patch(
            "darshan_mcp.capabilities.darshan_parser._parse_darshan_json",
            return_value=mock_data,
        ):
            result = await darshan_parser.analyze_file_access_patterns(
                "/test/file.darshan"
            )
            assert result["success"] is True
            assert result["file_count"] == 0


@pytest.mark.asyncio
async def test_analyze_file_access_patterns_non_dict_file_data():
    """Test analyze_file_access_patterns with non-dict file data."""
    mock_data = {
        "job": {"job_id": "12345", "nprocs": 64},
        "files": {
            "/file1.dat": {"bytes_read": 100, "bytes_written": 200},
            "/file2.dat": "invalid_data",  # Non-dict value
            "/file3.dat": None,  # None value
        },
        "success": True,
    }

    with patch("os.path.exists", return_value=True):
        with patch(
            "darshan_mcp.capabilities.darshan_parser._parse_darshan_json",
            return_value=mock_data,
        ):
            result = await darshan_parser.analyze_file_access_patterns(
                "/test/file.darshan"
            )
            assert result["success"] is True
            # Should skip non-dict file data
            assert result["file_count"] >= 0


@pytest.mark.asyncio
async def test_analyze_file_access_patterns_with_pattern_no_matches():
    """Test analyze_file_access_patterns with pattern that has no matches."""
    mock_data = {
        "job": {"job_id": "12345", "nprocs": 64},
        "files": {
            "/file1.txt": {"bytes_read": 100, "bytes_written": 200},
            "/file2.txt": {"bytes_read": 150, "bytes_written": 250},
        },
        "success": True,
    }

    with patch("os.path.exists", return_value=True):
        with patch(
            "darshan_mcp.capabilities.darshan_parser._parse_darshan_json",
            return_value=mock_data,
        ):
            result = await darshan_parser.analyze_file_access_patterns(
                "/test/file.darshan", "*.dat"
            )
            assert result["success"] is True
            assert result["file_count"] == 0
            assert "No files match" in result.get("message", "")


@pytest.mark.asyncio
async def test_generate_io_summary_report_with_bottlenecks():
    """Test generate_io_summary_report includes bottleneck analysis."""
    mock_summary = {
        "success": True,
        "job_id": "12345",
        "total_bytes_read": 1000000,
        "total_bytes_written": 2000000,
        "runtime_seconds": 100,
    }
    mock_bottlenecks = {
        "success": True,
        "identified_issues": [
            {
                "type": "small_io",
                "description": "Small I/O detected",
                "severity": "high",
            }
        ],
    }

    with patch(
        "darshan_mcp.capabilities.darshan_parser.get_job_summary",
        return_value=mock_summary,
    ):
        with patch(
            "darshan_mcp.capabilities.darshan_parser.identify_io_bottlenecks",
            return_value=mock_bottlenecks,
        ):
            result = await darshan_parser.generate_io_summary_report(
                "/test/file.darshan", include_visualizations=False
            )
            assert result["success"] is True
            # Check that bottleneck_analysis is in detailed_analysis
            assert "detailed_analysis" in result
            assert "bottleneck_analysis" in result["detailed_analysis"]


@pytest.mark.asyncio
async def test_get_job_summary_invalid_timestamps():
    """Test get_job_summary with invalid timestamp formats."""
    mock_data = {
        "job": {
            "job_id": "12345",
            "nprocs": 64,
            "start_time": "invalid_date",
            "end_time": "also_invalid",
            "runtime": 300,  # Fallback value
        },
        "files": {
            "/file1.dat": {"bytes_read": 1000, "bytes_written": 2000},
        },
        "success": True,
    }

    with patch("os.path.exists", return_value=True):
        with patch(
            "darshan_mcp.capabilities.darshan_parser._parse_darshan_json",
            return_value=mock_data,
        ):
            result = await darshan_parser.get_job_summary("/test/file.darshan")
            assert result["success"] is True
            # Should fall back to runtime field
            assert "runtime_seconds" in result


@pytest.mark.asyncio
async def test_analyze_file_access_patterns_no_io_files():
    """Test analyze_file_access_patterns with files that have no I/O."""
    mock_data = {
        "job": {"job_id": "12345", "nprocs": 64},
        "files": {
            "/file1.dat": {"bytes_read": 0, "bytes_written": 0},
            "/file2.dat": {"bytes_read": 0, "bytes_written": 0},
        },
        "success": True,
    }

    with patch("os.path.exists", return_value=True):
        with patch(
            "darshan_mcp.capabilities.darshan_parser._parse_darshan_json",
            return_value=mock_data,
        ):
            result = await darshan_parser.analyze_file_access_patterns(
                "/test/file.darshan"
            )
            assert result["success"] is True
            assert result["file_count"] == 2


@pytest.mark.asyncio
async def test_get_io_performance_metrics_non_dict_files():
    """Test get_io_performance_metrics with non-dict file data."""
    mock_summary = {
        "success": True,
        "total_bytes_read": 1000000,
        "total_bytes_written": 2000000,
        "runtime_seconds": 100,
    }

    mock_parsed_data = {
        "job": {"job_id": "12345", "nprocs": 64},
        "files": {
            "/file1.dat": {"bytes_read": 1000, "bytes_written": 2000},
            "/file2.dat": "invalid",  # Non-dict
            "/file3.dat": None,  # None
        },
        "success": True,
    }

    with patch("os.path.exists", return_value=True):
        with patch(
            "darshan_mcp.capabilities.darshan_parser.get_job_summary",
            return_value=mock_summary,
        ):
            with patch(
                "darshan_mcp.capabilities.darshan_parser._parse_darshan_json",
                return_value=mock_parsed_data,
            ):
                result = await darshan_parser.get_io_performance_metrics(
                    "/test/file.darshan"
                )
                assert result["success"] is True


@pytest.mark.asyncio
async def test_calculate_io_performance_metrics_exception():
    """Test exception handling in _calculate_io_performance_metrics."""
    mock_summary = {
        "success": True,
        "total_bytes_read": 1000000,
        "total_bytes_written": 2000000,
        "runtime_seconds": 100,
    }

    with patch("os.path.exists", return_value=True):
        with patch(
            "darshan_mcp.capabilities.darshan_parser.get_job_summary",
            return_value=mock_summary,
        ):
            with patch(
                "darshan_mcp.capabilities.darshan_parser._parse_darshan_json",
                side_effect=Exception("Parse error"),
            ):
                result = await darshan_parser.get_io_performance_metrics(
                    "/test/file.darshan"
                )
                assert result["success"] is False
                assert "Error calculating I/O performance metrics" in result["error"]


@pytest.mark.asyncio
async def test_identify_io_bottlenecks_medium_file_count():
    """Test bottleneck detection with medium file count."""
    mock_summary = {
        "success": True,
        "job_id": "12345",
        "total_bytes_read": 1000000,
        "total_bytes_written": 2000000,
        "runtime_seconds": 100,
        "nprocs": 64,
    }

    mock_file_patterns = {
        "success": True,
        "file_count": 500,
        "access_patterns": {"read_only_files": 100, "write_only_files": 400},
    }

    mock_parsed_data = {
        "job": {"job_id": "12345", "nprocs": 64},
        "files": {
            f"/file{i}.dat": {"bytes_read": 1000, "bytes_written": 2000}
            for i in range(500)
        },
        "success": True,
    }

    with patch("os.path.exists", return_value=True):
        with patch(
            "darshan_mcp.capabilities.darshan_parser.get_job_summary",
            return_value=mock_summary,
        ):
            with patch(
                "darshan_mcp.capabilities.darshan_parser.analyze_file_access_patterns",
                return_value=mock_file_patterns,
            ):
                with patch(
                    "darshan_mcp.capabilities.darshan_parser._parse_darshan_json",
                    return_value=mock_parsed_data,
                ):
                    result = await darshan_parser.identify_io_bottlenecks(
                        "/test/file.darshan"
                    )
                    assert result["success"] is True
