#!/usr/bin/env python3
"""
Plot MCP Server with comprehensive data visualization capabilities.
Provides plotting functionality for CSV, Excel, and other data formats using
pandas and matplotlib.
"""

import os
from typing import Annotated, Any, Literal, TypedDict, cast

from fastmcp import FastMCP
from fastmcp.exceptions import ToolError
from fastmcp.prompts import Message
from fastmcp.tools import ToolResult
from fastmcp.utilities.types import Image
from dotenv import load_dotenv
from pydantic import Field, TypeAdapter
import logging
from .implementation.plot_capabilities import (
    create_line_plot,
    create_bar_plot,
    create_scatter_plot,
    create_histogram,
    create_heatmap,
    create_timeseries_plot,
    get_data_info,
    build_preview_png,
)


# --- Structured result shapes (drive real MCP outputSchema declarations) ----


class LinePlotResult(TypedDict):
    """Structured result for a successful line plot."""

    status: Literal["success"]
    plot_type: Literal["line"]
    output_path: str
    x_column: str
    y_column: str
    title: str
    data_points: int


class BarPlotResult(TypedDict):
    """Structured result for a successful bar plot."""

    status: Literal["success"]
    plot_type: Literal["bar"]
    output_path: str
    x_column: str
    y_column: str
    title: str
    data_points: int
    aggregated: bool


class ScatterPlotResult(TypedDict):
    """Structured result for a successful scatter plot."""

    status: Literal["success"]
    plot_type: Literal["scatter"]
    output_path: str
    x_column: str
    y_column: str
    title: str
    data_points: int


class HistogramResult(TypedDict):
    """Structured result for a successful histogram."""

    status: Literal["success"]
    plot_type: Literal["histogram"]
    output_path: str
    column: str
    bins: int
    title: str
    data_points: int


class HeatmapResult(TypedDict):
    """Structured result for a successful correlation heatmap."""

    status: Literal["success"]
    plot_type: Literal["heatmap"]
    output_path: str
    title: str
    data_points: int
    numeric_columns: list[str]


class TimeseriesXAxis(TypedDict):
    """Inferred x-axis metadata for a time-series plot."""

    kind: Literal[
        "epoch_milliseconds",
        "epoch_seconds",
        "datetime",
        "numeric",
        "categorical",
        "row_index",
    ]
    label: str
    parse_success_ratio: float


class TimeseriesPlotResult(TypedDict):
    """Structured result for a successful multi-series time-series plot."""

    status: Literal["success"]
    plot_type: Literal["timeseries"]
    output_path: str
    x_column: str
    x_axis: TimeseriesXAxis
    y_columns: list[str]
    title: str
    data_points: int


class DataInfoResult(TypedDict):
    """Structured result describing a CSV/Excel file's schema and contents."""

    status: Literal["success"]
    file_path: str
    shape: tuple[int, int]
    columns: list[str]
    dtypes: dict[str, str]
    null_counts: dict[str, int]
    memory_usage: int
    head: dict[str, Any]


def _plot_tool_result(structured: dict[str, Any]) -> ToolResult:
    """Wrap a plot capability's structured result with a bounded PNG preview.

    Every image-producing plot tool returns both a rendered MCP
    ``ImageContent`` block (a downscaled preview, bounded to ~800px wide so
    the wire payload stays small) and the unmodified structured dict —
    ``output_path`` in that dict still points at the full-resolution file on
    disk; nothing about the saved file changes.
    """
    preview_bytes = build_preview_png(structured["output_path"])
    return ToolResult(
        content=[Image(data=preview_bytes, format="png")],
        structured_content=structured,
    )


# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

