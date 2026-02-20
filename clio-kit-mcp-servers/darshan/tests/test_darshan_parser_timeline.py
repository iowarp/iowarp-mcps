"""Tests for Darshan parser timeline analysis function."""

import pytest
from unittest.mock import patch

from darshan_mcp.capabilities import darshan_parser


@pytest.mark.asyncio
async def test_get_timeline_analysis_with_valid_timestamps():
    """Test get_timeline_analysis with valid ISO format timestamps."""
    mock_data = {
        "job": {
            "job_id": "12345",
            "start_time": "2024-01-01T10:00:00Z",
            "end_time": "2024-01-01T10:30:00Z",
        },
        "success": True,
    }

    with patch(
        "darshan_mcp.capabilities.darshan_parser._parse_darshan_json"
    ) as mock_parse:
        mock_parse.return_value = mock_data

        result = await darshan_parser.get_timeline_analysis(
            "/test/file.darshan", time_resolution="1s"
        )

        assert result["success"] is True
        assert result["time_resolution"] == "1s"
        assert "analysis" in result
        assert result["analysis"]["total_duration"] == 1800.0  # 30 minutes in seconds
        assert "peak_periods" in result["analysis"]
        assert "idle_periods" in result["analysis"]
        assert "io_phases" in result["analysis"]


@pytest.mark.asyncio
async def test_get_timeline_analysis_with_microsecond_timestamps():
    """Test get_timeline_analysis with timestamps including microseconds."""
    mock_data = {
        "job": {
            "job_id": "12345",
            "start_time": "2024-01-01T10:00:00.123456Z",
            "end_time": "2024-01-01T10:00:05.654321Z",
        },
        "success": True,
    }

    with patch(
        "darshan_mcp.capabilities.darshan_parser._parse_darshan_json"
    ) as mock_parse:
        mock_parse.return_value = mock_data

        result = await darshan_parser.get_timeline_analysis("/test/file.darshan")

        assert result["success"] is True
        # Duration should be approximately 5.53 seconds
        assert result["analysis"]["total_duration"] is not None
        assert 5.5 <= result["analysis"]["total_duration"] <= 5.6


@pytest.mark.asyncio
async def test_get_timeline_analysis_with_missing_start_time():
    """Test get_timeline_analysis when start_time is missing."""
    mock_data = {
        "job": {
            "job_id": "12345",
            "end_time": "2024-01-01T10:30:00Z",
        },
        "success": True,
    }

    with patch(
        "darshan_mcp.capabilities.darshan_parser._parse_darshan_json"
    ) as mock_parse:
        mock_parse.return_value = mock_data

        result = await darshan_parser.get_timeline_analysis("/test/file.darshan")

        assert result["success"] is True
        assert result["analysis"]["total_duration"] is None


@pytest.mark.asyncio
async def test_get_timeline_analysis_with_missing_end_time():
    """Test get_timeline_analysis when end_time is missing."""
    mock_data = {
        "job": {
            "job_id": "12345",
            "start_time": "2024-01-01T10:00:00Z",
        },
        "success": True,
    }

    with patch(
        "darshan_mcp.capabilities.darshan_parser._parse_darshan_json"
    ) as mock_parse:
        mock_parse.return_value = mock_data

        result = await darshan_parser.get_timeline_analysis("/test/file.darshan")

        assert result["success"] is True
        assert result["analysis"]["total_duration"] is None


@pytest.mark.asyncio
async def test_get_timeline_analysis_with_missing_timestamps():
    """Test get_timeline_analysis when both timestamps are missing."""
    mock_data = {
        "job": {
            "job_id": "12345",
            "nprocs": 16,
        },
        "success": True,
    }

    with patch(
        "darshan_mcp.capabilities.darshan_parser._parse_darshan_json"
    ) as mock_parse:
        mock_parse.return_value = mock_data

        result = await darshan_parser.get_timeline_analysis("/test/file.darshan")

        assert result["success"] is True
        assert result["analysis"]["total_duration"] is None
        assert "message" in result
        assert "requires timestamp data" in result["message"]


