"""
Data filtering capabilities using boolean indexing.
"""
import pandas as pd
import numpy as np
import os
from typing import Optional, List, Any, Dict
import traceback


def filter_data(file_path: str, filter_conditions: Dict[str, Any],
                output_file: Optional[str] = None) -> dict:
    """
    Filter data using boolean indexing.
    
    Args:
        file_path: Path to the data file
        filter_conditions: Dictionary of column: condition pairs
        output_file: Optional output file path
    
    Returns:
        Dictionary with filtering results
    """
    try:
        if not os.path.exists(file_path):
            return {
                "success": False,
                "error": f"File not found: {file_path}",
                "error_type": "FileNotFoundError"
            }
        
        # Load data
        df = pd.read_csv(file_path)
        original_shape = df.shape
        
        # Apply filters
        filtered_df = df.copy()
        applied_filters = []
        
        for column, condition in filter_conditions.items():
            if column not in df.columns:
                return {
                    "success": False,
                    "error": f"Column '{column}' not found",
                    "error_type": "ValueError"
                }
            
            # Apply different types of filters
            if isinstance(condition, dict):
                # Handle validation-style conditions
                if "min_value" in condition:
                    mask = filtered_df[column] >= condition["min_value"]
                    applied_filters.append(f"{column} >= {condition['min_value']}")
                    filtered_df = filtered_df[mask]
                elif "max_value" in condition:
                    mask = filtered_df[column] <= condition["max_value"]
                    applied_filters.append(f"{column} <= {condition['max_value']}")
                    filtered_df = filtered_df[mask]
                elif "operator" in condition and "value" in condition:
                    # Complex condition with operator
                    operator = condition["operator"]
                    value = condition["value"]
                    
                    if operator == "eq":
                        mask = filtered_df[column] == value
                    elif operator == "ne":
                        mask = filtered_df[column] != value
                    elif operator == "gt":
                        mask = filtered_df[column] > value
                    elif operator == "ge":
                        mask = filtered_df[column] >= value
                    elif operator == "lt":
                        mask = filtered_df[column] < value
                    elif operator == "le":
                        mask = filtered_df[column] <= value
                    elif operator == "in":
                        mask = filtered_df[column].isin(value)
                    elif operator == "not_in":
                        mask = ~filtered_df[column].isin(value)
                    elif operator == "contains":
                        mask = filtered_df[column].str.contains(str(value), na=False)
                    elif operator == "startswith":
                        mask = filtered_df[column].str.startswith(str(value), na=False)
                    elif operator == "endswith":
                        mask = filtered_df[column].str.endswith(str(value), na=False)
                    elif operator == "between":
                        if isinstance(value, list) and len(value) == 2:
                            mask = filtered_df[column].between(value[0], value[1])
                        else:
                            return {
                                "success": False,
                                "error": f"Between operator requires list of 2 values",
                                "error_type": "ValueError"
                            }
                    elif operator == "isnull":
                        mask = filtered_df[column].isnull()
                    elif operator == "notnull":
                        mask = filtered_df[column].notnull()
                    else:
                        return {
                            "success": False,
                            "error": f"Unknown operator: {operator}",
                            "error_type": "ValueError"
                        }
                    
                    rows_before = len(filtered_df)
                    filtered_df = filtered_df[mask]
                    rows_after = len(filtered_df)
                    
                    applied_filters.append({
                        "column": column,
                        "operator": operator,
                        "value": value,
                        "rows_before": rows_before,
                        "rows_after": rows_after,
                        "rows_filtered": rows_before - rows_after
                    })
                
                elif "range" in condition:
                    # Range filter
                    range_values = condition["range"]
                    if isinstance(range_values, list) and len(range_values) == 2:
                        mask = filtered_df[column].between(range_values[0], range_values[1])
                        rows_before = len(filtered_df)
                        filtered_df = filtered_df[mask]
                        rows_after = len(filtered_df)
                        
                        applied_filters.append({
                            "column": column,
                            "operator": "range",
                            "value": range_values,
                            "rows_before": rows_before,
                            "rows_after": rows_after,
                            "rows_filtered": rows_before - rows_after
                        })
            
            else:
                # Simple equality filter
                mask = filtered_df[column] == condition
                rows_before = len(filtered_df)
                filtered_df = filtered_df[mask]
                rows_after = len(filtered_df)
                
                applied_filters.append({
                    "column": column,
                    "operator": "eq",
                    "value": condition,
                    "rows_before": rows_before,
                    "rows_after": rows_after,
                    "rows_filtered": rows_before - rows_after
                })
        
        # Filter statistics
        final_shape = filtered_df.shape
        total_rows_filtered = original_shape[0] - final_shape[0]
        filter_percentage = (total_rows_filtered / original_shape[0]) * 100
        
        filter_stats = {
            "original_shape": original_shape,
            "final_shape": final_shape,
            "rows_filtered": total_rows_filtered,
            "filter_percentage": round(filter_percentage, 2),
            "applied_filters": applied_filters
        }
        
        # Save filtered data
        if output_file is None:
            output_file = file_path.replace('.csv', '_filtered.csv')
        
        filtered_df.to_csv(output_file, index=False)
        
        # Convert to JSON-serializable format (limit to first 100 rows)
        filtered_data = filtered_df.head(100).to_dict('records')
        
        return {
            "success": True,
            "file_path": file_path,
            "output_file": output_file,
            "filter_stats": filter_stats,
            "filtered_data": filtered_data,
            "message": f"Filtered data: {original_shape[0]} -> {final_shape[0]} rows ({filter_percentage:.1f}% filtered)"
        }
        
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "error_type": type(e).__name__,
            "traceback": traceback.format_exc()
        }


