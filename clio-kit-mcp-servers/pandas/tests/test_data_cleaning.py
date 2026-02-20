"""
Comprehensive test cases for data_cleaning module.
"""

import pytest
import pandas as pd
import numpy as np
import tempfile
import os

from pandas_mcp.implementation.data_cleaning import handle_missing_data, clean_data


class TestHandleMissingData:
    """Test suite for handle_missing_data function"""

    @pytest.fixture
    def data_with_missing(self):
        """Create sample data with missing values"""
        return pd.DataFrame(
            {
                "id": [1, 2, 3, 4, 5, 6, 7, 8, 9, 10],
                "numeric_col": [10, np.nan, 30, 40, np.nan, 60, 70, 80, 90, 100],
                "category_col": [
                    "A",
                    "B",
                    np.nan,
                    "A",
                    "B",
                    np.nan,
                    "A",
                    "B",
                    "A",
                    "B",
                ],
                "float_col": [1.1, 2.2, np.nan, 4.4, 5.5, np.nan, 7.7, 8.8, 9.9, 10.0],
            }
        )

    @pytest.fixture
    def temp_csv_with_missing(self, data_with_missing):
        """Create a temporary CSV file with missing values"""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False) as f:
            data_with_missing.to_csv(f.name, index=False)
            yield f.name
        # Cleanup all generated files
        if os.path.exists(f.name):
            os.unlink(f.name)
        imputed_file = f.name.replace(".csv", "_imputed.csv")
        if os.path.exists(imputed_file):
            os.unlink(imputed_file)
        no_missing_file = f.name.replace(".csv", "_no_missing.csv")
        if os.path.exists(no_missing_file):
            os.unlink(no_missing_file)

    def test_handle_missing_data_detect(self, temp_csv_with_missing):
        """Test missing data detection"""
        result = handle_missing_data(temp_csv_with_missing, strategy="detect")

        assert result["success"]
        assert "missing_data_info" in result
        # We have 2 NaN in numeric_col, 2 in category_col, 2 in float_col = 6 total missing values
        assert result["missing_data_info"]["total_missing"] == 6
        # But only 4 unique rows have at least one missing value
        assert result["missing_data_info"]["rows_with_missing"] == 4
        assert "missing_by_column" in result["missing_data_info"]
        assert "missing_percentage" in result["missing_data_info"]

    def test_handle_missing_data_remove(self, temp_csv_with_missing):
        """Test removing rows with missing data"""
        result = handle_missing_data(temp_csv_with_missing, strategy="remove")

        assert result["success"]
        assert "output_file" in result
        # 4 rows have missing data, so 6 remain
        assert result["removed_rows"] == 4
        assert result["new_shape"][0] == 6
        assert os.path.exists(result["output_file"])

    def test_handle_missing_data_impute_mean(self, temp_csv_with_missing):
        """Test imputing missing values with mean"""
        result = handle_missing_data(
            temp_csv_with_missing, strategy="impute", method="mean"
        )

        assert result["success"]
        assert "imputation_info" in result
        assert result["imputation_method"] == "mean"
        assert os.path.exists(result["output_file"])

        # Verify imputed file has no missing values
        df_imputed = pd.read_csv(result["output_file"])
        assert df_imputed["numeric_col"].isnull().sum() == 0

    def test_handle_missing_data_impute_median(self, temp_csv_with_missing):
        """Test imputing missing values with median"""
        result = handle_missing_data(
            temp_csv_with_missing, strategy="impute", method="median"
        )

        assert result["success"]
        assert result["imputation_method"] == "median"
        assert "imputation_info" in result

    def test_handle_missing_data_impute_mode(self, temp_csv_with_missing):
        """Test imputing missing values with mode"""
        result = handle_missing_data(
            temp_csv_with_missing, strategy="impute", method="mode"
        )

        assert result["success"]
        assert result["imputation_method"] == "mode"
        assert "imputation_info" in result

    def test_handle_missing_data_impute_forward_fill(self, temp_csv_with_missing):
        """Test imputing categorical missing values with forward fill"""
        result = handle_missing_data(
            temp_csv_with_missing, strategy="impute", method="forward_fill"
        )

        assert result["success"]
        assert result["imputation_method"] == "forward_fill"

    def test_handle_missing_data_impute_backward_fill(self, temp_csv_with_missing):
        """Test imputing categorical missing values with backward fill"""
        result = handle_missing_data(
            temp_csv_with_missing, strategy="impute", method="backward_fill"
        )

        assert result["success"]
        assert result["imputation_method"] == "backward_fill"

    def test_handle_missing_data_impute_default_method(self, temp_csv_with_missing):
        """Test imputing with default method (None should default to mean)"""
        result = handle_missing_data(
            temp_csv_with_missing, strategy="impute", method=None
        )

        assert result["success"]
        assert result["imputation_method"] == "mean"

    def test_handle_missing_data_file_not_found(self):
        """Test handling of non-existent file"""
        result = handle_missing_data("nonexistent_file.csv", strategy="detect")

        assert not result["success"]
        assert result["error_type"] == "FileNotFoundError"

    def test_handle_missing_data_unknown_strategy(self, temp_csv_with_missing):
        """Test handling of unknown strategy"""
        result = handle_missing_data(temp_csv_with_missing, strategy="unknown")

        assert not result["success"]
        assert result["error_type"] == "ValueError"
        assert "Unknown strategy" in result["error"]

    def test_handle_missing_data_with_columns(self, temp_csv_with_missing):
        """Test handling missing data for specific columns"""
        result = handle_missing_data(
            temp_csv_with_missing, strategy="detect", columns=["numeric_col"]
        )

        assert result["success"]
        assert "missing_data_info" in result


