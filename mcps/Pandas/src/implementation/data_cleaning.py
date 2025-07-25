"""
Data cleaning capabilities for handling missing data and outliers.
"""

import pandas as pd
import numpy as np
import os
from typing import Optional, List
import traceback


def handle_missing_data(
    file_path: str,
    strategy: str = "detect",
    method: Optional[str] = None,
    columns: Optional[List[str]] = None,
) -> dict:
    """
    Handle missing data in various ways.

    Args:
        file_path: Path to the data file
        strategy: Strategy to handle missing data (detect, remove, impute)
        method: Method for imputation (mean, median, mode, forward_fill, backward_fill)
        columns: Specific columns to process

    Returns:
        Dictionary with missing data handling results
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
        original_shape = df.shape

        if columns:
            df[columns].copy()
        else:
            df.copy()

        # Detect missing data
        missing_info = {
            "total_missing": int(df.isnull().sum().sum()),
            "missing_by_column": df.isnull().sum().to_dict(),
            "missing_percentage": (df.isnull().sum() / len(df) * 100).to_dict(),
            "rows_with_missing": int(df.isnull().any(axis=1).sum()),
            "complete_rows": int(df.dropna().shape[0]),
        }

        if strategy == "detect":
            return {
                "success": True,
                "file_path": file_path,
                "original_shape": original_shape,
                "missing_data_info": missing_info,
                "message": f"Found {missing_info['total_missing']} missing values",
            }

        elif strategy == "remove":
            # Remove rows with missing data
            df_cleaned = df.dropna()
            removed_rows = len(df) - len(df_cleaned)

            # Save cleaned data
            output_path = file_path.replace(".csv", "_no_missing.csv")
            df_cleaned.to_csv(output_path, index=False)

            return {
                "success": True,
                "file_path": file_path,
                "output_file": output_path,
                "original_shape": original_shape,
                "new_shape": df_cleaned.shape,
                "removed_rows": removed_rows,
                "missing_data_info": missing_info,
                "message": f"Removed {removed_rows} rows with missing data",
            }

        elif strategy == "impute":
            if method is None:
                method = "mean"

            df_imputed = df.copy()
            imputation_info = {}

            for col in df_imputed.columns:
                if df_imputed[col].isnull().sum() > 0:
                    if df_imputed[col].dtype in ["int64", "float64"]:
                        # Numeric columns
                        if method == "mean":
                            fill_value = df_imputed[col].mean()
                        elif method == "median":
                            fill_value = df_imputed[col].median()
                        elif method == "mode":
                            fill_value = (
                                df_imputed[col].mode()[0]
                                if not df_imputed[col].mode().empty
                                else 0
                            )
                        else:
                            fill_value = df_imputed[col].mean()

                        df_imputed[col].fillna(fill_value, inplace=True)
                        imputation_info[col] = {
                            "method": method,
                            "fill_value": float(fill_value),
                            "imputed_count": int(df[col].isnull().sum()),
                        }

                    else:
                        # Categorical columns
                        if method == "mode":
                            fill_value = (
                                df_imputed[col].mode()[0]
                                if not df_imputed[col].mode().empty
                                else "Unknown"
                            )
                        elif method == "forward_fill":
                            df_imputed[col].fillna(method="ffill", inplace=True)
                            fill_value = "forward_fill"
                        elif method == "backward_fill":
                            df_imputed[col].fillna(method="bfill", inplace=True)
                            fill_value = "backward_fill"
                        else:
                            fill_value = "Unknown"
                            df_imputed[col].fillna(fill_value, inplace=True)

                        imputation_info[col] = {
                            "method": method,
                            "fill_value": str(fill_value),
                            "imputed_count": int(df[col].isnull().sum()),
                        }

            # Save imputed data
            output_path = file_path.replace(".csv", "_imputed.csv")
            df_imputed.to_csv(output_path, index=False)

            return {
                "success": True,
                "file_path": file_path,
                "output_file": output_path,
                "original_shape": original_shape,
                "imputation_method": method,
                "imputation_info": imputation_info,
                "missing_data_info": missing_info,
                "message": f"Imputed missing values using {method} method",
            }

        else:
            return {
                "success": False,
                "error": f"Unknown strategy: {strategy}",
                "error_type": "ValueError",
            }

    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "error_type": type(e).__name__,
            "traceback": traceback.format_exc(),
        }


def clean_data(
    file_path: str,
    remove_duplicates: bool = False,
    detect_outliers: bool = False,
    convert_types: bool = False,
) -> dict:
    """
    Clean data by removing duplicates, detecting outliers, and converting types.

    Args:
        file_path: Path to the data file
        remove_duplicates: Whether to remove duplicate rows
        detect_outliers: Whether to detect outliers
        convert_types: Whether to optimize data types

    Returns:
        Dictionary with data cleaning results
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
        original_shape = df.shape
        original_memory = df.memory_usage(deep=True).sum()

        cleaning_results = {
            "original_shape": original_shape,
            "original_memory_mb": round(original_memory / (1024 * 1024), 2),
        }

        # Remove duplicates
        if remove_duplicates:
            duplicates_count = df.duplicated().sum()
            df = df.drop_duplicates()
            cleaning_results["duplicates_removed"] = int(duplicates_count)

        # Detect outliers
        outliers_info = {}
        if detect_outliers:
            numeric_cols = df.select_dtypes(include=[np.number]).columns

            for col in numeric_cols:
                # Using IQR method
                Q1 = df[col].quantile(0.25)
                Q3 = df[col].quantile(0.75)
                IQR = Q3 - Q1
                lower_bound = Q1 - 1.5 * IQR
                upper_bound = Q3 + 1.5 * IQR

                outliers = df[(df[col] < lower_bound) | (df[col] > upper_bound)][col]
                outliers_info[col] = {
                    "outlier_count": len(outliers),
                    "outlier_percentage": round(len(outliers) / len(df) * 100, 2),
                    "lower_bound": float(lower_bound),
                    "upper_bound": float(upper_bound),
                    "outlier_values": outliers.tolist()[:10],  # First 10 outliers
                }

        # Convert types
        type_changes = {}
        if convert_types:
            for col in df.columns:
                df[col].dtype

                if df[col].dtype == "object":
                    # Try to convert to numeric
                    try:
                        numeric_series = pd.to_numeric(df[col], errors="coerce")
                        if not numeric_series.isnull().all():
                            df[col] = numeric_series
                            type_changes[col] = f"object -> {numeric_series.dtype}"
                            continue
                    except (ValueError, TypeError):
                        pass

                    # Try to convert to datetime
                    try:
                        datetime_series = pd.to_datetime(df[col], errors="coerce")
                        if not datetime_series.isnull().all():
                            df[col] = datetime_series
                            type_changes[col] = "object -> datetime64[ns]"
                            continue
                    except (ValueError, TypeError):
                        pass

                    # Convert to category if it has repeated values
                    unique_ratio = df[col].nunique() / len(df[col])
                    if unique_ratio < 0.5:
                        df[col] = df[col].astype("category")
                        type_changes[col] = "object -> category"

        # Final stats
        final_shape = df.shape
        final_memory = df.memory_usage(deep=True).sum()

        cleaning_results.update(
            {
                "final_shape": final_shape,
                "final_memory_mb": round(final_memory / (1024 * 1024), 2),
                "memory_reduction_mb": round(
                    (original_memory - final_memory) / (1024 * 1024), 2
                ),
                "outliers_info": outliers_info if detect_outliers else None,
                "type_changes": type_changes if convert_types else None,
            }
        )

        # Save cleaned data
        output_path = file_path.replace(".csv", "_cleaned.csv")
        df.to_csv(output_path, index=False)

        return {
            "success": True,
            "file_path": file_path,
            "output_file": output_path,
            "cleaning_results": cleaning_results,
            "message": f"Data cleaned successfully. Shape: {original_shape} -> {final_shape}",
        }

    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "error_type": type(e).__name__,
            "traceback": traceback.format_exc(),
        }
