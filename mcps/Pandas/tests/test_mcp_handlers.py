"""
Test cases for pandas MCP handlers
"""

import pytest
import pandas as pd
import numpy as np
import os
import tempfile
from unittest.mock import patch

# Import the handlers
from pandasmcp.mcp_handlers import (
    load_data_handler,
    save_data_handler,
    statistical_summary_handler,
    correlation_analysis_handler,
    handle_missing_data_handler,
    clean_data_handler,
    profile_data_handler,
    filter_data_handler,
    optimize_memory_handler,
)


class TestPandasMCPHandlers:
    """Test suite for pandas MCP handlers"""

    @pytest.fixture
    def sample_data(self):
        """Create sample data for testing"""
        return pd.DataFrame(
            {
                "id": range(1, 51),
                "name": [f"Person_{i}" for i in range(1, 51)],
                "age": np.random.randint(18, 80, 50),
                "salary": np.random.randint(30000, 100000, 50),
                "department": np.random.choice(
                    ["Engineering", "Sales", "Marketing"], 50
                ),
            }
        )

    @pytest.fixture
    def temp_csv_file(self, sample_data):
        """Create a temporary CSV file for testing"""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False) as f:
            sample_data.to_csv(f.name, index=False)
            yield f.name
        os.unlink(f.name)

    def test_load_data_handler_success(self, temp_csv_file):
        """Test successful data loading handler"""
        result = load_data_handler(temp_csv_file)

        assert "content" in result
        assert result["_meta"]["tool"] == "load_data"
        assert result["_meta"]["success"]
        assert "isError" not in result

    def test_load_data_handler_file_not_found(self):
        """Test data loading handler with non-existent file"""
        result = load_data_handler("nonexistent.csv")

        assert "content" in result
        assert result["_meta"]["tool"] == "load_data"
        assert result["isError"]
        assert "error" in result["_meta"]

    def test_save_data_handler_success(self, sample_data):
        """Test successful data saving handler"""
        data_dict = sample_data.to_dict("records")

        with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False) as f:
            temp_file = f.name

        try:
            result = save_data_handler(data_dict, temp_file)

            assert "content" in result
            assert result["_meta"]["tool"] == "save_data"
            assert result["_meta"]["success"]
            assert "isError" not in result
        finally:
            if os.path.exists(temp_file):
                os.unlink(temp_file)

    def test_statistical_summary_handler_success(self, temp_csv_file):
        """Test successful statistical summary handler"""
        result = statistical_summary_handler(temp_csv_file)

        assert "content" in result
        assert result["_meta"]["tool"] == "statistical_summary"
        assert result["_meta"]["success"]
        assert "isError" not in result

    def test_correlation_analysis_handler_success(self, temp_csv_file):
        """Test successful correlation analysis handler"""
        result = correlation_analysis_handler(temp_csv_file)

        assert "content" in result
        assert result["_meta"]["tool"] == "correlation_analysis"
        assert result["_meta"]["success"]
        assert "isError" not in result

    def test_handle_missing_data_handler_success(self, temp_csv_file):
        """Test successful missing data handler"""
        result = handle_missing_data_handler(temp_csv_file, strategy="detect")

        assert "content" in result
        assert result["_meta"]["tool"] == "handle_missing_data"
        assert result["_meta"]["success"]
        assert "isError" not in result

    def test_clean_data_handler_success(self, temp_csv_file):
        """Test successful data cleaning handler"""
        result = clean_data_handler(temp_csv_file, remove_duplicates=True)

        assert "content" in result
        assert result["_meta"]["tool"] == "clean_data"
        assert result["_meta"]["success"]
        assert "isError" not in result

    def test_profile_data_handler_success(self, temp_csv_file):
        """Test successful data profiling handler"""
        result = profile_data_handler(temp_csv_file)

        assert "content" in result
        assert result["_meta"]["tool"] == "profile_data"
        assert result["_meta"]["success"]
        assert "isError" not in result

    def test_filter_data_handler_success(self, temp_csv_file):
        """Test successful data filtering handler"""
        filter_conditions = {"age": {"operator": "gt", "value": 25}}

        result = filter_data_handler(temp_csv_file, filter_conditions)

        assert "content" in result
        assert result["_meta"]["tool"] == "filter_data"
        assert result["_meta"]["success"]
        assert "isError" not in result

    def test_optimize_memory_handler_success(self, temp_csv_file):
        """Test successful memory optimization handler"""
        result = optimize_memory_handler(temp_csv_file, optimize_dtypes=True)

        assert "content" in result
        assert result["_meta"]["tool"] == "optimize_memory"
        assert result["_meta"]["success"]
        assert "isError" not in result

    def test_handler_error_handling(self):
        """Test error handling in handlers"""
        # Test with non-existent file
        result = load_data_handler("nonexistent.csv")

        assert result["isError"]
        assert "error" in result["_meta"]
        assert result["_meta"]["tool"] == "load_data"

    @patch("pandasmcp.mcp_handlers.load_data_file")
    def test_handler_exception_handling(self, mock_load_data):
        """Test exception handling in handlers"""
        # Mock an exception
        mock_load_data.side_effect = Exception("Test exception")

        result = load_data_handler("test.csv")

        assert result["isError"]
        assert "error" in result["_meta"]
        assert result["_meta"]["tool"] == "load_data"


if __name__ == "__main__":
    pytest.main([__file__])
