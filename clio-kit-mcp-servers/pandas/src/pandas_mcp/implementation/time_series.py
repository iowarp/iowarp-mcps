"""
Time series analysis capabilities.
"""

import pandas as pd
import numpy as np
import os
from typing import Optional, Dict, Any
import traceback


def time_series_operations(
    file_path: str,
    date_column: str,
    operation: str,
    window_size: Optional[int] = None,
    frequency: Optional[str] = None,
) -> dict:
    """
    Perform time series operations on data.

    Args:
        file_path: Path to the data file
        date_column: Column containing date/time information
        operation: Type of operation (resample, rolling, lag, diff)
        window_size: Window size for rolling operations
        frequency: Frequency for resampling operations

    Returns:
        Dictionary with time series results
    """
    try:
        if not os.path.exists(file_path):
            return {
                "success": False,
                "error": f"File not found: {file_path}",
                "error_type": "FileNotFoundError",
            }

        # Load data
        df = pd.read_csv(file_path)

        # Check if date column exists
        if date_column not in df.columns:
            return {
                "success": False,
                "error": f"Date column '{date_column}' not found",
                "error_type": "ValueError",
            }

        # Convert date column to datetime
        try:
            df[date_column] = pd.to_datetime(df[date_column])
        except Exception as e:
            return {
                "success": False,
                "error": f"Failed to convert '{date_column}' to datetime: {str(e)}",
                "error_type": "ValueError",
            }

        # Set date column as index
        df = df.set_index(date_column)

        # Sort by date
        df = df.sort_index()

        # Perform time series operations
        if operation == "resample":
            if not frequency:
                frequency = "D"  # Default to daily

            # Resample data
            numeric_cols = df.select_dtypes(include=[np.number]).columns
            resampled = df[numeric_cols].resample(frequency).mean()

            # Fill missing values using forward fill
            resampled = resampled.ffill()

            result_df = resampled.reset_index()

            operation_info = {
                "operation": "resample",
                "frequency": frequency,
                "original_shape": df.shape,
                "resampled_shape": resampled.shape,
                "date_range": {
                    "start": str(df.index.min()),
                    "end": str(df.index.max()),
                    "periods": len(resampled),
                },
            }

        elif operation == "rolling":
            if not window_size:
                window_size = 7  # Default to 7-day window

            # Calculate rolling statistics
            numeric_cols = df.select_dtypes(include=[np.number]).columns
            rolling_stats = {}

            for col in numeric_cols:
                rolling_mean = df[col].rolling(window=window_size).mean()
                rolling_std = df[col].rolling(window=window_size).std()
                rolling_min = df[col].rolling(window=window_size).min()
                rolling_max = df[col].rolling(window=window_size).max()

                rolling_stats[f"{col}_rolling_mean"] = rolling_mean
                rolling_stats[f"{col}_rolling_std"] = rolling_std
                rolling_stats[f"{col}_rolling_min"] = rolling_min
                rolling_stats[f"{col}_rolling_max"] = rolling_max

            result_df = pd.DataFrame(rolling_stats).reset_index()

            operation_info = {
                "operation": "rolling",
                "window_size": window_size,
                "original_shape": df.shape,
                "rolling_shape": result_df.shape,
                "statistics": ["mean", "std", "min", "max"],
            }

        elif operation == "lag":
            if not window_size:
                window_size = 1  # Default to 1-period lag

            # Create lagged features
            numeric_cols = df.select_dtypes(include=[np.number]).columns
            lagged_data = df.copy()

            for col in numeric_cols:
                for lag in range(1, window_size + 1):
                    lagged_data[f"{col}_lag_{lag}"] = df[col].shift(lag)

            result_df = lagged_data.reset_index()

            operation_info = {
                "operation": "lag",
                "lag_periods": window_size,
                "original_shape": df.shape,
                "lagged_shape": result_df.shape,
                "lagged_columns": [col for col in result_df.columns if "_lag_" in col],
            }

        elif operation == "diff":
            if not window_size:
                window_size = 1  # Default to 1-period difference

            # Calculate differences
            numeric_cols = df.select_dtypes(include=[np.number]).columns
            diff_data = df.copy()

            for col in numeric_cols:
                diff_data[f"{col}_diff"] = df[col].diff(periods=window_size)

            result_df = diff_data.reset_index()

            operation_info = {
                "operation": "diff",
                "diff_periods": window_size,
                "original_shape": df.shape,
                "diff_shape": result_df.shape,
                "diff_columns": [col for col in result_df.columns if "_diff" in col],
            }

        else:
            return {
                "success": False,
                "error": f"Unknown operation: {operation}",
                "error_type": "ValueError",
            }

        # Save result
        output_path = file_path.replace(".csv", f"_{operation}.csv")
        result_df.to_csv(output_path, index=False)

        # Convert to JSON-serializable format (limit to first 100 rows)
        result_dict = result_df.head(100).to_dict("records")

        return {
            "success": True,
            "file_path": file_path,
            "output_file": output_path,
            "operation_info": operation_info,
            "results": result_dict,
            "message": f"Time series {operation} operation completed",
        }

    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "error_type": type(e).__name__,
            "traceback": traceback.format_exc(),
        }


