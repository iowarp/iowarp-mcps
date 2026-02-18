"""
Tests for advanced filter handler functionality.
Tests for operators and edge cases not covered by main filter tests.
"""

import pytest
import tempfile
import os
from datetime import datetime
from parallel_sort_mcp.implementation.filter_handler import (
    filter_logs,
    parse_log_entry,
    apply_filters,
    evaluate_entry_conditions,
    evaluate_single_condition,
    get_field_value,
    apply_operator,
    compare_values,
    parse_time_string,
    FilterOperator,
)


class TestAdvancedFilterOperations:
    """Test suite for advanced filter operations."""

    @pytest.fixture
    def sample_log_file(self):
        """Create a temporary log file for testing."""
        content = """2024-01-01 08:00:00 INFO First message
2024-01-01 09:00:00 ERROR Second message
2024-01-01 10:00:00 WARN Third message"""
        with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".log") as f:
            f.write(content)
            temp_path = f.name
        yield temp_path
        if os.path.exists(temp_path):
            os.unlink(temp_path)

    def test_parse_log_entry_valid(self):
        """Test parsing a valid log entry."""
        line = "2024-01-01 10:00:00 ERROR Test message"
        entry = parse_log_entry(line)

        assert entry["level"] == "ERROR"
        assert entry["message"] == "Test message"
        assert isinstance(entry["timestamp"], datetime)
        assert entry["is_valid"] is True

    def test_parse_log_entry_invalid(self):
        """Test parsing an invalid log entry."""
        line = "Invalid line without timestamp"

        with pytest.raises(ValueError):
            parse_log_entry(line)

    def test_parse_log_entry_no_level(self):
        """Test parsing log entry without level."""
        line = "2024-01-01 10:00:00"
        entry = parse_log_entry(line)

        assert entry["level"] == ""
        assert entry["message"] == ""

    def test_apply_filters_empty_conditions(self):
        """Test applying filters with empty conditions."""
        entries = [{"level": "ERROR", "message": "test"}]
        result = apply_filters(entries, [], "and")
        assert result == entries

    def test_evaluate_entry_conditions_and(self):
        """Test evaluating entry with AND conditions."""
        entry = {"level": "ERROR", "message": "test message"}
        conditions = [
            {"field": "level", "operator": "equals", "value": "ERROR"},
            {"field": "message", "operator": "contains", "value": "test"},
        ]

        assert evaluate_entry_conditions(entry, conditions, "and") is True

    def test_evaluate_entry_conditions_or(self):
        """Test evaluating entry with OR conditions."""
        entry = {"level": "INFO", "message": "test message"}
        conditions = [
            {"field": "level", "operator": "equals", "value": "ERROR"},
            {"field": "message", "operator": "contains", "value": "test"},
        ]

        assert evaluate_entry_conditions(entry, conditions, "or") is True

    def test_evaluate_entry_conditions_default(self):
        """Test evaluating entry with invalid logical operator."""
        entry = {"level": "ERROR", "message": "test"}
        conditions = [{"field": "level", "operator": "equals", "value": "ERROR"}]

        # Invalid operator defaults to AND
        assert evaluate_entry_conditions(entry, conditions, "invalid") is True

    def test_get_field_value_nested(self):
        """Test getting nested field value."""
        entry = {"metadata": {"user": "admin"}}
        value = get_field_value(entry, "metadata.user")
        assert value == "admin"

    def test_get_field_value_nested_missing(self):
        """Test getting nested field value when path doesn't exist."""
        entry = {"metadata": {}}
        value = get_field_value(entry, "metadata.user.name")
        assert value == ""

    def test_get_field_value_direct(self):
        """Test getting direct field value."""
        entry = {"level": "ERROR", "message": "test"}
        assert get_field_value(entry, "level") == "ERROR"
        assert get_field_value(entry, "message") == "test"

    def test_apply_operator_equals(self):
        """Test EQUALS operator."""
        assert apply_operator("ERROR", FilterOperator.EQUALS.value, "ERROR") is True
        assert apply_operator("ERROR", FilterOperator.EQUALS.value, "INFO") is False

    def test_apply_operator_not_equals(self):
        """Test NOT_EQUALS operator."""
        assert apply_operator("ERROR", FilterOperator.NOT_EQUALS.value, "INFO") is True
        assert (
            apply_operator("ERROR", FilterOperator.NOT_EQUALS.value, "ERROR") is False
        )

    def test_apply_operator_contains(self):
        """Test CONTAINS operator."""
        assert (
            apply_operator("test message", FilterOperator.CONTAINS.value, "test")
            is True
        )
        assert (
            apply_operator("test message", FilterOperator.CONTAINS.value, "missing")
            is False
        )

    def test_apply_operator_not_contains(self):
        """Test NOT_CONTAINS operator."""
        assert (
            apply_operator("test message", FilterOperator.NOT_CONTAINS.value, "missing")
            is True
        )
        assert (
            apply_operator("test message", FilterOperator.NOT_CONTAINS.value, "test")
            is False
        )

    def test_apply_operator_starts_with(self):
        """Test STARTS_WITH operator."""
        assert (
            apply_operator("test message", FilterOperator.STARTS_WITH.value, "test")
            is True
        )
        assert (
            apply_operator("test message", FilterOperator.STARTS_WITH.value, "message")
            is False
        )

    def test_apply_operator_ends_with(self):
        """Test ENDS_WITH operator."""
        assert (
            apply_operator("test message", FilterOperator.ENDS_WITH.value, "message")
            is True
        )
        assert (
            apply_operator("test message", FilterOperator.ENDS_WITH.value, "test")
            is False
        )

    def test_apply_operator_regex(self):
        """Test REGEX operator."""
        assert apply_operator("test123", FilterOperator.REGEX.value, r"\d+") is True
        assert apply_operator("test", FilterOperator.REGEX.value, r"\d+") is False

    def test_apply_operator_regex_invalid(self):
        """Test REGEX operator with invalid regex."""
        assert apply_operator("test", FilterOperator.REGEX.value, "[invalid") is False

    def test_apply_operator_greater_than(self):
        """Test GREATER_THAN operator."""
        assert apply_operator(10, FilterOperator.GREATER_THAN.value, 5) is True
        assert apply_operator(5, FilterOperator.GREATER_THAN.value, 10) is False

    def test_apply_operator_less_than(self):
        """Test LESS_THAN operator."""
        assert apply_operator(5, FilterOperator.LESS_THAN.value, 10) is True
        assert apply_operator(10, FilterOperator.LESS_THAN.value, 5) is False

    def test_apply_operator_between(self):
        """Test BETWEEN operator."""
        assert apply_operator(5, FilterOperator.BETWEEN.value, [1, 10]) is True
        assert apply_operator(15, FilterOperator.BETWEEN.value, [1, 10]) is False

    def test_apply_operator_between_invalid(self):
        """Test BETWEEN operator with invalid value."""
        assert apply_operator(5, FilterOperator.BETWEEN.value, [1]) is False
        assert apply_operator(5, FilterOperator.BETWEEN.value, "not a list") is False

    def test_apply_operator_in(self):
        """Test IN operator."""
        assert (
            apply_operator("ERROR", FilterOperator.IN.value, ["ERROR", "WARN"]) is True
        )
        assert (
            apply_operator("INFO", FilterOperator.IN.value, ["ERROR", "WARN"]) is False
        )

    def test_apply_operator_in_invalid(self):
        """Test IN operator with non-list value."""
        assert apply_operator("ERROR", FilterOperator.IN.value, "not a list") is False

    def test_apply_operator_not_in(self):
        """Test NOT_IN operator."""
        assert (
            apply_operator("INFO", FilterOperator.NOT_IN.value, ["ERROR", "WARN"])
            is True
        )
        assert (
            apply_operator("ERROR", FilterOperator.NOT_IN.value, ["ERROR", "WARN"])
            is False
        )

    def test_apply_operator_not_in_invalid(self):
        """Test NOT_IN operator with non-list value."""
        assert (
            apply_operator("ERROR", FilterOperator.NOT_IN.value, "not a list") is True
        )

    def test_apply_operator_none_value(self):
        """Test operator with None field value."""
        assert apply_operator(None, FilterOperator.EQUALS.value, "") is True

    def test_apply_operator_unknown(self):
        """Test unknown operator."""
        assert apply_operator("test", "unknown_operator", "value") is False

    def test_compare_values_datetime(self):
        """Test comparing datetime values."""
        dt1 = datetime(2024, 1, 1, 10, 0, 0)
        dt2 = datetime(2024, 1, 1, 9, 0, 0)

        assert compare_values(dt1, dt2, ">") is True
        assert compare_values(dt2, dt1, "<") is True
        assert compare_values(dt1, dt1, ">=") is True
        assert compare_values(dt1, dt1, "<=") is True

    def test_compare_values_datetime_string(self):
        """Test comparing datetime with string."""
        dt1 = datetime(2024, 1, 1, 10, 0, 0)

        assert compare_values(dt1, "2024-01-01 09:00:00", ">") is True
        assert compare_values(dt1, "2024-01-01 11:00:00", "<") is True

    def test_compare_values_datetime_invalid_string(self):
        """Test comparing datetime with invalid string."""
        dt1 = datetime(2024, 1, 1, 10, 0, 0)

        assert compare_values(dt1, "invalid", ">") is False

    def test_compare_values_numeric(self):
        """Test comparing numeric values."""
        assert compare_values(10, 5, ">") is True
        assert compare_values(5, 10, "<") is True
        assert compare_values(10, 10, ">=") is True
        assert compare_values(10, 10, "<=") is True
        assert compare_values(10, 10, "equals") is True

    def test_compare_values_string_fallback(self):
        """Test comparing with string fallback."""
        assert compare_values("b", "a", ">") is True
        assert compare_values("a", "b", "<") is True

    def test_compare_values_exception(self):
        """Test compare_values with exception."""
        # This should handle exceptions gracefully
        result = compare_values(None, None, ">")
        assert result is False

    def test_parse_time_string_formats(self):
        """Test parsing various time string formats."""
        formats = [
            "2024-01-01 10:00:00",
            "2024-01-01T10:00:00",
            "2024-01-01",
            "2024-01-01T10:00:00Z",
            "2024-01-01T10:00:00.123456",
        ]

        for time_str in formats:
            result = parse_time_string(time_str)
            assert isinstance(result, datetime)

    def test_parse_time_string_iso(self):
        """Test parsing ISO format."""
        result = parse_time_string("2024-01-01T10:00:00+00:00")
        assert isinstance(result, datetime)

    def test_parse_time_string_invalid(self):
        """Test parsing invalid time string."""
        with pytest.raises(ValueError):
            parse_time_string("invalid time string")

    @pytest.mark.asyncio
    async def test_filter_with_or_operator(self, sample_log_file):
        """Test filtering with OR logical operator."""
        conditions = [
            {"field": "level", "operator": "equals", "value": "ERROR"},
            {"field": "level", "operator": "equals", "value": "WARN"},
        ]

        result = await filter_logs(sample_log_file, conditions, "or")
        assert result["matched_lines"] == 2

    @pytest.mark.asyncio
    async def test_filter_with_regex_operator(self, sample_log_file):
        """Test filtering with regex operator."""
        conditions = [
            {"field": "message", "operator": "regex", "value": r"(First|Second)"},
        ]

        result = await filter_logs(sample_log_file, conditions, "and")
        assert result["matched_lines"] == 2

    @pytest.mark.asyncio
    async def test_filter_with_starts_with(self, sample_log_file):
        """Test filtering with starts_with operator."""
        conditions = [
            {"field": "message", "operator": "starts_with", "value": "First"},
        ]

        result = await filter_logs(sample_log_file, conditions, "and")
        assert result["matched_lines"] == 1

    @pytest.mark.asyncio
    async def test_filter_with_ends_with(self, sample_log_file):
        """Test filtering with ends_with operator."""
        conditions = [
            {"field": "message", "operator": "ends_with", "value": "message"},
        ]

        result = await filter_logs(sample_log_file, conditions, "and")
        assert result["matched_lines"] == 3

    @pytest.mark.asyncio
    async def test_filter_with_not_equals(self, sample_log_file):
        """Test filtering with not_equals operator."""
        conditions = [
            {"field": "level", "operator": "not_equals", "value": "INFO"},
        ]

        result = await filter_logs(sample_log_file, conditions, "and")
        assert result["matched_lines"] == 2

    @pytest.mark.asyncio
    async def test_filter_with_not_contains(self, sample_log_file):
        """Test filtering with not_contains operator."""
        conditions = [
            {"field": "message", "operator": "not_contains", "value": "First"},
        ]

        result = await filter_logs(sample_log_file, conditions, "and")
        assert result["matched_lines"] == 2

    @pytest.mark.asyncio
    async def test_filter_with_in_operator(self, sample_log_file):
        """Test filtering with in operator."""
        conditions = [
            {"field": "level", "operator": "in", "value": ["ERROR", "WARN"]},
        ]

        result = await filter_logs(sample_log_file, conditions, "and")
        assert result["matched_lines"] == 2

    @pytest.mark.asyncio
    async def test_filter_with_not_in_operator(self, sample_log_file):
        """Test filtering with not_in operator."""
        conditions = [
            {"field": "level", "operator": "not_in", "value": ["ERROR", "WARN"]},
        ]

        result = await filter_logs(sample_log_file, conditions, "and")
        assert result["matched_lines"] == 1

    @pytest.mark.asyncio
    async def test_evaluate_condition_with_exception(self):
        """Test condition evaluation that raises exception."""
        entry = {"level": "ERROR"}
        condition = {"field": "invalid", "operator": "invalid", "value": None}

        # Should return False on exception
        result = evaluate_single_condition(entry, condition)
        assert result is False

    @pytest.mark.asyncio
    async def test_filter_preset_warnings_and_errors(self):
        """Test warnings_and_errors preset."""
        content = """2024-01-01 08:00:00 DEBUG Debug message
2024-01-01 09:00:00 WARN Warning message
2024-01-01 10:00:00 ERROR Error message
2024-01-01 11:00:00 FATAL Fatal message"""

        from parallel_sort_mcp.implementation.filter_handler import apply_filter_preset

        with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".log") as f:
            f.write(content)
            temp_path = f.name

        try:
            result = await apply_filter_preset(temp_path, "warnings_and_errors")
            assert result["matched_lines"] == 3
            assert result["preset_used"] == "warnings_and_errors"
        finally:
            os.unlink(temp_path)

    @pytest.mark.asyncio
    async def test_filter_preset_exclude_debug(self):
        """Test exclude_debug preset."""
        content = """2024-01-01 08:00:00 DEBUG Debug message
2024-01-01 09:00:00 INFO Info message
2024-01-01 10:00:00 TRACE Trace message"""

        from parallel_sort_mcp.implementation.filter_handler import apply_filter_preset

        with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".log") as f:
            f.write(content)
            temp_path = f.name

        try:
            result = await apply_filter_preset(temp_path, "exclude_debug")
            assert result["matched_lines"] == 1
        finally:
            os.unlink(temp_path)

    @pytest.mark.asyncio
    async def test_filter_preset_authentication_events(self):
        """Test authentication_events preset."""
        content = """2024-01-01 08:00:00 INFO User login successful
2024-01-01 09:00:00 ERROR Authentication failed
2024-01-01 10:00:00 INFO Database query
2024-01-01 11:00:00 WARN Invalid token"""

        from parallel_sort_mcp.implementation.filter_handler import apply_filter_preset

        with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".log") as f:
            f.write(content)
            temp_path = f.name

        try:
            result = await apply_filter_preset(temp_path, "authentication_events")
            assert result["matched_lines"] >= 2
        finally:
            os.unlink(temp_path)
