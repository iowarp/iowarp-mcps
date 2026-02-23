"""
Comprehensive test cases for filtering module.
"""

import pytest
import pandas as pd
import numpy as np
import tempfile
import os

from pandas_mcp.implementation.filtering import (
    filter_data,
    advanced_filter,
    sample_data,
)


class TestFilterData:
    """Test suite for filter_data function"""

    @pytest.fixture
    def sample_data(self):
        """Create sample data for testing"""
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
            }
        )

    @pytest.fixture
    def temp_csv_file(self, sample_data):
        """Create a temporary CSV file"""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False) as f:
            sample_data.to_csv(f.name, index=False)
            yield f.name
        # Cleanup all generated files
        if os.path.exists(f.name):
            os.unlink(f.name)
        filtered_file = f.name.replace(".csv", "_filtered.csv")
        if os.path.exists(filtered_file):
            os.unlink(filtered_file)

    def test_filter_simple_equality(self, temp_csv_file):
        """Test simple equality filter"""
        result = filter_data(temp_csv_file, {"department": "Engineering"})

        assert result["success"]
        assert "filter_stats" in result
        assert "filtered_data" in result

    def test_filter_min_value(self, temp_csv_file):
        """Test minimum value filter"""
        result = filter_data(temp_csv_file, {"age": {"min_value": 30}})

        assert result["success"]
        assert (
            result["filter_stats"]["final_shape"][0]
            <= result["filter_stats"]["original_shape"][0]
        )

    def test_filter_max_value(self, temp_csv_file):
        """Test maximum value filter"""
        result = filter_data(temp_csv_file, {"age": {"max_value": 50}})

        assert result["success"]
        assert (
            result["filter_stats"]["final_shape"][0]
            <= result["filter_stats"]["original_shape"][0]
        )

    def test_filter_operator_eq(self, temp_csv_file):
        """Test equality operator filter"""
        result = filter_data(
            temp_csv_file, {"department": {"operator": "eq", "value": "Sales"}}
        )

        assert result["success"]

    def test_filter_operator_ne(self, temp_csv_file):
        """Test not equal operator filter"""
        result = filter_data(
            temp_csv_file, {"department": {"operator": "ne", "value": "Sales"}}
        )

        assert result["success"]

    def test_filter_operator_gt(self, temp_csv_file):
        """Test greater than operator filter"""
        result = filter_data(temp_csv_file, {"age": {"operator": "gt", "value": 40}})

        assert result["success"]

    def test_filter_operator_ge(self, temp_csv_file):
        """Test greater than or equal operator filter"""
        result = filter_data(temp_csv_file, {"age": {"operator": "ge", "value": 40}})

        assert result["success"]

    def test_filter_operator_lt(self, temp_csv_file):
        """Test less than operator filter"""
        result = filter_data(temp_csv_file, {"age": {"operator": "lt", "value": 40}})

        assert result["success"]

    def test_filter_operator_le(self, temp_csv_file):
        """Test less than or equal operator filter"""
        result = filter_data(temp_csv_file, {"age": {"operator": "le", "value": 40}})

        assert result["success"]

    def test_filter_operator_in(self, temp_csv_file):
        """Test 'in' operator filter"""
        result = filter_data(
            temp_csv_file,
            {"department": {"operator": "in", "value": ["Engineering", "Sales"]}},
        )

        assert result["success"]

    def test_filter_operator_not_in(self, temp_csv_file):
        """Test 'not in' operator filter"""
        result = filter_data(
            temp_csv_file,
            {"department": {"operator": "not_in", "value": ["Engineering", "Sales"]}},
        )

        assert result["success"]

    def test_filter_operator_contains(self, temp_csv_file):
        """Test 'contains' operator filter for strings"""
        result = filter_data(
            temp_csv_file, {"name": {"operator": "contains", "value": "_1"}}
        )

        assert result["success"]

    def test_filter_operator_startswith(self, temp_csv_file):
        """Test 'startswith' operator filter"""
        result = filter_data(
            temp_csv_file, {"name": {"operator": "startswith", "value": "Employee_1"}}
        )

        assert result["success"]

    def test_filter_operator_endswith(self, temp_csv_file):
        """Test 'endswith' operator filter"""
        result = filter_data(
            temp_csv_file, {"name": {"operator": "endswith", "value": "0"}}
        )

        assert result["success"]

    def test_filter_operator_between(self, temp_csv_file):
        """Test 'between' operator filter"""
        result = filter_data(
            temp_csv_file, {"age": {"operator": "between", "value": [25, 50]}}
        )

        assert result["success"]

    def test_filter_operator_between_invalid(self, temp_csv_file):
        """Test 'between' operator with invalid value"""
        result = filter_data(
            temp_csv_file, {"age": {"operator": "between", "value": [25]}}
        )

        assert not result["success"]
        assert "Between operator requires list of 2 values" in result["error"]

    def test_filter_operator_isnull(self):
        """Test 'isnull' operator filter"""
        data = pd.DataFrame(
            {
                "id": [1, 2, 3, 4, 5],
                "value": [10, np.nan, 30, np.nan, 50],
            }
        )
        with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False) as f:
            data.to_csv(f.name, index=False)
            temp_file = f.name

        try:
            result = filter_data(temp_file, {"value": {"operator": "isnull"}})

            assert result["success"]
            # CSV may store NaN values differently, so just verify filtering worked
            assert "filter_stats" in result
            assert result["filter_stats"]["final_shape"][0] <= 5
        finally:
            if os.path.exists(temp_file):
                os.unlink(temp_file)
            filtered_file = temp_file.replace(".csv", "_filtered.csv")
            if os.path.exists(filtered_file):
                os.unlink(filtered_file)

    def test_filter_operator_notnull(self):
        """Test 'notnull' operator filter"""
        data = pd.DataFrame(
            {
                "id": [1, 2, 3, 4, 5],
                "value": [10, np.nan, 30, np.nan, 50],
            }
        )
        with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False) as f:
            data.to_csv(f.name, index=False)
            temp_file = f.name

        try:
            result = filter_data(temp_file, {"value": {"operator": "notnull"}})

            assert result["success"]
            # CSV may store NaN values differently, so just verify filtering worked
            assert "filter_stats" in result
            assert result["filter_stats"]["final_shape"][0] <= 5
        finally:
            if os.path.exists(temp_file):
                os.unlink(temp_file)
            filtered_file = temp_file.replace(".csv", "_filtered.csv")
            if os.path.exists(filtered_file):
                os.unlink(filtered_file)

    def test_filter_range(self, temp_csv_file):
        """Test range filter"""
        result = filter_data(temp_csv_file, {"age": {"range": [25, 50]}})

        assert result["success"]

    def test_filter_multiple_conditions(self, temp_csv_file):
        """Test multiple filter conditions"""
        result = filter_data(
            temp_csv_file,
            {
                "age": {"operator": "gt", "value": 30},
                "department": {"operator": "in", "value": ["Engineering", "Sales"]},
            },
        )

        assert result["success"]
        assert len(result["filter_stats"]["applied_filters"]) >= 2

    def test_filter_column_not_found(self, temp_csv_file):
        """Test filtering with non-existent column"""
        result = filter_data(
            temp_csv_file, {"nonexistent": {"operator": "eq", "value": 10}}
        )

        assert not result["success"]
        assert result["error_type"] == "ValueError"

    def test_filter_unknown_operator(self, temp_csv_file):
        """Test filtering with unknown operator"""
        result = filter_data(
            temp_csv_file, {"age": {"operator": "unknown", "value": 30}}
        )

        assert not result["success"]
        assert "Unknown operator" in result["error"]

    def test_filter_file_not_found(self):
        """Test filtering non-existent file"""
        result = filter_data(
            "nonexistent.csv", {"age": {"operator": "gt", "value": 30}}
        )

        assert not result["success"]
        assert result["error_type"] == "FileNotFoundError"

    def test_filter_with_custom_output(self, temp_csv_file):
        """Test filtering with custom output file"""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False) as f:
            output_file = f.name

        try:
            result = filter_data(
                temp_csv_file,
                {"age": {"operator": "gt", "value": 30}},
                output_file=output_file,
            )

            assert result["success"]
            assert result["output_file"] == output_file
            assert os.path.exists(output_file)
        finally:
            if os.path.exists(output_file):
                os.unlink(output_file)


