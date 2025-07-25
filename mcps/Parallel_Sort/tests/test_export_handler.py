"""
Tests for the export handler capability.
"""

import pytest
import json
import csv
import io
from implementation.export_handler import (
    export_to_json,
    export_to_csv,
    export_to_text,
    export_summary_report,
)


class TestExportHandler:
    """Test suite for export handler functionality."""

    @pytest.mark.asyncio
    async def test_export_to_json_basic(self):
        """Test basic JSON export functionality."""
        test_data = {
            "sorted_lines": [
                "2024-01-01 08:30:00 INFO First entry",
                "2024-01-01 09:15:00 ERROR Second entry",
            ],
            "total_lines": 2,
            "valid_lines": 2,
            "invalid_lines": 0,
        }

        result = await export_to_json(test_data, include_metadata=True)

        assert "error" not in result
        assert result["format"] == "json"
        assert "content" in result
        assert "size_bytes" in result

        # Parse the JSON content to verify it's valid
        parsed_content = json.loads(result["content"])
        assert "export_format" in parsed_content
        assert "data" in parsed_content
        assert parsed_content["data"]["total_lines"] == 2

    @pytest.mark.asyncio
    async def test_export_to_json_without_metadata(self):
        """Test JSON export without metadata."""
        test_data = {
            "sorted_lines": ["2024-01-01 08:30:00 INFO Test entry"],
            "_meta": {"tool": "sort"},
            "isError": False,
        }

        result = await export_to_json(test_data, include_metadata=False)

        assert result["format"] == "json"
        parsed_content = json.loads(result["content"])

        # Metadata fields should not be in the cleaned data
        assert "_meta" not in str(parsed_content["data"])
        assert "isError" not in str(parsed_content["data"])

    @pytest.mark.asyncio
    async def test_export_to_csv_basic(self):
        """Test basic CSV export functionality."""
        test_data = {
            "sorted_lines": [
                "2024-01-01 08:30:00 INFO Application started",
                "2024-01-01 09:15:00 ERROR Connection failed",
                "2024-01-01 10:00:00 WARN Memory usage high",
            ],
            "total_lines": 3,
            "valid_lines": 3,
        }

        result = await export_to_csv(test_data, include_headers=True)

        assert "error" not in result
        assert result["format"] == "csv"
        assert result["rows_exported"] == 3
        assert result["headers_included"] is True

        # Parse CSV content
        csv_reader = csv.DictReader(io.StringIO(result["content"]))
        rows = list(csv_reader)

        assert len(rows) == 3
        assert "timestamp" in rows[0]
        assert "level" in rows[0]
        assert "message" in rows[0]

        # Check first row
        assert rows[0]["timestamp"] == "2024-01-01 08:30:00"
        assert rows[0]["level"] == "INFO"
        assert "Application started" in rows[0]["message"]

    @pytest.mark.asyncio
    async def test_export_to_csv_without_headers(self):
        """Test CSV export without headers."""
        test_data = {"sorted_lines": ["2024-01-01 08:30:00 INFO Test message"]}

        result = await export_to_csv(test_data, include_headers=False)

        assert result["headers_included"] is False

        # Should not start with column names
        lines = result["content"].split("\n")
        assert not lines[0].startswith("line_number,timestamp")

    @pytest.mark.asyncio
    async def test_export_to_csv_no_data(self):
        """Test CSV export with no sorted lines."""
        test_data = {"sorted_lines": []}

        result = await export_to_csv(test_data)

        assert "error" in result
        assert "No log entries to export" in result["error"]

    @pytest.mark.asyncio
    async def test_export_to_text_with_summary(self):
        """Test text export with summary."""
        test_data = {
            "sorted_lines": [
                "2024-01-01 08:30:00 INFO First entry",
                "2024-01-01 09:15:00 ERROR Second entry",
            ],
            "total_lines": 3,
            "valid_lines": 2,
            "invalid_lines": 1,
            "invalid_entries": [
                {
                    "line_number": 2,
                    "content": "Invalid line",
                    "error": "No timestamp found",
                }
            ],
        }

        result = await export_to_text(test_data, include_summary=True)

        assert "error" not in result
        assert result["format"] == "text"
        assert result["summary_included"] is True

        content = result["content"]
        assert "LOG PROCESSING SUMMARY" in content
        assert "Total lines processed: 3" in content
        assert "Valid entries: 2" in content
        assert "INVALID ENTRIES:" in content
        assert "Invalid line" in content

    @pytest.mark.asyncio
    async def test_export_to_text_without_summary(self):
        """Test text export without summary."""
        test_data = {"sorted_lines": ["2024-01-01 08:30:00 INFO Test entry"]}

        result = await export_to_text(test_data, include_summary=False)

        assert result["summary_included"] is False
        content = result["content"]
        assert "LOG PROCESSING SUMMARY" not in content
        assert "2024-01-01 08:30:00 INFO Test entry" in content

    @pytest.mark.asyncio
    async def test_export_summary_report(self):
        """Test summary report generation."""
        test_data = {
            "sorted_lines": [
                "2024-01-01 08:30:00 INFO Application started",
                "2024-01-01 09:15:00 ERROR Database connection failed",
                "2024-01-01 10:00:00 WARN Memory usage high",
                "2024-01-01 11:30:00 ERROR Authentication failed",
            ],
            "total_lines": 4,
            "valid_lines": 4,
            "invalid_lines": 0,
        }

        result = await export_summary_report(test_data)

        assert "error" not in result
        assert result["format"] == "summary_report"
        assert "structured_data" in result

        structured = result["structured_data"]
        assert "processing_statistics" in structured
        assert "log_level_distribution" in structured
        assert "time_analysis" in structured

        # Check processing statistics
        stats = structured["processing_statistics"]
        assert stats["total_lines_processed"] == 4
        assert stats["valid_entries"] == 4
        assert stats["success_rate"] == 100.0

        # Check log level distribution
        levels = structured["log_level_distribution"]
        assert "INFO" in levels
        assert "ERROR" in levels
        assert "WARN" in levels
        assert levels["ERROR"] == 2  # Two ERROR entries

        # Check content formatting
        content = result["content"]
        assert "LOG PROCESSING SUMMARY REPORT" in content
        assert "PROCESSING STATISTICS:" in content
        assert "LOG LEVEL DISTRIBUTION:" in content

    @pytest.mark.asyncio
    async def test_export_summary_report_with_time_analysis(self):
        """Test summary report with time analysis."""
        test_data = {
            "sorted_lines": [
                "2024-01-01 08:30:00 INFO First entry",
                "2024-01-01 18:30:00 INFO Last entry",
            ],
            "total_lines": 2,
            "valid_lines": 2,
            "invalid_lines": 0,
        }

        result = await export_summary_report(test_data)

        structured = result["structured_data"]
        time_analysis = structured["time_analysis"]

        assert "earliest_timestamp" in time_analysis
        assert "latest_timestamp" in time_analysis
        assert "time_span_seconds" in time_analysis
        assert time_analysis["time_span_seconds"] == 36000.0  # 10 hours

    @pytest.mark.asyncio
    async def test_export_empty_data(self):
        """Test exporting empty or minimal data."""
        test_data = {"sorted_lines": []}

        # JSON export should work with empty data
        json_result = await export_to_json(test_data)
        assert "error" not in json_result

        # CSV export should handle empty data
        csv_result = await export_to_csv(test_data)
        assert "error" in csv_result

        # Text export should work with empty data
        text_result = await export_to_text(test_data)
        assert "error" not in text_result

        # Summary report should work with empty data
        summary_result = await export_summary_report(test_data)
        assert "error" not in summary_result

    @pytest.mark.asyncio
    async def test_export_invalid_data_types(self):
        """Test export functions with invalid data types."""
        # Test with None
        json_result = await export_to_json(None)
        assert "error" in json_result

        # Test with string instead of dict
        csv_result = await export_to_csv("invalid_data")
        assert "error" in csv_result

        # Test with list instead of dict
        text_result = await export_to_text([])
        assert "error" in text_result
