#!/usr/bin/env python3
"""
Plot MCP Server with comprehensive data visualization capabilities.
Provides plotting functionality for CSV, Excel, and other data formats using
pandas and matplotlib.
"""

import os
from typing import Annotated

from fastmcp import FastMCP
from fastmcp.exceptions import ToolError
from fastmcp.prompts import Message
from dotenv import load_dotenv
from pydantic import Field
import logging
from .implementation.plot_capabilities import (
    create_line_plot,
    create_bar_plot,
    create_scatter_plot,
    create_histogram,
    create_heatmap,
    create_timeseries_plot,
    get_data_info,
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
        "x axis. All plots are saved to files."
    ),
)


@mcp.tool(
    name="line_plot",
    description="Create a line plot from CSV or Excel data with customizable styling.",
    annotations={
        "readOnlyHint": False,
        "destructiveHint": True,
        "idempotentHint": True,
    },
    tags={"plot", "line-chart", "visualization"},
)
async def line_plot_tool(
    file_path: str,
    x_column: str,
    y_column: str,
    title: str = "Line Plot",
    output_path: str = "line_plot.png",
) -> dict:
    """
    Create a line plot from data file with comprehensive visualization options.

    Args:
        file_path: Absolute path to CSV or Excel file containing the data
        x_column: Column name for x-axis data (must exist in the dataset)
        y_column: Column name for y-axis data (must exist in the dataset)
        title: Custom title for the plot (supports LaTeX formatting)
        output_path: Absolute path where the plot image will be saved (supports PNG, PDF, SVG)

    Returns:
        Dictionary containing:
        - plot_info: Details about the generated plot including dimensions and format
        - data_summary: Statistical summary of the plotted data
        - file_details: Information about the output file size and location
        - visualization_stats: Metrics about data points and trends
    """
    logger.info(f"Creating line plot from {file_path}")
    result = create_line_plot(file_path, x_column, y_column, title, output_path)
    if result.get("status") == "error":
        raise ToolError(result["error"])
    return result


@mcp.tool(
    name="bar_plot",
    description="Create a bar chart from CSV or Excel data with categorical grouping.",
    annotations={
        "readOnlyHint": False,
        "destructiveHint": True,
        "idempotentHint": True,
    },
    tags={"plot", "bar-chart", "visualization"},
)
async def bar_plot_tool(
    file_path: str,
    x_column: str,
    y_column: str,
    title: str = "Bar Plot",
    output_path: str = "bar_plot.png",
) -> dict:
    """
    Create a bar plot from data file with comprehensive customization options.

    Args:
        file_path: Absolute path to CSV or Excel file containing the data
        x_column: Column name for x-axis categories (categorical data)
        y_column: Column name for y-axis values (numerical data)
        title: Custom title for the plot (supports LaTeX formatting)
        output_path: Absolute path where the plot image will be saved (supports PNG, PDF, SVG)

    Returns:
        Dictionary containing:
        - plot_info: Details about the generated bar chart including bar count and styling
        - data_summary: Statistical summary of the categorical and numerical data
        - file_details: Information about the output file size and location
        - visualization_stats: Metrics about data distribution and categories
    """
    logger.info(f"Creating bar plot from {file_path}")
    result = create_bar_plot(file_path, x_column, y_column, title, output_path)
    if result.get("status") == "error":
        raise ToolError(result["error"])
    return result


@mcp.tool(
    name="scatter_plot",
    description="Create a scatter plot from CSV or Excel data for correlation analysis.",
    annotations={
        "readOnlyHint": False,
        "destructiveHint": True,
        "idempotentHint": True,
    },
    tags={"plot", "scatter-plot", "visualization"},
)
async def scatter_plot_tool(
    file_path: str,
    x_column: str,
    y_column: str,
    title: str = "Scatter Plot",
    output_path: str = "scatter_plot.png",
) -> dict:
    """
    Create a scatter plot from data file with advanced correlation analysis.

    Args:
        file_path: Absolute path to CSV or Excel file containing the data
        x_column: Column name for x-axis data (numerical data for correlation analysis)
        y_column: Column name for y-axis data (numerical data for correlation analysis)
        title: Custom title for the plot (supports LaTeX formatting)
        output_path: Absolute path where the plot image will be saved (supports PNG, PDF, SVG)

    Returns:
        Dictionary containing:
        - plot_info: Details about the generated scatter plot including point count and styling
        - correlation_stats: Statistical correlation metrics and trend analysis
        - data_summary: Statistical summary of both x and y variables
        - file_details: Information about the output file size and location
    """
    logger.info(f"Creating scatter plot from {file_path}")
    result = create_scatter_plot(file_path, x_column, y_column, title, output_path)
    if result.get("status") == "error":
        raise ToolError(result["error"])
    return result


