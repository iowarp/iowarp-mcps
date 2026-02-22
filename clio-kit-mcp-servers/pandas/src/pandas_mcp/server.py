"""
Pandas MCP Server - Comprehensive Data Analysis Implementation

Provides pandas data analysis capabilities through the Model Context Protocol,
enabling data loading, statistical analysis, cleaning, transformation, and
hypothesis testing on various data formats.
"""

import os
import logging
from typing import Annotated, Optional, List, Any, Dict

from fastmcp import FastMCP
from fastmcp.exceptions import ToolError
from fastmcp.prompts import Message
from pydantic import Field

try:
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:
    pass

from .implementation.data_io import load_data_file, save_data_file
from .implementation.pandas_statistics import (
    get_statistical_summary,
    get_correlation_analysis,
)
from .implementation.data_cleaning import handle_missing_data, clean_data
from .implementation.transformations import (
    groupby_operations,
    merge_datasets,
    create_pivot_table,
)
from .implementation.data_profiling import profile_data
from .implementation.time_series import time_series_operations
from .implementation.memory_optimization import optimize_memory_usage
from .implementation.filtering import filter_data
from .implementation.validation import validate_data, hypothesis_testing

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize FastMCP server instance
mcp: FastMCP = FastMCP(
    "pandas",
    instructions=(
        "Performs data analysis operations using pandas DataFrames. "
        "Load CSV/Excel files, compute statistics, filter data, group and aggregate, "
        "and run hypothesis tests."
    ),
    list_page_size=10,
)


# Custom exception for pandas-related errors
class PandasMCPError(Exception):
    """Custom exception for pandas MCP-related errors"""

    pass


# ===============================================================================
# DATA I/O TOOLS
# ===============================================================================


@mcp.tool(
    name="load_data",
    description="Load and parse data from CSV, Excel, JSON, Parquet, or HDF5 files with optional column selection and row limiting.",
    annotations={
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
    },
    tags={"data-analysis", "io"},
)
async def load_data_tool(
    file_path: Annotated[str, Field(description="Absolute path to the data file")],
    file_format: Annotated[
        Optional[str],
        Field(
            description="File format (csv, excel, json, parquet, hdf5); auto-detected if omitted"
        ),
    ] = None,
    sheet_name: Annotated[
        Optional[str], Field(description="Excel sheet name or index")
    ] = None,
    encoding: Annotated[
        Optional[str],
        Field(
            description="Character encoding (e.g. utf-8, latin-1); auto-detected if omitted"
        ),
    ] = None,
    columns: Annotated[
        Optional[List[str]],
        Field(description="Specific columns to load; None loads all"),
    ] = None,
    nrows: Annotated[
        Optional[int], Field(description="Maximum rows to load; None loads all")
    ] = None,
) -> dict:
    """Load data from various file formats with comprehensive parsing options."""
    try:
        logger.info(f"Loading data from: {file_path}")
        return load_data_file(
            file_path, file_format, sheet_name, encoding, columns, nrows
        )
    except Exception as e:
        logger.error(f"Data loading error: {e}")
        raise ToolError(f"Data loading error: {e}") from e


@mcp.tool(
    name="save_data",
    description="Save data to CSV, Excel, JSON, Parquet, or HDF5 with auto-detected format and optional index inclusion.",
    annotations={
        "readOnlyHint": False,
        "destructiveHint": False,
        "idempotentHint": True,
    },
    tags={"data-analysis", "io"},
)
async def save_data_tool(
    data: Annotated[
        dict, Field(description="Data dictionary to save (structured data format)")
    ],
    file_path: Annotated[
        str, Field(description="Absolute path where the file will be saved")
    ],
    file_format: Annotated[
        Optional[str],
        Field(
            description="Output format (csv, excel, json, parquet, hdf5); auto-detected if omitted"
        ),
    ] = None,
    index: Annotated[
        bool, Field(description="Whether to include row indices in output")
    ] = True,
) -> dict:
    """Save data to various file formats with comprehensive export options."""
    try:
        logger.info(f"Saving data to: {file_path}")
        return save_data_file(data, file_path, file_format, index)
    except Exception as e:
        logger.error(f"Data saving error: {e}")
        raise ToolError(f"Data saving error: {e}") from e


