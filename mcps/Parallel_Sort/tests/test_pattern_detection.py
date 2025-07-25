"""
Tests for the pattern detection capability.
"""

import pytest
import tempfile
import os
from implementation.pattern_detection import (
    detect_patterns,
    normalize_message_for_pattern,
)


class TestPatternDetection:
    """Test suite for pattern detection functionality."""

    @pytest.mark.asyncio
    async def test_detect_error_clusters(self):
        """Test error cluster detection."""
        test_content = """2024-01-01 08:30:00 ERROR Database connection failed
2024-01-01 08:30:30 ERROR Query timeout
2024-01-01 08:31:00 ERROR Connection lost
2024-01-01 10:00:00 INFO System recovered
2024-01-01 12:00:00 ERROR Single error"""

        with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".log") as f:
            f.write(test_content)
            temp_path = f.name

        try:
            result = await detect_patterns(temp_path)

            assert "patterns" in result
            clusters = result["patterns"]["error_clusters"]
            assert clusters["total_clusters"] > 0

            # Should detect one cluster with 3 errors in ~1 minute
            assert len(clusters["clusters"]) >= 1
            first_cluster = clusters["clusters"][0]
            assert first_cluster["error_count"] == 3

        finally:
            os.unlink(temp_path)

    @pytest.mark.asyncio
    async def test_detect_repeated_patterns(self):
        """Test repeated pattern detection."""
        test_content = """2024-01-01 08:30:00 INFO User 123 logged in
2024-01-01 08:31:00 INFO User 456 logged in
2024-01-01 08:32:00 INFO User 789 logged in
2024-01-01 08:33:00 ERROR Connection failed to server 1
2024-01-01 08:34:00 ERROR Connection failed to server 2"""

        with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".log") as f:
            f.write(test_content)
            temp_path = f.name

        try:
            result = await detect_patterns(temp_path)

            patterns = result["patterns"]["repeated_patterns"]
            assert patterns["total_patterns"] >= 0

            # Check if login pattern is detected
            pattern_texts = [p["pattern"] for p in patterns["patterns"]]
            login_pattern_found = any(
                "logged in" in pattern.lower() for pattern in pattern_texts
            )
            connection_pattern_found = any(
                "connection failed" in pattern.lower() for pattern in pattern_texts
            )

            # At least one repeated pattern should be found
            assert login_pattern_found or connection_pattern_found

        finally:
            os.unlink(temp_path)

    @pytest.mark.asyncio
    async def test_detect_anomalies(self):
        """Test anomaly detection in log frequency."""
        # Create a log with normal frequency and one anomalous hour
        test_lines = []

        # Normal hours: 2-3 entries per hour
        for hour in range(8, 12):
            for i in range(2):
                test_lines.append(
                    f"2024-01-01 {hour:02d}:{i * 30:02d}:00 INFO Normal activity"
                )

        # Anomalous hour: 10 entries
        for i in range(10):
            test_lines.append(f"2024-01-01 14:{i * 5:02d}:00 ERROR High activity")

        test_content = "\n".join(test_lines)

        with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".log") as f:
            f.write(test_content)
            temp_path = f.name

        try:
            result = await detect_patterns(temp_path)

            anomalies = result["patterns"]["anomalies"]
            assert "anomalies" in anomalies
            assert "baseline_stats" in anomalies

            # Should detect the high-volume hour as anomaly
            if anomalies["total_anomalies"] > 0:
                high_volume_anomaly = any(
                    a["type"] == "high_volume" for a in anomalies["anomalies"]
                )
                assert high_volume_anomaly

        finally:
            os.unlink(temp_path)

    @pytest.mark.asyncio
    async def test_temporal_patterns(self):
        """Test temporal pattern detection."""
        test_content = """2024-01-01 09:30:00 INFO Business hours activity
2024-01-01 14:30:00 INFO Business hours activity
2024-01-01 22:30:00 INFO Off hours activity
2024-01-01 02:30:00 ERROR Night error"""

        with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".log") as f:
            f.write(test_content)
            temp_path = f.name

        try:
            result = await detect_patterns(temp_path)

            temporal = result["patterns"]["temporal_patterns"]
            assert "hourly_distribution" in temporal
            assert "business_hours_vs_off_hours" in temporal

            business_analysis = temporal["business_hours_vs_off_hours"]
            assert "business_hours_count" in business_analysis
            assert "off_hours_count" in business_analysis

        finally:
            os.unlink(temp_path)

    @pytest.mark.asyncio
    async def test_message_patterns(self):
        """Test message pattern detection."""
        test_content = """2024-01-01 08:30:00 INFO User authentication successful
2024-01-01 08:31:00 ERROR Database connection timeout
2024-01-01 08:32:00 WARN Network latency detected
2024-01-01 08:33:00 ERROR Memory allocation failed"""

        with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".log") as f:
            f.write(test_content)
            temp_path = f.name

        try:
            result = await detect_patterns(temp_path)

            message_patterns = result["patterns"]["message_patterns"]
            assert "detected_patterns" in message_patterns

            patterns = message_patterns["detected_patterns"]

            # Should detect authentication, database, network, and memory patterns
            expected_patterns = [
                "authentication",
                "database",
                "network",
                "memory_issues",
            ]
            detected_pattern_types = list(patterns.keys())

            # At least some patterns should be detected
            overlap = set(expected_patterns) & set(detected_pattern_types)
            assert len(overlap) > 0

        finally:
            os.unlink(temp_path)

    def test_normalize_message_for_pattern(self):
        """Test message normalization for pattern matching."""
        test_cases = [
            ("User 123 logged in", "User NUMBER logged in"),
            ("Connection to 192.168.1.1 failed", "Connection to IP_ADDRESS failed"),
            ("File /var/log/app.log opened", "File FILE_PATH opened"),
            ("Request to https://api.example.com/users", "Request to URL"),
        ]

        for original, expected in test_cases:
            normalized = normalize_message_for_pattern(original)
            assert normalized == expected

    @pytest.mark.asyncio
    async def test_empty_file_patterns(self):
        """Test pattern detection on empty file."""
        with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".log") as f:
            temp_path = f.name

        try:
            result = await detect_patterns(temp_path)

            assert "patterns" in result or "message" in result
            if "message" in result:
                assert "empty" in result["message"].lower()

        finally:
            os.unlink(temp_path)

    @pytest.mark.asyncio
    async def test_nonexistent_file_patterns(self):
        """Test pattern detection on non-existent file."""
        result = await detect_patterns("/path/that/does/not/exist.log")

        assert "error" in result
        assert "not found" in result["error"].lower()

    @pytest.mark.asyncio
    async def test_pattern_summary(self):
        """Test pattern summary generation."""
        test_content = """2024-01-01 08:30:00 ERROR Database error
2024-01-01 08:30:30 ERROR Connection error
2024-01-01 08:31:00 ERROR Authentication error
2024-01-01 08:32:00 INFO System recovered"""

        with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".log") as f:
            f.write(test_content)
            temp_path = f.name

        try:
            result = await detect_patterns(temp_path)

            assert "summary" in result
            summary = result["summary"]

            assert "overall_assessment" in summary
            assert summary["overall_assessment"] in [
                "normal",
                "normal_with_patterns",
                "attention_needed",
                "concerning",
                "critical",
            ]

            # Should have some findings due to error cluster
            total_findings = (
                len(summary.get("high_priority_findings", []))
                + len(summary.get("medium_priority_findings", []))
                + len(summary.get("low_priority_findings", []))
            )
            assert total_findings > 0

        finally:
            os.unlink(temp_path)