@pytest.mark.asyncio
async def test_get_timeline_analysis_with_invalid_timestamp_format():
    """Test get_timeline_analysis with invalid timestamp format."""
    mock_data = {
        "job": {
            "job_id": "12345",
            "start_time": "invalid-timestamp",
            "end_time": "2024-01-01T10:30:00Z",
        },
        "success": True,
    }

    with patch(
        "darshan_mcp.capabilities.darshan_parser._parse_darshan_json"
    ) as mock_parse:
        mock_parse.return_value = mock_data

        result = await darshan_parser.get_timeline_analysis("/test/file.darshan")

        # Should handle the error gracefully
        assert result["success"] is True
        assert result["analysis"]["total_duration"] is None


@pytest.mark.asyncio
async def test_get_timeline_analysis_with_malformed_end_timestamp():
    """Test get_timeline_analysis with malformed end_time."""
    mock_data = {
        "job": {
            "job_id": "12345",
            "start_time": "2024-01-01T10:00:00Z",
            "end_time": "not-a-date",
        },
        "success": True,
    }

    with patch(
        "darshan_mcp.capabilities.darshan_parser._parse_darshan_json"
    ) as mock_parse:
        mock_parse.return_value = mock_data

        result = await darshan_parser.get_timeline_analysis("/test/file.darshan")

        # Should handle the error gracefully
        assert result["success"] is True
        assert result["analysis"]["total_duration"] is None


@pytest.mark.asyncio
async def test_get_timeline_analysis_with_1s_resolution():
    """Test get_timeline_analysis with 1 second time resolution."""
    mock_data = {
        "job": {
            "start_time": "2024-01-01T10:00:00Z",
            "end_time": "2024-01-01T10:00:10Z",
        },
        "success": True,
    }

    with patch(
        "darshan_mcp.capabilities.darshan_parser._parse_darshan_json"
    ) as mock_parse:
        mock_parse.return_value = mock_data

        result = await darshan_parser.get_timeline_analysis(
            "/test/file.darshan", time_resolution="1s"
        )

        assert result["success"] is True
        assert result["time_resolution"] == "1s"
        assert result["analysis"]["total_duration"] == 10.0


@pytest.mark.asyncio
async def test_get_timeline_analysis_with_100ms_resolution():
    """Test get_timeline_analysis with 100 millisecond time resolution."""
    mock_data = {
        "job": {
            "start_time": "2024-01-01T10:00:00Z",
            "end_time": "2024-01-01T10:01:00Z",
        },
        "success": True,
    }

    with patch(
        "darshan_mcp.capabilities.darshan_parser._parse_darshan_json"
    ) as mock_parse:
        mock_parse.return_value = mock_data

        result = await darshan_parser.get_timeline_analysis(
            "/test/file.darshan", time_resolution="100ms"
        )

        assert result["success"] is True
        assert result["time_resolution"] == "100ms"
        assert result["analysis"]["total_duration"] == 60.0


@pytest.mark.asyncio
async def test_get_timeline_analysis_with_10ms_resolution():
    """Test get_timeline_analysis with 10 millisecond time resolution."""
    mock_data = {
        "job": {
            "start_time": "2024-01-01T10:00:00Z",
            "end_time": "2024-01-01T10:00:01Z",
        },
        "success": True,
    }

    with patch(
        "darshan_mcp.capabilities.darshan_parser._parse_darshan_json"
    ) as mock_parse:
        mock_parse.return_value = mock_data

        result = await darshan_parser.get_timeline_analysis(
            "/test/file.darshan", time_resolution="10ms"
        )

        assert result["success"] is True
        assert result["time_resolution"] == "10ms"
        assert result["analysis"]["total_duration"] == 1.0