# ===============================================================================
# STATISTICAL ANALYSIS TOOLS
# ===============================================================================


@mcp.tool(
    name="statistical_summary",
    description="Compute descriptive statistics, distribution analysis, and outlier detection for numerical and categorical columns.",
    annotations={
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
    },
    tags={"data-analysis", "statistics"},
)
async def statistical_summary_tool(
    file_path: Annotated[str, Field(description="Absolute path to the data file")],
    columns: Annotated[
        Optional[List[str]],
        Field(description="Columns to analyze; None analyzes all numerical columns"),
    ] = None,
    include_distributions: Annotated[
        bool, Field(description="Include distribution analysis and normality tests")
    ] = False,
) -> dict:
    """Generate comprehensive statistical summary with advanced analytics."""
    try:
        logger.info(f"Generating statistical summary for: {file_path}")
        return get_statistical_summary(file_path, columns, include_distributions)
    except Exception as e:
        logger.error(f"Statistical analysis error: {e}")
        raise ToolError(f"Statistical analysis error: {e}") from e


@mcp.tool(
    name="correlation_analysis",
    description="Compute correlation matrices (Pearson, Spearman, or Kendall) with significance testing and strong-correlation detection.",
    annotations={
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
    },
    tags={"data-analysis", "statistics"},
)
async def correlation_analysis_tool(
    file_path: Annotated[str, Field(description="Absolute path to the data file")],
    method: Annotated[
        str, Field(description="Correlation method: pearson, spearman, or kendall")
    ] = "pearson",
    columns: Annotated[
        Optional[List[str]],
        Field(description="Columns to analyze; None analyzes all numerical columns"),
    ] = None,
) -> dict:
    """Perform comprehensive correlation analysis with statistical significance testing."""
    try:
        logger.info(f"Performing correlation analysis on: {file_path}")
        return get_correlation_analysis(file_path, method, columns)
    except Exception as e:
        logger.error(f"Correlation analysis error: {e}")
        raise ToolError(f"Correlation analysis error: {e}") from e


@mcp.tool(
    name="hypothesis_testing",
    description="Run statistical hypothesis tests (t-test, chi-square, ANOVA, normality, Mann-Whitney) with p-values and effect sizes.",
    annotations={
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
    },
    tags={"data-analysis", "statistics"},
)
async def hypothesis_testing_tool(
    file_path: Annotated[str, Field(description="Absolute path to the data file")],
    test_type: Annotated[
        str,
        Field(
            description="Test type: t_test, chi_square, anova, normality, mann_whitney, correlation"
        ),
    ],
    column1: Annotated[str, Field(description="Primary column for testing")],
    column2: Annotated[
        Optional[str],
        Field(
            description="Secondary column for two-sample tests; None for single-sample"
        ),
    ] = None,
    alpha: Annotated[
        float, Field(description="Significance level (e.g. 0.05, 0.01)")
    ] = 0.05,
) -> dict:
    """Perform statistical hypothesis testing with effect size and confidence intervals."""
    try:
        logger.info(f"Performing hypothesis testing on: {file_path}")
        return hypothesis_testing(file_path, test_type, column1, column2, alpha)
    except Exception as e:
        logger.error(f"Hypothesis testing error: {e}")
        raise ToolError(f"Hypothesis testing error: {e}") from e


# ===============================================================================
# DATA CLEANING TOOLS
# ===============================================================================


