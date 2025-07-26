"""Tests for Darshan parser capabilities."""

import pytest
from unittest.mock import patch
import os
import sys

# Add the src directory to the path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from darshan_mcp.capabilities import darshan_parser


@pytest.mark.asyncio
async def test_load_darshan_log_file_not_found():
    """Test loading a non-existent Darshan log file."""
    result = await darshan_parser.load_darshan_log("/nonexistent/file.darshan")

    assert result["success"] is False
    assert "not found" in result["error"]


@pytest.mark.asyncio
async def test_load_darshan_log_success():
    """Test successful loading of a Darshan log file."""
    mock_data = {
        "job": {
            "job_id": "12345",
            "nprocs": 64,
            "start_time": "2024-01-01T10:00:00Z",
            "end_time": "2024-01-01T10:30:00Z",
        },
        "modules": ["POSIX", "MPIIO", "STDIO"],
        "files": {
            "/path/to/file1.dat": {"bytes_read": 1000, "bytes_written": 0},
            "/path/to/file2.dat": {"bytes_read": 0, "bytes_written": 2000},
        },
        "success": True,
    }

    with patch(
        "darshan_mcp.capabilities.darshan_parser._parse_darshan_json"
    ) as mock_parse:
        with patch("os.path.exists", return_value=True):
            with patch("os.path.getsize", return_value=1024000):
                mock_parse.return_value = mock_data

                result = await darshan_parser.load_darshan_log("/test/file.darshan")

                assert result["success"] is True
                assert result["job_info"]["job_id"] == "12345"
                assert result["modules"] == ["POSIX", "MPIIO", "STDIO"]
                assert result["file_count"] == 2


@pytest.mark.asyncio
async def test_get_job_summary():
    """Test job summary generation."""
    mock_data = {
        "job": {
            "job_id": "12345",
            "user_id": "testuser",
            "nprocs": 32,
            "start_time": "2024-01-01T10:00:00Z",
            "end_time": "2024-01-01T10:30:00Z",
        },
        "files": {
            "file1": {
                "bytes_read": 1000000,
                "bytes_written": 500000,
                "read_ops": 100,
                "write_ops": 50,
            },
            "file2": {
                "bytes_read": 2000000,
                "bytes_written": 1000000,
                "read_ops": 200,
                "write_ops": 100,
            },
        },
        "modules": ["POSIX"],
        "success": True,
    }

    with patch(
        "darshan_mcp.capabilities.darshan_parser._parse_darshan_json"
    ) as mock_parse:
        mock_parse.return_value = mock_data

        result = await darshan_parser.get_job_summary("/test/file.darshan")

        assert result["success"] is True
        assert result["job_id"] == "12345"
        assert result["nprocs"] == 32
        assert result["total_bytes_read"] == 3000000
        assert result["total_bytes_written"] == 1500000
        assert result["total_read_operations"] == 300
        assert result["total_write_operations"] == 150


@pytest.mark.asyncio
async def test_analyze_file_access_patterns():
    """Test file access pattern analysis."""
    mock_data = {
        "files": {
            "/data/input.dat": {
                "bytes_read": 1000000,
                "bytes_written": 0,
                "read_ops": 100,
                "write_ops": 0,
                "sequential_reads": 80,
                "sequential_writes": 0,
                "file_size": 1000000,
            },
            "/data/output.dat": {
                "bytes_read": 0,
                "bytes_written": 2000000,
                "read_ops": 0,
                "write_ops": 200,
                "sequential_reads": 0,
                "sequential_writes": 150,
                "file_size": 2000000,
            },
            "/tmp/random.tmp": {
                "bytes_read": 500000,
                "bytes_written": 500000,
                "read_ops": 500,
                "write_ops": 500,
                "sequential_reads": 100,
                "sequential_writes": 100,
                "file_size": 1000000,
            },
        },
        "success": True,
    }

    with patch(
        "darshan_mcp.capabilities.darshan_parser._parse_darshan_json"
    ) as mock_parse:
        mock_parse.return_value = mock_data

        result = await darshan_parser.analyze_file_access_patterns("/test/file.darshan")

        assert result["success"] is True
        assert result["file_count"] == 3
        assert result["read_only_files"] == 1
        assert result["write_only_files"] == 1
        assert result["read_write_files"] == 1
        assert result["sequential_access"] == 2  # input.dat and output.dat
        assert result["random_access"] == 1  # random.tmp