@pytest.mark.asyncio
async def test_get_timeline_analysis_default_time_resolution():
    """Test get_timeline_analysis uses default time resolution of 1s."""
    mock_data = {
        "job": {
            "start_time": "2024-01-01T10:00:00Z",
            "end_time": "2024-01-01T10:00:30Z",
        },
        "success": True,
    }

    with patch(
        "darshan_mcp.capabilities.darshan_parser._parse_darshan_json"
    ) as mock_parse:
        mock_parse.return_value = mock_data

        result = await darshan_parser.get_timeline_analysis("/test/file.darshan")

        assert result["success"] is True
        assert result["time_resolution"] == "1s"  # Default value
        assert result["analysis"]["total_duration"] == 30.0


@pytest.mark.asyncio
async def test_get_timeline_analysis_with_empty_job_info():
    """Test get_timeline_analysis with empty job information."""
    mock_data = {
        "job": {},
        "success": True,
    }

    with patch(
        "darshan_mcp.capabilities.darshan_parser._parse_darshan_json"
    ) as mock_parse:
        mock_parse.return_value = mock_data

        result = await darshan_parser.get_timeline_analysis("/test/file.darshan")

        assert result["success"] is True
        assert result["analysis"]["total_duration"] is None


@pytest.mark.asyncio
async def test_get_timeline_analysis_with_missing_job_key():
    """Test get_timeline_analysis when job key is missing from parsed data."""
    mock_data = {
        "files": {},
        "success": True,
    }

    with patch(
        "darshan_mcp.capabilities.darshan_parser._parse_darshan_json"
    ) as mock_parse:
        mock_parse.return_value = mock_data

        result = await darshan_parser.get_timeline_analysis("/test/file.darshan")

        assert result["success"] is True
        assert result["analysis"]["total_duration"] is None


@pytest.mark.asyncio
async def test_get_timeline_analysis_exception_handling():
    """Test get_timeline_analysis exception handling when parser fails."""
    with patch(
        "darshan_mcp.capabilities.darshan_parser._parse_darshan_json"
    ) as mock_parse:
        mock_parse.side_effect = Exception("Parser failed")

        result = await darshan_parser.get_timeline_analysis("/test/file.darshan")

        assert result["success"] is False
        assert "error" in result
        assert "Error generating timeline analysis" in result["error"]
        assert "Parser failed" in result["error"]


@pytest.mark.asyncio
async def test_get_timeline_analysis_with_null_timestamps():
    """Test get_timeline_analysis when timestamps are explicitly None."""
    mock_data = {
        "job": {
            "job_id": "12345",
            "start_time": None,
            "end_time": None,
        },
        "success": True,
    }

    with patch(
        "darshan_mcp.capabilities.darshan_parser._parse_darshan_json"
    ) as mock_parse:
        mock_parse.return_value = mock_data

        result = await darshan_parser.get_timeline_analysis("/test/file.darshan")

        # When timestamps are None, calling .replace() raises AttributeError
        # which is caught by the outer exception handler
        assert result["success"] is False
        assert "error" in result
        assert "Error generating timeline analysis" in result["error"]


@pytest.mark.asyncio
async def test_get_timeline_analysis_structure():
    """Test that get_timeline_analysis returns correct data structure."""
    mock_data = {
        "job": {
            "start_time": "2024-01-01T10:00:00Z",
            "end_time": "2024-01-01T11:00:00Z",
        },
        "success": True,
    }

    with patch(
        "darshan_mcp.capabilities.darshan_parser._parse_darshan_json"
    ) as mock_parse:
        mock_parse.return_value = mock_data

        result = await darshan_parser.get_timeline_analysis(
            "/test/file.darshan", time_resolution="1s"
        )

        # Check top-level structure
        assert "success" in result
        assert "time_resolution" in result
        assert "message" in result
        assert "analysis" in result

        # Check analysis structure
        analysis = result["analysis"]
        assert "total_duration" in analysis
        assert "peak_periods" in analysis
        assert "idle_periods" in analysis
        assert "io_phases" in analysis

        # Check types
        assert isinstance(result["success"], bool)
        assert isinstance(result["time_resolution"], str)
        assert isinstance(analysis["peak_periods"], list)
        assert isinstance(analysis["idle_periods"], list)
        assert isinstance(analysis["io_phases"], list)


