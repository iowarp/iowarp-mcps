"""
Test cases for the lightweight, domain-neutral csv_profiling module.
"""

import os
import tempfile

import pandas as pd
import pytest

from pandas_mcp.implementation.csv_profiling import (
    _DEFAULT_PROFILE_ROWS,
    profile_csv,
)


def _write_csv(df: pd.DataFrame) -> str:
    """Write a DataFrame to a temp CSV and return its path."""
    handle = tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False)
    df.to_csv(handle.name, index=False)
    handle.close()
    return handle.name


@pytest.fixture
def sample_csv():
    """A generic CSV with numeric, integer, and string columns plus blanks."""
    df = pd.DataFrame(
        {
            "col_int": [1, 2, 3, 4, 5],
            "col_float": [1.5, 2.5, 3.5, 4.5, 5.5],
            "col_text": ["a", "b", "c", "d", "e"],
            "col_sparse": [10.0, None, 30.0, None, 50.0],
        }
    )
    path = _write_csv(df)
    yield path
    if os.path.exists(path):
        os.unlink(path)


class TestProfileCsv:
    """Test suite for profile_csv."""

    def test_basic_success(self, sample_csv):
        result = profile_csv(sample_csv)
        assert result["success"]
        assert result["file_path"] == sample_csv
        assert result["size_bytes"] > 0
        assert result["message"]

    def test_row_and_column_counts(self, sample_csv):
        result = profile_csv(sample_csv)
        assert result["row_count"] == 5
        assert result["rows_profiled"] == 5
        assert result["column_count"] == 4
        assert result["columns"] == [
            "col_int",
            "col_float",
            "col_text",
            "col_sparse",
        ]

    def test_dtype_inference(self, sample_csv):
        result = profile_csv(sample_csv)
        dtypes = result["dtypes"]
        assert dtypes["col_int"] == "integer"
        assert dtypes["col_float"] == "float"
        assert dtypes["col_text"] == "string"
        # Mixed numeric with blanks still resolves to a numeric dtype.
        assert dtypes["col_sparse"] in {"integer", "float"}

    def test_null_counts(self, sample_csv):
        result = profile_csv(sample_csv)
        null_counts = result["null_counts"]
        assert null_counts["col_int"] == 0
        assert null_counts["col_text"] == 0
        assert null_counts["col_sparse"] == 2

    def test_numeric_summary(self, sample_csv):
        result = profile_csv(sample_csv)
        numeric = result["numeric_summary"]
        assert set(numeric.keys()) == {"col_int", "col_float", "col_sparse"}
        assert numeric["col_int"]["min"] == 1.0
        assert numeric["col_int"]["max"] == 5.0
        assert numeric["col_int"]["mean"] == 3.0
        assert numeric["col_int"]["count"] == 5
        # Numeric summary ignores blanks.
        assert numeric["col_sparse"]["count"] == 3
        assert numeric["col_sparse"]["mean"] == pytest.approx(30.0)
        # Pure-text columns are excluded from numeric summary.
        assert "col_text" not in numeric

    def test_sample_rows(self, sample_csv):
        result = profile_csv(sample_csv)
        assert len(result["sample_rows"]) == 3
        assert result["sample_rows"][0]["col_text"] == "a"

    def test_column_subset(self, sample_csv):
        result = profile_csv(sample_csv, columns=["col_int", "col_text"])
        assert result["columns"] == ["col_int", "col_text"]
        assert result["column_count"] == 2
        assert set(result["dtypes"].keys()) == {"col_int", "col_text"}
        assert "col_float" not in result["numeric_summary"]

    def test_column_subset_ignores_unknown(self, sample_csv):
        result = profile_csv(sample_csv, columns=["col_int", "does_not_exist"])
        assert result["columns"] == ["col_int"]
        assert result["column_count"] == 1

    def test_max_rows_limits_profile(self):
        df = pd.DataFrame({"x": range(100), "y": range(100, 200)})
        path = _write_csv(df)
        try:
            result = profile_csv(path, max_rows=10)
            assert result["row_count"] == 100
            assert result["rows_profiled"] == 10
            assert result["profile_limited"] is True
            assert result["numeric_summary"]["x"]["count"] == 10
        finally:
            os.unlink(path)

    def test_max_rows_default(self, sample_csv):
        result = profile_csv(sample_csv)
        # Sanity: default ceiling is exposed via the module constant.
        assert _DEFAULT_PROFILE_ROWS == 5000
        assert result["row_scan_cap"] == 250_000
        assert result["scan_limited"] is False

    def test_boolean_dtype(self):
        df = pd.DataFrame({"flag": ["true", "false", "true", "false"]})
        path = _write_csv(df)
        try:
            result = profile_csv(path)
            assert result["dtypes"]["flag"] == "boolean"
        finally:
            os.unlink(path)

    def test_empty_column_dtype(self):
        df = pd.DataFrame({"present": [1, 2, 3], "blank": [None, None, None]})
        path = _write_csv(df)
        try:
            result = profile_csv(path)
            assert result["dtypes"]["blank"] == "empty"
            assert result["null_counts"]["blank"] == 3
            assert "blank" not in result["numeric_summary"]
        finally:
            os.unlink(path)

    def test_file_not_found(self):
        result = profile_csv("/nonexistent/path/data.csv")
        assert not result["success"]
        assert result["error_type"] == "FileNotFoundError"

    def test_path_is_directory(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            result = profile_csv(tmpdir)
            assert not result["success"]
            assert result["error_type"] == "IsADirectoryError"

    def test_handles_blank_tokens(self):
        df = pd.DataFrame(
            {
                "v": ["1", "NA", "n/a", "NULL", "5", ""],
            }
        )
        path = _write_csv(df)
        try:
            result = profile_csv(path)
            assert result["null_counts"]["v"] == 4
            assert result["numeric_summary"]["v"]["count"] == 2
        finally:
            os.unlink(path)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
