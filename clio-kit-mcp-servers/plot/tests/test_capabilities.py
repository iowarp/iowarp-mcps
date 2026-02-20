"""
Comprehensive test coverage for plot_capabilities.py - all functionality, edge cases,        result = get_data_info(sample_csv_file)
        assert result["status"] == "success"
        assert result["shape"][0] == 5  # rows
        assert len(result["columns"]) == 3 error handling.
"""

import os
import tempfile
import pandas as pd
import pytest
import matplotlib

matplotlib.use("Agg")

from plot_mcp.implementation.plot_capabilities import (
    load_data,
    create_line_plot,
    create_bar_plot,
    create_scatter_plot,
    create_histogram,
    create_heatmap,
    get_data_info,
)


class TestPlotCapabilities:
    """Comprehensive test coverage for plot capabilities"""

    @pytest.fixture
    def sample_csv_file(self):
        """Create a sample CSV file for testing."""
        data = pd.DataFrame(
            {
                "x": [1, 2, 3, 4, 5],
                "y": [2, 4, 6, 8, 10],
                "category": ["A", "B", "A", "B", "A"],
                "value": [10, 20, 15, 25, 30],
                "numeric_cat": [1, 2, 1, 2, 1],
            }
        )
        with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False) as f:
            data.to_csv(f.name, index=False)
            yield f.name
        os.unlink(f.name)

    @pytest.fixture
    def sample_excel_file(self):
        """Create a sample Excel file for testing."""
        data = pd.DataFrame(
            {
                "x": [1, 2, 3, 4, 5],
                "y": [2, 4, 6, 8, 10],
                "category": ["A", "B", "A", "B", "A"],
            }
        )
        with tempfile.NamedTemporaryFile(suffix=".xlsx", delete=False) as f:
            data.to_excel(f.name, index=False)
            yield f.name
        os.unlink(f.name)

    def test_load_data_csv(self, sample_csv_file):
        """Test loading CSV data"""
        df = load_data(sample_csv_file)
        assert len(df) == 5
        assert "x" in df.columns
        assert "y" in df.columns

    def test_load_data_excel(self, sample_excel_file):
        """Test loading Excel data"""
        df = load_data(sample_excel_file)
        assert len(df) == 5
        assert "x" in df.columns
        assert "y" in df.columns

    def test_load_data_unsupported_format(self):
        """Test unsupported file format error"""
        with tempfile.NamedTemporaryFile(suffix=".txt", delete=False) as f:
            f.write(b"test data")
            f.flush()

            with pytest.raises(ValueError, match="Unsupported file format"):
                load_data(f.name)

        os.unlink(f.name)

    def test_load_data_file_not_found(self):
        """Test file not found error"""
        with pytest.raises(FileNotFoundError):
            load_data("/nonexistent/path/file.csv")

    def test_get_data_info_success(self, sample_csv_file):
        """Test successful data info retrieval"""
        result = get_data_info(sample_csv_file)
        assert result["status"] == "success"
        assert result["shape"][0] == 5  # rows
        assert (
            len(result["columns"]) == 5
        )  # columns (x, y, category, value, numeric_cat)
        assert "x" in result["columns"]

    def test_get_data_info_file_not_found(self):
        """Test data info with non-existent file"""
        result = get_data_info("/nonexistent/file.csv")
        assert result["status"] == "error"
        assert (
            "No such file or directory" in result["error"]
            or "cannot find the file" in result["error"]
        )

    def test_get_data_info_empty_file(self):
        """Test data info with empty file"""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False) as f:
            f.write("")
            f.flush()

            result = get_data_info(f.name)
            assert result["status"] == "error"

        os.unlink(f.name)

    def test_create_line_plot_success(self, sample_csv_file):
        """Test successful line plot creation"""
        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as f:
            result = create_line_plot(
                sample_csv_file, "x", "y", "Test Line Plot", f.name
            )
            assert result["status"] == "success"
            assert os.path.exists(f.name)
        os.unlink(f.name)

    def test_create_line_plot_invalid_column(self, sample_csv_file):
        """Test line plot with invalid column"""
        result = create_line_plot(
            sample_csv_file, "x", "invalid_column", "Test", "output.png"
        )
        assert result["status"] == "error"
        assert "not found in data" in result["error"]

    def test_create_line_plot_missing_y_column(self):
        """Test line plot with missing y column"""
        data = pd.DataFrame({"x": [1, 2, 3], "valid_y": [1, 2, 3]})
        with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False) as f:
            data.to_csv(f.name, index=False)

            result = create_line_plot(
                f.name, "x", "invalid_y", "Test Plot", "output.png"
            )
            assert result["status"] == "error"
            assert "Column 'invalid_y' not found in data" in result["error"]

        os.unlink(f.name)

    def test_create_bar_plot_success(self, sample_csv_file):
        """Test successful bar plot creation"""
        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as f:
            result = create_bar_plot(
                sample_csv_file, "category", "value", "Test Bar Plot", f.name
            )
            assert result["status"] == "success"
            assert os.path.exists(f.name)
        os.unlink(f.name)

    def test_create_bar_plot_numeric_data_path(self):
        """Test bar plot with numeric data - direct path"""
        data = pd.DataFrame(
            {"x_numeric": [1.1, 2.2, 3.3, 4.4, 5.5], "y": [10, 20, 15, 25, 30]}
        )

        with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False) as f:
            data.to_csv(f.name, index=False)

            with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as output_f:
                result = create_bar_plot(
                    f.name, "x_numeric", "y", "Numeric Bar Plot", output_f.name
                )
                assert result["status"] == "success"

            os.unlink(output_f.name)
        os.unlink(f.name)

    def test_create_bar_plot_large_categories(self):
        """Test bar plot with > 20 categories"""
        categories = [f"Cat_{i}" for i in range(25)]
        values = list(range(25, 0, -1))

        data = pd.DataFrame({"category": categories, "value": values})

        with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False) as f:
            data.to_csv(f.name, index=False)

            with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as output_f:
                result = create_bar_plot(
                    f.name, "category", "value", "Large Category Plot", output_f.name
                )
                assert result["status"] == "success"

            os.unlink(output_f.name)
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

    def test_create_scatter_plot_missing_columns(self):
        """Test scatter plot with missing columns"""
        data = pd.DataFrame({"valid_x": [1, 2, 3], "valid_y": [1, 2, 3]})
        with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False) as f:
            data.to_csv(f.name, index=False)

            # Test missing y column
            result = create_scatter_plot(
                f.name, "valid_x", "missing_y", "Test Scatter", "output.png"
            )
            assert result["status"] == "error"
            assert "Column 'missing_y' not found in data" in result["error"]

            # Test missing x column
            result = create_scatter_plot(
                f.name, "missing_x", "valid_y", "Test Scatter", "output.png"
            )
            assert result["status"] == "error"
            assert "Column 'missing_x' not found in data" in result["error"]

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

    def test_create_histogram_invalid_column(self, sample_csv_file):
        """Test histogram with invalid column"""
        result = create_histogram(
            sample_csv_file, "invalid_column", 10, "Test", "output.png"
        )
        assert result["status"] == "error"
        assert "not found in data" in result["error"]

    def test_create_histogram_edge_cases(self, sample_csv_file):
        """Test histogram with edge cases"""
        # Test with very few bins
        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as f:
            result = create_histogram(sample_csv_file, "value", 2, "Few Bins", f.name)
            assert result["status"] == "success"
        os.unlink(f.name)

        # Test with many bins
        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as f:
            result = create_histogram(sample_csv_file, "value", 50, "Many Bins", f.name)
            assert result["status"] == "success"
        os.unlink(f.name)

    def test_create_heatmap_success(self, sample_csv_file):
        """Test successful heatmap creation"""
        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as f:
            result = create_heatmap(sample_csv_file, "Test Heatmap", f.name)
            assert result["status"] == "success"
            assert os.path.exists(f.name)
        os.unlink(f.name)

    def test_create_heatmap_no_numeric_columns(self):
        """Test heatmap with no numeric columns"""
        data = pd.DataFrame(
            {
                "text1": ["a", "b", "c"],
                "text2": ["x", "y", "z"],
                "text3": ["p", "q", "r"],
            }
        )

        with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False) as f:
            data.to_csv(f.name, index=False)

            result = create_heatmap(f.name, "Test Heatmap", "output.png")
            assert result["status"] == "error"
            assert "No numeric columns found" in result["error"]

        os.unlink(f.name)

    def test_create_heatmap_edge_cases(self):
        """Test heatmap edge cases"""
        # Single numeric column
        data = pd.DataFrame(
            {"value": [1, 2, 3, 4, 5], "text": ["a", "b", "c", "d", "e"]}
        )

        with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False) as f:
            data.to_csv(f.name, index=False)

            with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as output_f:
                result = create_heatmap(f.name, "Single Column Heatmap", output_f.name)
                assert result["status"] == "success"

            os.unlink(output_f.name)
        os.unlink(f.name)

    def test_data_handling_comprehensive(self):
        """Test comprehensive data handling scenarios"""
        # Test with missing values
        data = pd.DataFrame(
            {
                "x": [1, 2, None, 4, 5],
                "y": [10, None, 30, 40, 50],
                "category": ["A", "B", None, "D", "E"],
            }
        )

        with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False) as f:
            data.to_csv(f.name, index=False)

            # Test that functions handle missing data gracefully
            with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as output_f:
                result = create_line_plot(
                    f.name, "x", "y", "Missing Data Plot", output_f.name
                )
                assert result["status"] == "success"

            os.unlink(output_f.name)
        os.unlink(f.name)

    def test_excel_comprehensive_workflow(self):
        """Test complete workflow with Excel files"""
        # Create Excel with multiple sheets (use first sheet)
        data = pd.DataFrame(
            {
                "timestamp": pd.date_range("2023-01-01", periods=10),
                "value1": range(10, 20),
                "value2": range(20, 30),
                "category": ["A", "B"] * 5,
            }
        )

        with tempfile.NamedTemporaryFile(suffix=".xlsx", delete=False) as f:
            data.to_excel(f.name, index=False)

            # Test data info
            result = get_data_info(f.name)
            assert result["status"] == "success"

            # Test various plots
            with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as output_f:
                result = create_line_plot(
                    f.name, "value1", "value2", "Excel Line Plot", output_f.name
                )
                assert result["status"] == "success"

            os.unlink(output_f.name)
        os.unlink(f.name)

    def test_performance_large_dataset(self):
        """Test performance with larger datasets"""
        # Create larger dataset
        large_data = pd.DataFrame(
            {
                "x": range(1000),
                "y": [i * 2 for i in range(1000)],
                "category": [f"Cat_{i % 10}" for i in range(1000)],
                "value": [i + 100 for i in range(1000)],
            }
        )

        with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False) as f:
            large_data.to_csv(f.name, index=False)

            # Test that functions handle large data
            with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as output_f:
                result = create_scatter_plot(
                    f.name, "x", "y", "Large Dataset Scatter", output_f.name
                )
                assert result["status"] == "success"

            os.unlink(output_f.name)
        os.unlink(f.name)
