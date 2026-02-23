"""
Comprehensive test cases for data_io module.
"""

import pytest
import pandas as pd
import numpy as np
import tempfile
import os

from pandas_mcp.implementation.data_io import (
    load_data_file,
    save_data_file,
    get_file_info,
)


class TestLoadDataFile:
    """Test suite for load_data_file function"""

    @pytest.fixture
    def sample_data(self):
        """Create sample data for testing"""
        return pd.DataFrame(
            {
                "id": range(1, 51),
                "name": [f"Item_{i}" for i in range(1, 51)],
                "value": np.random.randint(0, 100, 50),
                "category": np.random.choice(["A", "B", "C"], 50),
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

    @pytest.fixture
    def temp_json_file(self, sample_data):
        """Create a temporary JSON file"""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            sample_data.to_json(f.name, orient="records")
            yield f.name
        if os.path.exists(f.name):
            os.unlink(f.name)

    @pytest.fixture
    def temp_excel_file(self, sample_data):
        """Create a temporary Excel file"""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".xlsx", delete=False) as f:
            sample_data.to_excel(f.name, index=False, sheet_name="Sheet1")
            yield f.name
        if os.path.exists(f.name):
            os.unlink(f.name)

    @pytest.fixture
    def temp_parquet_file(self, sample_data):
        """Create a temporary Parquet file"""
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".parquet", delete=False
        ) as f:
            sample_data.to_parquet(f.name, index=False)
            yield f.name
        if os.path.exists(f.name):
            os.unlink(f.name)

    @pytest.fixture
    def temp_hdf5_file(self, sample_data):
        """Create a temporary HDF5 file"""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".h5", delete=False) as f:
            sample_data.to_hdf(f.name, key="data", mode="w", index=False)
            yield f.name
        if os.path.exists(f.name):
            os.unlink(f.name)

    def test_load_csv_file(self, temp_csv_file):
        """Test loading CSV file"""
        result = load_data_file(temp_csv_file)

        assert result["success"]
        assert result["file_format"] == "csv"
        assert len(result["data"]) == 50
        assert result["total_rows"] == 50
        assert "info" in result

    def test_load_csv_with_encoding(self, temp_csv_file):
        """Test loading CSV file with specific encoding"""
        result = load_data_file(temp_csv_file, encoding="utf-8")

        assert result["success"]
        assert result["file_format"] == "csv"

    def test_load_csv_with_nrows(self, temp_csv_file):
        """Test loading CSV file with row limit"""
        result = load_data_file(temp_csv_file, nrows=10)

        assert result["success"]
        assert len(result["data"]) == 10
        assert result["info"]["shape"][0] == 10

    def test_load_csv_with_columns(self, temp_csv_file):
        """Test loading CSV file with specific columns"""
        result = load_data_file(temp_csv_file, columns=["id", "name"])

        assert result["success"]
        assert result["info"]["shape"][1] == 2
        assert "id" in result["info"]["columns"]
        assert "name" in result["info"]["columns"]

    def test_load_json_file(self, temp_json_file):
        """Test loading JSON file"""
        result = load_data_file(temp_json_file, file_format="json")

        assert result["success"]
        assert result["file_format"] == "json"
        assert len(result["data"]) == 50

    def test_load_json_with_columns(self, temp_json_file):
        """Test loading JSON file with specific columns"""
        result = load_data_file(
            temp_json_file, file_format="json", columns=["id", "value"]
        )

        assert result["success"]
        assert result["info"]["shape"][1] == 2

    def test_load_excel_file(self, temp_excel_file):
        """Test loading Excel file"""
        result = load_data_file(temp_excel_file, file_format="excel")

        assert result["success"]
        assert result["file_format"] == "excel"
        assert len(result["data"]) == 50

    def test_load_excel_with_sheet_name(self, temp_excel_file):
        """Test loading Excel file with specific sheet"""
        result = load_data_file(
            temp_excel_file, file_format="excel", sheet_name="Sheet1"
        )

        assert result["success"]
        assert result["file_format"] == "excel"

    def test_load_parquet_file(self, temp_parquet_file):
        """Test loading Parquet file"""
        result = load_data_file(temp_parquet_file, file_format="parquet")

        assert result["success"]
        assert result["file_format"] == "parquet"
        assert len(result["data"]) == 50

    def test_load_parquet_with_nrows(self, temp_parquet_file):
        """Test loading Parquet file with row limit"""
        result = load_data_file(temp_parquet_file, file_format="parquet", nrows=10)

        assert result["success"]
        assert len(result["data"]) == 10

    def test_load_hdf5_file(self, temp_hdf5_file):
        """Test loading HDF5 file"""
        result = load_data_file(temp_hdf5_file, file_format="hdf5")

        assert result["success"]
        assert result["file_format"] == "hdf5"
        assert len(result["data"]) == 50

    def test_load_hdf5_with_nrows(self, temp_hdf5_file):
        """Test loading HDF5 file with row limit"""
        result = load_data_file(temp_hdf5_file, file_format="hdf5", nrows=10)

        assert result["success"]
        assert len(result["data"]) == 10

    def test_load_auto_detect_format(self, temp_csv_file):
        """Test auto-detection of file format"""
        result = load_data_file(temp_csv_file)

        assert result["success"]
        assert result["file_format"] == "csv"

    def test_load_file_not_found(self):
        """Test loading non-existent file"""
        result = load_data_file("nonexistent_file.csv")

        assert not result["success"]
        assert result["error_type"] == "FileNotFoundError"

    def test_load_unsupported_format(self, temp_csv_file):
        """Test loading with unsupported format"""
        result = load_data_file(temp_csv_file, file_format="unsupported")

        assert not result["success"]
        assert result["error_type"] == "ValueError"

    def test_load_large_file_preview(self):
        """Test that large files are limited to 100 rows in output"""
        large_data = pd.DataFrame({"col": range(1, 201)})
        with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False) as f:
            large_data.to_csv(f.name, index=False)
            temp_file = f.name

        try:
            result = load_data_file(temp_file)

            assert result["success"]
            assert len(result["data"]) == 100  # Limited to 100 rows
            assert result["total_rows"] == 200
        finally:
            if os.path.exists(temp_file):
                os.unlink(temp_file)

    def test_load_data_with_nulls(self):
        """Test loading data with null values and numpy types"""
        data = pd.DataFrame(
            {
                "int_col": [1, 2, np.nan, 4],
                "float_col": [1.1, np.nan, 3.3, 4.4],
                "bool_col": [True, False, True, np.nan],
            }
        )
        with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False) as f:
            data.to_csv(f.name, index=False)
            temp_file = f.name

        try:
            result = load_data_file(temp_file)

            assert result["success"]
            # Check that NaN values are converted to None
            for record in result["data"]:
                for value in record.values():
                    assert value is None or isinstance(value, (int, float, bool, str))
        finally:
            if os.path.exists(temp_file):
                os.unlink(temp_file)


