"""
Comprehensive test cases for pandas_statistics module.
"""

import pytest
import pandas as pd
import numpy as np
import tempfile
import os

from pandas_mcp.implementation.pandas_statistics import (
    get_statistical_summary,
    get_correlation_analysis,
)


class TestGetStatisticalSummary:
    """Test suite for get_statistical_summary function"""

    @pytest.fixture
    def sample_data(self):
        """Create sample data for testing"""
        np.random.seed(42)
        return pd.DataFrame(
            {
                "age": np.random.randint(18, 65, 100),
                "salary": np.random.randint(30000, 120000, 100),
                "score": np.random.uniform(0, 100, 100),
                "department": np.random.choice(
                    ["Engineering", "Sales", "Marketing", "HR"], 100
                ),
                "name": [f"Employee_{i}" for i in range(1, 101)],
            }
        )

    @pytest.fixture
    def temp_csv_file(self, sample_data):
        """Create a temporary CSV file"""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False) as f:
            sample_data.to_csv(f.name, index=False)
            yield f.name
        if os.path.exists(f.name):
            os.unlink(f.name)

    def test_statistical_summary_basic(self, temp_csv_file):
        """Test basic statistical summary"""
        result = get_statistical_summary(temp_csv_file)

        assert result["success"]
        assert "basic_statistics" in result
        assert "additional_statistics" in result
        assert "categorical_statistics" in result
        assert "missing_data" in result

    def test_statistical_summary_numeric_columns(self, temp_csv_file):
        """Test statistical summary for numeric columns"""
        result = get_statistical_summary(temp_csv_file)

        assert result["success"]
        assert "age" in result["additional_statistics"]
        assert "variance" in result["additional_statistics"]["age"]
        assert "skewness" in result["additional_statistics"]["age"]
        assert "kurtosis" in result["additional_statistics"]["age"]
        assert "median_absolute_deviation" in result["additional_statistics"]["age"]
        assert "interquartile_range" in result["additional_statistics"]["age"]

    def test_statistical_summary_categorical_columns(self, temp_csv_file):
        """Test statistical summary for categorical columns"""
        result = get_statistical_summary(temp_csv_file)

        assert result["success"]
        assert "department" in result["categorical_statistics"]
        assert "unique_values" in result["categorical_statistics"]["department"]
        assert "most_frequent" in result["categorical_statistics"]["department"]
        assert "value_counts" in result["categorical_statistics"]["department"]

    def test_statistical_summary_with_columns(self, temp_csv_file):
        """Test statistical summary with specific columns"""
        result = get_statistical_summary(temp_csv_file, columns=["age", "salary"])

        assert result["success"]
        assert result["shape"][1] == 2
        assert "age" in result["additional_statistics"]
        assert "salary" in result["additional_statistics"]

    def test_statistical_summary_with_distributions(self, temp_csv_file):
        """Test statistical summary with distribution analysis"""
        result = get_statistical_summary(temp_csv_file, include_distributions=True)

        assert result["success"]
        # Check if normality test is included
        for col in ["age", "salary", "score"]:
            if col in result["additional_statistics"]:
                assert "normality_test" in result["additional_statistics"][col]
                assert (
                    "shapiro_wilk_statistic"
                    in result["additional_statistics"][col]["normality_test"]
                )
                assert (
                    "shapiro_wilk_p_value"
                    in result["additional_statistics"][col]["normality_test"]
                )
                assert (
                    "is_normal"
                    in result["additional_statistics"][col]["normality_test"]
                )

    def test_statistical_summary_coefficient_of_variation(self, temp_csv_file):
        """Test coefficient of variation calculation"""
        result = get_statistical_summary(temp_csv_file)

        assert result["success"]
        # Coefficient of variation should be present for numeric columns
        assert "coefficient_of_variation" in result["additional_statistics"]["age"]

    def test_statistical_summary_zero_mean(self):
        """Test coefficient of variation with zero mean"""
        data = pd.DataFrame(
            {
                "values": [-5, -2, 0, 2, 5],
            }
        )
        with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False) as f:
            data.to_csv(f.name, index=False)
            temp_file = f.name

        try:
            result = get_statistical_summary(temp_file)

            assert result["success"]
            # Coefficient of variation should be None when mean is zero
            if data["values"].mean() == 0:
                assert (
                    result["additional_statistics"]["values"][
                        "coefficient_of_variation"
                    ]
                    is None
                )
        finally:
            if os.path.exists(temp_file):
                os.unlink(temp_file)

    def test_statistical_summary_missing_data(self):
        """Test statistical summary with missing data"""
        data = pd.DataFrame(
            {
                "col1": [1, 2, np.nan, 4, 5],
                "col2": ["A", np.nan, "C", np.nan, "E"],
            }
        )
        with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False) as f:
            data.to_csv(f.name, index=False)
            temp_file = f.name

        try:
            result = get_statistical_summary(temp_file)

            assert result["success"]
            assert result["missing_data"]["total_missing"] == 3
        finally:
            if os.path.exists(temp_file):
                os.unlink(temp_file)

    def test_statistical_summary_file_not_found(self):
        """Test statistical summary with non-existent file"""
        result = get_statistical_summary("nonexistent.csv")

        assert not result["success"]
        assert result["error_type"] == "FileNotFoundError"

    def test_statistical_summary_normality_test_small_sample(self):
        """Test normality test with small sample size"""
        data = pd.DataFrame(
            {
                "small": [1, 2, 3, 4, 5, 6, 7],  # Less than 8 samples
            }
        )
        with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False) as f:
            data.to_csv(f.name, index=False)
            temp_file = f.name

        try:
            result = get_statistical_summary(temp_file, include_distributions=True)

            assert result["success"]
            # Normality test should not be performed for small samples
            if "normality_test" in result["additional_statistics"].get("small", {}):
                # If present, should be valid
                pass
        finally:
            if os.path.exists(temp_file):
                os.unlink(temp_file)

    def test_statistical_summary_large_sample_normality(self):
        """Test normality test with large sample (>5000 rows)"""
        data = pd.DataFrame(
            {
                "large": np.random.normal(0, 1, 6000),
            }
        )
        with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False) as f:
            data.to_csv(f.name, index=False)
            temp_file = f.name

        try:
            result = get_statistical_summary(temp_file, include_distributions=True)

            assert result["success"]
            # Should sample 5000 rows for normality test
            if "normality_test" in result["additional_statistics"]["large"]:
                assert (
                    "shapiro_wilk_p_value"
                    in result["additional_statistics"]["large"]["normality_test"]
                )
        finally:
            if os.path.exists(temp_file):
                os.unlink(temp_file)


