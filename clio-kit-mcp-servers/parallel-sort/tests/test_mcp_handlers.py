"""
Tests for MCP handlers.
"""

import pytest
import tempfile
import os
from parallel_sort_mcp.mcp_handlers import (
    sort_log_handler,
    parallel_sort_handler,
    analyze_statistics_handler,
    detect_patterns_handler,
    filter_logs_handler,
    filter_time_range_handler,
    filter_level_handler,
    filter_keyword_handler,
    filter_preset_handler,
    export_json_handler,
    export_csv_handler,
    export_text_handler,
    summary_report_handler,
)


class TestMCPHandlers:
    """Test suite for MCP handler functionality."""

    @pytest.fixture
    def sample_log_content(self):
        """Create sample log content for testing."""
        return """2024-01-02 10:00:00 INFO Second entry
2024-01-01 08:30:00 DEBUG First entry
2024-01-01 09:00:00 ERROR Third entry"""

    @pytest.fixture
    def sample_log_file(self, sample_log_content):
        """Create a temporary log file for testing."""
        with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".log") as f:
            f.write(sample_log_content)
            temp_path = f.name
        yield temp_path
        if os.path.exists(temp_path):
            os.unlink(temp_path)

    @pytest.mark.asyncio
    async def test_sort_log_handler_success(self, sample_log_content):
        """Test successful log sorting through MCP handler."""
        test_content = """2024-01-02 10:00:00 INFO Second entry
2024-01-01 08:30:00 DEBUG First entry"""

        with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".log") as f:
            f.write(test_content)
            temp_path = f.name

        try:
            result = await sort_log_handler(temp_path)

            # Should return the actual sort result, not MCP error format
            assert "error" not in result or result.get("error") is None
            assert "sorted_lines" in result
            assert result["total_lines"] == 2
            assert result["valid_lines"] == 2

        finally:
            os.unlink(temp_path)

    @pytest.mark.asyncio
    async def test_sort_log_handler_file_not_found(self):
        """Test MCP handler with non-existent file."""
        # The implementation returns error dict (not raises), so handler returns it
        result = await sort_log_handler("/nonexistent/file.log")

        # The implementation itself returns {"error": "..."} for file not found
        assert "error" in result
        assert "not found" in result["error"].lower()

    @pytest.mark.asyncio
    async def test_sort_log_handler_empty_file(self):
        """Test MCP handler with empty file."""
        with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".log") as f:
            temp_path = f.name

        try:
            result = await sort_log_handler(temp_path)

            assert "error" not in result or result.get("error") is None
            assert result["total_lines"] == 0
            assert result["sorted_lines"] == []
            assert "empty" in result["message"].lower()

        finally:
            os.unlink(temp_path)

    @pytest.mark.asyncio
    async def test_parallel_sort_handler_success(self, sample_log_file):
        """Test parallel sort handler with valid input."""
        output_file = tempfile.mktemp(suffix=".log")
        try:
            result = await parallel_sort_handler(sample_log_file, 1, 2)
            assert "error" not in result or result.get("error") is None
        finally:
            if os.path.exists(output_file):
                os.unlink(output_file)

    @pytest.mark.asyncio
    async def test_parallel_sort_handler_file_not_found(self):
        """Test parallel sort handler with non-existent file."""
        result = await parallel_sort_handler("/nonexistent/file.log")
        assert "error" in result

    @pytest.mark.asyncio
    async def test_analyze_statistics_handler_success(self, sample_log_file):
        """Test analyze statistics handler."""
        result = await analyze_statistics_handler(sample_log_file)
        assert "error" not in result or result.get("error") is None
        assert "statistics" in result or "total_lines" in result

    @pytest.mark.asyncio
    async def test_analyze_statistics_handler_error(self):
        """Test analyze statistics handler with error."""
        result = await analyze_statistics_handler("/nonexistent/file.log")
        assert "error" in result

    @pytest.mark.asyncio
    async def test_detect_patterns_handler_success(self, sample_log_file):
        """Test detect patterns handler."""
        result = await detect_patterns_handler(sample_log_file, None)
        assert "error" not in result or result.get("error") is None

    @pytest.mark.asyncio
    async def test_detect_patterns_handler_error(self):
        """Test detect patterns handler with error."""
        result = await detect_patterns_handler("/nonexistent/file.log", None)
        assert "error" in result

    @pytest.mark.asyncio
    async def test_filter_logs_handler_success(self, sample_log_file):
        """Test filter logs handler."""
        conditions = [{"field": "level", "operator": "equals", "value": "ERROR"}]
        result = await filter_logs_handler(sample_log_file, conditions, "and")
        assert "filtered_lines" in result
        assert len(result["filtered_lines"]) > 0

    @pytest.mark.asyncio
    async def test_filter_logs_handler_error(self):
        """Test filter logs handler with error."""
        conditions = [{"field": "level", "operator": "equals", "value": "ERROR"}]
        result = await filter_logs_handler("/nonexistent/file.log", conditions, "and")
        assert "error" in result

    @pytest.mark.asyncio
    async def test_filter_time_range_handler_success(self, sample_log_file):
        """Test filter time range handler."""
        result = await filter_time_range_handler(
            sample_log_file, "2024-01-01 08:00:00", "2024-01-01 10:00:00"
        )
        assert "filtered_lines" in result

    @pytest.mark.asyncio
    async def test_filter_time_range_handler_error(self):
        """Test filter time range handler with error."""
        result = await filter_time_range_handler(
            "/nonexistent/file.log", "2024-01-01 08:00:00", "2024-01-01 10:00:00"
        )
        assert "error" in result

    @pytest.mark.asyncio
    async def test_filter_level_handler_success(self, sample_log_file):
        """Test filter level handler."""
        result = await filter_level_handler(sample_log_file, "ERROR", False)
        assert "filtered_lines" in result

    @pytest.mark.asyncio
    async def test_filter_level_handler_error(self):
        """Test filter level handler with error."""
        result = await filter_level_handler("/nonexistent/file.log", "ERROR", False)
        assert "error" in result

    @pytest.mark.asyncio
    async def test_filter_keyword_handler_success(self, sample_log_file):
        """Test filter keyword handler."""
        result = await filter_keyword_handler(sample_log_file, "entry", False, False)
        assert "filtered_lines" in result

    @pytest.mark.asyncio
    async def test_filter_keyword_handler_error(self):
        """Test filter keyword handler with error."""
        result = await filter_keyword_handler(
            "/nonexistent/file.log", "entry", False, False
        )
        assert "error" in result

    @pytest.mark.asyncio
    async def test_filter_preset_handler_success(self, sample_log_file):
        """Test filter preset handler."""
        result = await filter_preset_handler(sample_log_file, "errors_only")
        assert "filtered_lines" in result

    @pytest.mark.asyncio
    async def test_filter_preset_handler_error(self):
        """Test filter preset handler with error."""
        result = await filter_preset_handler("/nonexistent/file.log", "errors_only")
        assert "error" in result

    @pytest.mark.asyncio
    async def test_export_json_handler_success(self):
        """Test export JSON handler."""
        data = {"test": "data", "items": [1, 2, 3]}
        result = await export_json_handler(data, True)
        assert "error" not in result or result.get("error") is None

    @pytest.mark.asyncio
    async def test_export_json_handler_error(self):
        """Test export JSON handler with invalid data."""
        # The implementation handles None gracefully and returns an error dict
        result = await export_json_handler(None, True)
        assert "error" in result

    @pytest.mark.asyncio
    async def test_export_csv_handler_success(self):
        """Test export CSV handler."""
        data = {
            "sorted_lines": [
                "2024-01-01 10:00:00 INFO Test message",
                "2024-01-02 11:00:00 ERROR Error message",
            ]
        }
        result = await export_csv_handler(data, True)
        assert "error" not in result or result.get("error") is None

    @pytest.mark.asyncio
    async def test_export_csv_handler_error(self):
        """Test export CSV handler with error."""
        result = await export_csv_handler(None, True)
        assert "error" in result

    @pytest.mark.asyncio
    async def test_export_text_handler_success(self):
        """Test export text handler."""
        data = {
            "sorted_lines": [
                "2024-01-01 10:00:00 INFO Test message",
                "2024-01-02 11:00:00 ERROR Error message",
            ]
        }
        result = await export_text_handler(data, True)
        assert "error" not in result or result.get("error") is None

    @pytest.mark.asyncio
    async def test_export_text_handler_error(self):
        """Test export text handler with error."""
        result = await export_text_handler(None, True)
        assert "error" in result

    @pytest.mark.asyncio
    async def test_summary_report_handler_success(self):
        """Test summary report handler."""
        data = {
            "total_lines": 100,
            "filtered_lines": ["test line"],
            "statistics": {"level_distribution": {"ERROR": 10}},
        }
        result = await summary_report_handler(data)
        assert "error" not in result or result.get("error") is None

    @pytest.mark.asyncio
    async def test_summary_report_handler_error(self):
        """Test summary report handler with error."""
        result = await summary_report_handler(None)
        assert "error" in result