@pytest.mark.asyncio
async def test_get_timeline_analysis_with_zero_duration():
    """Test get_timeline_analysis when start and end times are the same."""
    mock_data = {
        "job": {
            "start_time": "2024-01-01T10:00:00Z",
            "end_time": "2024-01-01T10:00:00Z",
        },
        "success": True,
    }

    with patch(
        "darshan_mcp.capabilities.darshan_parser._parse_darshan_json"
    ) as mock_parse:
        mock_parse.return_value = mock_data

        result = await darshan_parser.get_timeline_analysis("/test/file.darshan")

        assert result["success"] is True
        assert result["analysis"]["total_duration"] == 0.0


@pytest.mark.asyncio
async def test_get_timeline_analysis_with_negative_duration():
    """Test get_timeline_analysis when end_time is before start_time."""
    mock_data = {
        "job": {
            "start_time": "2024-01-01T10:30:00Z",
            "end_time": "2024-01-01T10:00:00Z",  # Earlier than start
        },
        "success": True,
    }

    with patch(
        "darshan_mcp.capabilities.darshan_parser._parse_darshan_json"
    ) as mock_parse:
        mock_parse.return_value = mock_data

        result = await darshan_parser.get_timeline_analysis("/test/file.darshan")

        assert result["success"] is True
        # Should calculate negative duration
        assert result["analysis"]["total_duration"] == -1800.0


@pytest.mark.asyncio
async def test_get_timeline_analysis_with_long_duration():
    """Test get_timeline_analysis with a very long job duration (multiple days)."""
    mock_data = {
        "job": {
            "start_time": "2024-01-01T00:00:00Z",
            "end_time": "2024-01-05T12:30:45Z",  # 4.5 days later
        },
        "success": True,
    }

    with patch(
        "darshan_mcp.capabilities.darshan_parser._parse_darshan_json"
    ) as mock_parse:
        mock_parse.return_value = mock_data

        result = await darshan_parser.get_timeline_analysis("/test/file.darshan")

        assert result["success"] is True
        # 4 days = 345600 seconds, 12 hours = 43200, 30 min = 1800, 45 sec = 45
        expected_duration = 345600 + 43200 + 1800 + 45
        assert result["analysis"]["total_duration"] == expected_duration


@pytest.mark.asyncio
async def test_get_timeline_analysis_with_timezone_aware_timestamps():
    """Test get_timeline_analysis with timezone-aware timestamps."""
    mock_data = {
        "job": {
            "start_time": "2024-01-01T10:00:00+00:00",
            "end_time": "2024-01-01T10:15:00+00:00",
        },
        "success": True,
    }

    with patch(
        "darshan_mcp.capabilities.darshan_parser._parse_darshan_json"
    ) as mock_parse:
        mock_parse.return_value = mock_data

        result = await darshan_parser.get_timeline_analysis("/test/file.darshan")

        assert result["success"] is True
        assert result["analysis"]["total_duration"] == 900.0  # 15 minutes


@pytest.mark.asyncio
async def test_get_timeline_analysis_parser_mock_called():
    """Test that _parse_darshan_json is called with correct arguments."""
    mock_data = {
        "job": {},
        "success": True,
    }

    with patch(
        "darshan_mcp.capabilities.darshan_parser._parse_darshan_json"
    ) as mock_parse:
        mock_parse.return_value = mock_data

        await darshan_parser.get_timeline_analysis("/test/file.darshan")

        # Verify the mock was called with the correct file path
        mock_parse.assert_called_once_with("/test/file.darshan")
