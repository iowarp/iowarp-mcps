#!/usr/bin/env python3
"""
Plot MCP Server with comprehensive data visualization capabilities.
Provides plotting functionality for CSV, Excel, and other data formats using pandas and matplotlib.
"""
import os
import sys
import json
import argparse
from fastmcp import FastMCP
from dotenv import load_dotenv
import logging

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Add current directory to path for relative imports
sys.path.insert(0, os.path.dirname(__file__))

# Load environment variables
load_dotenv()

# Import implementation module directly
from implementation.plot_capabilities import (
    create_line_plot, create_bar_plot, create_scatter_plot, 
    create_histogram, create_heatmap, get_data_info
)

# Initialize MCP server
mcp = FastMCP("PlotServer")

@mcp.tool(
    name="line_plot",
    description="Create line plots from CSV or Excel data with customizable styling and formatting. Supports multiple data series, trend analysis, and time-series visualization with advanced customization options."
)
async def line_plot_tool(
    file_path: str,
    x_column: str,
    y_column: str,
    title: str = "Line Plot",
    output_path: str = "line_plot.png"
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
    return create_line_plot(file_path, x_column, y_column, title, output_path)

@mcp.tool(
    name="bar_plot",
    description="Create bar charts from CSV or Excel data with advanced styling and categorical data visualization. Supports grouped bars, stacked bars, and horizontal orientation with customizable colors and annotations."
)
async def bar_plot_tool(
    file_path: str,
    x_column: str,
    y_column: str,
    title: str = "Bar Plot",
    output_path: str = "bar_plot.png"
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
    return create_bar_plot(file_path, x_column, y_column, title, output_path)

@mcp.tool(
    name="scatter_plot",
    description="Create scatter plots from CSV or Excel data with correlation analysis and trend visualization. Supports multi-dimensional data exploration, regression lines, and statistical annotations for data relationships."
)
async def scatter_plot_tool(
    file_path: str,
    x_column: str,
    y_column: str,
    title: str = "Scatter Plot",
    output_path: str = "scatter_plot.png"
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
    return create_scatter_plot(file_path, x_column, y_column, title, output_path)

@mcp.tool(
    name="histogram_plot",
    description="Create histograms from CSV or Excel data with statistical distribution analysis. Supports density plots, normal distribution overlays, and comprehensive statistical metrics for data distribution visualization."
)
async def histogram_plot_tool(
    file_path: str,
    column: str,
    bins: int = 30,
    title: str = "Histogram",
    output_path: str = "histogram.png"
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
    return create_histogram(file_path, column, bins, title, output_path)

@mcp.tool(
    name="heatmap_plot",
    description="Create heatmaps from CSV or Excel data with correlation matrix analysis and color-coded data visualization. Supports hierarchical clustering, dendrograms, and advanced color mapping for multi-dimensional data exploration."
)
async def heatmap_plot_tool(
    file_path: str,
    title: str = "Heatmap",
    output_path: str = "heatmap.png"
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
    return create_heatmap(file_path, title, output_path)

@mcp.tool(
    name="data_info",
    description="Get comprehensive data file information including detailed schema analysis, data quality assessment, and statistical profiling. Provides thorough data exploration with column types, distributions, and data health metrics."
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
    return get_data_info(file_path)

def main():
    """
    Main entry point for the Plot MCP server.
    Supports both stdio and SSE transports based on environment variables.
    """
    # Handle 'help' command (without dashes) by converting to --help
    if len(sys.argv) > 1 and sys.argv[1] == "help":
        sys.argv[1] = "--help"
    
    parser = argparse.ArgumentParser(
        description="Plot MCP Server - Data visualization server with comprehensive plotting capabilities",
        prog="plot-mcp"
    )
    parser.add_argument(
        "--version", 
        action="version", 
        version="Plot MCP Server v1.0.0"
    )
    parser.add_argument(
        "--transport",
        choices=["stdio", "sse"],
        default="stdio",
        help="Transport type to use (default: stdio)"
    )
    parser.add_argument(
        "--host",
        default="0.0.0.0",
        help="Host for SSE transport (default: 0.0.0.0)"
    )
    parser.add_argument(
        "--port",
        type=int,
        default=8000,
        help="Port for SSE transport (default: 8000)"
    )
    
    args = parser.parse_args()
    
    try:
        logger.info("Starting Plot MCP Server")
        
        # Use command-line args or environment variables
        transport = args.transport or os.getenv("MCP_TRANSPORT", "stdio").lower()
        
        if transport == "sse":
            # SSE transport for web-based clients
            host = args.host or os.getenv("MCP_SSE_HOST", "0.0.0.0")
            port = args.port or int(os.getenv("MCP_SSE_PORT", "8000"))
            logger.info(f"Starting SSE transport on {host}:{port}")
            print(json.dumps({"message": f"Starting SSE on {host}:{port}"}), file=sys.stderr)
            mcp.run(transport="sse", host=host, port=port)
        else:
            # Default stdio transport
            logger.info("Starting stdio transport")
            print(json.dumps({"message": "Starting stdio transport"}), file=sys.stderr)
            mcp.run(transport="stdio")

    except Exception as e:
        logger.error(f"Server error: {e}")
        print(json.dumps({"error": str(e)}), file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    main()