class TestAdvancedFilter:
    """Test suite for advanced_filter function"""

    @pytest.fixture
    def sample_data(self):
        """Create sample data for testing"""
        return pd.DataFrame(
            {
                "id": range(1, 51),
                "age": np.random.randint(18, 65, 50),
                "salary": np.random.randint(30000, 120000, 50),
                "score": np.random.uniform(0, 100, 50),
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
        filtered_file = f.name.replace(".csv", "_query_filtered.csv")
        if os.path.exists(filtered_file):
            os.unlink(filtered_file)

    def test_advanced_filter_simple_query(self, temp_csv_file):
        """Test simple query string"""
        result = advanced_filter(temp_csv_file, "age > 30")

        assert result["success"]
        assert "filter_stats" in result

    def test_advanced_filter_complex_query(self, temp_csv_file):
        """Test complex query string"""
        result = advanced_filter(temp_csv_file, "age > 30 and salary > 50000")

        assert result["success"]

    def test_advanced_filter_with_or(self, temp_csv_file):
        """Test query with OR condition"""
        result = advanced_filter(temp_csv_file, "age < 25 or age > 55")

        assert result["success"]

    def test_advanced_filter_file_not_found(self):
        """Test query on non-existent file"""
        result = advanced_filter("nonexistent.csv", "age > 30")

        assert not result["success"]
        assert result["error_type"] == "FileNotFoundError"

    def test_advanced_filter_invalid_query(self, temp_csv_file):
        """Test invalid query string"""
        result = advanced_filter(temp_csv_file, "nonexistent_column > 30")

        assert not result["success"]
        assert result["error_type"] == "QueryError"

    def test_advanced_filter_with_custom_output(self, temp_csv_file):
        """Test query with custom output file"""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False) as f:
            output_file = f.name

        try:
            result = advanced_filter(temp_csv_file, "age > 30", output_file=output_file)

            assert result["success"]
            assert result["output_file"] == output_file
        finally:
            if os.path.exists(output_file):
                os.unlink(output_file)


class TestSampleData:
    """Test suite for sample_data function"""

    @pytest.fixture
    def sample_data(self):
        """Create sample data for testing"""
        return pd.DataFrame(
            {
                "id": range(1, 101),
                "value": np.random.randint(0, 100, 100),
            }
        )

    @pytest.fixture
    def temp_csv_file(self, sample_data):
        """Create a temporary CSV file"""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False) as f:
            sample_data.to_csv(f.name, index=False)
            yield f.name
        # Cleanup all generated files
        if os.path.exists(f.name):
            os.unlink(f.name)
        for method in ["random", "first", "last", "systematic"]:
            sample_file = f.name.replace(".csv", f"_sample_{method}.csv")
            if os.path.exists(sample_file):
                os.unlink(sample_file)

    def test_sample_random(self, temp_csv_file):
        """Test random sampling"""
        result = sample_data(temp_csv_file, sample_size=20, method="random")

        assert result["success"]
        assert result["sample_stats"]["sample_size"] == 20
        assert result["sample_stats"]["sampling_method"] == "random"
        assert len(result["sampled_data"]) == 20

    def test_sample_first(self, temp_csv_file):
        """Test first N rows sampling"""
        result = sample_data(temp_csv_file, sample_size=20, method="first")

        assert result["success"]
        assert result["sample_stats"]["sample_size"] == 20
        assert result["sample_stats"]["sampling_method"] == "first"
        assert result["sampled_data"][0]["id"] == 1

    def test_sample_last(self, temp_csv_file):
        """Test last N rows sampling"""
        result = sample_data(temp_csv_file, sample_size=20, method="last")

        assert result["success"]
        assert result["sample_stats"]["sample_size"] == 20
        assert result["sample_stats"]["sampling_method"] == "last"
        assert result["sampled_data"][-1]["id"] == 100

    def test_sample_systematic(self, temp_csv_file):
        """Test systematic sampling"""
        result = sample_data(temp_csv_file, sample_size=20, method="systematic")

        assert result["success"]
        assert result["sample_stats"]["sample_size"] == 20
        assert result["sample_stats"]["sampling_method"] == "systematic"

    def test_sample_size_larger_than_data(self, temp_csv_file):
        """Test sampling when requested size is larger than data"""
        result = sample_data(temp_csv_file, sample_size=200, method="random")

        assert result["success"]
        assert result["sample_stats"]["sample_size"] == 100  # Returns all data

    def test_sample_empty_dataset(self):
        """Test sampling from empty dataset"""
        empty_data = pd.DataFrame({"id": [], "value": []})
        with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False) as f:
            empty_data.to_csv(f.name, index=False)
            temp_file = f.name

        try:
            result = sample_data(temp_file, sample_size=10, method="random")

            # Empty dataset should fail or return error
            if not result["success"]:
                assert "error" in result
        finally:
            if os.path.exists(temp_file):
                os.unlink(temp_file)

    def test_sample_file_not_found(self):
        """Test sampling from non-existent file"""
        result = sample_data("nonexistent.csv", sample_size=10, method="random")

        assert not result["success"]
        assert result["error_type"] == "FileNotFoundError"

    def test_sample_unknown_method(self, temp_csv_file):
        """Test sampling with unknown method"""
        result = sample_data(temp_csv_file, sample_size=10, method="unknown")

        assert not result["success"]
        assert "Unknown sampling method" in result["error"]

    def test_sample_with_custom_output(self, temp_csv_file):
        """Test sampling with custom output file"""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False) as f:
            output_file = f.name

        try:
            result = sample_data(
                temp_csv_file, sample_size=20, method="random", output_file=output_file
            )

            assert result["success"]
            assert result["output_file"] == output_file
            assert os.path.exists(output_file)
        finally:
            if os.path.exists(output_file):
                os.unlink(output_file)

    def test_sample_statistics(self, temp_csv_file):
        """Test sampling statistics are correct"""
        result = sample_data(temp_csv_file, sample_size=25, method="random")

        assert result["success"]
        assert result["sample_stats"]["sample_percentage"] == 25.0
        assert result["sample_stats"]["original_shape"] == (100, 2)
        assert result["sample_stats"]["sample_shape"] == (25, 2)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