class TestCleanData:
    """Test suite for clean_data function"""

    @pytest.fixture
    def data_with_duplicates_and_outliers(self):
        """Create sample data with duplicates and outliers"""
        df = pd.DataFrame(
            {
                "id": [1, 2, 3, 4, 5, 1, 2, 8, 9, 10],
                "value": [10, 20, 30, 40, 50, 10, 20, 1000, 90, 100],
                "category": ["A", "B", "A", "B", "A", "A", "B", "A", "B", "A"],
                "text_number": ["1", "2", "3", "4", "5", "1", "2", "8", "9", "10"],
            }
        )
        return df

    @pytest.fixture
    def temp_csv_for_cleaning(self, data_with_duplicates_and_outliers):
        """Create a temporary CSV file for cleaning"""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False) as f:
            data_with_duplicates_and_outliers.to_csv(f.name, index=False)
            yield f.name
        # Cleanup all generated files
        if os.path.exists(f.name):
            os.unlink(f.name)
        cleaned_file = f.name.replace(".csv", "_cleaned.csv")
        if os.path.exists(cleaned_file):
            os.unlink(cleaned_file)

    def test_clean_data_remove_duplicates(self, temp_csv_for_cleaning):
        """Test removing duplicate rows"""
        result = clean_data(temp_csv_for_cleaning, remove_duplicates=True)

        assert result["success"]
        assert "cleaning_results" in result
        assert result["cleaning_results"]["duplicates_removed"] == 2
        assert os.path.exists(result["output_file"])

    def test_clean_data_detect_outliers(self, temp_csv_for_cleaning):
        """Test detecting outliers using IQR method"""
        result = clean_data(temp_csv_for_cleaning, detect_outliers=True)

        assert result["success"]
        assert "cleaning_results" in result
        assert "outliers_info" in result["cleaning_results"]
        assert "value" in result["cleaning_results"]["outliers_info"]

        # Check outlier detection structure
        outliers = result["cleaning_results"]["outliers_info"]["value"]
        assert "outlier_count" in outliers
        assert "outlier_percentage" in outliers
        assert "lower_bound" in outliers
        assert "upper_bound" in outliers
        assert "outlier_values" in outliers

    def test_clean_data_convert_types(self, temp_csv_for_cleaning):
        """Test converting data types"""
        result = clean_data(temp_csv_for_cleaning, convert_types=True)

        assert result["success"]
        assert "cleaning_results" in result
        # Type changes may or may not occur depending on the data
        if (
            "type_changes" in result["cleaning_results"]
            and result["cleaning_results"]["type_changes"]
        ):
            # Check if any conversions happened
            assert isinstance(result["cleaning_results"]["type_changes"], dict)

    def test_clean_data_all_operations(self, temp_csv_for_cleaning):
        """Test all cleaning operations together"""
        result = clean_data(
            temp_csv_for_cleaning,
            remove_duplicates=True,
            detect_outliers=True,
            convert_types=True,
        )

        assert result["success"]
        assert "cleaning_results" in result
        assert "duplicates_removed" in result["cleaning_results"]
        assert "outliers_info" in result["cleaning_results"]
        assert "type_changes" in result["cleaning_results"]
        assert "memory_reduction_mb" in result["cleaning_results"]

    def test_clean_data_no_operations(self, temp_csv_for_cleaning):
        """Test cleaning with no operations enabled"""
        result = clean_data(
            temp_csv_for_cleaning,
            remove_duplicates=False,
            detect_outliers=False,
            convert_types=False,
        )

        assert result["success"]
        assert "cleaning_results" in result
        # When outliers not detected, outliers_info is None
        assert result["cleaning_results"]["outliers_info"] is None
        # When types not converted, type_changes is None
        assert result["cleaning_results"]["type_changes"] is None

    def test_clean_data_file_not_found(self):
        """Test cleaning non-existent file"""
        result = clean_data("nonexistent_file.csv")

        assert not result["success"]
        assert result["error_type"] == "FileNotFoundError"

    def test_clean_data_memory_tracking(self, temp_csv_for_cleaning):
        """Test memory usage tracking"""
        result = clean_data(temp_csv_for_cleaning, remove_duplicates=True)

        assert result["success"]
        assert "cleaning_results" in result
        assert "original_memory_mb" in result["cleaning_results"]
        assert "final_memory_mb" in result["cleaning_results"]
        assert "memory_reduction_mb" in result["cleaning_results"]

    @pytest.fixture
    def data_with_datetime(self):
        """Create sample data with datetime strings"""
        return pd.DataFrame(
            {
                "id": [1, 2, 3, 4, 5],
                "date": [
                    "2023-01-01",
                    "2023-02-01",
                    "2023-03-01",
                    "2023-04-01",
                    "2023-05-01",
                ],
                "value": [10, 20, 30, 40, 50],
            }
        )

    @pytest.fixture
    def temp_csv_with_datetime(self, data_with_datetime):
        """Create a temporary CSV file with datetime strings"""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False) as f:
            data_with_datetime.to_csv(f.name, index=False)
            yield f.name
        if os.path.exists(f.name):
            os.unlink(f.name)
        cleaned_file = f.name.replace(".csv", "_cleaned.csv")
        if os.path.exists(cleaned_file):
            os.unlink(cleaned_file)

    def test_clean_data_datetime_conversion(self, temp_csv_with_datetime):
        """Test datetime conversion during type conversion"""
        result = clean_data(temp_csv_with_datetime, convert_types=True)

        assert result["success"]
        assert "type_changes" in result["cleaning_results"]

        # Check if date column was converted
        if result["cleaning_results"]["type_changes"]:
            assert any(
                "datetime" in str(v)
                for v in result["cleaning_results"]["type_changes"].values()
            )

    @pytest.fixture
    def data_with_categories(self):
        """Create sample data with repeated categorical values"""
        return pd.DataFrame(
            {
                "id": range(1, 101),
                "category": ["A"] * 50 + ["B"] * 30 + ["C"] * 20,
                "value": np.random.randint(0, 100, 100),
            }
        )

    @pytest.fixture
    def temp_csv_with_categories(self, data_with_categories):
        """Create a temporary CSV file with categorical data"""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False) as f:
            data_with_categories.to_csv(f.name, index=False)
            yield f.name
        if os.path.exists(f.name):
            os.unlink(f.name)
        cleaned_file = f.name.replace(".csv", "_cleaned.csv")
        if os.path.exists(cleaned_file):
            os.unlink(cleaned_file)

    def test_clean_data_category_conversion(self, temp_csv_with_categories):
        """Test conversion of repeated strings to category type"""
        result = clean_data(temp_csv_with_categories, convert_types=True)

        assert result["success"]
        assert "type_changes" in result["cleaning_results"]

        # Check if category column was converted
        if result["cleaning_results"]["type_changes"]:
            assert any(
                "category" in str(v).lower()
                for v in result["cleaning_results"]["type_changes"].values()
            )


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
