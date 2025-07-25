"""
Tests for the sort handler capability.
"""
import pytest
import tempfile
import os
from implementation.sort_handler import sort_log_by_timestamp, parse_timestamp
from datetime import datetime


class TestSortHandler:
    """Test suite for sort handler functionality."""

    @pytest.mark.asyncio
    async def test_sort_valid_log_file(self):
        """Test sorting a valid log file with proper timestamps."""
        test_content = """2024-01-03 10:00:00 INFO Application started
2024-01-01 08:30:00 DEBUG System initialized
2024-01-02 14:45:00 ERROR Connection failed
2024-01-01 09:15:00 WARN Memory usage high"""
        
        with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.log') as f:
            f.write(test_content)
            temp_path = f.name
        
        try:
            result = await sort_log_by_timestamp(temp_path)
            
            assert "error" not in result
            assert result["total_lines"] == 4
            assert result["valid_lines"] == 4
            assert result["invalid_lines"] == 0
            assert len(result["sorted_lines"]) == 4
            
            # Check if sorted correctly
            expected_order = [
                "2024-01-01 08:30:00 DEBUG System initialized",
                "2024-01-01 09:15:00 WARN Memory usage high",
                "2024-01-02 14:45:00 ERROR Connection failed",
                "2024-01-03 10:00:00 INFO Application started"
            ]
            assert result["sorted_lines"] == expected_order
            
        finally:
            os.unlink(temp_path)

    @pytest.mark.asyncio
    async def test_sort_empty_file(self):
        """Test handling of empty log file."""
        with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.log') as f:
            temp_path = f.name
        
        try:
            result = await sort_log_by_timestamp(temp_path)
            
            assert "error" not in result
            assert result["total_lines"] == 0
            assert result["valid_lines"] == 0
            assert result["invalid_lines"] == 0
            assert result["sorted_lines"] == []
            assert "empty" in result["message"].lower()
            
        finally:
            os.unlink(temp_path)

    @pytest.mark.asyncio
    async def test_sort_file_with_invalid_timestamps(self):
        """Test handling of log file with some invalid timestamp entries."""
        test_content = """2024-01-02 10:00:00 INFO Valid entry
Invalid line without timestamp
2024-01-01 08:30:00 DEBUG Another valid entry
2024/01/03 14:45:00 ERROR Wrong timestamp format
2024-01-01 09:15:00 WARN Valid entry again"""
        
        with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.log') as f:
            f.write(test_content)
            temp_path = f.name
        
        try:
            result = await sort_log_by_timestamp(temp_path)
            
            assert "error" not in result
            assert result["total_lines"] == 5
            assert result["valid_lines"] == 3
            assert result["invalid_lines"] == 2
            assert len(result["sorted_lines"]) == 3
            assert "invalid_entries" in result
            assert len(result["invalid_entries"]) == 2
            
            # Check if valid entries are sorted correctly
            expected_order = [
                "2024-01-01 08:30:00 DEBUG Another valid entry",
                "2024-01-01 09:15:00 WARN Valid entry again",
                "2024-01-02 10:00:00 INFO Valid entry"
            ]
            assert result["sorted_lines"] == expected_order
            
        finally:
            os.unlink(temp_path)

    @pytest.mark.asyncio
    async def test_sort_nonexistent_file(self):
        """Test handling of non-existent file."""
        result = await sort_log_by_timestamp("/path/that/does/not/exist.log")
        
        assert "error" in result
        assert "not found" in result["error"].lower()
        assert result["sorted_lines"] == []
        assert result["total_lines"] == 0
        assert result["valid_lines"] == 0
        assert result["invalid_lines"] == 0

    def test_parse_timestamp_valid(self):
        """Test timestamp parsing with valid formats."""
        test_line = "2024-01-15 14:30:25 INFO Test message"
        dt, original = parse_timestamp(test_line)
        
        assert isinstance(dt, datetime)
        assert dt.year == 2024
        assert dt.month == 1
        assert dt.day == 15
        assert dt.hour == 14
        assert dt.minute == 30
        assert dt.second == 25
        assert original == test_line

    def test_parse_timestamp_invalid(self):
        """Test timestamp parsing with invalid formats."""
        invalid_lines = [
            "No timestamp here",
            "2024/01/15 14:30:25 Wrong format",
            "2024-13-15 14:30:25 Invalid month",
            "2024-01-32 14:30:25 Invalid day"
        ]
        
        for line in invalid_lines:
            with pytest.raises(ValueError):
                parse_timestamp(line)

    @pytest.mark.asyncio
    async def test_sort_with_same_timestamps(self):
        """Test sorting entries with identical timestamps."""
        test_content = """2024-01-01 10:00:00 INFO First message
2024-01-01 10:00:00 WARN Second message
2024-01-01 10:00:00 ERROR Third message"""
        
        with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.log') as f:
            f.write(test_content)
            temp_path = f.name
        
        try:
            result = await sort_log_by_timestamp(temp_path)
            
            assert "error" not in result
            assert result["total_lines"] == 3
            assert result["valid_lines"] == 3
            assert result["invalid_lines"] == 0
            assert len(result["sorted_lines"]) == 3
            
            # All entries should be present (stable sort)
            for line in test_content.split('\n'):
                if line.strip():
                    assert line in result["sorted_lines"]
                    
        finally:
            os.unlink(temp_path)