@pytest.mark.asyncio
async def test_analyze_file_access_patterns_with_filter():
    """Test file access pattern analysis with file pattern filter."""
    mock_data = {
        "files": {
            "/data/input.dat": {
                "bytes_read": 1000000,
                "bytes_written": 0,
                "read_ops": 100,
                "write_ops": 0,
                "file_size": 1000000,
            },
            "/data/output.dat": {
                "bytes_read": 0,
                "bytes_written": 2000000,
                "read_ops": 0,
                "write_ops": 200,
                "file_size": 2000000,
            },
            "/tmp/temp.tmp": {
                "bytes_read": 500000,
                "bytes_written": 0,
                "read_ops": 50,
                "write_ops": 0,
                "file_size": 500000,
            },
        },
        "success": True,
    }

    with patch(
        "darshan_mcp.capabilities.darshan_parser._parse_darshan_json"
    ) as mock_parse:
        mock_parse.return_value = mock_data

        result = await darshan_parser.analyze_file_access_patterns(
            "/test/file.darshan", "*.dat"
        )

        assert result["success"] is True
        assert result["file_count"] == 2  # Only .dat files
        assert result["filter_pattern"] == "*.dat"


@pytest.mark.asyncio
async def test_get_io_performance_metrics():
    """Test I/O performance metrics calculation."""
    mock_data = {
        "job": {"nprocs": 16},
        "files": {
            "file1": {
                "bytes_read": 1000000,
                "bytes_written": 500000,
                "read_ops": 100,
                "write_ops": 50,
                "read_time": 10.0,
                "write_time": 5.0,
            },
            "file2": {
                "bytes_read": 2000000,
                "bytes_written": 1000000,
                "read_ops": 200,
                "write_ops": 100,
                "read_time": 20.0,
                "write_time": 10.0,
            },
        },
        "success": True,
    }

    with patch(
        "darshan_mcp.capabilities.darshan_parser._parse_darshan_json"
    ) as mock_parse:
        mock_parse.return_value = mock_data

        result = await darshan_parser.get_io_performance_metrics("/test/file.darshan")

        assert result["success"] is True
        assert "read_metrics" in result
        assert "write_metrics" in result
        assert "overall_metrics" in result

        # Check read metrics
        read_metrics = result["read_metrics"]
        assert read_metrics["total_bytes"] == 3000000
        assert read_metrics["total_operations"] == 300
        assert read_metrics["avg_request_size"] == 10000  # 3000000 / 300

        # Check write metrics
        write_metrics = result["write_metrics"]
        assert write_metrics["total_bytes"] == 1500000
        assert write_metrics["total_operations"] == 150
        assert write_metrics["avg_request_size"] == 10000  # 1500000 / 150


@pytest.mark.asyncio
async def test_identify_io_bottlenecks():
    """Test I/O bottleneck identification."""
    # Mock performance metrics with small I/O operations
    perf_metrics = {
        "success": True,
        "read_metrics": {
            "avg_request_size": 1024,  # Small reads (1KB)
            "bandwidth_mbps": 50,
        },
        "write_metrics": {
            "avg_request_size": 2048,  # Small writes (2KB)
            "bandwidth_mbps": 30,
        },
        "overall_metrics": {"total_bandwidth_mbps": 80},
    }

    # Mock file patterns with many random access files
    file_patterns = {
        "success": True,
        "file_count": 100,
        "random_access": 60,  # 60% random access
        "sequential_access": 40,
    }

    with patch(
        "darshan_mcp.capabilities.darshan_parser.get_io_performance_metrics"
    ) as mock_perf:
        with patch(
            "darshan_mcp.capabilities.darshan_parser.analyze_file_access_patterns"
        ) as mock_patterns:
            mock_perf.return_value = perf_metrics
            mock_patterns.return_value = file_patterns

            result = await darshan_parser.identify_io_bottlenecks("/test/file.darshan")

            assert result["success"] is True
            assert len(result["identified_issues"]) > 0
            assert len(result["recommendations"]) > 0
            assert result["severity_score"] > 0

            # Should identify small I/O and random access issues
            issue_types = [issue["type"] for issue in result["identified_issues"]]
            assert "small_reads" in issue_types
            assert "small_writes" in issue_types
            assert "random_access" in issue_types


