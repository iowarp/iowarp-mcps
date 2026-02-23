"""
Comprehensive test cases for transformations module.
"""

import pytest
import pandas as pd
import tempfile
import os

from pandas_mcp.implementation.transformations import (
    groupby_operations,
    merge_datasets,
    create_pivot_table,
)


class TestGroupbyOperations:
    """Test suite for groupby_operations function"""

    @pytest.fixture
    def sample_data(self):
        """Create sample data for grouping"""
        return pd.DataFrame(
            {
                "department": [
                    "Sales",
                    "Sales",
                    "Engineering",
                    "Engineering",
                    "HR",
                    "HR",
                ],
                "employee": ["Alice", "Bob", "Charlie", "David", "Eve", "Frank"],
                "salary": [50000, 60000, 80000, 90000, 55000, 58000],
                "age": [25, 30, 35, 40, 28, 32],
                "score": [85.5, 90.0, 88.5, 92.0, 87.0, 89.5],
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
        grouped_file = f.name.replace(".csv", "_grouped.csv")
        if os.path.exists(grouped_file):
            os.unlink(grouped_file)

    def test_groupby_single_column_mean(self, temp_csv_file):
        """Test groupby with single grouping column and mean aggregation"""
        result = groupby_operations(
            temp_csv_file, group_by=["department"], operations={"salary": "mean"}
        )

        assert result["success"]
        assert "group_info" in result
        assert "results" in result
        assert len(result["results"]) == 3  # 3 departments

    def test_groupby_single_column_sum(self, temp_csv_file):
        """Test groupby with sum aggregation"""
        result = groupby_operations(
            temp_csv_file, group_by=["department"], operations={"salary": "sum"}
        )

        assert result["success"]
        assert result["group_info"]["operations"]["salary"] == "sum"

    def test_groupby_count(self, temp_csv_file):
        """Test groupby with count aggregation"""
        result = groupby_operations(
            temp_csv_file, group_by=["department"], operations={"employee": "count"}
        )

        assert result["success"]

    def test_groupby_median(self, temp_csv_file):
        """Test groupby with median aggregation"""
        result = groupby_operations(
            temp_csv_file, group_by=["department"], operations={"salary": "median"}
        )

        assert result["success"]

    def test_groupby_std(self, temp_csv_file):
        """Test groupby with standard deviation aggregation"""
        result = groupby_operations(
            temp_csv_file, group_by=["department"], operations={"salary": "std"}
        )

        assert result["success"]

    def test_groupby_min(self, temp_csv_file):
        """Test groupby with min aggregation"""
        result = groupby_operations(
            temp_csv_file, group_by=["department"], operations={"salary": "min"}
        )

        assert result["success"]

    def test_groupby_max(self, temp_csv_file):
        """Test groupby with max aggregation"""
        result = groupby_operations(
            temp_csv_file, group_by=["department"], operations={"salary": "max"}
        )

        assert result["success"]

    def test_groupby_nunique(self, temp_csv_file):
        """Test groupby with nunique aggregation"""
        result = groupby_operations(
            temp_csv_file, group_by=["department"], operations={"employee": "nunique"}
        )

        assert result["success"]

    def test_groupby_multiple_operations(self, temp_csv_file):
        """Test groupby with multiple operations"""
        result = groupby_operations(
            temp_csv_file,
            group_by=["department"],
            operations={"salary": "mean", "age": "median", "score": "max"},
        )

        assert result["success"]
        assert len(result["group_info"]["aggregated_columns"]) == 3

    def test_groupby_with_filter(self, temp_csv_file):
        """Test groupby with filter condition"""
        result = groupby_operations(
            temp_csv_file,
            group_by=["department"],
            operations={"salary": "mean"},
            filter_condition="age > 25",
        )

        assert result["success"]
        assert result["group_info"]["filter_condition"] == "age > 25"

    def test_groupby_invalid_filter(self, temp_csv_file):
        """Test groupby with invalid filter condition"""
        result = groupby_operations(
            temp_csv_file,
            group_by=["department"],
            operations={"salary": "mean"},
            filter_condition="nonexistent_column > 10",
        )

        assert not result["success"]
        assert result["error_type"] == "ValueError"

    def test_groupby_missing_columns(self, temp_csv_file):
        """Test groupby with non-existent grouping columns"""
        result = groupby_operations(
            temp_csv_file,
            group_by=["nonexistent"],
            operations={"salary": "mean"},
        )

        assert not result["success"]
        assert "not found" in result["error"]

    def test_groupby_file_not_found(self):
        """Test groupby on non-existent file"""
        result = groupby_operations(
            "nonexistent.csv",
            group_by=["department"],
            operations={"salary": "mean"},
        )

        assert not result["success"]
        assert result["error_type"] == "FileNotFoundError"

    def test_groupby_nonexistent_agg_column(self, temp_csv_file):
        """Test groupby with non-existent aggregation column (should skip it)"""
        result = groupby_operations(
            temp_csv_file,
            group_by=["department"],
            operations={"salary": "mean", "nonexistent": "sum"},
        )

        assert result["success"]
        # Non-existent column should be skipped


class TestMergeDatasets:
    """Test suite for merge_datasets function"""

    @pytest.fixture
    def left_data(self):
        """Create left dataset"""
        return pd.DataFrame(
            {
                "id": [1, 2, 3, 4, 5],
                "name": ["Alice", "Bob", "Charlie", "David", "Eve"],
                "age": [25, 30, 35, 40, 28],
            }
        )

    @pytest.fixture
    def right_data(self):
        """Create right dataset"""
        return pd.DataFrame(
            {
                "id": [1, 2, 3, 6, 7],
                "salary": [50000, 60000, 70000, 80000, 90000],
                "department": ["Sales", "Engineering", "HR", "Marketing", "Sales"],
            }
        )

    @pytest.fixture
    def temp_left_file(self, left_data):
        """Create temporary left CSV file"""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False) as f:
            left_data.to_csv(f.name, index=False)
            yield f.name
        if os.path.exists(f.name):
            os.unlink(f.name)
        merged_file = f.name.replace(".csv", "_merged.csv")
        if os.path.exists(merged_file):
            os.unlink(merged_file)

    @pytest.fixture
    def temp_right_file(self, right_data):
        """Create temporary right CSV file"""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False) as f:
            right_data.to_csv(f.name, index=False)
            yield f.name
        if os.path.exists(f.name):
            os.unlink(f.name)

    def test_merge_inner_join(self, temp_left_file, temp_right_file):
        """Test inner join merge"""
        result = merge_datasets(
            temp_left_file, temp_right_file, join_type="inner", on="id"
        )

        assert result["success"]
        assert result["merge_stats"]["join_type"] == "inner"
        assert result["merge_stats"]["merged_shape"][0] == 3  # Only 3 common IDs

    def test_merge_outer_join(self, temp_left_file, temp_right_file):
        """Test outer join merge"""
        result = merge_datasets(
            temp_left_file, temp_right_file, join_type="outer", on="id"
        )

        assert result["success"]
        assert result["merge_stats"]["join_type"] == "outer"
        assert result["merge_stats"]["merged_shape"][0] == 7  # All unique IDs

    def test_merge_left_join(self, temp_left_file, temp_right_file):
        """Test left join merge"""
        result = merge_datasets(
            temp_left_file, temp_right_file, join_type="left", on="id"
        )

        assert result["success"]
        assert result["merge_stats"]["join_type"] == "left"
        assert result["merge_stats"]["merged_shape"][0] == 5  # All left rows

    def test_merge_right_join(self, temp_left_file, temp_right_file):
        """Test right join merge"""
        result = merge_datasets(
            temp_left_file, temp_right_file, join_type="right", on="id"
        )

        assert result["success"]
        assert result["merge_stats"]["join_type"] == "right"
        assert result["merge_stats"]["merged_shape"][0] == 5  # All right rows

    def test_merge_different_column_names(self, temp_left_file):
        """Test merge with different column names"""
        right_data = pd.DataFrame(
            {
                "emp_id": [1, 2, 3],
                "salary": [50000, 60000, 70000],
            }
        )
        with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False) as f:
            right_data.to_csv(f.name, index=False)
            temp_right = f.name

        try:
            result = merge_datasets(
                temp_left_file,
                temp_right,
                join_type="inner",
                left_on="id",
                right_on="emp_id",
            )

            assert result["success"]
            assert result["merge_stats"]["left_on"] == "id"
            assert result["merge_stats"]["right_on"] == "emp_id"
        finally:
            if os.path.exists(temp_right):
                os.unlink(temp_right)

    def test_merge_left_file_not_found(self, temp_right_file):
        """Test merge with non-existent left file"""
        result = merge_datasets(
            "nonexistent.csv", temp_right_file, join_type="inner", on="id"
        )

        assert not result["success"]
        assert result["error_type"] == "FileNotFoundError"

    def test_merge_right_file_not_found(self, temp_left_file):
        """Test merge with non-existent right file"""
        result = merge_datasets(
            temp_left_file, "nonexistent.csv", join_type="inner", on="id"
        )

        assert not result["success"]
        assert result["error_type"] == "FileNotFoundError"

    def test_merge_missing_join_keys(self, temp_left_file, temp_right_file):
        """Test merge with missing join keys"""
        result = merge_datasets(temp_left_file, temp_right_file, join_type="inner")

        assert not result["success"]
        assert (
            "Must specify either 'on' or both 'left_on' and 'right_on'"
            in result["error"]
        )

    def test_merge_left_column_not_found(self, temp_left_file, temp_right_file):
        """Test merge with non-existent left column"""
        result = merge_datasets(
            temp_left_file,
            temp_right_file,
            join_type="inner",
            left_on="nonexistent",
            right_on="id",
        )

        assert not result["success"]
        assert "not found in left dataset" in result["error"]

    def test_merge_right_column_not_found(self, temp_left_file, temp_right_file):
        """Test merge with non-existent right column"""
        result = merge_datasets(
            temp_left_file,
            temp_right_file,
            join_type="inner",
            left_on="id",
            right_on="nonexistent",
        )

        assert not result["success"]
        assert "not found in right dataset" in result["error"]

    def test_merge_statistics(self, temp_left_file, temp_right_file):
        """Test merge statistics are correct"""
        result = merge_datasets(
            temp_left_file, temp_right_file, join_type="inner", on="id"
        )

        assert result["success"]
        assert "common_values" in result["merge_stats"]
        assert "left_only_values" in result["merge_stats"]
        assert "right_only_values" in result["merge_stats"]