def detect_seasonality(
    file_path: str, date_column: str, value_column: str, period: Optional[int] = None
) -> Dict[str, Any]:
    """
    Detect seasonality in time series data.

    Args:
        file_path: Path to the data file
        date_column: Column containing date/time information
        value_column: Column containing values to analyze
        period: Expected period length (e.g., 12 for monthly data)

    Returns:
        Dictionary with seasonality detection results
    """
    try:
        if not os.path.exists(file_path):
            return {
                "success": False,
                "error": f"File not found: {file_path}",
                "error_type": "FileNotFoundError",
            }

        # Load data
        df = pd.read_csv(file_path)

        # Check if columns exist
        if date_column not in df.columns:
            return {
                "success": False,
                "error": f"Date column '{date_column}' not found",
                "error_type": "ValueError",
            }

        if value_column not in df.columns:
            return {
                "success": False,
                "error": f"Value column '{value_column}' not found",
                "error_type": "ValueError",
            }

        # Convert date column to datetime
        df[date_column] = pd.to_datetime(df[date_column])
        df = df.set_index(date_column).sort_index()

        # Get time series data
        ts_data = df[value_column].dropna()

        # Basic seasonality detection using autocorrelation
        from scipy.stats import pearsonr

        # If period not specified, try to detect it
        if period is None:
            # Try common periods
            periods_to_test = [7, 12, 24, 30, 365]  # Weekly, monthly, daily patterns
            best_period = None
            best_correlation = 0

            for test_period in periods_to_test:
                if len(ts_data) > test_period:
                    # Calculate autocorrelation
                    lagged_data = ts_data.shift(test_period)
                    valid_data = pd.DataFrame(
                        {"original": ts_data, "lagged": lagged_data}
                    ).dropna()

                    if len(valid_data) > 10:
                        correlation, p_value = pearsonr(
                            valid_data["original"], valid_data["lagged"]
                        )
                        if abs(correlation) > best_correlation:
                            best_correlation = abs(correlation)
                            best_period = test_period

            period = best_period

        # Analyze seasonality
        seasonality_results = {
            "detected_period": period,
            "data_length": len(ts_data),
            "date_range": {
                "start": str(ts_data.index.min()),
                "end": str(ts_data.index.max()),
            },
        }

        if period and len(ts_data) > period:
            # Calculate seasonal statistics
            ts_data_df = ts_data.reset_index()
            ts_data_df["period_index"] = ts_data_df.index % period

            seasonal_stats = (
                ts_data_df.groupby("period_index")[value_column]
                .agg(["mean", "std", "min", "max", "count"])
                .reset_index()
            )

            seasonality_results.update(
                {
                    "seasonal_statistics": seasonal_stats.to_dict("records"),
                    "seasonal_strength": int(
                        seasonal_stats["mean"].std() / seasonal_stats["mean"].mean()
                    ),
                    "has_seasonality": seasonal_stats["mean"].std()
                    > 0.1 * seasonal_stats["mean"].mean(),
                }
            )

        return {
            "success": True,
            "file_path": file_path,
            "value_column": value_column,
            "seasonality_results": seasonality_results,
            "message": f"Seasonality analysis completed for {value_column}",
        }

    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "error_type": type(e).__name__,
            "traceback": traceback.format_exc(),
        }
