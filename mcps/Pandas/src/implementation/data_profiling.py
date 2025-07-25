"""
Data profiling capabilities for quick dataset analysis.
"""

import pandas as pd
import numpy as np
import os
from typing import Optional, Dict, Any
import traceback


def profile_data(
    file_path: str,
    include_correlations: bool = False,
    sample_size: Optional[int] = None,
) -> dict:
    """
    Generate a comprehensive data profile.

    Args:
        file_path: Path to the data file
        include_correlations: Whether to include correlation analysis
        sample_size: Number of rows to sample for analysis

    Returns:
        Dictionary with data profiling results
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

        # Sample data if requested
        if sample_size and len(df) > sample_size:
            df = df.sample(n=sample_size, random_state=42)

        # Basic info
        basic_info = {
            "shape": df.shape,
            "columns": df.columns.tolist(),
            "dtypes": df.dtypes.astype(str).to_dict(),
            "memory_usage_mb": round(
                df.memory_usage(deep=True).sum() / (1024 * 1024), 2
            ),
        }

        # Missing data analysis
        missing_data = {
            "total_missing": int(df.isnull().sum().sum()),
            "missing_by_column": df.isnull().sum().to_dict(),
            "missing_percentage": (df.isnull().sum() / len(df) * 100)
            .round(2)
            .to_dict(),
            "columns_with_missing": df.columns[df.isnull().any()].tolist(),
            "complete_rows": int(df.dropna().shape[0]),
        }

        # Column analysis
        column_analysis = {}

        # Numeric columns
        numeric_cols = df.select_dtypes(include=[np.number]).columns
        for col in numeric_cols:
            col_data = df[col].dropna()
            if len(col_data) > 0:
                column_analysis[col] = {
                    "type": "numeric",
                    "count": len(col_data),
                    "mean": float(col_data.mean()),
                    "std": float(col_data.std()),
                    "min": float(col_data.min()),
                    "25%": float(col_data.quantile(0.25)),
                    "50%": float(col_data.median()),
                    "75%": float(col_data.quantile(0.75)),
                    "max": float(col_data.max()),
                    "unique_values": int(col_data.nunique()),
                    "zeros_count": int((col_data == 0).sum()),
                    "negative_count": int((col_data < 0).sum()),
                    "skewness": float(col_data.skew()),
                    "kurtosis": float(col_data.kurtosis()),
                }

        # Categorical columns
        categorical_cols = df.select_dtypes(include=["object", "category"]).columns
        for col in categorical_cols:
            col_data = df[col].dropna()
            if len(col_data) > 0:
                value_counts = col_data.value_counts()
                column_analysis[col] = {
                    "type": "categorical",
                    "count": len(col_data),
                    "unique_values": int(col_data.nunique()),
                    "most_frequent": str(value_counts.index[0])
                    if len(value_counts) > 0
                    else None,
                    "most_frequent_count": int(value_counts.iloc[0])
                    if len(value_counts) > 0
                    else 0,
                    "least_frequent": str(value_counts.index[-1])
                    if len(value_counts) > 0
                    else None,
                    "least_frequent_count": int(value_counts.iloc[-1])
                    if len(value_counts) > 0
                    else 0,
                    "top_10_values": value_counts.head(10).to_dict(),
                    "average_length": float(col_data.astype(str).str.len().mean()),
                    "empty_strings": int((col_data == "").sum()),
                }

        # DateTime columns
        datetime_cols = df.select_dtypes(include=["datetime64"]).columns
        for col in datetime_cols:
            col_data = df[col].dropna()
            if len(col_data) > 0:
                column_analysis[col] = {
                    "type": "datetime",
                    "count": len(col_data),
                    "min_date": str(col_data.min()),
                    "max_date": str(col_data.max()),
                    "date_range_days": (col_data.max() - col_data.min()).days,
                    "unique_dates": int(col_data.nunique()),
                }

        # Data quality checks
        quality_checks: Dict[str, Any] = {
            "duplicate_rows": int(df.duplicated().sum()),
            "constant_columns": [col for col in df.columns if df[col].nunique() <= 1],
            "high_cardinality_columns": [
                col for col in df.columns if df[col].nunique() > 0.9 * len(df)
            ],
            "mixed_type_columns": [],
        }

        # Check for mixed types in object columns
        for col in df.select_dtypes(include=["object"]).columns:
            col_data = df[col].dropna()
            if len(col_data) > 0:
                # Check if column has mixed numeric and string values
                numeric_count = 0
                string_count = 0
                for value in col_data.sample(min(100, len(col_data))):
                    try:
                        float(value)
                        numeric_count += 1
                    except (ValueError, TypeError):
                        string_count += 1

                if numeric_count > 0 and string_count > 0:
                    quality_checks["mixed_type_columns"].append(col)

        # Correlation analysis (if requested)
        correlations = None
        if include_correlations and len(numeric_cols) > 1:
            corr_matrix = df[numeric_cols].corr()
            correlations = {
                "correlation_matrix": corr_matrix.to_dict(),
                "high_correlations": [],
            }

            # Find high correlations
            for i in range(len(corr_matrix.columns)):
                for j in range(i + 1, len(corr_matrix.columns)):
                    corr_value = corr_matrix.iloc[i, j]
                    if abs(corr_value) > 0.7:
                        correlations["high_correlations"].append(
                            {
                                "variable1": corr_matrix.columns[i],
                                "variable2": corr_matrix.columns[j],
                                "correlation": float(corr_value),
                            }
                        )

        # Summary statistics
        summary = {
            "total_columns": len(df.columns),
            "numeric_columns": len(numeric_cols),
            "categorical_columns": len(categorical_cols),
            "datetime_columns": len(datetime_cols),
            "total_rows": len(df),
            "complete_rows": int(df.dropna().shape[0]),
            "duplicate_rows": quality_checks["duplicate_rows"],
            "memory_usage_mb": basic_info["memory_usage_mb"],
        }

        return {
            "success": True,
            "file_path": file_path,
            "basic_info": basic_info,
            "summary": summary,
            "missing_data": missing_data,
            "column_analysis": column_analysis,
            "quality_checks": quality_checks,
            "correlations": correlations,
            "message": f"Data profile generated for {len(df.columns)} columns and {len(df)} rows",
        }

    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "error_type": type(e).__name__,
            "traceback": traceback.format_exc(),
        }
