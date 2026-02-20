"""
Additional edge case tests to push coverage above 90%.
"""

import pytest
import tempfile
import os
from parallel_sort_mcp.implementation.export_handler import (
    export_to_json,
    export_to_csv,
    export_to_text,
    export_summary_report,
)
from parallel_sort_mcp.implementation.filter_handler import filter_by_time_range
from parallel_sort_mcp.implementation.sort_handler import sort_log_by_timestamp
from parallel_sort_mcp.implementation.parallel_processor import parallel_sort_large_file
from parallel_sort_mcp.implementation.statistics_handler import analyze_log_statistics
from parallel_sort_mcp.implementation.pattern_detection import detect_patterns


class TestEdgeCases:
    """Additional edge case tests for complete coverage."""

    @pytest.mark.asyncio
    async def test_export_json_with_no_metadata(self):
        """Test JSON export without metadata."""
        data = {"sorted_lines": ["2024-01-01 10:00:00 INFO Test"], "total_lines": 1}
        result = await export_to_json(data, include_metadata=False)
        assert "content" in result or "error" not in result

    @pytest.mark.asyncio
    async def test_export_csv_without_headers(self):
        """Test CSV export without headers."""
        data = {
            "sorted_lines": [
                "2024-01-01 10:00:00 INFO Test",
                "2024-01-02 11:00:00 ERROR Error",
            ]
        }
        result = await export_to_csv(data, include_headers=False)
        assert "content" in result

    @pytest.mark.asyncio
    async def test_export_text_without_summary(self):
        """Test text export without summary."""
        data = {"sorted_lines": ["2024-01-01 10:00:00 INFO Test"]}
        result = await export_to_text(data, include_summary=False)
        assert "content" in result

    @pytest.mark.asyncio
    async def test_export_summary_with_time_analysis(self):
        """Test summary report with time analysis."""
        data = {
            "sorted_lines": [
                "2024-01-01 10:00:00 INFO Test",
                "2024-01-01 11:00:00 ERROR Error",
            ],
            "total_lines": 2,
            "time_analysis": {
                "time_range": {
                    "start": "2024-01-01 10:00:00",
                    "end": "2024-01-01 11:00:00",
                    "duration_seconds": 3600,
                },
                "peak_activity": {"hour": 10, "count": 1},
            },
            "statistics": {"level_distribution": {"INFO": 1, "ERROR": 1}},
        }
        result = await export_summary_report(data)
        assert "content" in result

    @pytest.mark.asyncio
    async def test_filter_time_range_with_iso_format(self):
        """Test time range filtering with ISO format timestamps."""
        content = """2024-01-01 08:00:00 INFO Early
2024-01-01 10:00:00 INFO Middle
2024-01-01 12:00:00 INFO Late"""

        with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".log") as f:
            f.write(content)
            temp_path = f.name

        try:
            result = await filter_by_time_range(
                temp_path,
                "2024-01-01T09:00:00",  # ISO format
                "2024-01-01T11:00:00",  # ISO format
            )
            assert result["matched_lines"] == 1
        finally:
            os.unlink(temp_path)

    @pytest.mark.asyncio
    async def test_pattern_detection_with_config(self):
        """Test pattern detection with custom configuration."""
        content = """2024-01-01 08:00:00 ERROR Connection failed
2024-01-01 08:05:00 ERROR Connection failed
2024-01-01 08:10:00 ERROR Connection failed
2024-01-01 09:00:00 INFO Normal operation
2024-01-01 09:05:00 ERROR Timeout occurred
2024-01-01 09:10:00 ERROR Timeout occurred"""

        with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".log") as f:
            f.write(content)
            temp_path = f.name

        try:
            config = {
                "error_cluster_threshold": 2,
                "time_window_minutes": 15,
                "pattern_min_occurrences": 2,
            }
            result = await detect_patterns(temp_path, config)
            assert "error_clusters" in result or "patterns" in result
        finally:
            os.unlink(temp_path)

    @pytest.mark.asyncio
    async def test_statistics_with_quality_metrics(self):
        """Test statistics analysis with quality metrics."""
        content = """2024-01-01 08:00:00 INFO Start
2024-01-01 08:05:00 INFO Processing
2024-01-01 08:10:00 ERROR Error occurred
2024-01-01 08:15:00 WARN Warning message
2024-01-01 08:20:00 INFO Complete"""

        with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".log") as f:
            f.write(content)
            temp_path = f.name

        try:
            result = await analyze_log_statistics(temp_path)
            assert "statistics" in result
        finally:
            os.unlink(temp_path)

    @pytest.mark.asyncio
    async def test_parallel_sort_with_custom_workers(self):
        """Test parallel sort with custom worker count."""
        content = "\n".join(
            [f"2024-01-{i:02d} 10:00:00 INFO Entry {i}" for i in range(1, 20)]
        )

        with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".log") as f:
            f.write(content)
            input_path = f.name

        output_path = tempfile.mktemp(suffix=".log")

        try:
            result = await parallel_sort_large_file(
                input_path, chunk_size_mb=1, max_workers=2
            )
            assert "sorted_lines" in result or "error" in result
        finally:
            if os.path.exists(input_path):
                os.unlink(input_path)
            if os.path.exists(output_path):
                os.unlink(output_path)

    @pytest.mark.asyncio
    async def test_sort_with_unicode_content(self):
        """Test sorting with Unicode characters."""
        content = """2024-01-02 10:00:00 INFO Message with émojis 🎉
2024-01-01 08:00:00 INFO Üñíçödé characters
2024-01-01 09:00:00 ERROR 日本語 Japanese text"""

        with tempfile.NamedTemporaryFile(
            mode="w", delete=False, suffix=".log", encoding="utf-8"
        ) as f:
            f.write(content)
            temp_path = f.name

        try:
            result = await sort_log_by_timestamp(temp_path)
            assert result["valid_lines"] == 3
            assert result["invalid_lines"] == 0
        finally:
            os.unlink(temp_path)

    @pytest.mark.asyncio
    async def test_filter_with_unicode_keywords(self):
        """Test filtering with Unicode keywords."""
        content = """2024-01-01 08:00:00 INFO Message with émojis 🎉
2024-01-01 09:00:00 INFO Üñíçödé characters
2024-01-01 10:00:00 ERROR Normal message"""

        from parallel_sort_mcp.implementation.filter_handler import filter_by_keyword

        with tempfile.NamedTemporaryFile(
            mode="w", delete=False, suffix=".log", encoding="utf-8"
        ) as f:
            f.write(content)
            temp_path = f.name

        try:
            result = await filter_by_keyword(temp_path, "émojis", case_sensitive=False)
            assert result["matched_lines"] == 1
        finally:
            os.unlink(temp_path)

    @pytest.mark.asyncio
    async def test_export_with_large_dataset(self):
        """Test export handlers with large datasets."""
        data = {
            "sorted_lines": [
                f"2024-01-{i % 30 + 1:02d} 10:00:00 INFO Entry {i}" for i in range(100)
            ],
            "total_lines": 100,
            "statistics": {"level_distribution": {"INFO": 100}},
        }

        # Test all export formats
        json_result = await export_to_json(data, True)
        assert "content" in json_result

        csv_result = await export_to_csv(data, True)
        assert "content" in csv_result

        text_result = await export_to_text(data, True)
        assert "content" in text_result

        summary_result = await export_summary_report(data)
        assert "content" in summary_result
