"""
Plot capabilities implementation for data visualization.
"""

import json
import math
import os
from datetime import datetime, timezone
from typing import Any, Dict, List

import matplotlib.dates as mdates
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import seaborn as sns
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
            "dtypes": {column: str(dtype) for column, dtype in df.dtypes.items()},
            "null_counts": {
                column: int(count) for column, count in df.isnull().sum().items()
            },
            "memory_usage": int(df.memory_usage(deep=True).sum()),
            "head": json.loads(df.head().to_json()),
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


def _to_float(value: Any) -> float | None:
    """Best-effort float coercion that tolerates blanks and non-numeric text."""
    try:
        text = str(value).strip()
        if not text or text.lower() in {"nan", "none", "null"}:
            return None
        return float(text)
    except (TypeError, ValueError):
        return None


def _parse_datetime_text(value: Any) -> datetime | None:
    """Parse an ISO or common date string into a naive UTC datetime."""
    text = str(value or "").strip()
    if not text:
        return None
    normalized = text.replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(normalized)
        if parsed.tzinfo is not None:
            return parsed.astimezone(timezone.utc).replace(tzinfo=None)
        return parsed
    except ValueError:
        pass
    for fmt in ("%m/%d/%Y", "%Y/%m/%d", "%Y-%m-%d", "%m/%d/%Y %H:%M:%S"):
        try:
            return datetime.strptime(text, fmt)  # noqa: DTZ007
        except ValueError:
            continue
    return None


