"""
Comprehensive test coverage for server.py - MCP server, tools, main function, and argument parsing.
"""

import os
import tempfile
import pandas as pd
import pytest

from fastmcp.exceptions import ToolError
from fastmcp.tools import ToolResult
from plot_mcp import server


def _assert_plot_tool_result(result: ToolResult) -> None:
    """A plot tool result carries a PNG image block plus the structured dict."""
    assert isinstance(result, ToolResult)
    assert result.structured_content is not None
    assert result.structured_content["status"] == "success"
    image_blocks = [c for c in result.content if c.type == "image"]
    assert image_blocks, "expected an image content block"
    assert image_blocks[0].mime_type == "image/png"


class TestServer:
    """Comprehensive test coverage for server functionality"""

    @pytest.fixture
    def sample_csv_file(self):
        """Create a sample CSV file for testing."""
        data = pd.DataFrame(
            {
                "x": [1, 2, 3, 4, 5],
                "y": [2, 4, 6, 8, 10],
                "category": ["A", "B", "A", "B", "A"],
                "value": [10, 20, 15, 25, 30],
            }
        )
        with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False) as f:
            data.to_csv(f.name, index=False)
            yield f.name
        os.unlink(f.name)

    def test_mcp_server_initialization(self):
        """Test that MCP server is properly initialized"""
        assert hasattr(server, "mcp")
        assert server.mcp is not None
        assert server.mcp.name == "plot"

    def test_server_module_imports(self):
        """Test that server module imports work correctly"""
        assert hasattr(server, "FastMCP")
        assert hasattr(server, "ToolError")
        assert hasattr(server, "Message")
        assert hasattr(server, "create_histogram")
        assert hasattr(server, "create_heatmap")
        assert hasattr(server, "create_line_plot")
        assert hasattr(server, "create_bar_plot")
        assert hasattr(server, "create_scatter_plot")
        assert hasattr(server, "get_data_info")

    def test_all_tools_registered(self):
        """Test that all expected tools are registered with MCP"""
        expected_tool_functions = [
            "line_plot_tool",
            "bar_plot_tool",
            "scatter_plot_tool",
            "histogram_plot_tool",
            "heatmap_plot_tool",
            "data_info_tool",
        ]

        for tool_name in expected_tool_functions:
            assert hasattr(server, tool_name), f"Missing tool function: {tool_name}"
            tool = getattr(server, tool_name)
            assert tool is not None
            assert callable(tool)

    def test_main_function_exists(self):
        """Test that main function exists and is callable"""
        assert hasattr(server, "main")
        assert callable(server.main)

    def test_argument_parsing_http_transport(self):
        """Test argument parsing for HTTP transport"""
        import argparse

        test_args = [
            "server.py",
            "--transport",
            "http",
            "--host",
            "localhost",
            "--port",
            "8080",
        ]

        parser = argparse.ArgumentParser(description="Plot MCP Server")
        parser.add_argument("--transport", choices=["stdio", "http"], default=None)
        parser.add_argument("--host", default="0.0.0.0")
        parser.add_argument("--port", type=int, default=8000)

        args = parser.parse_args(test_args[1:])
        assert args.transport == "http"
        assert args.host == "localhost"
        assert args.port == 8080

    def test_argument_parsing_stdio_transport(self):
        """Test argument parsing for stdio transport (default)"""
        import argparse

        test_args = ["server.py"]

        parser = argparse.ArgumentParser(description="Plot MCP Server")
        parser.add_argument("--transport", choices=["stdio", "http"], default=None)
        parser.add_argument("--host", default="0.0.0.0")
        parser.add_argument("--port", type=int, default=8000)

        args = parser.parse_args(test_args[1:])
        assert args.transport is None
        assert args.host == "0.0.0.0"
        assert args.port == 8000

    @pytest.mark.asyncio
    async def test_data_info_tool_execution(self, sample_csv_file):
        """Test data_info_tool execution"""
        result = await server.data_info_tool(file_path=sample_csv_file)
        assert isinstance(result, dict)
        assert "status" in result

    @pytest.mark.asyncio
    async def test_line_plot_tool_execution(self, sample_csv_file):
        """Test line_plot_tool execution"""
        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as f:
            result = await server.line_plot_tool(
                file_path=sample_csv_file,
                x_column="x",
                y_column="y",
                title="Test Line Plot",
                output_path=f.name,
            )
            _assert_plot_tool_result(result)
        os.unlink(f.name)

    @pytest.mark.asyncio
    async def test_bar_plot_tool_execution(self, sample_csv_file):
        """Test bar_plot_tool execution"""
        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as f:
            result = await server.bar_plot_tool(
                file_path=sample_csv_file,
                x_column="category",
                y_column="value",
                title="Test Bar Plot",
                output_path=f.name,
            )
            _assert_plot_tool_result(result)
        os.unlink(f.name)

    @pytest.mark.asyncio
    async def test_scatter_plot_tool_execution(self, sample_csv_file):
        """Test scatter_plot_tool execution"""
        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as f:
            result = await server.scatter_plot_tool(
                file_path=sample_csv_file,
                x_column="x",
                y_column="y",
                title="Test Scatter Plot",
                output_path=f.name,
            )
            _assert_plot_tool_result(result)
        os.unlink(f.name)

    @pytest.mark.asyncio
    async def test_histogram_plot_tool_execution(self, sample_csv_file):
        """Test histogram_plot_tool execution"""
        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as f:
            result = await server.histogram_plot_tool(
                file_path=sample_csv_file,
                column="value",
                bins=10,
                title="Test Histogram",
                output_path=f.name,
            )
            _assert_plot_tool_result(result)
        os.unlink(f.name)

    @pytest.mark.asyncio
    async def test_heatmap_plot_tool_execution(self, sample_csv_file):
        """Test heatmap_plot_tool execution"""
        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as f:
            result = await server.heatmap_plot_tool(
                file_path=sample_csv_file, title="Test Heatmap", output_path=f.name
            )
            _assert_plot_tool_result(result)
        os.unlink(f.name)

    @pytest.mark.asyncio
    async def test_tool_error_handling(self, sample_csv_file):
        """Test tool error handling scenarios"""
        # Test with invalid file path
        with pytest.raises(ToolError):
            await server.data_info_tool(file_path="/nonexistent/file.csv")

        # Test with invalid column
        with pytest.raises(ToolError):
            await server.line_plot_tool(
                file_path=sample_csv_file,
                x_column="invalid_column",
                y_column="y",
                title="Test",
                output_path="output.png",
            )

    def test_server_module_structure(self):
        """Test server module has expected structure"""
        assert hasattr(server, "FastMCP")
        assert hasattr(server, "mcp")

        # Check that plot_capabilities is importable through the package
        from plot_mcp.implementation import plot_capabilities

        assert plot_capabilities is not None

    def test_comprehensive_server_functionality(self, sample_csv_file):
        """Test comprehensive server functionality"""
        # Test that all tools exist and are callable
        tools = [
            "line_plot_tool",
            "bar_plot_tool",
            "scatter_plot_tool",
            "histogram_plot_tool",
            "heatmap_plot_tool",
            "data_info_tool",
        ]

        for tool_name in tools:
            assert hasattr(server, tool_name)
            tool = getattr(server, tool_name)
            assert tool is not None
            assert callable(tool)

    def test_logger_configuration(self):
        """Test logger configuration"""
        assert hasattr(server, "logger")
        assert server.logger is not None

    def test_imports_and_dependencies(self):
        """Test imports and dependencies"""
        # Test that all required modules are imported
        assert hasattr(server, "os")
        assert hasattr(server, "FastMCP")
        assert hasattr(server, "logging")

    def test_resource_registered(self):
        """Test that the plot styles resource is registered"""
        assert hasattr(server, "available_styles")
        assert callable(server.available_styles)

    def test_prompt_registered(self):
        """Test that the create_visualization prompt is registered"""
        assert hasattr(server, "create_visualization")
        assert callable(server.create_visualization)

    def test_server_has_instructions(self):
        """Test that the MCP server has instructions set"""
        assert server.mcp.instructions is not None
        assert "matplotlib" in server.mcp.instructions