@mcp.tool(
    name="histogram_plot",
    description="Create a histogram from CSV or Excel data showing value distribution.",
    annotations={
        "readOnlyHint": False,
        "destructiveHint": True,
        "idempotentHint": True,
    },
    tags={"plot", "histogram", "visualization"},
)
async def histogram_plot_tool(
    file_path: str,
    column: str,
    bins: int = 30,
    title: str = "Histogram",
    output_path: str = "histogram.png",
) -> dict:
    """
    Create a histogram from data file with advanced statistical analysis.

    Args:
        file_path: Absolute path to CSV or Excel file containing the data
        column: Column name for histogram generation (numerical data)
        bins: Number of bins for histogram (affects granularity of distribution)
        title: Custom title for the plot (supports LaTeX formatting)
        output_path: Absolute path where the plot image will be saved (supports PNG, PDF, SVG)

    Returns:
        Dictionary containing:
        - plot_info: Details about the generated histogram including bin information
        - distribution_stats: Statistical metrics including mean, median, mode, and standard deviation
        - data_summary: Comprehensive summary of the data distribution
        - file_details: Information about the output file size and location
    """
    logger.info(f"Creating histogram from {file_path}")
    result = create_histogram(file_path, column, bins, title, output_path)
    if result.get("status") == "error":
        raise ToolError(result["error"])
    return result


@mcp.tool(
    name="heatmap_plot",
    description="Create a correlation heatmap from numeric columns in CSV or Excel data.",
    annotations={
        "readOnlyHint": False,
        "destructiveHint": True,
        "idempotentHint": True,
    },
    tags={"plot", "heatmap", "visualization"},
)
async def heatmap_plot_tool(
    file_path: str, title: str = "Heatmap", output_path: str = "heatmap.png"
) -> dict:
    """
    Create a heatmap from data file with advanced correlation visualization.

    Args:
        file_path: Absolute path to CSV or Excel file containing numerical data
        title: Custom title for the plot (supports LaTeX formatting)
        output_path: Absolute path where the plot image will be saved (supports PNG, PDF, SVG)

    Returns:
        Dictionary containing:
        - plot_info: Details about the generated heatmap including matrix dimensions
        - correlation_matrix: Full correlation matrix with statistical significance
        - data_summary: Statistical summary of all numerical variables
        - file_details: Information about the output file size and location
    """
    logger.info(f"Creating heatmap from {file_path}")
    result = create_heatmap(file_path, title, output_path)
    if result.get("status") == "error":
        raise ToolError(result["error"])
    return result


@mcp.tool(
    name="plot_timeseries",
    description="Create a multi-series line chart PNG from one or more y columns of a CSV or Excel file, auto-detecting a time, numeric, or categorical x axis.",
    annotations={
        "readOnlyHint": False,
        "destructiveHint": True,
        "idempotentHint": True,
    },
    tags={"plot", "line-chart", "timeseries", "visualization"},
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
) -> dict:
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
        Dictionary containing:
        - plot_info: Details about the generated plot including the resolved y columns
        - x_axis: The inferred x-axis kind, label, and parse-success ratio
        - data_summary: Number of data points plotted
        - file_details: Information about the output file location
    """
    logger.info(f"Creating timeseries plot from {data_path}")
    result = create_timeseries_plot(
        data_path, x_column, y_columns, title, output_path, max_rows
    )
    if result.get("status") == "error":
        raise ToolError(result["error"])
    return result


@mcp.tool(
    name="data_info",
    description="Get schema, column types, and summary statistics for a CSV or Excel file.",
    annotations={
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
    },
    tags={"data", "analysis", "visualization"},
)
async def data_info_tool(file_path: str) -> dict:
    """
    Get comprehensive data file information with detailed analysis.

    Args:
        file_path: Absolute path to CSV or Excel file

    Returns:
        Dictionary containing:
        - data_schema: Column names, data types, and null value analysis
        - data_quality: Missing values, duplicates, and data consistency metrics
        - statistical_summary: Basic statistics for numerical and categorical columns
        - visualization_recommendations: Suggested plot types based on data characteristics
    """
    logger.info(f"Getting data info for {file_path}")
    result = get_data_info(file_path)
    if result.get("status") == "error":
        raise ToolError(result["error"])
    return result


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