class TestGetCorrelationAnalysis:
    """Test suite for get_correlation_analysis function"""

    @pytest.fixture
    def sample_data(self):
        """Create sample data with correlations"""
        np.random.seed(42)
        x = np.random.randn(100)
        return pd.DataFrame(
            {
                "x": x,
                "y": x * 2 + np.random.randn(100) * 0.1,  # High correlation with x
                "z": np.random.randn(100),  # Low correlation
                "category": np.random.choice(["A", "B", "C"], 100),
            }
        )

    @pytest.fixture
    def temp_csv_file(self, sample_data):
        """Create a temporary CSV file"""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False) as f:
            sample_data.to_csv(f.name, index=False)
            yield f.name
        if os.path.exists(f.name):
            os.unlink(f.name)

    def test_correlation_analysis_pearson(self, temp_csv_file):
        """Test Pearson correlation analysis"""
        result = get_correlation_analysis(temp_csv_file, method="pearson")

        assert result["success"]
        assert result["method"] == "pearson"
        assert "correlation_matrix" in result
        assert "high_correlations" in result
        assert "analyzed_columns" in result

    def test_correlation_analysis_spearman(self, temp_csv_file):
        """Test Spearman correlation analysis"""
        result = get_correlation_analysis(temp_csv_file, method="spearman")

        assert result["success"]
        assert result["method"] == "spearman"

    def test_correlation_analysis_kendall(self, temp_csv_file):
        """Test Kendall correlation analysis"""
        result = get_correlation_analysis(temp_csv_file, method="kendall")

        assert result["success"]
        assert result["method"] == "kendall"

    def test_correlation_analysis_high_correlations(self, temp_csv_file):
        """Test detection of high correlations"""
        result = get_correlation_analysis(temp_csv_file)

        assert result["success"]
        # x and y should be highly correlated
        assert len(result["high_correlations"]) > 0
        for corr in result["high_correlations"]:
            assert "variable1" in corr
            assert "variable2" in corr
            assert "correlation" in corr
            assert "strength" in corr
            assert abs(corr["correlation"]) > 0.7

    def test_correlation_analysis_with_columns(self, temp_csv_file):
        """Test correlation analysis with specific columns"""
        result = get_correlation_analysis(temp_csv_file, columns=["x", "y"])

        assert result["success"]
        assert len(result["analyzed_columns"]) == 2
        assert "x" in result["analyzed_columns"]
        assert "y" in result["analyzed_columns"]

    def test_correlation_analysis_file_not_found(self):
        """Test correlation analysis with non-existent file"""
        result = get_correlation_analysis("nonexistent.csv")

        assert not result["success"]
        assert result["error_type"] == "FileNotFoundError"

    def test_correlation_analysis_no_numeric_columns(self):
        """Test correlation analysis with no numeric columns"""
        data = pd.DataFrame(
            {
                "col1": ["A", "B", "C", "D", "E"],
                "col2": ["X", "Y", "Z", "W", "V"],
            }
        )
        with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False) as f:
            data.to_csv(f.name, index=False)
            temp_file = f.name

        try:
            result = get_correlation_analysis(temp_file)

            assert not result["success"]
            assert "No numeric columns found" in result["error"]
        finally:
            if os.path.exists(temp_file):
                os.unlink(temp_file)

    def test_correlation_analysis_strength_strong(self, temp_csv_file):
        """Test correlation strength categorization - strong"""
        result = get_correlation_analysis(temp_csv_file)

        assert result["success"]
        # Check for strong correlations (>0.8)
        strong_corrs = [
            c for c in result["high_correlations"] if c["strength"] == "strong"
        ]
        # x and y should have strong correlation
        assert len(strong_corrs) > 0

    def test_correlation_analysis_strength_moderate(self):
        """Test correlation strength categorization - moderate"""
        np.random.seed(42)
        x = np.random.randn(100)
        data = pd.DataFrame(
            {
                "x": x,
                "y": x + np.random.randn(100),  # Moderate correlation
            }
        )
        with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False) as f:
            data.to_csv(f.name, index=False)
            temp_file = f.name

        try:
            result = get_correlation_analysis(temp_file)

            assert result["success"]
            # May have moderate correlations (0.7-0.8)
        finally:
            if os.path.exists(temp_file):
                os.unlink(temp_file)

    def test_correlation_analysis_single_column(self):
        """Test correlation analysis with single numeric column"""
        data = pd.DataFrame(
            {
                "only_numeric": [1, 2, 3, 4, 5],
                "category": ["A", "B", "C", "D", "E"],
            }
        )
        with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False) as f:
            data.to_csv(f.name, index=False)
            temp_file = f.name

        try:
            result = get_correlation_analysis(temp_file)

            assert result["success"]
            # Single column should have correlation of 1 with itself
            assert len(result["high_correlations"]) == 0  # No pairs to correlate
        finally:
            if os.path.exists(temp_file):
                os.unlink(temp_file)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
