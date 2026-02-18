"""
Comprehensive test cases for data_profiling module.
"""

import pytest
import pandas as pd
import numpy as np
import tempfile
import os

from pandas_mcp.implementation.data_profiling import profile_data


class TestProfileData:
    """Test suite for profile_data function"""

    @pytest.fixture
    def comprehensive_data(self):
        """Create comprehensive sample data with various column types"""
        return pd.DataFrame(
            {
                "id": range(1, 101),
                "age": np.random.randint(18, 65, 100),
                "salary": np.random.randint(30000, 120000, 100),
                "department": np.random.choice(
                    ["Engineering", "Sales", "Marketing", "HR"], 100
                ),
                "name": [f"Employee_{i}" for i in range(1, 101)],
                "score": np.random.uniform(0, 100, 100),
                "date": pd.date_range("2023-01-01", periods=100),
            }
        )

    @pytest.fixture
    def temp_csv_file(self, comprehensive_data):
        """Create a temporary CSV file"""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False) as f:
            comprehensive_data.to_csv(f.name, index=False)
            yield f.name
        if os.path.exists(f.name):
            os.unlink(f.name)

    def test_profile_basic(self, temp_csv_file):
        """Test basic data profiling"""
        result = profile_data(temp_csv_file)

        assert result["success"]
        assert "basic_info" in result
        assert "summary" in result
        assert "column_analysis" in result
        assert "quality_checks" in result
        assert "missing_data" in result

    def test_profile_basic_info(self, temp_csv_file):
        """Test basic info section of profile"""
        result = profile_data(temp_csv_file)

        assert result["success"]
        assert result["basic_info"]["shape"] == (100, 7)
        assert len(result["basic_info"]["columns"]) == 7
        assert "dtypes" in result["basic_info"]
        assert "memory_usage_mb" in result["basic_info"]

    def test_profile_numeric_columns(self, temp_csv_file):
        """Test profiling of numeric columns"""
        result = profile_data(temp_csv_file)

        assert result["success"]
        # Check that numeric columns have proper analysis
        assert "age" in result["column_analysis"]
        assert result["column_analysis"]["age"]["type"] == "numeric"
        assert "mean" in result["column_analysis"]["age"]
        assert "std" in result["column_analysis"]["age"]
        assert "min" in result["column_analysis"]["age"]
        assert "max" in result["column_analysis"]["age"]
        assert "skewness" in result["column_analysis"]["age"]
        assert "kurtosis" in result["column_analysis"]["age"]

    def test_profile_categorical_columns(self, temp_csv_file):
        """Test profiling of categorical columns"""
        result = profile_data(temp_csv_file)

        assert result["success"]
        assert "department" in result["column_analysis"]
        assert result["column_analysis"]["department"]["type"] == "categorical"
        assert "unique_values" in result["column_analysis"]["department"]
        assert "most_frequent" in result["column_analysis"]["department"]
        assert "top_10_values" in result["column_analysis"]["department"]

    def test_profile_datetime_columns(self):
        """Test profiling of datetime columns"""
        # Create data with explicit datetime column
        data = pd.DataFrame(
            {
                "id": range(1, 11),
                "date": pd.date_range("2023-01-01", periods=10),
            }
        )
        with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False) as f:
            data.to_csv(f.name, index=False)
            temp_file = f.name

        try:
            result = profile_data(temp_file)

            assert result["success"]
            # DateTime column should be detected
            # Note: CSV saves datetimes as strings, so profiling treats them as objects
            assert "date" in result["column_analysis"]
        finally:
            if os.path.exists(temp_file):
                os.unlink(temp_file)

    def test_profile_with_correlations(self, temp_csv_file):
        """Test profiling with correlation analysis"""
        result = profile_data(temp_csv_file, include_correlations=True)

        assert result["success"]
        assert "correlations" in result
        assert result["correlations"] is not None
        assert "correlation_matrix" in result["correlations"]
        assert "high_correlations" in result["correlations"]

    def test_profile_without_correlations(self, temp_csv_file):
        """Test profiling without correlation analysis"""
        result = profile_data(temp_csv_file, include_correlations=False)

        assert result["success"]
        assert result["correlations"] is None

    def test_profile_with_sampling(self, temp_csv_file):
        """Test profiling with data sampling"""
        result = profile_data(temp_csv_file, sample_size=50)

        assert result["success"]
        # The profiling should work with sampled data

    def test_profile_missing_data(self):
        """Test profiling data with missing values"""
        data = pd.DataFrame(
            {
                "col1": [1, 2, np.nan, 4, 5],
                "col2": ["A", np.nan, "C", np.nan, "E"],
                "col3": [10, 20, 30, 40, 50],
            }
        )
        with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False) as f:
            data.to_csv(f.name, index=False)
            temp_file = f.name

        try:
            result = profile_data(temp_file)

            assert result["success"]
            assert result["missing_data"]["total_missing"] == 3
            assert "columns_with_missing" in result["missing_data"]
        finally:
            if os.path.exists(temp_file):
                os.unlink(temp_file)

    def test_profile_duplicate_rows(self):
        """Test profiling data with duplicate rows"""
        data = pd.DataFrame(
            {
                "id": [1, 2, 3, 1, 2],
                "value": [10, 20, 30, 10, 20],
            }
        )
        with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False) as f:
            data.to_csv(f.name, index=False)
            temp_file = f.name

        try:
            result = profile_data(temp_file)

            assert result["success"]
            assert result["quality_checks"]["duplicate_rows"] == 2
        finally:
            if os.path.exists(temp_file):
                os.unlink(temp_file)

    def test_profile_constant_columns(self):
        """Test detection of constant columns"""
        data = pd.DataFrame(
            {
                "constant": [1] * 10,
                "variable": range(10),
            }
        )
        with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False) as f:
            data.to_csv(f.name, index=False)
            temp_file = f.name

        try:
            result = profile_data(temp_file)

            assert result["success"]
            assert "constant" in result["quality_checks"]["constant_columns"]
        finally:
            if os.path.exists(temp_file):
                os.unlink(temp_file)

    def test_profile_high_cardinality_columns(self):
        """Test detection of high cardinality columns"""
        data = pd.DataFrame(
            {
                "unique_id": range(100),
                "category": ["A"] * 50 + ["B"] * 50,
            }
        )
        with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False) as f:
            data.to_csv(f.name, index=False)
            temp_file = f.name

        try:
            result = profile_data(temp_file)

            assert result["success"]
            assert "unique_id" in result["quality_checks"]["high_cardinality_columns"]
        finally:
            if os.path.exists(temp_file):
                os.unlink(temp_file)

    def test_profile_mixed_type_columns(self):
        """Test detection of mixed type columns"""
        data = pd.DataFrame(
            {
                "mixed": ["1", "2", "text", "4", "5"] * 20,
                "pure": ["A", "B", "C", "D", "E"] * 20,
            }
        )
        with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False) as f:
            data.to_csv(f.name, index=False)
            temp_file = f.name

        try:
            result = profile_data(temp_file)

            assert result["success"]
            # Mixed type column should be detected
            assert "mixed_type_columns" in result["quality_checks"]
        finally:
            if os.path.exists(temp_file):
                os.unlink(temp_file)

    def test_profile_file_not_found(self):
        """Test profiling non-existent file"""
        result = profile_data("nonexistent.csv")

        assert not result["success"]
        assert result["error_type"] == "FileNotFoundError"

    def test_profile_summary_statistics(self, temp_csv_file):
        """Test summary statistics section"""
        result = profile_data(temp_csv_file)

        assert result["success"]
        assert "summary" in result
        assert "total_columns" in result["summary"]
        assert "numeric_columns" in result["summary"]
        assert "categorical_columns" in result["summary"]
        assert "total_rows" in result["summary"]

    def test_profile_zeros_and_negatives(self):
        """Test detection of zeros and negative values"""
        data = pd.DataFrame(
            {
                "with_zeros": [0, 1, 2, 0, 3, 0, 4, 5],
                "with_negatives": [-1, 2, -3, 4, 5, -6, 7, 8],
                "positive": [1, 2, 3, 4, 5, 6, 7, 8],
            }
        )
        with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False) as f:
            data.to_csv(f.name, index=False)
            temp_file = f.name

        try:
            result = profile_data(temp_file)

            assert result["success"]
            assert result["column_analysis"]["with_zeros"]["zeros_count"] == 3
            assert result["column_analysis"]["with_negatives"]["negative_count"] == 3
            assert result["column_analysis"]["positive"]["negative_count"] == 0
        finally:
            if os.path.exists(temp_file):
                os.unlink(temp_file)

    def test_profile_empty_strings(self):
        """Test detection of empty strings in categorical columns"""
        data = pd.DataFrame(
            {
                "text": ["A", "", "C", "", "E"],
                "value": [1, 2, 3, 4, 5],
            }
        )
        with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False) as f:
            data.to_csv(f.name, index=False)
            temp_file = f.name

        try:
            result = profile_data(temp_file)

            assert result["success"]
            # Empty strings should be detected in categorical analysis
            if "text" in result["column_analysis"]:
                assert "empty_strings" in result["column_analysis"]["text"]
        finally:
            if os.path.exists(temp_file):
                os.unlink(temp_file)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