# Initialize MCP server
mcp: FastMCP = FastMCP(
    "plot",
    instructions=(
        "Creates data visualizations using matplotlib. "
        "Generate line plots, bar charts, scatter plots, histograms, heatmaps, and "
        "multi-series time-series line charts from data. Use plot_timeseries to plot "
        "one or more y columns against an auto-detected time, numeric, or categorical "
        "x axis. Every plot tool saves the full-resolution image to output_path and "
        "also returns a bounded PNG preview inline in the response for immediate viewing."
    ),
)


@mcp.tool(
    name="line_plot",
    title="Line Plot",
    description="Create a line plot from CSV or Excel data with customizable styling.",
    annotations={
        "readOnlyHint": False,
        "destructiveHint": True,
        "idempotentHint": True,
    },
    tags={"plot", "line-chart", "visualization"},
    output_schema=TypeAdapter(LinePlotResult).json_schema(mode="serialization"),
)
async def line_plot_tool(
    file_path: str,
    x_column: str,
    y_column: str,
    title: str = "Line Plot",
    output_path: str = "line_plot.png",
) -> ToolResult:
    """
    Create a line plot from data file with comprehensive visualization options.

    Args:
        file_path: Absolute path to CSV or Excel file containing the data
        x_column: Column name for x-axis data (must exist in the dataset)
        y_column: Column name for y-axis data (must exist in the dataset)
        title: Custom title for the plot (supports LaTeX formatting)
        output_path: Absolute path where the plot image will be saved (supports PNG, PDF, SVG)

    Returns:
        A result carrying both a rendered PNG preview (bounded to ~800px
        wide) and a structured dict: status, plot_type, output_path (the
        full-resolution file on disk), x_column, y_column, title, and
        data_points.
    """
    logger.info(f"Creating line plot from {file_path}")
    result = create_line_plot(file_path, x_column, y_column, title, output_path)
    if result.get("status") == "error":
        raise ToolError(result["error"])
    return _plot_tool_result(result)


@mcp.tool(
    name="bar_plot",
    title="Bar Plot",
    description="Create a bar chart from CSV or Excel data with categorical grouping.",
    annotations={
        "readOnlyHint": False,
        "destructiveHint": True,
        "idempotentHint": True,
    },
    tags={"plot", "bar-chart", "visualization"},
    output_schema=TypeAdapter(BarPlotResult).json_schema(mode="serialization"),
)
async def bar_plot_tool(
    file_path: str,
    x_column: str,
    y_column: str,
    title: str = "Bar Plot",
    output_path: str = "bar_plot.png",
) -> ToolResult:
    """
    Create a bar plot from data file with comprehensive customization options.

    Args:
        file_path: Absolute path to CSV or Excel file containing the data
        x_column: Column name for x-axis categories (categorical data)
        y_column: Column name for y-axis values (numerical data)
        title: Custom title for the plot (supports LaTeX formatting)
        output_path: Absolute path where the plot image will be saved (supports PNG, PDF, SVG)

    Returns:
        A result carrying both a rendered PNG preview (bounded to ~800px
        wide) and a structured dict: status, plot_type, output_path (the
        full-resolution file on disk), x_column, y_column, title,
        data_points, and whether the bars were aggregated by mean.
    """
    logger.info(f"Creating bar plot from {file_path}")
    result = create_bar_plot(file_path, x_column, y_column, title, output_path)
    if result.get("status") == "error":
        raise ToolError(result["error"])
    return _plot_tool_result(result)