@mcp.tool(
    name="handle_missing_data",
    description="Detect, impute, or remove missing values using strategies like mean/median/mode fill, forward/backward fill, or interpolation.",
    annotations={
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
    },
    tags={"data-analysis", "cleaning"},
)
async def handle_missing_data_tool(
    file_path: Annotated[str, Field(description="Absolute path to the data file")],
    strategy: Annotated[
        str, Field(description="Strategy: detect, impute, remove, or analyze")
    ] = "detect",
    method: Annotated[
        Optional[str],
        Field(
            description="Imputation method: mean, median, mode, forward_fill, backward_fill, interpolate"
        ),
    ] = None,
    columns: Annotated[
        Optional[List[str]], Field(description="Columns to process; None processes all")
    ] = None,
) -> dict:
    """Handle missing data with comprehensive strategies and statistical methods."""
    try:
        logger.info(f"Handling missing data in: {file_path}")
        return handle_missing_data(file_path, strategy, method, columns)
    except Exception as e:
        logger.error(f"Missing data handling error: {e}")
        raise ToolError(f"Missing data handling error: {e}") from e


@mcp.tool(
    name="clean_data",
    description="Remove duplicates, detect outliers via IQR/Z-score, and optimize data types in a single pass.",
    annotations={
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
    },
    tags={"data-analysis", "cleaning"},
)
async def clean_data_tool(
    file_path: Annotated[str, Field(description="Absolute path to the data file")],
    remove_duplicates: Annotated[
        bool, Field(description="Identify and remove duplicate records")
    ] = False,
    detect_outliers: Annotated[
        bool, Field(description="Detect outliers using IQR and Z-score")
    ] = False,
    convert_types: Annotated[
        bool, Field(description="Automatically optimize data types")
    ] = False,
) -> dict:
    """Perform comprehensive data cleaning with advanced quality improvement techniques."""
    try:
        logger.info(f"Cleaning data in: {file_path}")
        return clean_data(file_path, remove_duplicates, detect_outliers, convert_types)
    except Exception as e:
        logger.error(f"Data cleaning error: {e}")
        raise ToolError(f"Data cleaning error: {e}") from e


# ===============================================================================
# DATA TRANSFORMATION TOOLS
# ===============================================================================


@mcp.tool(
    name="groupby_operations",
    description="Group data by columns and apply aggregations (sum, mean, count, min, max, std, median) with optional pre-filter.",
    annotations={
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
    },
    tags={"data-analysis", "transformation"},
)
async def groupby_operations_tool(
    file_path: Annotated[str, Field(description="Absolute path to the data file")],
    group_by: Annotated[List[str], Field(description="Columns to group by")],
    operations: Annotated[
        Dict[str, str],
        Field(
            description="Column:operation pairs, e.g. {'salary': 'mean', 'age': 'sum'}"
        ),
    ],
    filter_condition: Annotated[
        Optional[str],
        Field(description="Optional pandas query string to filter before grouping"),
    ] = None,
) -> dict:
    """Perform sophisticated groupby operations with comprehensive aggregation options."""
    try:
        logger.info(f"Performing groupby operations on: {file_path}")
        return groupby_operations(file_path, group_by, operations, filter_condition)
    except Exception as e:
        logger.error(f"Groupby operations error: {e}")
        raise ToolError(f"Groupby operations error: {e}") from e


@mcp.tool(
    name="merge_datasets",
    description="Join two datasets using inner, outer, left, or right joins on specified key columns.",
    annotations={
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
    },
    tags={"data-analysis", "transformation"},
)
async def merge_datasets_tool(
    left_file: Annotated[str, Field(description="Absolute path to the left dataset")],
    right_file: Annotated[str, Field(description="Absolute path to the right dataset")],
    join_type: Annotated[
        str, Field(description="Join type: inner, outer, left, or right")
    ] = "inner",
    left_on: Annotated[
        Optional[str], Field(description="Join column in left dataset")
    ] = None,
    right_on: Annotated[
        Optional[str], Field(description="Join column in right dataset")
    ] = None,
    on: Annotated[
        Optional[str], Field(description="Common join column (if same name in both)")
    ] = None,
) -> dict:
    """Merge and join datasets with comprehensive integration capabilities."""
    try:
        logger.info(f"Merging datasets: {left_file} and {right_file}")
        return merge_datasets(left_file, right_file, join_type, left_on, right_on, on)
    except Exception as e:
        logger.error(f"Dataset merge error: {e}")
        raise ToolError(f"Dataset merge error: {e}") from e


