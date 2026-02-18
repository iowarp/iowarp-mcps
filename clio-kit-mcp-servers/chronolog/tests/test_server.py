"""Tests for Chronolog MCP server configuration and FastMCP 3.0 features."""

import pytest

try:
    from chronomcp.server import (
        mcp,
        start_chronolog,
        record_interaction,
        stop_chronolog,
        retrieve_interaction,
        chronolog_status,
        logging_workflow,
    )
    from fastmcp.exceptions import ToolError
    from fastmcp.prompts import Message

    HAS_DEPENDENCIES = True
except ImportError:
    HAS_DEPENDENCIES = False

pytestmark = pytest.mark.skipif(
    not HAS_DEPENDENCIES,
    reason="ChronoLog system dependencies not available",
)


class TestServerConfig:
    """Test FastMCP server configuration"""

    def test_server_name(self):
        """Test that the MCP server has the correct name"""
        assert mcp.name == "chronolog"

    def test_server_instructions(self):
        """Test that the MCP server has instructions set"""
        assert mcp.instructions is not None
        assert "ChronoLog" in mcp.instructions
        assert "distributed logging" in mcp.instructions.lower()


class TestToolDecorators:
    """Test that tools are properly decorated with FastMCP 3.0 features"""

    def test_tools_are_original_functions(self):
        """In FastMCP 3.0, @mcp.tool() returns the original function"""
        assert callable(start_chronolog)
        assert callable(record_interaction)
        assert callable(stop_chronolog)
        assert callable(retrieve_interaction)

    def test_start_chronolog_is_async(self):
        """Test that start_chronolog is still an async function"""
        import asyncio

        assert asyncio.iscoroutinefunction(start_chronolog)

    def test_record_interaction_is_async(self):
        """Test that record_interaction is still an async function"""
        import asyncio

        assert asyncio.iscoroutinefunction(record_interaction)

    def test_stop_chronolog_is_async(self):
        """Test that stop_chronolog is still an async function"""
        import asyncio

        assert asyncio.iscoroutinefunction(stop_chronolog)

    def test_retrieve_interaction_is_async(self):
        """Test that retrieve_interaction is still an async function"""
        import asyncio

        assert asyncio.iscoroutinefunction(retrieve_interaction)


class TestResource:
    """Test the chronolog://status resource"""

    def test_chronolog_status_returns_dict(self):
        """Test that the status resource returns expected data"""
        result = chronolog_status()
        assert isinstance(result, dict)
        assert result["service"] == "chronolog"
        assert result["status"] == "ready"
        assert "description" in result


class TestPrompt:
    """Test the logging_workflow prompt"""

    def test_logging_workflow_default(self):
        """Test the prompt with default time range"""
        messages = logging_workflow()
        assert isinstance(messages, list)
        assert len(messages) == 1
        assert isinstance(messages[0], Message)

    def test_logging_workflow_custom_range(self):
        """Test the prompt with custom time range"""
        messages = logging_workflow(time_range="last 24 hours")
        assert isinstance(messages, list)
        assert len(messages) == 1
        assert isinstance(messages[0], Message)


class TestMainFunction:
    """Test the main entry point"""

    def test_main_function_exists(self):
        """Test that main function exists and is callable"""
        from chronomcp.server import main

        assert callable(main)