def _infer_x_axis(values: List[str]) -> Dict[str, Any]:
    """Infer plot-ready x values and trace metadata from a generic x column.

    Detects, in order: epoch-millisecond integers, epoch-second integers,
    parseable date/time strings, and finally falls back to a categorical row
    index. This is fully domain-neutral and makes no assumptions about the
    meaning of the data.

    Args:
        values: Raw string values from the chosen x column.

    Returns:
        Dictionary with the inferred ``kind``, plot-ready ``values``, an axis
        ``label``, the ``parse_success_ratio``, and (for categorical data) the
        original ``labels``.
    """
    if not values:
        return {
            "kind": "row_index",
            "values": [],
            "label": "row index",
            "parse_success_ratio": 0.0,
        }

    numeric: list[float | None] = [_to_float(value) for value in values]
    numeric_values = [v for v in numeric if v is not None and math.isfinite(v)]
    numeric_ratio = len(numeric_values) / len(values)
    if numeric_ratio >= 0.8 and numeric_values:
        median_abs = sorted(abs(v) for v in numeric_values)[len(numeric_values) // 2]
        if median_abs >= 1_000_000_000_000:
            datetimes = [
                datetime.fromtimestamp(v / 1000, timezone.utc).replace(tzinfo=None)
                if v is not None and math.isfinite(v)
                else None
                for v in numeric
            ]
            return {
                "kind": "epoch_milliseconds",
                "values": datetimes,
                "label": "time (UTC)",
                "parse_success_ratio": numeric_ratio,
            }
        if median_abs >= 1_000_000_000:
            datetimes = [
                datetime.fromtimestamp(v, timezone.utc).replace(tzinfo=None)
                if v is not None and math.isfinite(v)
                else None
                for v in numeric
            ]
            return {
                "kind": "epoch_seconds",
                "values": datetimes,
                "label": "time (UTC)",
                "parse_success_ratio": numeric_ratio,
            }
        return {
            "kind": "numeric",
            "values": [
                v if (v is not None and math.isfinite(v)) else None for v in numeric
            ],
            "label": "value",
            "parse_success_ratio": numeric_ratio,
        }

    parsed_datetimes = [_parse_datetime_text(value) for value in values]
    parsed_count = sum(value is not None for value in parsed_datetimes)
    parsed_ratio = parsed_count / len(values)
    if parsed_ratio >= 0.8 and parsed_count:
        return {
            "kind": "datetime",
            "values": parsed_datetimes,
            "label": "time",
            "parse_success_ratio": parsed_ratio,
        }

    return {
        "kind": "categorical",
        "values": list(range(len(values))),
        "labels": values,
        "label": "row index",
        "parse_success_ratio": max(numeric_ratio, parsed_ratio),
    }


def create_timeseries_plot(
    file_path: str,
    x_column: str,
    y_columns: List[str] | str,
    title: str | None = None,
    output_path: str = "timeseries.png",
    max_rows: int = 2000,
) -> Dict[str, Any]:
    """Create a multi-series line plot from one or more y columns of a data file.

    The x axis type is inferred automatically: epoch-millisecond/second
    integers and date strings are rendered as a time axis, plain numbers as a
    numeric axis, and anything else falls back to a categorical row index. This
    is domain-neutral and works with any tabular CSV/Excel input.

    Args:
        file_path: Path to a CSV or Excel data file.
        x_column: Column to use for the x axis.
        y_columns: One or more numeric y columns (a list, or a comma-separated
            string such as ``"temp,pressure"``).
        title: Optional plot title (defaults to the file name).
        output_path: Output image file path (PNG, PDF, or SVG).
        max_rows: Maximum number of leading rows to read and plot.

    Returns:
        Dictionary with plot information, or an ``{"status": "error"}`` payload.
    """
    try:
        if isinstance(y_columns, str):
            selected_y = [part.strip() for part in y_columns.split(",") if part.strip()]
        else:
            selected_y = [str(part).strip() for part in y_columns if str(part).strip()]
        if not selected_y:
            raise ValueError("At least one y column is required for a time-series plot")

        df = load_data(file_path)
        row_limit = max(1, int(max_rows))
        if len(df) > row_limit:
            df = df.head(row_limit)

        missing = [col for col in [x_column, *selected_y] if col not in df.columns]
        if missing:
            raise ValueError(
                f"Column(s) not found in data: {missing}. "
                f"Available columns: {df.columns.tolist()}"
            )

        x_raw = ["" if pd.isna(v) else str(v) for v in df[x_column].tolist()]
        x_axis = _infer_x_axis(x_raw)
        x_plot_values = x_axis["values"]
        valid_x = [value is not None for value in x_plot_values]

        series: Dict[str, list[float | None]] = {
            col: [_to_float(v) for v in df[col].tolist()] for col in selected_y
        }
        plotted = {
            col: vals
            for col, vals in series.items()
            if any(v is not None for v in vals)
        }
        if not plotted:
            raise ValueError(
                "None of the requested y columns contained numeric values in the scanned rows"
            )

        fig, ax = plt.subplots(figsize=(10, 4.8))
        for col, vals in plotted.items():
            xy = [
                (xv, val)
                for xv, val, ok in zip(x_plot_values, vals, valid_x, strict=False)
                if ok
            ]
            x_series = [item[0] for item in xy]
            y_series = [float("nan") if item[1] is None else item[1] for item in xy]
            ax.plot(x_series, y_series, linewidth=1.2, label=col)

        if x_axis["kind"] in {"epoch_milliseconds", "epoch_seconds", "datetime"}:
            locator = mdates.AutoDateLocator(minticks=4, maxticks=8)
            ax.xaxis.set_major_locator(locator)
            ax.xaxis.set_major_formatter(mdates.ConciseDateFormatter(locator))
            fig.autofmt_xdate(rotation=30, ha="right")
        elif x_axis["kind"] == "categorical":
            tick_count = min(8, len(x_raw))
            if tick_count:
                step = max(1, len(x_raw) // tick_count)
                tick_positions = list(range(0, len(x_raw), step))[:tick_count]
                tick_labels = x_axis.get("labels", x_raw)
                ax.set_xticks(tick_positions)
                ax.set_xticklabels(
                    [tick_labels[i] for i in tick_positions], rotation=35, ha="right"
                )

        ax.set_xlabel(f"{x_column} ({x_axis['label']})", fontsize=12)
        ax.set_ylabel(", ".join(plotted), fontsize=12)
        ax.set_title(
            title or os.path.basename(file_path), fontsize=14, fontweight="bold"
        )
        ax.grid(True, alpha=0.25)
        ax.legend(loc="best")
        fig.tight_layout()

        os.makedirs(
            os.path.dirname(output_path) if os.path.dirname(output_path) else ".",
            exist_ok=True,
        )
        fig.savefig(output_path, dpi=300, bbox_inches="tight")
        plt.close(fig)

        return {
            "status": "success",
            "plot_type": "timeseries",
            "output_path": output_path,
            "x_column": x_column,
            "x_axis": {
                "kind": x_axis["kind"],
                "label": x_axis["label"],
                "parse_success_ratio": x_axis["parse_success_ratio"],
            },
            "y_columns": sorted(plotted),
            "title": title or os.path.basename(file_path),
            "data_points": len(x_raw),
        }
    except Exception as e:
        logger.error(f"Error creating timeseries plot: {e}")
        return {"status": "error", "error": str(e)}
