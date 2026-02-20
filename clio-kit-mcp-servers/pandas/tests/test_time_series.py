"""
Test cases for time series analysis capabilities.
"""

import pytest
import pandas as pd
import numpy as np
import tempfile
import os

from pandas_mcp.implementation.time_series import (
    time_series_operations,
    detect_seasonality,
)


class TestTimeSeriesOperations:
    """Test suite for time series operations"""

    @pytest.fixture
    def sample_time_series_data(self):
        """Create sample time series data"""
        dates = pd.date_range(start="2023-01-01", periods=100, freq="D")
        df = pd.DataFrame(
            {
                "date": dates,
                "temperature": np.random.rand(100) * 20 + 10,
                "humidity": np.random.rand(100) * 50 + 30,
                "pressure": np.random.rand(100) * 10 + 1000,
            }
        )
        return df

    @pytest.fixture
    def temp_ts_file(self, sample_time_series_data):
        """Create a temporary time series file"""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False) as f:
            sample_time_series_data.to_csv(f.name, index=False)
            yield f.name
        if os.path.exists(f.name):
            os.unlink(f.name)
            # Clean up generated files
            for operation in ["resample", "rolling", "lag", "diff"]:
                output_file = f.name.replace(".csv", f"_{operation}.csv")
                if os.path.exists(output_file):
                    os.unlink(output_file)

    def test_resample_operation_success(self, temp_ts_file):
        """Test resampling operation"""
        result = time_series_operations(
            temp_ts_file, date_column="date", operation="resample", frequency="W"
        )

        assert result["success"]
        assert "operation_info" in result
        assert result["operation_info"]["operation"] == "resample"
        assert result["operation_info"]["frequency"] == "W"
        assert "results" in result
        assert os.path.exists(result["output_file"])

    def test_resample_default_frequency(self, temp_ts_file):
        """Test resampling with default frequency"""
        result = time_series_operations(
            temp_ts_file, date_column="date", operation="resample"
        )

        assert result["success"]
        assert result["operation_info"]["frequency"] == "D"

    def test_rolling_operation_success(self, temp_ts_file):
        """Test rolling window operation"""
        result = time_series_operations(
            temp_ts_file, date_column="date", operation="rolling", window_size=7
        )

        assert result["success"]
        assert result["operation_info"]["operation"] == "rolling"
        assert result["operation_info"]["window_size"] == 7
        assert "temperature_rolling_mean" in str(result["results"])
        assert os.path.exists(result["output_file"])

    def test_rolling_default_window(self, temp_ts_file):
        """Test rolling with default window size"""
        result = time_series_operations(
            temp_ts_file, date_column="date", operation="rolling"
        )

        assert result["success"]
        assert result["operation_info"]["window_size"] == 7

    def test_lag_operation_success(self, temp_ts_file):
        """Test lag operation"""
        result = time_series_operations(
            temp_ts_file, date_column="date", operation="lag", window_size=3
        )

        assert result["success"]
        assert result["operation_info"]["operation"] == "lag"
        assert result["operation_info"]["lag_periods"] == 3
        # Should have lag columns
        assert len(result["operation_info"]["lagged_columns"]) > 0
        assert os.path.exists(result["output_file"])

    def test_diff_operation_success(self, temp_ts_file):
        """Test difference operation"""
        result = time_series_operations(
            temp_ts_file, date_column="date", operation="diff", window_size=1
        )

        assert result["success"]
        assert result["operation_info"]["operation"] == "diff"
        assert result["operation_info"]["diff_periods"] == 1
        assert len(result["operation_info"]["diff_columns"]) > 0
        assert os.path.exists(result["output_file"])

    def test_file_not_found(self):
        """Test with non-existent file"""
        result = time_series_operations(
            "nonexistent.csv", date_column="date", operation="resample"
        )

        assert not result["success"]
        assert result["error_type"] == "FileNotFoundError"

    def test_invalid_date_column(self, temp_ts_file):
        """Test with invalid date column"""
        result = time_series_operations(
            temp_ts_file, date_column="nonexistent", operation="resample"
        )

        assert not result["success"]
        assert "not found" in result["error"]

    def test_invalid_datetime_conversion(self):
        """Test with non-datetime column"""
        df = pd.DataFrame({"date": ["not", "a", "date"], "value": [1, 2, 3]})

        with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False) as f:
            df.to_csv(f.name, index=False)
            temp_file = f.name

        try:
            result = time_series_operations(
                temp_file, date_column="date", operation="resample"
            )

            assert not result["success"]
            assert "Failed to convert" in result["error"]
        finally:
            os.unlink(temp_file)

    def test_unknown_operation(self, temp_ts_file):
        """Test with unknown operation"""
        result = time_series_operations(
            temp_ts_file, date_column="date", operation="unknown_op"
        )

        assert not result["success"]
        assert "Unknown operation" in result["error"]

    def test_resample_multiple_frequencies(self, temp_ts_file):
        """Test resampling with different frequencies"""
        frequencies = ["D", "W", "M"]

        for freq in frequencies:
            result = time_series_operations(
                temp_ts_file, date_column="date", operation="resample", frequency=freq
            )

            assert result["success"]
            assert result["operation_info"]["frequency"] == freq
            if os.path.exists(result["output_file"]):
                os.unlink(result["output_file"])

    def test_rolling_statistics_completeness(self, temp_ts_file):
        """Test that rolling operation includes all statistics"""
        result = time_series_operations(
            temp_ts_file, date_column="date", operation="rolling", window_size=5
        )

        assert result["success"]
        assert "mean" in result["operation_info"]["statistics"]
        assert "std" in result["operation_info"]["statistics"]
        assert "min" in result["operation_info"]["statistics"]
        assert "max" in result["operation_info"]["statistics"]

    def test_lag_multiple_periods(self, temp_ts_file):
        """Test lag with multiple periods"""
        result = time_series_operations(
            temp_ts_file, date_column="date", operation="lag", window_size=5
        )

        assert result["success"]
        # Should create lag_1 through lag_5 for each numeric column
        lagged_columns = result["operation_info"]["lagged_columns"]
        assert len(lagged_columns) > 5


