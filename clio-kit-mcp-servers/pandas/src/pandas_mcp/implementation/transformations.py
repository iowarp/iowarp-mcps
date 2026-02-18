"""
Data transformation capabilities including groupby, merge, and pivot operations.
"""

import pandas as pd
import os
from typing import Optional, List, Dict
import traceback


def groupby_operations(
    file_path: str,
    group_by: List[str],
    operations: Dict[str, str],
    filter_condition: Optional[str] = None,
) -> dict:
    """
    Perform groupby operations on data.

    Args:
        file_path: Path to the data file
        group_by: Columns to group by
        operations: Dictionary of column: operation pairs
        filter_condition: Optional filter condition

    Returns:
        Dictionary with groupby results
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

        # Apply filter if provided
        if filter_condition:
            try:
                df = df.query(filter_condition)
            except Exception as e:
                return {
                    "success": False,
                    "error": f"Filter condition error: {str(e)}",
                    "error_type": "ValueError",
                }

        # Check if group_by columns exist
        missing_cols = [col for col in group_by if col not in df.columns]
        if missing_cols:
            return {
                "success": False,
                "error": f"Group by columns not found: {missing_cols}",
                "error_type": "ValueError",
            }

        # Group by operations
        grouped = df.groupby(group_by)

        # Apply aggregations
        agg_dict = {}
        for col, operation in operations.items():
            if col not in df.columns:
                continue

            if operation == "count":
                agg_dict[col] = "count"
            elif operation == "sum":
                agg_dict[col] = "sum"
            elif operation == "mean":
                agg_dict[col] = "mean"
            elif operation == "median":
                agg_dict[col] = "median"
            elif operation == "std":
                agg_dict[col] = "std"
            elif operation == "min":
                agg_dict[col] = "min"
            elif operation == "max":
                agg_dict[col] = "max"
            elif operation == "nunique":
                agg_dict[col] = "nunique"
            else:
                agg_dict[col] = "mean"  # Default to mean

        # Perform aggregation
        result = grouped.agg(agg_dict)

        # Reset index to make group columns regular columns
        result = result.reset_index()

        # Convert to JSON-serializable format
        result_dict = result.to_dict("records")

        # Group information
        group_info = {
            "group_by_columns": group_by,
            "operations": operations,
            "filter_condition": filter_condition,
            "number_of_groups": len(result),
            "original_rows": len(df),
            "aggregated_columns": list(agg_dict.keys()),
        }

        # Save result
        output_path = file_path.replace(".csv", "_grouped.csv")
        result.to_csv(output_path, index=False)

        return {
            "success": True,
            "file_path": file_path,
            "output_file": output_path,
            "group_info": group_info,
            "results": result_dict,
            "message": f"Grouped data into {len(result)} groups",
        }

    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "error_type": type(e).__name__,
            "traceback": traceback.format_exc(),
        }


def merge_datasets(
    left_file: str,
    right_file: str,
    join_type: str = "inner",
    left_on: Optional[str] = None,
    right_on: Optional[str] = None,
    on: Optional[str] = None,
) -> dict:
    """
    Merge two datasets.

    Args:
        left_file: Path to the left dataset
        right_file: Path to the right dataset
        join_type: Type of join (inner, outer, left, right)
        left_on: Column to join on in left dataset
        right_on: Column to join on in right dataset
        on: Column to join on (if same in both datasets)

    Returns:
        Dictionary with merge results
    """
    try:
        if not os.path.exists(left_file):
            return {
                "success": False,
                "error": f"Left file not found: {left_file}",
                "error_type": "FileNotFoundError",
            }

        if not os.path.exists(right_file):
            return {
                "success": False,
                "error": f"Right file not found: {right_file}",
                "error_type": "FileNotFoundError",
            }

        # Load datasets
        left_df = pd.read_csv(left_file)
        right_df = pd.read_csv(right_file)

        # Determine join keys
        if on:
            left_on = on
            right_on = on
        elif not left_on or not right_on:
            return {
                "success": False,
                "error": "Must specify either 'on' or both 'left_on' and 'right_on'",
                "error_type": "ValueError",
            }

        # Check if join columns exist
        if left_on not in left_df.columns:
            return {
                "success": False,
                "error": f"Left join column '{left_on}' not found in left dataset",
                "error_type": "ValueError",
            }

        if right_on not in right_df.columns:
            return {
                "success": False,
                "error": f"Right join column '{right_on}' not found in right dataset",
                "error_type": "ValueError",
            }

        # Perform merge
        merged_df = pd.merge(
            left_df,
            right_df,
            left_on=left_on,
            right_on=right_on,
            how=join_type,
            suffixes=("_left", "_right"),
        )

        # Merge statistics
        merge_stats = {
            "left_shape": left_df.shape,
            "right_shape": right_df.shape,
            "merged_shape": merged_df.shape,
            "join_type": join_type,
            "left_on": left_on,
            "right_on": right_on,
            "common_values": int(left_df[left_on].isin(right_df[right_on]).sum()),
            "left_only_values": int((~left_df[left_on].isin(right_df[right_on])).sum()),
            "right_only_values": int(
                (~right_df[right_on].isin(left_df[left_on])).sum()
            ),
        }

        # Save merged dataset
        output_path = left_file.replace(".csv", "_merged.csv")
        merged_df.to_csv(output_path, index=False)

        # Convert to JSON-serializable format (limit to first 100 rows)
        merged_dict = merged_df.head(100).to_dict("records")

        return {
            "success": True,
            "left_file": left_file,
            "right_file": right_file,
            "output_file": output_path,
            "merge_stats": merge_stats,
            "merged_data": merged_dict,
            "message": f"Merged datasets: {merge_stats['left_shape']} + {merge_stats['right_shape']} = {merge_stats['merged_shape']}",
        }

    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "error_type": type(e).__name__,
            "traceback": traceback.format_exc(),
        }


def create_pivot_table(
    file_path: str,
    index: List[str],
    columns: Optional[List[str]] = None,
    values: Optional[List[str]] = None,
    aggfunc: str = "mean",
) -> dict:
    """
    Create a pivot table from data.

    Args:
        file_path: Path to the data file
        index: Columns to use as row index
        columns: Columns to use as column headers
        values: Columns to aggregate
        aggfunc: Aggregation function

    Returns:
        Dictionary with pivot table results
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

        # Check if index columns exist
        missing_cols = [col for col in index if col not in df.columns]
        if missing_cols:
            return {
                "success": False,
                "error": f"Index columns not found: {missing_cols}",
                "error_type": "ValueError",
            }

        # Check if column headers exist
        if columns:
            missing_cols = [col for col in columns if col not in df.columns]
            if missing_cols:
                return {
                    "success": False,
                    "error": f"Column header columns not found: {missing_cols}",
                    "error_type": "ValueError",
                }

        # Check if value columns exist
        if values:
            missing_cols = [col for col in values if col not in df.columns]
            if missing_cols:
                return {
                    "success": False,
                    "error": f"Value columns not found: {missing_cols}",
                    "error_type": "ValueError",
                }

        # Create pivot table
        pivot_table = pd.pivot_table(
            df,
            index=index,
            columns=columns,
            values=values,
            aggfunc=aggfunc,
            fill_value=0,
        )

        # Reset index to make it a regular DataFrame
        pivot_table = pivot_table.reset_index()

        # Flatten column names if they are MultiIndex
        if isinstance(pivot_table.columns, pd.MultiIndex):
            pivot_table.columns = [
                "_".join(col).strip() if col[1] != "" else col[0]
                for col in pivot_table.columns.values
            ]

        # Convert to JSON-serializable format
        pivot_dict = pivot_table.to_dict("records")

        # Pivot table information
        pivot_info = {
            "index_columns": index,
            "column_headers": columns,
            "value_columns": values,
            "aggregation_function": aggfunc,
            "pivot_shape": pivot_table.shape,
            "original_shape": df.shape,
        }

        # Save pivot table
        output_path = file_path.replace(".csv", "_pivot.csv")
        pivot_table.to_csv(output_path, index=False)

        return {
            "success": True,
            "file_path": file_path,
            "output_file": output_path,
            "pivot_info": pivot_info,
            "pivot_table": pivot_dict,
            "message": f"Created pivot table with shape {pivot_table.shape}",
        }

    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "error_type": type(e).__name__,
            "traceback": traceback.format_exc(),
        }
