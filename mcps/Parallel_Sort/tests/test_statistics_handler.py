"""
Tests for the statistics handler capability.
"""

import pytest
import tempfile
import os
from implementation.statistics_handler import analyze_log_statistics, parse_log_entry


class TestStatisticsHandler:
    """Test suite for statistics handler functionality."""

    @pytest.mark.asyncio
    async def test_analyze_basic_statistics(self):
        """Test basic statistics analysis."""
        test_content = """2024-01-01 08:30:00 DEBUG System initialized
2024-01-01 09:15:00 WARN Memory usage high
2024-01-01 10:00:00 INFO Application started
2024-01-01 11:30:00 ERROR Connection failed
Invalid line without timestamp"""

        with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".log") as f:
            f.write(test_content)
            temp_path = f.name

        try:
            result = await analyze_log_statistics(temp_path)

            assert "error" not in result
            assert result["total_lines"] == 5
            assert result["valid_entries"] == 4
            assert result["invalid_entries"] == 1

            # Check basic statistics
            stats = result["statistics"]["basic_statistics"]
            assert stats["total_lines"] == 5
            assert stats["valid_entries"] == 4
            assert stats["invalid_entries"] == 1
            assert stats["success_rate"] == 80.0

        finally:
            os.unlink(temp_path)

    @pytest.mark.asyncio
    async def test_log_level_analysis(self):
        """Test log level distribution analysis."""
        test_content = """2024-01-01 08:30:00 ERROR First error
2024-01-01 09:15:00 ERROR Second error
2024-01-01 10:00:00 WARN Warning message
2024-01-01 11:30:00 INFO Info message"""

        with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".log") as f:
            f.write(test_content)
            temp_path = f.name

        try:
            result = await analyze_log_statistics(temp_path)

            level_analysis = result["statistics"]["log_level_analysis"]
            level_dist = level_analysis["level_distribution"]

            assert "ERROR" in level_dist
            assert level_dist["ERROR"]["count"] == 2
            assert level_dist["ERROR"]["percentage"] == 50.0

            assert "WARN" in level_dist
            assert level_dist["WARN"]["count"] == 1
            assert level_dist["WARN"]["percentage"] == 25.0

            assert level_analysis["error_rate"] == 50.0

        finally:
            os.unlink(temp_path)

    @pytest.mark.asyncio
    async def test_temporal_analysis(self):
        """Test temporal analysis features."""
        test_content = """2024-01-01 08:30:00 INFO First entry
2024-01-01 12:00:00 INFO Middle entry
2024-01-01 18:30:00 INFO Last entry"""

        with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".log") as f:
            f.write(test_content)
            temp_path = f.name

        try:
            result = await analyze_log_statistics(temp_path)

            temporal = result["statistics"]["temporal_analysis"]
            assert "earliest_entry" in temporal
            assert "latest_entry" in temporal
            assert "duration_seconds" in temporal
            assert temporal["total_events"] == 3

            # Duration should be 10 hours (36000 seconds)
            assert temporal["duration_seconds"] == 36000.0

        finally:
            os.unlink(temp_path)

    @pytest.mark.asyncio
    async def test_empty_file_analysis(self):
        """Test analysis of empty file."""
        with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".log") as f:
            temp_path = f.name

        try:
            result = await analyze_log_statistics(temp_path)

            assert "error" not in result
            assert result["total_lines"] == 0
            assert "empty" in result["message"].lower()

        finally:
            os.unlink(temp_path)

    @pytest.mark.asyncio
    async def test_nonexistent_file(self):
        """Test analysis of non-existent file."""
        result = await analyze_log_statistics("/path/that/does/not/exist.log")

        assert "error" in result
        assert "not found" in result["error"].lower()

    def test_parse_log_entry_valid(self):
        """Test parsing valid log entries."""
        test_line = "2024-01-15 14:30:25 ERROR Test error message"
        entry = parse_log_entry(test_line)

        assert entry["level"] == "ERROR"
        assert entry["message"] == "Test error message"
        assert entry["timestamp"].year == 2024
        assert entry["timestamp"].month == 1
        assert entry["timestamp"].day == 15

    def test_parse_log_entry_invalid(self):
        """Test parsing invalid log entries."""
        invalid_lines = [
            "No timestamp here",
            "2024/01/15 14:30:25 Wrong format",
            "Invalid entry",
        ]

        for line in invalid_lines:
            with pytest.raises(ValueError):
                parse_log_entry(line)

    @pytest.mark.asyncio
    async def test_quality_metrics(self):
        """Test data quality metrics generation."""
        test_content = """2024-01-01 08:30:00 INFO Valid entry 1
2024-01-01 09:15:00 WARN Valid entry 2
Invalid line
2024-01-01 10:00:00 ERROR Valid entry 3"""

        with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".log") as f:
            f.write(test_content)
            temp_path = f.name

        try:
            result = await analyze_log_statistics(temp_path)

            quality = result["statistics"]["quality_metrics"]
            assert "completeness_score" in quality
            assert "consistency_score" in quality
            assert "overall_quality_score" in quality
            assert "recommendations" in quality

            # Should be 75% complete (3 valid out of 4 lines)
            assert quality["completeness_score"] == 75.0

        finally:
            os.unlink(temp_path)