def advanced_filter(file_path: str, query_string: str, output_file: Optional[str] = None) -> dict:
    """
    Filter data using pandas query string.
    
    Args:
        file_path: Path to the data file
        query_string: Pandas query string
        output_file: Optional output file path
    
    Returns:
        Dictionary with filtering results
    """
    try:
        if not os.path.exists(file_path):
            return {
                "success": False,
                "error": f"File not found: {file_path}",
                "error_type": "FileNotFoundError"
            }
        
        # Load data
        df = pd.read_csv(file_path)
        original_shape = df.shape
        
        # Apply query filter
        try:
            filtered_df = df.query(query_string)
        except Exception as e:
            return {
                "success": False,
                "error": f"Query error: {str(e)}",
                "error_type": "QueryError"
            }
        
        # Filter statistics
        final_shape = filtered_df.shape
        total_rows_filtered = original_shape[0] - final_shape[0]
        filter_percentage = (total_rows_filtered / original_shape[0]) * 100
        
        filter_stats = {
            "original_shape": original_shape,
            "final_shape": final_shape,
            "rows_filtered": total_rows_filtered,
            "filter_percentage": round(filter_percentage, 2),
            "query_string": query_string
        }
        
        # Save filtered data
        if output_file is None:
            output_file = file_path.replace('.csv', '_query_filtered.csv')
        
        filtered_df.to_csv(output_file, index=False)
        
        # Convert to JSON-serializable format (limit to first 100 rows)
        filtered_data = filtered_df.head(100).to_dict('records')
        
        return {
            "success": True,
            "file_path": file_path,
            "output_file": output_file,
            "filter_stats": filter_stats,
            "filtered_data": filtered_data,
            "message": f"Query filtered data: {original_shape[0]} -> {final_shape[0]} rows ({filter_percentage:.1f}% filtered)"
        }
        
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "error_type": type(e).__name__,
            "traceback": traceback.format_exc()
        }


def sample_data(file_path: str, sample_size: int, method: str = "random",
                output_file: Optional[str] = None) -> dict:
    """
    Sample data from a dataset.
    
    Args:
        file_path: Path to the data file
        sample_size: Number of samples to extract
        method: Sampling method (random, first, last, systematic)
        output_file: Optional output file path
    
    Returns:
        Dictionary with sampling results
    """
    try:
        if not os.path.exists(file_path):
            return {
                "success": False,
                "error": f"File not found: {file_path}",
                "error_type": "FileNotFoundError"
            }
        
        # Load data
        df = pd.read_csv(file_path)
        original_shape = df.shape
        
        if sample_size > len(df):
            # If requested sample size is larger than dataset, return all data
            sampled_df = df.copy()
            sample_size = len(df)
        elif len(df) == 0:
            return {
                "success": False,
                "error": "Cannot sample from empty dataset",
                "error_type": "ValueError"
            }
        
        # Apply sampling method
        if method == "random":
            sampled_df = df.sample(n=sample_size, random_state=42)
        elif method == "first":
            sampled_df = df.head(sample_size)
        elif method == "last":
            sampled_df = df.tail(sample_size)
        elif method == "systematic":
            # Systematic sampling
            step = len(df) // sample_size
            indices = list(range(0, len(df), step))[:sample_size]
            sampled_df = df.iloc[indices]
        else:
            return {
                "success": False,
                "error": f"Unknown sampling method: {method}",
                "error_type": "ValueError"
            }
        
        # Sampling statistics
        final_shape = sampled_df.shape
        sample_percentage = (sample_size / original_shape[0]) * 100
        
        sample_stats = {
            "original_shape": original_shape,
            "sample_shape": final_shape,
            "sample_size": sample_size,
            "sample_percentage": round(sample_percentage, 2),
            "sampling_method": method
        }
        
        # Save sampled data
        if output_file is None:
            output_file = file_path.replace('.csv', f'_sample_{method}.csv')
        
        sampled_df.to_csv(output_file, index=False)
        
        # Convert to JSON-serializable format
        sampled_data = sampled_df.to_dict('records')
        
        return {
            "success": True,
            "file_path": file_path,
            "output_file": output_file,
            "sample_stats": sample_stats,
            "sampled_data": sampled_data,
            "message": f"Sampled {sample_size} rows using {method} method ({sample_percentage:.1f}% of data)"
        }
        
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "error_type": type(e).__name__,
            "traceback": traceback.format_exc()
        }
