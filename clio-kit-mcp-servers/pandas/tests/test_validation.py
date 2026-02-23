"""
Test cases for data validation and hypothesis testing capabilities.
"""

import pytest
import pandas as pd
import numpy as np
import tempfile
import os

from pandas_mcp.implementation.validation import (
    validate_data,
    hypothesis_testing,
)


class TestDataValidation:
    """Test suite for data validation"""

    @pytest.fixture
    def sample_data(self):
        """Create sample data for validation"""
        return pd.DataFrame(
            {
                "id": range(1, 101),
                "age": np.random.randint(18, 80, 100),
                "score": np.random.randint(0, 100, 100),
                "category": np.random.choice(["A", "B", "C"], 100),
                "email": [f"user{i}@test.com" for i in range(100)],
            }
        )

    @pytest.fixture
    def temp_file(self, sample_data):
        """Create temporary file"""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False) as f:
            sample_data.to_csv(f.name, index=False)
            yield f.name
        if os.path.exists(f.name):
            os.unlink(f.name)

    def test_validate_data_min_value_success(self, temp_file):
        """Test min value validation"""
        rules = {"age": {"min_value": 0}, "score": {"min_value": 0}}

        result = validate_data(temp_file, rules)

        assert result["success"]
        assert "validation_results" in result
        assert result["validation_results"]["age"]["valid"]
        assert result["validation_results"]["score"]["valid"]

    def test_validate_data_max_value_success(self, temp_file):
        """Test max value validation"""
        rules = {"age": {"max_value": 100}, "score": {"max_value": 100}}

        result = validate_data(temp_file, rules)

        assert result["success"]
        assert result["validation_results"]["age"]["valid"]

    def test_validate_data_min_value_violation(self):
        """Test min value violation"""
        df = pd.DataFrame({"value": [-10, 5, 10, 15, 20]})

        with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False) as f:
            df.to_csv(f.name, index=False)
            temp_file = f.name

        try:
            rules = {"value": {"min_value": 0}}
            result = validate_data(temp_file, rules)

            assert result["success"]
            assert not result["validation_results"]["value"]["valid"]
            assert len(result["validation_results"]["value"]["violations"]) > 0
        finally:
            os.unlink(temp_file)

    def test_validate_data_max_value_violation(self):
        """Test max value violation"""
        df = pd.DataFrame({"value": [5, 10, 15, 105, 110]})

        with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False) as f:
            df.to_csv(f.name, index=False)
            temp_file = f.name

        try:
            rules = {"value": {"max_value": 100}}
            result = validate_data(temp_file, rules)

            assert result["success"]
            assert not result["validation_results"]["value"]["valid"]
            violations = result["validation_results"]["value"]["violations"]
            assert len(violations) > 0
            assert violations[0]["rule"] == "max_value"
        finally:
            os.unlink(temp_file)

    def test_validate_data_dtype_check(self, temp_file):
        """Test data type validation"""
        rules = {"id": {"dtype": "int64"}, "category": {"dtype": "object"}}

        result = validate_data(temp_file, rules)

        assert result["success"]
        assert result["validation_results"]["id"]["valid"]
        assert result["validation_results"]["category"]["valid"]

    def test_validate_data_null_not_allowed(self):
        """Test null value validation when not allowed"""
        df = pd.DataFrame({"value": [1, 2, None, 4, 5]})

        with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False) as f:
            df.to_csv(f.name, index=False)
            temp_file = f.name

        try:
            rules = {"value": {"allow_null": False}}
            result = validate_data(temp_file, rules)

            assert result["success"]
            assert not result["validation_results"]["value"]["valid"]
            assert any(
                v["rule"] == "allow_null"
                for v in result["validation_results"]["value"]["violations"]
            )
        finally:
            os.unlink(temp_file)

    def test_validate_data_uniqueness(self, temp_file):
        """Test uniqueness validation"""
        rules = {"id": {"unique": True}}

        result = validate_data(temp_file, rules)

        assert result["success"]
        # IDs are unique, so should be valid
        assert result["validation_results"]["id"]["valid"]

    def test_validate_data_uniqueness_violation(self):
        """Test uniqueness violation"""
        df = pd.DataFrame({"value": [1, 2, 2, 3, 3, 3]})

        with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False) as f:
            df.to_csv(f.name, index=False)
            temp_file = f.name

        try:
            rules = {"value": {"unique": True}}
            result = validate_data(temp_file, rules)

            assert result["success"]
            assert not result["validation_results"]["value"]["valid"]
        finally:
            os.unlink(temp_file)

    def test_validate_data_pattern_match(self, temp_file):
        """Test pattern matching"""
        # Email pattern
        rules = {
            "email": {"pattern": r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$"}
        }

        result = validate_data(temp_file, rules)

        assert result["success"]
        # Our test emails should match
        assert result["validation_results"]["email"]["valid"]

    def test_validate_data_column_not_found(self, temp_file):
        """Test validation with non-existent column"""
        rules = {"nonexistent": {"min_value": 0}}

        result = validate_data(temp_file, rules)

        # Non-existent columns return error
        assert not result["success"]

    def test_validate_data_file_not_found(self):
        """Test with non-existent file"""
        result = validate_data("nonexistent.csv", {})

        assert not result["success"]
        assert result["error_type"] == "FileNotFoundError"

    def test_validate_data_summary(self, temp_file):
        """Test validation summary"""
        rules = {
            "age": {"min_value": 0, "max_value": 100},
            "score": {"min_value": 0, "max_value": 100},
        }

        result = validate_data(temp_file, rules)

        assert result["success"]
        assert "validation_summary" in result
        assert "overall_valid" in result["validation_summary"]
        assert "total_columns_validated" in result["validation_summary"]
        assert result["validation_summary"]["total_columns_validated"] == 2

    def test_validate_data_statistics_numeric(self, temp_file):
        """Test that statistics are included for numeric columns"""
        rules = {"age": {"min_value": 0}}

        result = validate_data(temp_file, rules)

        assert result["success"]
        stats = result["validation_results"]["age"]["statistics"]
        assert "count" in stats
        assert "mean" in stats
        assert "std" in stats
        assert "min" in stats
        assert "max" in stats

    def test_validate_data_statistics_categorical(self, temp_file):
        """Test that statistics are included for categorical columns"""
        rules = {"category": {}}

        result = validate_data(temp_file, rules)

        assert result["success"]
        stats = result["validation_results"]["category"]["statistics"]
        assert "count" in stats
        assert "unique_count" in stats
        assert "most_frequent" in stats


class TestHypothesisTesting:
    """Test suite for hypothesis testing"""

    @pytest.fixture
    def sample_data(self):
        """Create sample data for hypothesis testing"""
        np.random.seed(42)
        return pd.DataFrame(
            {
                "group": np.repeat(["A", "B"], 50),
                "value1": np.concatenate(
                    [np.random.normal(10, 2, 50), np.random.normal(12, 2, 50)]
                ),
                "value2": np.random.normal(50, 10, 100),
                "category": np.random.choice(["X", "Y", "Z"], 100),
            }
        )

    @pytest.fixture
    def temp_file(self, sample_data):
        """Create temporary file"""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False) as f:
            sample_data.to_csv(f.name, index=False)
            yield f.name
        if os.path.exists(f.name):
            os.unlink(f.name)

    def test_hypothesis_testing_one_sample_ttest(self, temp_file):
        """Test one-sample t-test"""
        result = hypothesis_testing(
            temp_file, test_type="t_test", column1="value1", alpha=0.05
        )

        assert result["success"]
        assert result["test_info"]["test_type"] == "one_sample_t_test"
        assert "statistic" in result["results"]
        assert "p_value" in result["results"]
        assert "is_significant" in result["results"]

    def test_hypothesis_testing_two_sample_ttest(self, temp_file):
        """Test two-sample t-test"""
        result = hypothesis_testing(
            temp_file,
            test_type="t_test",
            column1="value1",
            column2="value2",
            alpha=0.05,
        )

        assert result["success"]
        assert result["test_info"]["test_type"] == "two_sample_t_test"
        assert "sample1_mean" in result["test_info"]
        assert "sample2_mean" in result["test_info"]

    def test_hypothesis_testing_chi_square_goodness_of_fit(self, temp_file):
        """Test chi-square goodness of fit"""
        result = hypothesis_testing(
            temp_file, test_type="chi_square", column1="category", alpha=0.05
        )

        assert result["success"]
        assert result["test_info"]["test_type"] == "chi_square_goodness_of_fit"

    def test_hypothesis_testing_chi_square_independence(self, temp_file):
        """Test chi-square test of independence"""
        result = hypothesis_testing(
            temp_file,
            test_type="chi_square",
            column1="group",
            column2="category",
            alpha=0.05,
        )

        assert result["success"]
        assert result["test_info"]["test_type"] == "chi_square_independence"
        assert "degrees_of_freedom" in result["test_info"]

    def test_hypothesis_testing_correlation(self, temp_file):
        """Test Pearson correlation"""
        result = hypothesis_testing(
            temp_file,
            test_type="correlation",
            column1="value1",
            column2="value2",
            alpha=0.05,
        )

        assert result["success"]
        assert result["test_info"]["test_type"] == "pearson_correlation"
        assert "correlation_coefficient" in result["test_info"]

    def test_hypothesis_testing_anova(self, temp_file):
        """Test ANOVA"""
        result = hypothesis_testing(
            temp_file, test_type="anova", column1="value1", column2="group", alpha=0.05
        )

        assert result["success"]
        assert result["test_info"]["test_type"] == "one_way_anova"
        assert "number_of_groups" in result["test_info"]

    def test_hypothesis_testing_file_not_found(self):
        """Test with non-existent file"""
        result = hypothesis_testing(
            "nonexistent.csv", test_type="t_test", column1="col1"
        )

        assert not result["success"]
        assert result["error_type"] == "FileNotFoundError"

    def test_hypothesis_testing_column_not_found(self, temp_file):
        """Test with non-existent column"""
        result = hypothesis_testing(
            temp_file, test_type="t_test", column1="nonexistent"
        )

        assert not result["success"]
        assert "not found" in result["error"]

    def test_hypothesis_testing_invalid_test_type(self, temp_file):
        """Test with invalid test type"""
        result = hypothesis_testing(
            temp_file, test_type="invalid_test", column1="value1"
        )

        assert not result["success"]
        assert "Unknown test type" in result["error"]

    def test_hypothesis_testing_correlation_missing_column2(self, temp_file):
        """Test correlation without second column"""
        result = hypothesis_testing(
            temp_file, test_type="correlation", column1="value1"
        )

        assert not result["success"]
        assert "requires two columns" in result["error"]

    def test_hypothesis_testing_anova_missing_grouping(self, temp_file):
        """Test ANOVA without grouping variable"""
        result = hypothesis_testing(temp_file, test_type="anova", column1="value1")

        assert not result["success"]
        assert "requires grouping variable" in result["error"]

    def test_hypothesis_testing_interpretation(self, temp_file):
        """Test that interpretation is included"""
        result = hypothesis_testing(temp_file, test_type="t_test", column1="value1")

        assert result["success"]
        assert "conclusion" in result["results"]
        assert "effect_size" in result["results"]
        assert result["results"]["conclusion"] in [
            "Reject null hypothesis",
            "Fail to reject null hypothesis",
        ]

    def test_hypothesis_testing_alpha_level(self, temp_file):
        """Test different alpha levels"""
        result = hypothesis_testing(
            temp_file, test_type="t_test", column1="value1", alpha=0.01
        )

        assert result["success"]
        assert result["results"]["alpha"] == 0.01


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
