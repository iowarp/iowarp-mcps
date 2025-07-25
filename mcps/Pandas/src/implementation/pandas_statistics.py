"""
Statistical analysis capabilities for comprehensive data analysis.
"""
import pandas as pd
import numpy as np
import os
from scipy import stats
from typing import Optional, List, Any, Dict
import traceback


def get_statistical_summary(file_path: str, columns: Optional[List[str]] = None,
                           include_distributions: bool = False) -> dict:
    """
    Generate comprehensive statistical summaries.
    
    Args:
        file_path: Path to the data file
        columns: Specific columns to analyze
        include_distributions: Whether to include distribution analysis
    
    Returns:
        Dictionary with statistical summaries
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
        
        if columns:
            df = df[columns]
        
        # Basic statistics
        basic_stats = df.describe(include='all').to_dict()
        
        # Additional statistics for numeric columns
        numeric_cols = df.select_dtypes(include=[np.number]).columns
        additional_stats = {}
        
        for col in numeric_cols:
            col_data = df[col].dropna()
            if len(col_data) > 0:
                additional_stats[col] = {
                    "variance": float(col_data.var()),
                    "skewness": float(col_data.skew()),
                    "kurtosis": float(col_data.kurtosis()),
                    "median_absolute_deviation": float((col_data - col_data.median()).abs().median()),
                    "interquartile_range": float(col_data.quantile(0.75) - col_data.quantile(0.25)),
                    "coefficient_of_variation": float(col_data.std() / col_data.mean()) if col_data.mean() != 0 else None
                }
                
                if include_distributions:
                    # Test for normality
                    if len(col_data) >= 8:  # Minimum sample size for Shapiro-Wilk
                        shapiro_stat, shapiro_p = stats.shapiro(col_data.sample(min(5000, len(col_data))))
                        additional_stats[col]["normality_test"] = {
                            "shapiro_wilk_statistic": float(shapiro_stat),
                            "shapiro_wilk_p_value": float(shapiro_p),
                            "is_normal": shapiro_p > 0.05
                        }
        
        # Categorical column analysis
        categorical_cols = df.select_dtypes(include=['object', 'category']).columns
        categorical_stats = {}
        
        for col in categorical_cols:
            col_data = df[col].dropna()
            if len(col_data) > 0:
                value_counts = col_data.value_counts()
                categorical_stats[col] = {
                    "unique_values": int(col_data.nunique()),
                    "most_frequent": str(value_counts.index[0]) if len(value_counts) > 0 else None,
                    "most_frequent_count": int(value_counts.iloc[0]) if len(value_counts) > 0 else 0,
                    "value_counts": value_counts.head(10).to_dict()
                }
        
        # Missing data analysis
        missing_data = {
            "total_missing": int(df.isnull().sum().sum()),
            "missing_by_column": df.isnull().sum().to_dict(),
            "missing_percentage": (df.isnull().sum() / len(df) * 100).to_dict()
        }
        
        return {
            "success": True,
            "file_path": file_path,
            "shape": df.shape,
            "basic_statistics": basic_stats,
            "additional_statistics": additional_stats,
            "categorical_statistics": categorical_stats,
            "missing_data": missing_data,
            "message": f"Statistical summary generated for {len(df.columns)} columns"
        }
        
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "error_type": type(e).__name__,
            "traceback": traceback.format_exc()
        }


def get_correlation_analysis(file_path: str, method: str = "pearson",
                           columns: Optional[List[str]] = None) -> dict:
    """
    Perform correlation analysis.
    
    Args:
        file_path: Path to the data file
        method: Correlation method (pearson, spearman, kendall)
        columns: Specific columns to analyze
    
    Returns:
        Dictionary with correlation results
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
        
        # Select numeric columns
        numeric_df = df.select_dtypes(include=[np.number])
        
        if columns:
            numeric_df = numeric_df[columns]
        
        if numeric_df.empty:
            return {
                "success": False,
                "error": "No numeric columns found for correlation analysis",
                "error_type": "ValueError"
            }
        
        # Calculate correlation matrix
        correlation_matrix = numeric_df.corr(method=method)
        
        # Find highly correlated pairs
        high_correlations = []
        for i in range(len(correlation_matrix.columns)):
            for j in range(i+1, len(correlation_matrix.columns)):
                corr_value = correlation_matrix.iloc[i, j]
                if abs(corr_value) > 0.7:  # High correlation threshold
                    high_correlations.append({
                        "variable1": correlation_matrix.columns[i],
                        "variable2": correlation_matrix.columns[j],
                        "correlation": float(corr_value),
                        "strength": "strong" if abs(corr_value) > 0.8 else "moderate"
                    })
        
        # Convert correlation matrix to dictionary
        correlation_dict = correlation_matrix.to_dict()
        
        return {
            "success": True,
            "file_path": file_path,
            "method": method,
            "correlation_matrix": correlation_dict,
            "high_correlations": high_correlations,
            "analyzed_columns": numeric_df.columns.tolist(),
            "message": f"Correlation analysis completed using {method} method"
        }
        
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "error_type": type(e).__name__,
            "traceback": traceback.format_exc()
        }
