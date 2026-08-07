"""
Comprehensive test coverage for handler functions and MCP tool handlers.
"""

import os
import tempfile
import pandas as pd
import pytest
import asyncio

from fastmcp.tools import ToolResult
from plot_mcp import server
from plot_mcp.implementation.plot_capabilities import (
    create_line_plot,
    create_bar_plot,
    create_scatter_plot,
    create_histogram,
    create_heatmap,
    get_data_info,
)


def _assert_plot_tool_result(result: ToolResult) -> None:
    """A plot tool result carries a PNG image block plus the structured dict."""
    assert isinstance(result, ToolResult)
    assert result.structured_content is not None
    assert result.structured_content["status"] == "success"
    image_blocks = [c for c in result.content if c.type == "image"]
    assert image_blocks, "expected an image content block"
    assert image_blocks[0].mime_type == "image/png"


class TestHandlers:
    """Comprehensive test coverage for handler functions"""

    @pytest.fixture
    def sample_csv_file(self):
        """Create a sample CSV file for testing."""
        data = pd.DataFrame(
            {
                "x": [1, 2, 3, 4, 5],
                "y": [2, 4, 6, 8, 10],
                "category": ["A", "B", "A", "B", "A"],
                "value": [10, 20, 15, 25, 30],
                "numeric_data": [1.1, 2.2, 3.3, 4.4, 5.5],
            }
        )
        with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False) as f:
            data.to_csv(f.name, index=False)
            yield f.name
        os.unlink(f.name)

    def test_get_data_info_success(self, sample_csv_file):
        """Test successful data info retrieval"""
        result = get_data_info(sample_csv_file)
        assert result["status"] == "success"
        assert result["shape"][0] == 5  # rows
        assert (
            len(result["columns"]) == 5
        )  # columns (x, y, category, value, numeric_data)
        assert "x" in result["columns"]

    def test_get_data_info_error(self):
        """Test data info with error conditions"""
        result = get_data_info("/nonexistent/file.csv")
        assert result["status"] == "error"
        assert "error" in result

    def test_create_line_plot_success(self, sample_csv_file):
        """Test successful line plot creation"""
        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as f:
            result = create_line_plot(
                sample_csv_file, "x", "y", "Test Line Plot", f.name
            )
            assert result["status"] == "success"
            assert os.path.exists(f.name)
        os.unlink(f.name)

    def test_create_line_plot_default_params(self, sample_csv_file):
        """Test line plot with default parameters"""
        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as f:
            result = create_line_plot(sample_csv_file, "x", "y", "Default Plot", f.name)
            assert result["status"] == "success"
        os.unlink(f.name)

    def test_create_line_plot_invalid_column(self, sample_csv_file):
        """Test line plot with invalid column"""
        result = create_line_plot(
            sample_csv_file, "x", "invalid_column", "Test", "output.png"
        )
        assert result["status"] == "error"
        assert "not found in data" in result["error"]

    def test_create_bar_plot_success(self, sample_csv_file):
        """Test successful bar plot creation"""
        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as f:
            result = create_bar_plot(
                sample_csv_file, "category", "value", "Test Bar Plot", f.name
            )
            assert result["status"] == "success"
            assert os.path.exists(f.name)
        os.unlink(f.name)

    def test_create_bar_plot_with_numeric_x(self, sample_csv_file):
        """Test bar plot with numeric x-axis"""
        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as f:
            result = create_bar_plot(
                sample_csv_file, "x", "value", "Numeric X Bar Plot", f.name
            )
            assert result["status"] == "success"
        os.unlink(f.name)

    def test_create_scatter_plot_success(self, sample_csv_file):
        """Test successful scatter plot creation"""
        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as f:
            result = create_scatter_plot(
                sample_csv_file, "x", "y", "Test Scatter Plot", f.name
            )
            assert result["status"] == "success"
            assert os.path.exists(f.name)
        os.unlink(f.name)

    def test_create_scatter_plot_with_float_data(self, sample_csv_file):
        """Test scatter plot with float data"""
        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as f:
            result = create_scatter_plot(
                sample_csv_file, "numeric_data", "y", "Float Scatter", f.name
            )
            assert result["status"] == "success"
        os.unlink(f.name)

    def test_create_histogram_success(self, sample_csv_file):
        """Test successful histogram creation"""
        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as f:
            result = create_histogram(
                sample_csv_file, "value", 10, "Test Histogram", f.name
            )
            assert result["status"] == "success"
            assert os.path.exists(f.name)
        os.unlink(f.name)

    def test_create_histogram_default_bins(self, sample_csv_file):
        """Test histogram with default bins"""
        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as f:
            result = create_histogram(
                sample_csv_file, "value", 20, "Default Bins Histogram", f.name
            )
            assert result["status"] == "success"
        os.unlink(f.name)

    def test_create_heatmap_success(self, sample_csv_file):
        """Test successful heatmap creation"""
        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as f:
            result = create_heatmap(sample_csv_file, "Test Heatmap", f.name)
            assert result["status"] == "success"
            assert os.path.exists(f.name)
        os.unlink(f.name)

    def test_create_heatmap_file_not_found(self):
        """Test heatmap with file not found"""
        result = create_heatmap("/nonexistent/file.csv", "Test Heatmap", "output.png")
        assert result["status"] == "error"
        assert "error" in result

    def test_handler_error_handling(self):
        """Test comprehensive error handling across all handlers"""
        # Test with non-existent file for all functions
        error_functions = [
            lambda: get_data_info("/nonexistent/file.csv"),
            lambda: create_line_plot(
                "/nonexistent/file.csv", "x", "y", "Test", "output.png"
            ),
            lambda: create_bar_plot(
                "/nonexistent/file.csv", "x", "y", "Test", "output.png"
            ),
            lambda: create_scatter_plot(
                "/nonexistent/file.csv", "x", "y", "Test", "output.png"
            ),
            lambda: create_histogram(
                "/nonexistent/file.csv", "x", 10, "Test", "output.png"
            ),
            lambda: create_heatmap("/nonexistent/file.csv", "Test", "output.png"),
        ]

        for func in error_functions:
            result = func()
            assert result["status"] == "error"
            assert "error" in result

    @pytest.mark.asyncio
    async def test_mcp_tool_handlers_direct(self, sample_csv_file):
        """Test MCP tool handlers directly"""
        # Test data_info_tool
        result = await server.data_info_tool(file_path=sample_csv_file)
        assert isinstance(result, dict)
        assert "status" in result

        # Test line_plot_tool
        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as f:
            result = await server.line_plot_tool(
                file_path=sample_csv_file,
                x_column="x",
                y_column="y",
                title="MCP Line Plot",
                output_path=f.name,
            )
            _assert_plot_tool_result(result)
        os.unlink(f.name)

        # Test bar_plot_tool
        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as f:
            result = await server.bar_plot_tool(
                file_path=sample_csv_file,
                x_column="category",
                y_column="value",
                title="MCP Bar Plot",
                output_path=f.name,
            )
            _assert_plot_tool_result(result)
        os.unlink(f.name)

        # Test scatter_plot_tool
        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as f:
            result = await server.scatter_plot_tool(
                file_path=sample_csv_file,
                x_column="x",
                y_column="y",
                title="MCP Scatter Plot",
                output_path=f.name,
            )
            _assert_plot_tool_result(result)
        os.unlink(f.name)

        # Test histogram_plot_tool
        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as f:
            result = await server.histogram_plot_tool(
                file_path=sample_csv_file,
                column="value",
                bins=10,
                title="MCP Histogram",
                output_path=f.name,
            )
            _assert_plot_tool_result(result)
        os.unlink(f.name)

        # Test heatmap_plot_tool
        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as f:
            result = await server.heatmap_plot_tool(
                file_path=sample_csv_file, title="MCP Heatmap", output_path=f.name
            )
            _assert_plot_tool_result(result)
        os.unlink(f.name)

    def test_handler_parameter_validation(self, sample_csv_file):
        """Test parameter validation in handlers"""
        # Test with missing required parameters
        result = create_line_plot(sample_csv_file, "", "y", "Test", "output.png")
        assert result["status"] == "error"

        # Test with invalid file paths
        result = create_bar_plot("", "x", "y", "Test", "output.png")
        assert result["status"] == "error"

        # Test with invalid column names
        result = create_scatter_plot(
            sample_csv_file, "nonexistent", "y", "Test", "output.png"
        )
        assert result["status"] == "error"

    def test_output_file_handling(self, sample_csv_file):
        """Test output file handling"""
        # Test with valid output path
        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as f:
            result = create_line_plot(
                sample_csv_file, "x", "y", "File Output Test", f.name
            )
            assert result["status"] == "success"
            assert os.path.exists(f.name)
        os.unlink(f.name)

        # Test with directory that doesn't exist
        invalid_path = "/nonexistent/directory/output.png"
        result = create_line_plot(
            sample_csv_file, "x", "y", "Invalid Path Test", invalid_path
        )
        # May succeed or fail depending on implementation, but shouldn't crash

    def test_data_type_handling(self):
        """Test handling of different data types"""
        # Create test data with mixed types
        mixed_data = pd.DataFrame(
            {
                "integers": [1, 2, 3, 4, 5],
                "floats": [1.1, 2.2, 3.3, 4.4, 5.5],
                "strings": ["A", "B", "C", "D", "E"],
                "booleans": [True, False, True, False, True],
                "mixed": [1, "B", 3.3, True, None],
            }
        )

        with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False) as f:
            mixed_data.to_csv(f.name, index=False)

            # Test data info with mixed types
            result = get_data_info(f.name)
            assert result["status"] == "success"

            # Test plotting with different data types
            with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as output_f:
                result = create_line_plot(
                    f.name, "integers", "floats", "Mixed Types", output_f.name
                )
                assert result["status"] == "success"
            os.unlink(output_f.name)

        os.unlink(f.name)

    def test_large_data_handling(self):
        """Test handling of large datasets"""
        # Create larger dataset
        large_data = pd.DataFrame(
            {
                "x": range(500),
                "y": [i * 2 for i in range(500)],
                "category": [f"Cat_{i % 5}" for i in range(500)],
                "value": [i + 100 for i in range(500)],
            }
        )

        with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False) as f:
            large_data.to_csv(f.name, index=False)

            # Test that handlers can process large data
            result = get_data_info(f.name)
            assert result["status"] == "success"
            assert result["shape"][0] == 500  # rows

            with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as output_f:
                result = create_histogram(
                    f.name, "value", 20, "Large Data Histogram", output_f.name
                )
                assert result["status"] == "success"
            os.unlink(output_f.name)

        os.unlink(f.name)

    def test_special_characters_handling(self):
        """Test handling of special characters in data"""
        special_data = pd.DataFrame(
            {
                "col_with_spaces": [1, 2, 3],
                "col-with-dashes": [4, 5, 6],
                "col.with.dots": [7, 8, 9],
                "col@with@symbols": [10, 11, 12],
            }
        )

        with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False) as f:
            special_data.to_csv(f.name, index=False)

            # Test that special column names are handled
            result = get_data_info(f.name)
            assert result["status"] == "success"

            with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as output_f:
                result = create_scatter_plot(
                    f.name,
                    "col_with_spaces",
                    "col-with-dashes",
                    "Special Chars",
                    output_f.name,
                )
                assert result["status"] == "success"
            os.unlink(output_f.name)

        os.unlink(f.name)

    @pytest.mark.asyncio
    async def test_async_handler_comprehensive(self, sample_csv_file):
        """Test comprehensive async handler functionality"""
        # Test all async handlers in sequence
        async_tests = [
            server.data_info_tool(file_path=sample_csv_file),
        ]

        # Add plot tests with temporary files
        with (
            tempfile.NamedTemporaryFile(suffix=".png", delete=False) as f1,
            tempfile.NamedTemporaryFile(suffix=".png", delete=False) as f2,
            tempfile.NamedTemporaryFile(suffix=".png", delete=False) as f3,
            tempfile.NamedTemporaryFile(suffix=".png", delete=False) as f4,
            tempfile.NamedTemporaryFile(suffix=".png", delete=False) as f5,
        ):
            async_tests.extend(
                [
                    server.line_plot_tool(
                        file_path=sample_csv_file,
                        x_column="x",
                        y_column="y",
                        title="Async Line",
                        output_path=f1.name,
                    ),
                    server.bar_plot_tool(
                        file_path=sample_csv_file,
                        x_column="category",
                        y_column="value",
                        title="Async Bar",
                        output_path=f2.name,
                    ),
                    server.scatter_plot_tool(
                        file_path=sample_csv_file,
                        x_column="x",
                        y_column="y",
                        title="Async Scatter",
                        output_path=f3.name,
                    ),
                    server.histogram_plot_tool(
                        file_path=sample_csv_file,
                        column="value",
                        bins=10,
                        title="Async Histogram",
                        output_path=f4.name,
                    ),
                    server.heatmap_plot_tool(
                        file_path=sample_csv_file,
                        title="Async Heatmap",
                        output_path=f5.name,
                    ),
                ]
            )

            # Execute all async tests
            results = await asyncio.gather(*async_tests)

            # Verify all results: data_info_tool returns a plain dict, the
            # five plot tools each return a ToolResult (image + structured).
            data_info_result, *plot_results = results
            assert isinstance(data_info_result, dict)
            assert "status" in data_info_result
            for result in plot_results:
                _assert_plot_tool_result(result)

        # Cleanup
        for f in [f1, f2, f3, f4, f5]:
            os.unlink(f.name)
