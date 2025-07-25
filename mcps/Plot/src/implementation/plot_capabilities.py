"""
Plot capabilities implementation for data visualization.
"""

import os
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
import numpy as np
from typing import Dict, Any
import logging

logger = logging.getLogger(__name__)


def load_data(file_path: str) -> pd.DataFrame:
    """
    Load data from CSV or Excel file.

    Args:
        file_path: Path to the data file

    Returns:
        pandas DataFrame with the data
    """
    try:
        if file_path.endswith(".csv"):
            return pd.read_csv(file_path)
        elif file_path.endswith((".xlsx", ".xls")):
            return pd.read_excel(file_path)
        else:
            raise ValueError(f"Unsupported file format: {file_path}")
    except Exception as e:
        logger.error(f"Error loading data from {file_path}: {e}")
        raise


def get_data_info(file_path: str) -> Dict[str, Any]:
    """
    Get information about the data file.

    Args:
        file_path: Path to the data file

    Returns:
        Dictionary containing data information
    """
    try:
        df = load_data(file_path)

        return {
            "status": "success",
            "file_path": file_path,
            "shape": df.shape,
            "columns": df.columns.tolist(),
            "dtypes": df.dtypes.to_dict(),
            "null_counts": df.isnull().sum().to_dict(),
            "memory_usage": df.memory_usage(deep=True).sum(),
            "head": df.head().to_dict(),
        }
    except Exception as e:
        logger.error(f"Error getting data info: {e}")
        return {"status": "error", "error": str(e)}


def create_line_plot(
    file_path: str,
    x_column: str,
    y_column: str,
    title: str = "Line Plot",
    output_path: str = "line_plot.png",
) -> Dict[str, Any]:
    """
    Create a line plot from data.

    Args:
        file_path: Path to the data file
        x_column: Column name for x-axis
        y_column: Column name for y-axis
        title: Plot title
        output_path: Output image file path

    Returns:
        Dictionary with plot information
    """
    try:
        df = load_data(file_path)

        if x_column not in df.columns:
            raise ValueError(f"Column '{x_column}' not found in data")
        if y_column not in df.columns:
            raise ValueError(f"Column '{y_column}' not found in data")

        plt.figure(figsize=(10, 6))
        plt.plot(df[x_column], df[y_column], marker="o", linewidth=2, markersize=6)
        plt.title(title, fontsize=14, fontweight="bold")
        plt.xlabel(x_column, fontsize=12)
        plt.ylabel(y_column, fontsize=12)
        plt.grid(True, alpha=0.3)
        plt.tight_layout()

        # Create output directory if it doesn't exist
        os.makedirs(
            os.path.dirname(output_path) if os.path.dirname(output_path) else ".",
            exist_ok=True,
        )

        plt.savefig(output_path, dpi=300, bbox_inches="tight")
        plt.close()

        return {
            "status": "success",
            "plot_type": "line",
            "output_path": output_path,
            "x_column": x_column,
            "y_column": y_column,
            "title": title,
            "data_points": len(df),
        }
    except Exception as e:
        logger.error(f"Error creating line plot: {e}")
        return {"status": "error", "error": str(e)}


def create_bar_plot(
    file_path: str,
    x_column: str,
    y_column: str,
    title: str = "Bar Plot",
    output_path: str = "bar_plot.png",
) -> Dict[str, Any]:
    """
    Create a bar plot from data.

    Args:
        file_path: Path to the data file
        x_column: Column name for x-axis
        y_column: Column name for y-axis
        title: Plot title
        output_path: Output image file path

    Returns:
        Dictionary with plot information
    """
    try:
        df = load_data(file_path)

        if x_column not in df.columns:
            raise ValueError(f"Column '{x_column}' not found in data")
        if y_column not in df.columns:
            raise ValueError(f"Column '{y_column}' not found in data")

        # Clean the data by removing NaN values
        df_clean = df.dropna(subset=[x_column, y_column])

        # If x_column is categorical and y_column is numeric, aggregate by mean
        if df_clean[x_column].dtype == "object" and pd.api.types.is_numeric_dtype(
            df_clean[y_column]
        ):
            # Group by x_column and take mean of y_column
            grouped_data = df_clean.groupby(x_column)[y_column].mean().reset_index()

            # Limit to top 20 categories for better visualization
            if len(grouped_data) > 20:
                grouped_data = grouped_data.nlargest(20, y_column)

            x_values = grouped_data[x_column]
            y_values = grouped_data[y_column]
        else:
            # Use data as-is if it's already suitable for bar plotting
            x_values = df_clean[x_column]
            y_values = df_clean[y_column]

        plt.figure(figsize=(12, 6))
        plt.bar(x_values, y_values, color="skyblue", edgecolor="navy", alpha=0.7)
        plt.title(title, fontsize=14, fontweight="bold")
        plt.xlabel(x_column, fontsize=12)
        plt.ylabel(y_column, fontsize=12)
        plt.grid(True, alpha=0.3, axis="y")

        # Rotate x-axis labels if they're text and long
        if df_clean[x_column].dtype == "object":
            plt.xticks(rotation=45, ha="right")

        plt.tight_layout()

        # Create output directory if it doesn't exist
        os.makedirs(
            os.path.dirname(output_path) if os.path.dirname(output_path) else ".",
            exist_ok=True,
        )

        plt.savefig(output_path, dpi=300, bbox_inches="tight")
        plt.close()

        return {
            "status": "success",
            "plot_type": "bar",
            "output_path": output_path,
            "x_column": x_column,
            "y_column": y_column,
            "title": title,
            "data_points": len(df_clean),
            "aggregated": df_clean[x_column].dtype == "object"
            and pd.api.types.is_numeric_dtype(df_clean[y_column]),
        }
    except Exception as e:
        logger.error(f"Error creating bar plot: {e}")
        return {"status": "error", "error": str(e)}