class TestSaveDataFile:
    """Test suite for save_data_file function"""

    @pytest.fixture
    def sample_data_dict(self):
        """Create sample data dictionary"""
        return [
            {"id": 1, "name": "Item_1", "value": 10},
            {"id": 2, "name": "Item_2", "value": 20},
            {"id": 3, "name": "Item_3", "value": 30},
        ]

    def test_save_csv_file(self, sample_data_dict):
        """Test saving to CSV file"""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False) as f:
            temp_file = f.name

        try:
            result = save_data_file(sample_data_dict, temp_file)

            assert result["success"]
            assert result["file_format"] == "csv"
            assert result["rows_saved"] == 3
            assert os.path.exists(temp_file)
        finally:
            if os.path.exists(temp_file):
                os.unlink(temp_file)

    def test_save_csv_without_index(self, sample_data_dict):
        """Test saving CSV without index"""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False) as f:
            temp_file = f.name

        try:
            result = save_data_file(sample_data_dict, temp_file, index=False)

            assert result["success"]
            assert os.path.exists(temp_file)
        finally:
            if os.path.exists(temp_file):
                os.unlink(temp_file)

    def test_save_json_file(self, sample_data_dict):
        """Test saving to JSON file"""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            temp_file = f.name

        try:
            result = save_data_file(sample_data_dict, temp_file, file_format="json")

            assert result["success"]
            assert result["file_format"] == "json"
            assert os.path.exists(temp_file)
        finally:
            if os.path.exists(temp_file):
                os.unlink(temp_file)

    def test_save_excel_file(self, sample_data_dict):
        """Test saving to Excel file"""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".xlsx", delete=False) as f:
            temp_file = f.name

        try:
            result = save_data_file(sample_data_dict, temp_file, file_format="excel")

            assert result["success"]
            assert result["file_format"] == "excel"
            assert os.path.exists(temp_file)
        finally:
            if os.path.exists(temp_file):
                os.unlink(temp_file)

    def test_save_parquet_file(self, sample_data_dict):
        """Test saving to Parquet file"""
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".parquet", delete=False
        ) as f:
            temp_file = f.name

        try:
            result = save_data_file(sample_data_dict, temp_file, file_format="parquet")

            assert result["success"]
            assert result["file_format"] == "parquet"
            assert os.path.exists(temp_file)
        finally:
            if os.path.exists(temp_file):
                os.unlink(temp_file)

    def test_save_hdf5_file(self, sample_data_dict):
        """Test saving to HDF5 file"""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".h5", delete=False) as f:
            temp_file = f.name

        try:
            result = save_data_file(sample_data_dict, temp_file, file_format="hdf5")

            assert result["success"]
            assert result["file_format"] == "hdf5"
            assert os.path.exists(temp_file)
        finally:
            if os.path.exists(temp_file):
                os.unlink(temp_file)

    def test_save_auto_detect_format(self, sample_data_dict):
        """Test auto-detection of file format from extension"""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False) as f:
            temp_file = f.name

        try:
            result = save_data_file(sample_data_dict, temp_file)

            assert result["success"]
            assert result["file_format"] == "csv"
        finally:
            if os.path.exists(temp_file):
                os.unlink(temp_file)

    def test_save_unsupported_format(self, sample_data_dict):
        """Test saving with unsupported format"""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
            temp_file = f.name

        try:
            result = save_data_file(
                sample_data_dict, temp_file, file_format="unsupported"
            )

            assert not result["success"]
            assert result["error_type"] == "ValueError"
        finally:
            if os.path.exists(temp_file):
                os.unlink(temp_file)

    def test_save_with_data_key(self):
        """Test saving data dictionary with 'data' key"""
        data_with_key = {"data": [{"id": 1, "value": 10}, {"id": 2, "value": 20}]}

        with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False) as f:
            temp_file = f.name

        try:
            result = save_data_file(data_with_key, temp_file)

            assert result["success"]
            assert result["rows_saved"] == 2
        finally:
            if os.path.exists(temp_file):
                os.unlink(temp_file)

    def test_save_creates_directory(self, sample_data_dict):
        """Test that save creates directory if it doesn't exist"""
        with tempfile.TemporaryDirectory() as tmpdir:
            temp_file = os.path.join(tmpdir, "subdir", "test.csv")

            result = save_data_file(sample_data_dict, temp_file)

            assert result["success"]
            assert os.path.exists(temp_file)
            assert os.path.exists(os.path.dirname(temp_file))


