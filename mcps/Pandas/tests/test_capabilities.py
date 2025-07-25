"""
Test cases for the pandas capabilities modules.
"""

import pytest
import pandas as pd
import numpy as np
import tempfile
import os
import sys

# Add the parent directory to Python path so we can import src
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.implementation.data_io import load_data_file, save_data_file
from src.implementation.pandas_statistics import (
    get_statistical_summary,
    get_correlation_analysis,
)
from src.implementation.data_cleaning import handle_missing_data, clean_data
from src.implementation.data_profiling import profile_data
from src.implementation.transformations import (
    groupby_operations,
    merge_datasets,
    create_pivot_table,
)
from src.implementation.filtering import filter_data
from src.implementation.memory_optimization import optimize_memory_usage


class TestPandasMCPCapabilities:
    """Test suite for pandas MCP capabilities"""

    @pytest.fixture
    def sample_data(self):
        """Create sample data for testing"""
        return pd.DataFrame(
            {
                "id": range(1, 101),
                "name": [f"Person_{i}" for i in range(1, 101)],
                "age": np.random.randint(18, 80, 100),
                "salary": np.random.randint(30000, 100000, 100),
                "department": np.random.choice(
                    ["Engineering", "Sales", "Marketing", "HR"], 100
                ),
                "score": np.random.uniform(0, 100, 100),
            }
        )

    @pytest.fixture
    def temp_csv_file(self, sample_data):
        """Create a temporary CSV file for testing"""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False) as f:
            sample_data.to_csv(f.name, index=False)
            yield f.name
        os.unlink(f.name)

    def test_load_data_file_csv(self, temp_csv_file):
        """Test loading CSV file"""
        result = load_data_file(temp_csv_file)

        assert result["success"]
        assert "data" in result
        assert "info" in result
        assert result["info"]["shape"] == (100, 6)
        assert len(result["data"]) <= 100  # Limited to 100 rows

    def test_load_data_file_with_columns(self, temp_csv_file):
        """Test loading CSV file with specific columns"""
        result = load_data_file(temp_csv_file, columns=["name", "age"])

        assert result["success"]
        assert result["info"]["shape"][1] == 2  # Only 2 columns
        assert "name" in result["data"][0]
        assert "age" in result["data"][0]

    def test_load_data_file_not_found(self):
        """Test loading non-existent file"""
        result = load_data_file("nonexistent.csv")

        assert not result["success"]
        assert result["error_type"] == "FileNotFoundError"

    def test_save_data_file(self, sample_data):
        """Test saving data to CSV file"""
        data_dict = sample_data.to_dict("records")

        with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False) as f:
            temp_file = f.name

        try:
            result = save_data_file(data_dict, temp_file)

            assert result["success"]
            assert result["rows_saved"] == 100
            assert os.path.exists(temp_file)
        finally:
            if os.path.exists(temp_file):
                os.unlink(temp_file)

    def test_statistical_summary(self, temp_csv_file):
        """Test statistical summary generation"""
        result = get_statistical_summary(temp_csv_file)

        assert result["success"]
        assert "basic_statistics" in result
        assert "additional_statistics" in result
        assert "categorical_statistics" in result
        assert "missing_data" in result

    def test_correlation_analysis(self, temp_csv_file):
        """Test correlation analysis"""
        result = get_correlation_analysis(temp_csv_file)

        assert result["success"]
        assert "correlation_matrix" in result
        assert "analyzed_columns" in result
        assert result["method"] == "pearson"

    def test_handle_missing_data_detect(self, temp_csv_file):
        """Test missing data detection"""
        result = handle_missing_data(temp_csv_file, strategy="detect")

        assert result["success"]
        assert "missing_data_info" in result
        assert "total_missing" in result["missing_data_info"]

    def test_clean_data(self, temp_csv_file):
        """Test data cleaning"""
        result = clean_data(temp_csv_file, remove_duplicates=True, detect_outliers=True)

        assert result["success"]
        assert "cleaning_results" in result
        assert "output_file" in result

    def test_profile_data(self, temp_csv_file):
        """Test data profiling"""
        result = profile_data(temp_csv_file)

        assert result["success"]
        assert "basic_info" in result
        assert "summary" in result
        assert "column_analysis" in result
        assert "quality_checks" in result

    def test_groupby_operations(self, temp_csv_file):
        """Test groupby operations"""
        result = groupby_operations(
            temp_csv_file,
            group_by=["department"],
            operations={"salary": "mean", "age": "avg"},
        )

        assert result["success"]
        assert "group_info" in result
        assert "results" in result

    def test_filter_data(self, temp_csv_file):
        """Test data filtering"""
        filter_conditions = {
            "age": {"operator": "gt", "value": 30},
            "department": {"operator": "in", "value": ["Engineering", "Sales"]},
        }

        result = filter_data(temp_csv_file, filter_conditions)

        assert result["success"]
        assert "filter_stats" in result
        assert "filtered_data" in result

    def test_optimize_memory_usage(self, temp_csv_file):
        """Test memory optimization"""
        result = optimize_memory_usage(temp_csv_file, optimize_dtypes=True)

        assert result["success"]
        assert "optimization_results" in result
        assert "column_memory_usage" in result
        assert "recommendations" in result

    def test_merge_datasets(self, sample_data):
        """Test dataset merging"""
        # Create two datasets
        df1 = sample_data[["id", "name", "age"]].copy()
        df2 = sample_data[["id", "salary", "department"]].copy()

        # Save to temp files
        with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False) as f1:
            df1.to_csv(f1.name, index=False)
            temp_file1 = f1.name

        with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False) as f2:
            df2.to_csv(f2.name, index=False)
            temp_file2 = f2.name

        try:
            result = merge_datasets(temp_file1, temp_file2, join_type="inner", on="id")

            assert result["success"]
            assert "merge_stats" in result
            assert "merged_data" in result
        finally:
            os.unlink(temp_file1)
            os.unlink(temp_file2)

    def test_create_pivot_table(self, temp_csv_file):
        """Test pivot table creation"""
        result = create_pivot_table(
            temp_csv_file, index=["department"], values=["salary"], aggfunc="mean"
        )

        assert result["success"]
        assert "pivot_info" in result
        assert "pivot_table" in result


if __name__ == "__main__":
    pytest.main([__file__])
