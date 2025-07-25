"""
Tests for the filter handler capability.
"""
import pytest
import tempfile
import os
from implementation.filter_handler import (
    filter_logs, filter_by_time_range, filter_by_log_level, 
    filter_by_keyword, apply_filter_preset, FilterOperator
)


class TestFilterHandler:
    """Test suite for filter handler functionality."""

    @pytest.mark.asyncio
    async def test_filter_by_log_level_include(self):
        """Test filtering by log level (include)."""
        test_content = """2024-01-01 08:30:00 DEBUG Debug message
2024-01-01 09:15:00 INFO Info message
2024-01-01 10:00:00 WARN Warning message
2024-01-01 11:30:00 ERROR Error message
2024-01-01 12:00:00 FATAL Fatal message"""
        
        with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.log') as f:
            f.write(test_content)
            temp_path = f.name
        
        try:
            result = await filter_by_log_level(temp_path, ["ERROR", "FATAL"], exclude=False)
            
            assert "error" not in result
            assert result["total_lines"] == 5
            assert result["matched_lines"] == 2
            
            # Check that only ERROR and FATAL lines are included
            for line in result["filtered_lines"]:
                assert "ERROR" in line or "FATAL" in line
            
        finally:
            os.unlink(temp_path)

    @pytest.mark.asyncio
    async def test_filter_by_log_level_exclude(self):
        """Test filtering by log level (exclude)."""
        test_content = """2024-01-01 08:30:00 DEBUG Debug message
2024-01-01 09:15:00 INFO Info message
2024-01-01 10:00:00 ERROR Error message"""
        
        with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.log') as f:
            f.write(test_content)
            temp_path = f.name
        
        try:
            result = await filter_by_log_level(temp_path, ["DEBUG"], exclude=True)
            
            assert result["matched_lines"] == 2
            
            # Check that DEBUG lines are excluded
            for line in result["filtered_lines"]:
                assert "DEBUG" not in line
            
        finally:
            os.unlink(temp_path)

    @pytest.mark.asyncio
    async def test_filter_by_keyword_single(self):
        """Test filtering by single keyword."""
        test_content = """2024-01-01 08:30:00 INFO User login successful
2024-01-01 09:15:00 INFO Database connection established
2024-01-01 10:00:00 ERROR Database connection failed
2024-01-01 11:30:00 INFO User logout completed"""
        
        with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.log') as f:
            f.write(test_content)
            temp_path = f.name
        
        try:
            result = await filter_by_keyword(temp_path, "database", case_sensitive=False)
            
            assert result["matched_lines"] == 2
            
            # Check that all filtered lines contain "database"
            for line in result["filtered_lines"]:
                assert "database" in line.lower()
            
        finally:
            os.unlink(temp_path)

    @pytest.mark.asyncio
    async def test_filter_by_keyword_multiple_or(self):
        """Test filtering by multiple keywords with OR logic."""
        test_content = """2024-01-01 08:30:00 INFO User login successful
2024-01-01 09:15:00 INFO Database connection established
2024-01-01 10:00:00 ERROR Authentication failed
2024-01-01 11:30:00 INFO System startup completed"""
        
        with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.log') as f:
            f.write(test_content)
            temp_path = f.name
        
        try:
            result = await filter_by_keyword(
                temp_path, 
                ["login", "database"], 
                case_sensitive=False, 
                match_all=False
            )
            
            assert result["matched_lines"] == 2
            
        finally:
            os.unlink(temp_path)

    @pytest.mark.asyncio
    async def test_filter_by_keyword_multiple_and(self):
        """Test filtering by multiple keywords with AND logic."""
        test_content = """2024-01-01 08:30:00 INFO User login database access
2024-01-01 09:15:00 INFO Database connection established
2024-01-01 10:00:00 INFO User login successful
2024-01-01 11:30:00 ERROR Login database authentication failed"""
        
        with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.log') as f:
            f.write(test_content)
            temp_path = f.name
        
        try:
            result = await filter_by_keyword(
                temp_path, 
                ["login", "database"], 
                case_sensitive=False, 
                match_all=True
            )
            
            assert result["matched_lines"] == 2
            
            # Check that all filtered lines contain both keywords
            for line in result["filtered_lines"]:
                assert "login" in line.lower() and "database" in line.lower()
            
        finally:
            os.unlink(temp_path)

    @pytest.mark.asyncio
    async def test_filter_by_time_range(self):
        """Test filtering by time range."""
        test_content = """2024-01-01 08:30:00 INFO Early message
2024-01-01 09:15:00 INFO Target message 1
2024-01-01 09:45:00 INFO Target message 2
2024-01-01 10:30:00 INFO Late message"""
        
        with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.log') as f:
            f.write(test_content)
            temp_path = f.name
        
        try:
            result = await filter_by_time_range(
                temp_path, 
                "2024-01-01 09:00:00", 
                "2024-01-01 10:00:00"
            )
            
            assert result["matched_lines"] == 2
            
            # Check that filtered lines are within time range
            for line in result["filtered_lines"]:
                assert "09:" in line
            
        finally:
            os.unlink(temp_path)

    @pytest.mark.asyncio
    async def test_filter_complex_conditions(self):
        """Test filtering with complex multiple conditions."""
        test_content = """2024-01-01 08:30:00 DEBUG User authentication started
2024-01-01 09:15:00 ERROR User authentication failed
2024-01-01 10:00:00 INFO Database connection successful
2024-01-01 11:30:00 ERROR Database connection timeout"""
        
        with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.log') as f:
            f.write(test_content)
            temp_path = f.name
        
        try:
            # Filter for ERROR level entries containing "authentication"
            filter_conditions = [
                {
                    "field": "level",
                    "operator": "equals",
                    "value": "ERROR"
                },
                {
                    "field": "message",
                    "operator": "contains",
                    "value": "authentication"
                }
            ]
            
            result = await filter_logs(temp_path, filter_conditions, "and")
            
            assert result["matched_lines"] == 1
            
            filtered_line = result["filtered_lines"][0]
            assert "ERROR" in filtered_line
            assert "authentication" in filtered_line
            
        finally:
            os.unlink(temp_path)

    @pytest.mark.asyncio
    async def test_apply_filter_preset_errors_only(self):
        """Test applying the 'errors_only' filter preset."""
        test_content = """2024-01-01 08:30:00 DEBUG Debug message
2024-01-01 09:15:00 INFO Info message
2024-01-01 10:00:00 WARN Warning message
2024-01-01 11:30:00 ERROR Error message
2024-01-01 12:00:00 FATAL Fatal message"""
        
        with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.log') as f:
            f.write(test_content)
            temp_path = f.name
        
        try:
            result = await apply_filter_preset(temp_path, "errors_only")
            
            assert "preset_used" in result
            assert result["preset_used"] == "errors_only"
            assert result["matched_lines"] == 2
            
            # Should only contain ERROR and FATAL
            for line in result["filtered_lines"]:
                assert "ERROR" in line or "FATAL" in line
            
        finally:
            os.unlink(temp_path)

    @pytest.mark.asyncio
    async def test_apply_filter_preset_connection_issues(self):
        """Test applying the 'connection_issues' filter preset."""
        test_content = """2024-01-01 08:30:00 INFO User login successful
2024-01-01 09:15:00 ERROR Database connection failed
2024-01-01 10:00:00 INFO System startup
2024-01-01 11:30:00 WARN Network timeout detected"""
        
        with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.log') as f:
            f.write(test_content)
            temp_path = f.name
        
        try:
            result = await apply_filter_preset(temp_path, "connection_issues")
            
            assert result["matched_lines"] >= 1
            
            # Should contain connection or network related entries
            connection_keywords = ["connection", "timeout", "network"]
            for line in result["filtered_lines"]:
                line_lower = line.lower()
                assert any(keyword in line_lower for keyword in connection_keywords)
            
        finally:
            os.unlink(temp_path)

    @pytest.mark.asyncio
    async def test_filter_unknown_preset(self):
        """Test applying an unknown filter preset."""
        test_content = """2024-01-01 08:30:00 INFO Test message"""
        
        with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.log') as f:
            f.write(test_content)
            temp_path = f.name
        
        try:
            result = await apply_filter_preset(temp_path, "unknown_preset")
            
            assert "error" in result
            assert "Unknown preset" in result["error"]
            
        finally:
            os.unlink(temp_path)

    @pytest.mark.asyncio
    async def test_filter_empty_file(self):
        """Test filtering an empty file."""
        with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.log') as f:
            temp_path = f.name
        
        try:
            result = await filter_by_log_level(temp_path, ["ERROR"])
            
            assert result["total_lines"] == 0
            assert result["matched_lines"] == 0
            assert result["filtered_lines"] == []
            assert "empty" in result["message"].lower()
            
        finally:
            os.unlink(temp_path)

    @pytest.mark.asyncio
    async def test_filter_nonexistent_file(self):
        """Test filtering a non-existent file."""
        result = await filter_by_log_level("/path/that/does/not/exist.log", ["ERROR"])
        
        assert "error" in result
        assert "not found" in result["error"].lower()

    @pytest.mark.asyncio
    async def test_filter_invalid_entries(self):
        """Test filtering with invalid log entries."""
        test_content = """2024-01-01 08:30:00 INFO Valid entry
Invalid line without timestamp
2024-01-01 09:15:00 ERROR Valid error
Another invalid line"""
        
        with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.log') as f:
            f.write(test_content)
            temp_path = f.name
        
        try:
            result = await filter_by_log_level(temp_path, ["ERROR"])
            
            assert result["total_lines"] == 4
            assert result["matched_lines"] == 1
            
            # Should find the ERROR line
            assert len(result["filtered_lines"]) == 1
            assert "ERROR" in result["filtered_lines"][0]
            
        finally:
            os.unlink(temp_path)