@mcp.tool(
    name="pivot_table",
    description="Create pivot tables with configurable row index, column headers, value columns, and aggregation function.",
    annotations={
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
    },
    tags={"data-analysis", "transformation"},
)
async def pivot_table_tool(
    file_path: Annotated[str, Field(description="Absolute path to the data file")],
    index: Annotated[List[str], Field(description="Columns to use as row index")],
    columns: Annotated[
        Optional[List[str]], Field(description="Columns to use as column headers")
    ] = None,
    values: Annotated[
        Optional[List[str]],
        Field(description="Columns to aggregate; None uses all numerical"),
    ] = None,
    aggfunc: Annotated[
        str,
        Field(description="Aggregation function: mean, sum, count, min, max, std, var"),
    ] = "mean",
) -> dict:
    """Create sophisticated pivot tables with comprehensive aggregation options."""
    try:
        logger.info(f"Creating pivot table for: {file_path}")
        return create_pivot_table(file_path, index, columns, values, aggfunc)
    except Exception as e:
        logger.error(f"Pivot table error: {e}")
        raise ToolError(f"Pivot table error: {e}") from e


# ===============================================================================
# TIME SERIES TOOLS
# ===============================================================================


@mcp.tool(
    name="time_series_operations",
    description="Resample, compute rolling statistics, create lag features, or difference a time series.",
    annotations={
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
    },
    tags={"data-analysis", "time-series"},
)
async def time_series_operations_tool(
    file_path: Annotated[str, Field(description="Absolute path to the data file")],
    date_column: Annotated[str, Field(description="Column containing datetime values")],
    operation: Annotated[
        str,
        Field(
            description="Operation: resample, rolling_mean, lag, trend, seasonality, rolling, diff"
        ),
    ],
    window_size: Annotated[
        Optional[int], Field(description="Window size for rolling/lag operations")
    ] = None,
    frequency: Annotated[
        Optional[str], Field(description="Resampling frequency: D, W, M, Q, Y")
    ] = None,
) -> dict:
    """Perform comprehensive time series operations with advanced temporal analysis."""
    try:
        logger.info(f"Performing time series operations on: {file_path}")
        return time_series_operations(
            file_path, date_column, operation, window_size, frequency
        )
    except Exception as e:
        logger.error(f"Time series operations error: {e}")
        raise ToolError(f"Time series operations error: {e}") from e


# ===============================================================================
# DATA VALIDATION TOOLS
# ===============================================================================


@mcp.tool(
    name="validate_data",
    description="Validate columns against rules for min/max range, data type, nullability, uniqueness, and regex patterns.",
    annotations={
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
    },
    tags={"data-analysis", "validation"},
)
async def validate_data_tool(
    file_path: Annotated[str, Field(description="Absolute path to the data file")],
    validation_rules: Annotated[
        Dict[str, Dict[str, Any]],
        Field(
            description="Validation rules: {column: {rule_type: value}}. Rules: min_value, max_value, dtype, allow_null, unique, pattern"
        ),
    ],
) -> dict:
    """Perform comprehensive data validation with advanced constraint checking."""
    try:
        logger.info(f"Validating data in: {file_path}")
        return validate_data(file_path, validation_rules)
    except Exception as e:
        logger.error(f"Data validation error: {e}")
        raise ToolError(f"Data validation error: {e}") from e


# ===============================================================================
# DATA FILTERING TOOLS
# ===============================================================================