def create_scatter_plot(
    file_path: str,
    x_column: str,
    y_column: str,
    title: str = "Scatter Plot",
    output_path: str = "scatter_plot.png",
) -> Dict[str, Any]:
    """
    Create a scatter plot from data.

    Args:
        file_path: Path to the data file
        x_column: Column name for x-axis
        y_column: Column name for y-axis
        title: Plot title
        output_path: Output image file path

    Returns:
        Dictionary with plot information
    """
    try:
        df = load_data(file_path)

        if x_column not in df.columns:
            raise ValueError(f"Column '{x_column}' not found in data")
        if y_column not in df.columns:
            raise ValueError(f"Column '{y_column}' not found in data")

        plt.figure(figsize=(10, 6))
        plt.scatter(df[x_column], df[y_column], alpha=0.6, s=60, color="darkblue")
        plt.title(title, fontsize=14, fontweight="bold")
        plt.xlabel(x_column, fontsize=12)
        plt.ylabel(y_column, fontsize=12)
        plt.grid(True, alpha=0.3)
        plt.tight_layout()

        # Create output directory if it doesn't exist
        os.makedirs(
            os.path.dirname(output_path) if os.path.dirname(output_path) else ".",
            exist_ok=True,
        )

        plt.savefig(output_path, dpi=300, bbox_inches="tight")
        plt.close()

        return {
            "status": "success",
            "plot_type": "scatter",
            "output_path": output_path,
            "x_column": x_column,
            "y_column": y_column,
            "title": title,
            "data_points": len(df),
        }
    except Exception as e:
        logger.error(f"Error creating scatter plot: {e}")
        return {"status": "error", "error": str(e)}


def create_histogram(
    file_path: str,
    column: str,
    bins: int = 30,
    title: str = "Histogram",
    output_path: str = "histogram.png",
) -> Dict[str, Any]:
    """
    Create a histogram from data.

    Args:
        file_path: Path to the data file
        column: Column name for histogram
        bins: Number of bins
        title: Plot title
        output_path: Output image file path

    Returns:
        Dictionary with plot information
    """
    try:
        df = load_data(file_path)

        if column not in df.columns:
            raise ValueError(f"Column '{column}' not found in data")

        plt.figure(figsize=(10, 6))
        plt.hist(
            df[column], bins=bins, color="lightcoral", edgecolor="black", alpha=0.7
        )
        plt.title(title, fontsize=14, fontweight="bold")
        plt.xlabel(column, fontsize=12)
        plt.ylabel("Frequency", fontsize=12)
        plt.grid(True, alpha=0.3, axis="y")
        plt.tight_layout()

        # Create output directory if it doesn't exist
        os.makedirs(
            os.path.dirname(output_path) if os.path.dirname(output_path) else ".",
            exist_ok=True,
        )

        plt.savefig(output_path, dpi=300, bbox_inches="tight")
        plt.close()

        return {
            "status": "success",
            "plot_type": "histogram",
            "output_path": output_path,
            "column": column,
            "bins": bins,
            "title": title,
            "data_points": len(df),
        }
    except Exception as e:
        logger.error(f"Error creating histogram: {e}")
        return {"status": "error", "error": str(e)}


def create_heatmap(
    file_path: str, title: str = "Heatmap", output_path: str = "heatmap.png"
) -> Dict[str, Any]:
    """
    Create a heatmap from data.

    Args:
        file_path: Path to the data file
        title: Plot title
        output_path: Output image file path

    Returns:
        Dictionary with plot information
    """
    try:
        df = load_data(file_path)

        # Select only numeric columns for correlation heatmap
        numeric_df = df.select_dtypes(include=[np.number])

        if numeric_df.empty:
            raise ValueError("No numeric columns found for heatmap")

        # Calculate correlation matrix
        corr_matrix = numeric_df.corr()

        plt.figure(figsize=(10, 8))
        sns.heatmap(
            corr_matrix,
            annot=True,
            cmap="coolwarm",
            center=0,
            square=True,
            linewidths=0.5,
        )
        plt.title(title, fontsize=14, fontweight="bold")
        plt.tight_layout()

        # Create output directory if it doesn't exist
        os.makedirs(
            os.path.dirname(output_path) if os.path.dirname(output_path) else ".",
            exist_ok=True,
        )

        plt.savefig(output_path, dpi=300, bbox_inches="tight")
        plt.close()

        return {
            "status": "success",
            "plot_type": "heatmap",
            "output_path": output_path,
            "title": title,
            "data_points": len(df),
            "numeric_columns": numeric_df.columns.tolist(),
        }
    except Exception as e:
        logger.error(f"Error creating heatmap: {e}")
        return {"status": "error", "error": str(e)}