@pytest.mark.asyncio
async def test_compare_darshan_logs():
    """Test comparison of two Darshan log files."""
    metrics_1 = {
        "success": True,
        "overall_metrics": {"total_bandwidth_mbps": 100, "total_iops": 1000},
    }

    metrics_2 = {
        "success": True,
        "overall_metrics": {"total_bandwidth_mbps": 150, "total_iops": 1200},
    }

    with patch(
        "darshan_mcp.capabilities.darshan_parser.get_io_performance_metrics"
    ) as mock_perf:
        mock_perf.side_effect = [metrics_1, metrics_2]

        result = await darshan_parser.compare_darshan_logs(
            "/test/file1.darshan", "/test/file2.darshan", ["bandwidth", "iops"]
        )

        assert result["success"] is True
        assert result["log_file_1"] == "/test/file1.darshan"
        assert result["log_file_2"] == "/test/file2.darshan"

        # Check bandwidth comparison
        bw_diff = result["differences"]["bandwidth"]
        assert bw_diff["log_1"] == 100
        assert bw_diff["log_2"] == 150
        assert bw_diff["difference"] == 50
        assert bw_diff["percent_change"] == 50.0

        # Check IOPS comparison
        iops_diff = result["differences"]["iops"]
        assert iops_diff["log_1"] == 1000
        assert iops_diff["log_2"] == 1200
        assert iops_diff["difference"] == 200
        assert iops_diff["percent_change"] == 20.0


@pytest.mark.asyncio
async def test_generate_io_summary_report():
    """Test comprehensive I/O summary report generation."""
    job_summary = {
        "success": True,
        "total_io_volume": 1024**3,  # 1GB
        "runtime_seconds": 3600,  # 1 hour
        "nprocs": 64,
    }

    file_patterns = {"success": True}
    performance = {"success": True, "overall_metrics": {"total_bandwidth_mbps": 200}}
    bottlenecks = {
        "success": True,
        "identified_issues": [{"description": "Test issue", "severity": "medium"}],
        "recommendations": ["Test recommendation"],
    }

    with patch("darshan_mcp.capabilities.darshan_parser.get_job_summary") as mock_job:
        with patch(
            "darshan_mcp.capabilities.darshan_parser.analyze_file_access_patterns"
        ) as mock_patterns:
            with patch(
                "darshan_mcp.capabilities.darshan_parser.get_io_performance_metrics"
            ) as mock_perf:
                with patch(
                    "darshan_mcp.capabilities.darshan_parser.identify_io_bottlenecks"
                ) as mock_bottlenecks:
                    mock_job.return_value = job_summary
                    mock_patterns.return_value = file_patterns
                    mock_perf.return_value = performance
                    mock_bottlenecks.return_value = bottlenecks

                    result = await darshan_parser.generate_io_summary_report(
                        "/test/file.darshan"
                    )

                    assert result["success"] is True
                    assert "executive_summary" in result
                    assert "detailed_analysis" in result
                    assert "key_findings" in result
                    assert "recommendations" in result

                    # Check executive summary
                    exec_summary = result["executive_summary"]
                    assert exec_summary["total_io_volume_gb"] == 1.0
                    assert exec_summary["runtime_minutes"] == 60.0
                    assert exec_summary["process_count"] == 64

                    # Check that key findings and recommendations are populated
                    assert len(result["key_findings"]) > 0
                    assert len(result["recommendations"]) > 0


@pytest.mark.asyncio
async def test_run_darshan_command_not_found():
    """Test handling when darshan-parser is not found."""
    with patch(
        "darshan_mcp.capabilities.darshan_parser.asyncio.create_subprocess_exec"
    ) as mock_exec:
        mock_exec.side_effect = FileNotFoundError()

        stdout, stderr, returncode = await darshan_parser._run_darshan_command(
            ["--help"], "/test/file.darshan"
        )

        assert returncode == 1
        assert "darshan-parser command not found" in stderr
        assert stdout == ""