@mcp.tool(
    name="filter_data",
    description="Filter rows using comparison, membership, pattern-matching, and null-check operators across multiple columns.",
    annotations={
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
    },
    tags={"data-analysis", "filtering"},
)
async def filter_data_tool(
    file_path: Annotated[str, Field(description="Absolute path to the data file")],
    filter_conditions: Annotated[
        Dict[str, Any],
        Field(
            description="Filter conditions: {column: {operator: value}}. Operators: eq, ne, gt, lt, ge, le, in, not_in, contains, regex"
        ),
    ],
    output_file: Annotated[
        Optional[str],
        Field(description="Path to save filtered data; None returns in memory"),
    ] = None,
) -> dict:
    """Perform advanced data filtering with boolean indexing and conditional expressions."""
    try:
        logger.info(f"Filtering data in: {file_path}")
        return filter_data(file_path, filter_conditions, output_file)
    except Exception as e:
        logger.error(f"Data filtering error: {e}")
        raise ToolError(f"Data filtering error: {e}") from e


# ===============================================================================
# MEMORY OPTIMIZATION TOOLS
# ===============================================================================


@mcp.tool(
    name="optimize_memory",
    description="Analyze and reduce DataFrame memory usage through automatic dtype optimization and chunked-processing recommendations.",
    annotations={
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
    },
    tags={"data-analysis", "optimization"},
)
async def optimize_memory_tool(
    file_path: Annotated[str, Field(description="Absolute path to the data file")],
    optimize_dtypes: Annotated[
        bool,
        Field(description="Automatically optimize data types for memory efficiency"),
    ] = True,
    chunk_size: Annotated[
        Optional[int],
        Field(description="Chunk size for processing large files; None for automatic"),
    ] = None,
) -> dict:
    """Perform advanced memory optimization for large datasets."""
    try:
        logger.info(f"Optimizing memory usage for: {file_path}")
        return optimize_memory_usage(file_path, optimize_dtypes, chunk_size)
    except Exception as e:
        logger.error(f"Memory optimization error: {e}")
        raise ToolError(f"Memory optimization error: {e}") from e


# ===============================================================================
# DATA PROFILING TOOLS
# ===============================================================================


@mcp.tool(
    name="profile_data",
    description="Generate a full dataset profile: shape, types, missing values, distributions, quality checks, and optional correlations.",
    annotations={
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
    },
    tags={"data-analysis", "profiling"},
)
async def profile_data_tool(
    file_path: Annotated[str, Field(description="Absolute path to the data file")],
    include_correlations: Annotated[
        bool, Field(description="Include correlation analysis between variables")
    ] = False,
    sample_size: Annotated[
        Optional[int],
        Field(description="Rows to sample for large datasets; None uses full dataset"),
    ] = None,
) -> dict:
    """Perform comprehensive data profiling with statistical analysis and quality assessment."""
    try:
        logger.info(f"Profiling data in: {file_path}")
        return profile_data(file_path, include_correlations, sample_size)
    except Exception as e:
        logger.error(f"Data profiling error: {e}")
        raise ToolError(f"Data profiling error: {e}") from e


# ===============================================================================
# RESOURCES
# ===============================================================================


@mcp.resource("pandas://capabilities")
def pandas_capabilities() -> dict:
    """Supported pandas operations and file formats."""
    return {
        "file_formats": ["csv", "excel", "parquet", "json"],
        "operations": [
            "statistics",
            "filtering",
            "groupby",
            "aggregation",
            "hypothesis testing",
        ],
    }


# ===============================================================================
# PROMPTS
# ===============================================================================


@mcp.prompt()
def analyze_dataset(file_path: str) -> list[Message]:
    """Guided workflow for exploring and analyzing a dataset."""
    return [
        Message(
            f"I need to analyze the dataset at {file_path}. "
            "Load it, show basic statistics, identify interesting patterns, "
            "and suggest further analysis."
        ),
    ]


def main() -> None:
    """Main entry point for the Pandas MCP server."""
    import argparse

    parser = argparse.ArgumentParser(description="Pandas MCP Server")
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