@mcp.tool(
    name="scatter_plot",
    title="Scatter Plot",
    description="Create a scatter plot from CSV or Excel data for correlation analysis.",
    annotations={
        "readOnlyHint": False,
        "destructiveHint": True,
        "idempotentHint": True,
    },
    tags={"plot", "scatter-plot", "visualization"},
    output_schema=TypeAdapter(ScatterPlotResult).json_schema(mode="serialization"),
)
async def scatter_plot_tool(
    file_path: str,
    x_column: str,
    y_column: str,
    title: str = "Scatter Plot",
    output_path: str = "scatter_plot.png",
) -> ToolResult:
    """
    Create a scatter plot from data file with advanced correlation analysis.

    Args:
        file_path: Absolute path to CSV or Excel file containing the data
        x_column: Column name for x-axis data (numerical data for correlation analysis)
        y_column: Column name for y-axis data (numerical data for correlation analysis)
        title: Custom title for the plot (supports LaTeX formatting)
        output_path: Absolute path where the plot image will be saved (supports PNG, PDF, SVG)

    Returns:
        A result carrying both a rendered PNG preview (bounded to ~800px
        wide) and a structured dict: status, plot_type, output_path (the
        full-resolution file on disk), x_column, y_column, title, and
        data_points.
    """
    logger.info(f"Creating scatter plot from {file_path}")
    result = create_scatter_plot(file_path, x_column, y_column, title, output_path)
    if result.get("status") == "error":
        raise ToolError(result["error"])
    return _plot_tool_result(result)


@mcp.tool(
    name="histogram_plot",
    title="Histogram",
    description="Create a histogram from CSV or Excel data showing value distribution.",
    annotations={
        "readOnlyHint": False,
        "destructiveHint": True,
        "idempotentHint": True,
    },
    tags={"plot", "histogram", "visualization"},
    output_schema=TypeAdapter(HistogramResult).json_schema(mode="serialization"),
)
async def histogram_plot_tool(
    file_path: str,
    column: str,
    bins: int = 30,
    title: str = "Histogram",
    output_path: str = "histogram.png",
) -> ToolResult:
    """
    Create a histogram from data file with advanced statistical analysis.

    Args:
        file_path: Absolute path to CSV or Excel file containing the data
        column: Column name for histogram generation (numerical data)
        bins: Number of bins for histogram (affects granularity of distribution)
        title: Custom title for the plot (supports LaTeX formatting)
        output_path: Absolute path where the plot image will be saved (supports PNG, PDF, SVG)

    Returns:
        A result carrying both a rendered PNG preview (bounded to ~800px
        wide) and a structured dict: status, plot_type, output_path (the
        full-resolution file on disk), column, bins, title, and data_points.
    """
    logger.info(f"Creating histogram from {file_path}")
    result = create_histogram(file_path, column, bins, title, output_path)
    if result.get("status") == "error":
        raise ToolError(result["error"])
    return _plot_tool_result(result)


@mcp.tool(
    name="heatmap_plot",
    title="Heatmap",
    description="Create a correlation heatmap from numeric columns in CSV or Excel data.",
    annotations={
        "readOnlyHint": False,
        "destructiveHint": True,
        "idempotentHint": True,
    },
    tags={"plot", "heatmap", "visualization"},
    output_schema=TypeAdapter(HeatmapResult).json_schema(mode="serialization"),
)
async def heatmap_plot_tool(
    file_path: str, title: str = "Heatmap", output_path: str = "heatmap.png"
) -> ToolResult:
    """
    Create a heatmap from data file with advanced correlation visualization.

    Args:
        file_path: Absolute path to CSV or Excel file containing numerical data
        title: Custom title for the plot (supports LaTeX formatting)
        output_path: Absolute path where the plot image will be saved (supports PNG, PDF, SVG)

    Returns:
        A result carrying both a rendered PNG preview (bounded to ~800px
        wide) and a structured dict: status, plot_type, output_path (the
        full-resolution file on disk), title, data_points, and the numeric
        columns included in the correlation matrix.
    """
    logger.info(f"Creating heatmap from {file_path}")
    result = create_heatmap(file_path, title, output_path)
    if result.get("status") == "error":
        raise ToolError(result["error"])
    return _plot_tool_result(result)