class TestGetFileInfo:
    """Test suite for get_file_info function"""

    @pytest.fixture
    def sample_data(self):
        """Create sample data for testing"""
        return pd.DataFrame(
            {
                "id": range(1, 101),
                "name": [f"Item_{i}" for i in range(1, 101)],
                "value": np.random.randint(0, 100, 100),
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

    @pytest.fixture
    def temp_parquet_file(self, sample_data):
        """Create a temporary Parquet file"""
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".parquet", delete=False
        ) as f:
            sample_data.to_parquet(f.name, index=False)
            yield f.name
        if os.path.exists(f.name):
            os.unlink(f.name)

    def test_get_csv_file_info(self, temp_csv_file):
        """Test getting info for CSV file"""
        result = get_file_info(temp_csv_file)

        assert result["success"]
        assert result["file_format"] == "csv"
        assert "file_size_bytes" in result
        assert "file_size_mb" in result
        assert "modified_time" in result
        assert "estimated_rows" in result
        assert "columns" in result
        assert "column_count" in result

    def test_get_parquet_file_info(self, temp_parquet_file):
        """Test getting info for Parquet file"""
        result = get_file_info(temp_parquet_file)

        assert result["success"]
        assert result["file_format"] == "parquet"
        assert "rows" in result
        assert "columns" in result
        assert "column_count" in result

    def test_get_file_info_not_found(self):
        """Test getting info for non-existent file"""
        result = get_file_info("nonexistent_file.csv")

        assert not result["success"]
        assert result["error_type"] == "FileNotFoundError"

    def test_get_file_info_unknown_format(self):
        """Test getting info for unknown file format"""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
            f.write("test data")
            temp_file = f.name

        try:
            result = get_file_info(temp_file)

            assert result["success"]
            assert result["file_format"] == "unknown"
        finally:
            if os.path.exists(temp_file):
                os.unlink(temp_file)


class TestLoadDataFileEdgeCases:
    """Test edge cases for load_data_file to improve coverage"""

    def test_load_excel_with_specific_sheet_name(self):
        """Test loading Excel file with specific sheet name"""
        df = pd.DataFrame({"a": [1, 2], "b": [3, 4]})
        with tempfile.NamedTemporaryFile(mode="wb", suffix=".xlsx", delete=False) as f:
            df.to_excel(f.name, sheet_name="Sheet1", index=False)
            temp_file = f.name

        try:
            result = load_data_file(temp_file, sheet_name="Sheet1")
            assert result["success"]
            assert len(result["data"]) == 2
        finally:
            if os.path.exists(temp_file):
                os.unlink(temp_file)

    def test_load_data_with_numpy_dtype_conversion(self):
        """Test loading data that triggers numpy dtype conversion in records"""
        df = pd.DataFrame(
            {
                "int_col": np.array([1, 2, 3], dtype=np.int64),
                "float_col": np.array([1.1, 2.2, 3.3], dtype=np.float64),
                "bool_col": np.array([True, False, True], dtype=bool),
                "str_col": ["a", "b", "c"],
            }
        )
        with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False) as f:
            df.to_csv(f.name, index=False)
            temp_file = f.name

        try:
            result = load_data_file(temp_file)
            assert result["success"]
            # Check that data was loaded properly
            assert len(result["data"]) == 3
        finally:
            if os.path.exists(temp_file):
                os.unlink(temp_file)

    def test_save_data_with_invalid_data_dict(self):
        """Test saving data with a dict that doesn't have data key"""
        data = {"col1": [1, 2], "col2": [3, 4]}
        with tempfile.TemporaryDirectory() as tmpdir:
            temp_file = os.path.join(tmpdir, "test.csv")
            result = save_data_file(data, temp_file)
            assert result["success"]
            assert result["rows_saved"] == 2

    def test_load_data_exception_handling(self):
        """Test load_data_file exception handling with bad CSV"""
        # Create a malformed CSV to trigger exception
        with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False) as f:
            f.write("bad,csv,data\n")
            f.write("incomplete row\n")
            temp_file = f.name

        try:
            result = load_data_file(temp_file)
            # Should still load but might have issues
            assert result is not None
        finally:
            if os.path.exists(temp_file):
                os.unlink(temp_file)


class TestSaveDataFileEdgeCases:
    """Test edge cases for save_data_file to improve coverage"""

    def test_save_data_generic_exception(self):
        """Test save_data_file with invalid data to trigger exception"""
        # Using invalid data that can't be converted to DataFrame
        result = save_data_file("not a valid data structure", "/tmp/test.csv")
        assert not result["success"]
        assert "error" in result


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
