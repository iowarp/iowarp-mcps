"""
Tests for MCP handlers.
"""
import pytest
import tempfile
import os
from mcp_handlers import sort_log_handler


class TestMCPHandlers:
    """Test suite for MCP handler functionality."""

    @pytest.mark.asyncio
    async def test_sort_log_handler_success(self):
        """Test successful log sorting through MCP handler."""
        test_content = """2024-01-02 10:00:00 INFO Second entry
2024-01-01 08:30:00 DEBUG First entry"""
        
        with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.log') as f:
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
        result = await sort_log_handler("/nonexistent/file.log")
        
        # Should return error in the result
        assert "error" in result
        assert "not found" in result["error"].lower()

    @pytest.mark.asyncio
    async def test_sort_log_handler_empty_file(self):
        """Test MCP handler with empty file."""
        with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.log') as f:
            temp_path = f.name
        
        try:
            result = await sort_log_handler(temp_path)
            
            assert "error" not in result or result.get("error") is None
            assert result["total_lines"] == 0
            assert result["sorted_lines"] == []
            assert "empty" in result["message"].lower()
            
        finally:
            os.unlink(temp_path)