@mcp.tool(
    name="plot_timeseries",
    title="Timeseries Plot",
    description="Create a multi-series line chart PNG from one or more y columns of a CSV or Excel file, auto-detecting a time, numeric, or categorical x axis.",
    annotations={
        "readOnlyHint": False,
        "destructiveHint": True,
        "idempotentHint": True,
    },
    tags={"plot", "line-chart", "timeseries", "visualization"},
    output_schema=TypeAdapter(TimeseriesPlotResult).json_schema(mode="serialization"),
)
async def plot_timeseries(
    data_path: str,
    x_column: str,
    y_columns: Annotated[
        list[str] | str,
        Field(
            description="One or more numeric y columns: a list, or a comma-separated string such as 'temp,pressure'."
        ),
    ],
    output_path: str = "timeseries.png",
    title: str | None = None,
    max_rows: int = 2000,
) -> ToolResult:
    """
    Create a time-series line plot from one or more columns of a data file.

    The x-axis type is inferred automatically and is fully domain-neutral:
    epoch-millisecond/second integers and date strings render as a time axis,
    plain numbers as a numeric axis, and anything else falls back to a
    categorical row index. Multiple y columns are drawn as separate labeled
    lines on shared axes.

    Args:
        data_path: Absolute path to a CSV or Excel file containing the data
        x_column: Column name for the x-axis (must exist in the dataset)
        y_columns: One or more numeric y columns to plot, as a list or a
            comma-separated string (each column must exist in the dataset)
        output_path: Absolute path where the plot image will be saved (supports PNG, PDF, SVG)
        title: Custom title for the plot (defaults to the file name)
        max_rows: Maximum number of leading rows to read and plot

    Returns:
        A result carrying both a rendered PNG preview (bounded to ~800px
        wide) and a structured dict: status, plot_type, output_path (the
        full-resolution file on disk), x_column, the inferred x_axis (kind,
        label, parse_success_ratio), the resolved y_columns, title, and
        data_points.
    """
    logger.info(f"Creating timeseries plot from {data_path}")
    result = create_timeseries_plot(
        data_path, x_column, y_columns, title, output_path, max_rows
    )
    if result.get("status") == "error":
        raise ToolError(result["error"])
    return _plot_tool_result(result)


@mcp.tool(
    name="data_info",
    title="Describe Data",
    description="Get schema, column types, and summary statistics for a CSV or Excel file.",
    annotations={
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
    },
    tags={"data", "analysis", "visualization"},
)
async def data_info_tool(file_path: str) -> DataInfoResult:
    """
    Get comprehensive data file information with detailed analysis.

    Args:
        file_path: Absolute path to CSV or Excel file

    Returns:
        Dictionary containing status, file_path, shape (rows, columns),
        columns, dtypes, null_counts, memory_usage, and a JSON preview of the
        first rows (head).
    """
    logger.info(f"Getting data info for {file_path}")
    result = get_data_info(file_path)
    if result.get("status") == "error":
        raise ToolError(result["error"])
    return cast(DataInfoResult, result)


@mcp.resource("plot://styles")
def available_styles() -> dict:
    """Available matplotlib plot styles and color palettes."""
    import matplotlib.pyplot as plt

    return {
        "styles": plt.style.available,
        "default_format": "png",
        "supported_formats": ["png", "svg", "pdf", "jpg"],
    }


@mcp.prompt()
def create_visualization(data_description: str) -> list[Message]:
    """Guided workflow for creating a data visualization."""
    return [
        Message(
            f"I need to visualize the following data: {data_description}. "
            "Suggest the best chart type, create the plot with appropriate labels and styling, "
            "and save it to a file."
        ),
    ]


def main() -> None:
    """Main entry point for the Plot MCP server."""
    import argparse

    parser = argparse.ArgumentParser(description="Plot MCP Server")
    parser.add_argument("--transport", choices=["stdio", "http"], default=None)
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--port", type=int, default=8000)
    args = parser.parse_args()
    transport = args.transport or os.getenv("MCP_TRANSPORT", "stdio")
    if transport == "http":
        mcp.run(transport="http", host=args.host, port=args.port)
    else:
        mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
