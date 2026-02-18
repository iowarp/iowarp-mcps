"""Tests for the FastMCP server and tool integration."""

import pytest
import pyarrow as pa
import pyarrow.parquet as pq
from unittest.mock import patch
from parquet_mcp import server


class TestServerToolsIntegration:
    """Test FastMCP tool integration with real files."""

    @pytest.fixture
    def simple_test_file(self, tmp_path):
        """Create a simple test file for integration testing."""
        file_path = tmp_path / "simple.parquet"
        table = pa.table(
            {
                "id": [1, 2, 3, 4, 5],
                "value": [10, 20, 30, 40, 50],
            }
        )
        pq.write_table(table, file_path)
        return str(file_path)

    def test_summarize_tool_exists(self):
        """Test that summarize_tool is registered."""
        assert hasattr(server, "summarize_tool")

    def test_read_slice_tool_exists(self):
        """Test that read_slice_tool is registered."""
        assert hasattr(server, "read_slice_tool")

    def test_get_column_preview_tool_exists(self):
        """Test that get_column_preview_tool is registered."""
        assert hasattr(server, "get_column_preview_tool")

    def test_aggregate_column_tool_exists(self):
        """Test that aggregate_column_tool is registered."""
        assert hasattr(server, "aggregate_column_tool")


class TestServerMain:
    """Test server main function."""

    def test_main_function_exists(self):
        """Test that main function is defined."""
        assert hasattr(server, "main")
        assert callable(server.main)

    def test_main_initializes_mcp_server(self):
        """Test that main function initializes the MCP server."""
        with patch("sys.argv", ["parquet-mcp"]):
            with patch.object(server.mcp, "run") as mock_run:
                server.main()
                mock_run.assert_called_once_with(
                    transport="stdio"
                )

    def test_main_with_http_transport(self):
        """Test main with HTTP transport argument."""
        with patch(
            "sys.argv", ["parquet-mcp", "--transport", "http", "--port", "9000"]
        ):
            with patch.object(server.mcp, "run") as mock_run:
                server.main()
                mock_run.assert_called_once_with(
                    transport="http", host="0.0.0.0", port=9000
                )


class TestMCPServerInstance:
    """Test MCP server instance configuration."""

    def test_mcp_server_is_fastmcp_instance(self):
        """Test that mcp is a FastMCP instance."""
        from fastmcp import FastMCP

        assert isinstance(server.mcp, FastMCP)

    def test_mcp_server_name(self):
        """Test that MCP server has correct name."""
        assert server.mcp.name == "parquet"

    def test_mcp_server_has_tools_registered(self):
        """Test that MCP server has tools registered."""
        # Verify that our tool functions are defined
        assert hasattr(server, "summarize_tool")
        assert hasattr(server, "read_slice_tool")
        assert hasattr(server, "get_column_preview_tool")
        assert hasattr(server, "aggregate_column_tool")

    def test_tools_are_callable(self):
        """Test that tools are callable functions in FastMCP 3.0."""
        # In FastMCP 3.0, @mcp.tool() returns the original function, not a FunctionTool wrapper
        assert callable(server.summarize_tool)
        assert callable(server.read_slice_tool)
        assert callable(server.get_column_preview_tool)
        assert callable(server.aggregate_column_tool)