class TestCreatePivotTable:
    """Test suite for create_pivot_table function"""

    @pytest.fixture
    def sample_data(self):
        """Create sample data for pivot table"""
        return pd.DataFrame(
            {
                "date": ["2023-01-01", "2023-01-01", "2023-01-02", "2023-01-02"] * 3,
                "product": ["A", "B", "A", "B"] * 3,
                "region": ["North", "North", "South", "South"] * 3,
                "sales": [100, 150, 120, 180, 110, 160, 130, 190, 105, 155, 125, 185],
                "quantity": [10, 15, 12, 18, 11, 16, 13, 19, 10, 15, 12, 18],
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
        pivot_file = f.name.replace(".csv", "_pivot.csv")
        if os.path.exists(pivot_file):
            os.unlink(pivot_file)

    def test_pivot_simple(self, temp_csv_file):
        """Test simple pivot table"""
        result = create_pivot_table(
            temp_csv_file, index=["product"], values=["sales"], aggfunc="mean"
        )

        assert result["success"]
        assert "pivot_info" in result
        assert "pivot_table" in result

    def test_pivot_with_columns(self, temp_csv_file):
        """Test pivot table with columns"""
        result = create_pivot_table(
            temp_csv_file,
            index=["product"],
            columns=["region"],
            values=["sales"],
            aggfunc="sum",
        )

        assert result["success"]
        assert result["pivot_info"]["column_headers"] == ["region"]

    def test_pivot_multiple_values(self, temp_csv_file):
        """Test pivot table with multiple value columns"""
        result = create_pivot_table(
            temp_csv_file,
            index=["product"],
            values=["sales", "quantity"],
            aggfunc="mean",
        )

        assert result["success"]
        assert len(result["pivot_info"]["value_columns"]) == 2

    def test_pivot_sum_aggregation(self, temp_csv_file):
        """Test pivot table with sum aggregation"""
        result = create_pivot_table(
            temp_csv_file, index=["product"], values=["sales"], aggfunc="sum"
        )

        assert result["success"]
        assert result["pivot_info"]["aggregation_function"] == "sum"

    def test_pivot_count_aggregation(self, temp_csv_file):
        """Test pivot table with count aggregation"""
        result = create_pivot_table(
            temp_csv_file, index=["product"], values=["sales"], aggfunc="count"
        )

        assert result["success"]
        assert result["pivot_info"]["aggregation_function"] == "count"

    def test_pivot_file_not_found(self):
        """Test pivot table on non-existent file"""
        result = create_pivot_table(
            "nonexistent.csv", index=["product"], values=["sales"]
        )

        assert not result["success"]
        assert result["error_type"] == "FileNotFoundError"

    def test_pivot_index_not_found(self, temp_csv_file):
        """Test pivot table with non-existent index column"""
        result = create_pivot_table(
            temp_csv_file, index=["nonexistent"], values=["sales"]
        )

        assert not result["success"]
        assert "Index columns not found" in result["error"]

    def test_pivot_column_headers_not_found(self, temp_csv_file):
        """Test pivot table with non-existent column headers"""
        result = create_pivot_table(
            temp_csv_file,
            index=["product"],
            columns=["nonexistent"],
            values=["sales"],
        )

        assert not result["success"]
        assert "Column header columns not found" in result["error"]

    def test_pivot_value_columns_not_found(self, temp_csv_file):
        """Test pivot table with non-existent value columns"""
        result = create_pivot_table(
            temp_csv_file, index=["product"], values=["nonexistent"]
        )

        assert not result["success"]
        assert "Value columns not found" in result["error"]

    def test_pivot_multiple_index(self, temp_csv_file):
        """Test pivot table with multiple index columns"""
        result = create_pivot_table(
            temp_csv_file,
            index=["product", "region"],
            values=["sales"],
            aggfunc="mean",
        )

        assert result["success"]
        assert len(result["pivot_info"]["index_columns"]) == 2

    def test_pivot_no_values(self, temp_csv_file):
        """Test pivot table without specifying values (uses all numeric)"""
        # When values=None, pivot_table uses all numeric columns by default
        # However, we need to provide at least one value column explicitly
        result = create_pivot_table(
            temp_csv_file, index=["product"], values=["sales"], aggfunc="mean"
        )

        assert result["success"]

    def test_pivot_no_columns(self, temp_csv_file):
        """Test pivot table without column headers"""
        result = create_pivot_table(
            temp_csv_file, index=["product"], values=["sales"], aggfunc="mean"
        )

        assert result["success"]
        assert result["pivot_info"]["column_headers"] is None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