class TestSeasonalityDetection:
    """Test suite for seasonality detection"""

    @pytest.fixture
    def seasonal_data(self):
        """Create data with known seasonality"""
        dates = pd.date_range(start="2020-01-01", periods=365, freq="D")
        # Create seasonal pattern (weekly)
        day_of_week = dates.dayofweek
        seasonal_component = np.sin(2 * np.pi * day_of_week / 7) * 10
        trend = np.linspace(0, 10, 365)
        noise = np.random.randn(365) * 2

        df = pd.DataFrame(
            {
                "date": dates,
                "value": seasonal_component + trend + noise + 50,
            }
        )
        return df

    @pytest.fixture
    def temp_seasonal_file(self, seasonal_data):
        """Create temporary file with seasonal data"""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False) as f:
            seasonal_data.to_csv(f.name, index=False)
            yield f.name
        if os.path.exists(f.name):
            os.unlink(f.name)

    def test_detect_seasonality_success(self, temp_seasonal_file):
        """Test seasonality detection"""
        result = detect_seasonality(
            temp_seasonal_file, date_column="date", value_column="value", period=7
        )

        assert result["success"]
        assert "seasonality_results" in result
        assert result["seasonality_results"]["detected_period"] == 7

    def test_detect_seasonality_auto_period(self, temp_seasonal_file):
        """Test seasonality detection with auto period detection"""
        result = detect_seasonality(
            temp_seasonal_file, date_column="date", value_column="value"
        )

        assert result["success"]
        assert "detected_period" in result["seasonality_results"]
        # Should detect some period
        assert result["seasonality_results"]["detected_period"] is not None

    def test_detect_seasonality_file_not_found(self):
        """Test with non-existent file"""
        result = detect_seasonality(
            "nonexistent.csv", date_column="date", value_column="value"
        )

        assert not result["success"]
        assert result["error_type"] == "FileNotFoundError"

    def test_detect_seasonality_invalid_date_column(self, temp_seasonal_file):
        """Test with invalid date column"""
        result = detect_seasonality(
            temp_seasonal_file, date_column="nonexistent", value_column="value"
        )

        assert not result["success"]
        assert "not found" in result["error"]

    def test_detect_seasonality_invalid_value_column(self, temp_seasonal_file):
        """Test with invalid value column"""
        result = detect_seasonality(
            temp_seasonal_file, date_column="date", value_column="nonexistent"
        )

        assert not result["success"]
        assert "not found" in result["error"]

    def test_seasonality_statistics_included(self, temp_seasonal_file):
        """Test that seasonal statistics are included"""
        result = detect_seasonality(
            temp_seasonal_file, date_column="date", value_column="value", period=7
        )

        assert result["success"]
        assert "seasonal_statistics" in result["seasonality_results"]
        assert "seasonal_strength" in result["seasonality_results"]
        assert "has_seasonality" in result["seasonality_results"]

    def test_seasonality_date_range(self, temp_seasonal_file):
        """Test that date range is included in results"""
        result = detect_seasonality(
            temp_seasonal_file, date_column="date", value_column="value"
        )

        assert result["success"]
        assert "date_range" in result["seasonality_results"]
        assert "start" in result["seasonality_results"]["date_range"]
        assert "end" in result["seasonality_results"]["date_range"]

    def test_seasonality_with_missing_values(self):
        """Test seasonality detection with missing values"""
        dates = pd.date_range(start="2020-01-01", periods=100, freq="D")
        values = np.random.rand(100)
        # Introduce missing values
        values[::10] = np.nan

        df = pd.DataFrame({"date": dates, "value": values})

        with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False) as f:
            df.to_csv(f.name, index=False)
            temp_file = f.name

        try:
            result = detect_seasonality(
                temp_file, date_column="date", value_column="value"
            )

            # Should still work with missing values
            assert result["success"]
        finally:
            os.unlink(temp_file)

    def test_short_time_series(self):
        """Test with short time series (insufficient data)"""
        dates = pd.date_range(start="2020-01-01", periods=5, freq="D")
        df = pd.DataFrame({"date": dates, "value": [1, 2, 3, 4, 5]})

        with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False) as f:
            df.to_csv(f.name, index=False)
            temp_file = f.name

        try:
            result = detect_seasonality(
                temp_file, date_column="date", value_column="value", period=7
            )

            # Should handle gracefully
            assert result["success"]
        finally:
            os.unlink(temp_file)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
