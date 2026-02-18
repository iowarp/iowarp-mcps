"""
Tests for MCP handlers error paths and exception handling.
"""

import pytest
from unittest.mock import patch

from fastmcp.exceptions import ToolError
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


class TestMCPHandlersErrorPaths:
    """Test suite for MCP handlers error handling paths."""

    @pytest.mark.asyncio
    @patch("parallel_sort_mcp.mcp_handlers.sort_log_by_timestamp")
    async def test_sort_log_handler_exception_path(self, mock_sort):
        """Test sort_log_handler exception handling."""
        mock_sort.side_effect = RuntimeError("Unexpected error")

        with pytest.raises(ToolError, match="sort_log failed"):
            await sort_log_handler("test.log")

    @pytest.mark.asyncio
    @patch("parallel_sort_mcp.mcp_handlers.parallel_sort_large_file")
    async def test_parallel_sort_handler_exception_path(self, mock_sort):
        """Test parallel_sort_handler exception handling."""
        mock_sort.side_effect = ValueError("Invalid chunk size")

        with pytest.raises(ToolError, match="parallel_sort failed"):
            await parallel_sort_handler("test.log", 100, 4)

    @pytest.mark.asyncio
    @patch("parallel_sort_mcp.mcp_handlers.analyze_log_statistics")
    async def test_analyze_statistics_handler_exception_path(self, mock_analyze):
        """Test analyze_statistics_handler exception handling."""
        mock_analyze.side_effect = IOError("File read error")

        with pytest.raises(ToolError, match="analyze_statistics failed"):
            await analyze_statistics_handler("test.log")

    @pytest.mark.asyncio
    @patch("parallel_sort_mcp.mcp_handlers.detect_patterns")
    async def test_detect_patterns_handler_exception_path(self, mock_detect):
        """Test detect_patterns_handler exception handling."""
        mock_detect.side_effect = KeyError("Missing pattern config")

        with pytest.raises(ToolError, match="detect_patterns failed"):
            await detect_patterns_handler("test.log", None)

    @pytest.mark.asyncio
    @patch("parallel_sort_mcp.mcp_handlers.filter_logs")
    async def test_filter_logs_handler_exception_path(self, mock_filter):
        """Test filter_logs_handler exception handling."""
        mock_filter.side_effect = TypeError("Invalid filter condition")

        with pytest.raises(ToolError, match="filter_logs failed"):
            await filter_logs_handler("test.log", [], "and")

    @pytest.mark.asyncio
    @patch("parallel_sort_mcp.mcp_handlers.filter_by_time_range")
    async def test_filter_time_range_handler_exception_path(self, mock_filter):
        """Test filter_time_range_handler exception handling."""
        mock_filter.side_effect = ValueError("Invalid time format")

        with pytest.raises(ToolError, match="filter_time_range failed"):
            await filter_time_range_handler("test.log", "invalid", "invalid")

    @pytest.mark.asyncio
    @patch("parallel_sort_mcp.mcp_handlers.filter_by_log_level")
    async def test_filter_level_handler_exception_path(self, mock_filter):
        """Test filter_level_handler exception handling."""
        mock_filter.side_effect = AttributeError("Missing level attribute")

        with pytest.raises(ToolError, match="filter_level failed"):
            await filter_level_handler("test.log", "ERROR", False)

    @pytest.mark.asyncio
    @patch("parallel_sort_mcp.mcp_handlers.filter_by_keyword")
    async def test_filter_keyword_handler_exception_path(self, mock_filter):
        """Test filter_keyword_handler exception handling."""
        mock_filter.side_effect = IndexError("Invalid keyword index")

        with pytest.raises(ToolError, match="filter_keyword failed"):
            await filter_keyword_handler("test.log", "error", False, False)

    @pytest.mark.asyncio
    @patch("parallel_sort_mcp.mcp_handlers.apply_filter_preset")
    async def test_filter_preset_handler_exception_path(self, mock_filter):
        """Test filter_preset_handler exception handling."""
        mock_filter.side_effect = LookupError("Preset not found")

        with pytest.raises(ToolError, match="filter_preset failed"):
            await filter_preset_handler("test.log", "invalid_preset")

    @pytest.mark.asyncio
    @patch("parallel_sort_mcp.mcp_handlers.export_to_json")
    async def test_export_json_handler_exception_path(self, mock_export):
        """Test export_json_handler exception handling."""
        mock_export.side_effect = TypeError("Cannot serialize object")

        with pytest.raises(ToolError, match="export_json failed"):
            await export_json_handler({"data": "test"}, True)

    @pytest.mark.asyncio
    @patch("parallel_sort_mcp.mcp_handlers.export_to_csv")
    async def test_export_csv_handler_exception_path(self, mock_export):
        """Test export_csv_handler exception handling."""
        mock_export.side_effect = ValueError("Invalid CSV format")

        with pytest.raises(ToolError, match="export_csv failed"):
            await export_csv_handler({"data": "test"}, True)

    @pytest.mark.asyncio
    @patch("parallel_sort_mcp.mcp_handlers.export_to_text")
    async def test_export_text_handler_exception_path(self, mock_export):
        """Test export_text_handler exception handling."""
        mock_export.side_effect = UnicodeEncodeError("utf-8", "", 0, 1, "Cannot encode")

        with pytest.raises(ToolError, match="export_text failed"):
            await export_text_handler({"data": "test"}, True)

    @pytest.mark.asyncio
    @patch("parallel_sort_mcp.mcp_handlers.export_summary_report")
    async def test_summary_report_handler_exception_path(self, mock_export):
        """Test summary_report_handler exception handling."""
        mock_export.side_effect = RuntimeError("Report generation failed")

        with pytest.raises(ToolError, match="summary_report failed"):
            await summary_report_handler({"data": "test"})

    @pytest.mark.asyncio
    @patch("parallel_sort_mcp.mcp_handlers.sort_log_by_timestamp")
    async def test_sort_log_handler_generic_exception(self, mock_sort):
        """Test sort_log_handler with generic Exception."""
        mock_sort.side_effect = Exception("Generic error")

        with pytest.raises(ToolError, match="sort_log failed"):
            await sort_log_handler("test.log")

    @pytest.mark.asyncio
    @patch("parallel_sort_mcp.mcp_handlers.parallel_sort_large_file")
    async def test_parallel_sort_handler_memory_error(self, mock_sort):
        """Test parallel_sort_handler with MemoryError."""
        mock_sort.side_effect = MemoryError("Out of memory")

        with pytest.raises(ToolError, match="parallel_sort failed"):
            await parallel_sort_handler("test.log", 100, 4)

    @pytest.mark.asyncio
    @patch("parallel_sort_mcp.mcp_handlers.filter_logs")
    async def test_filter_logs_handler_permission_error(self, mock_filter):
        """Test filter_logs_handler with PermissionError."""
        mock_filter.side_effect = PermissionError("Access denied")

        with pytest.raises(ToolError, match="filter_logs failed"):
            await filter_logs_handler("test.log", [], "and")
