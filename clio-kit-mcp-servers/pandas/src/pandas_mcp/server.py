"""
Pandas MCP Server - Comprehensive Data Analysis Implementation

Provides pandas data analysis capabilities through the Model Context Protocol,
enabling data loading, statistical analysis, cleaning, transformation, and
hypothesis testing on various data formats.
"""

import os
import logging
from typing import Annotated, Optional, List, Any, Dict, Literal, cast

from fastmcp import FastMCP
from fastmcp.exceptions import ToolError
from fastmcp.prompts import Message
from pydantic import Field
from typing_extensions import NotRequired, TypedDict

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
from .implementation.csv_profiling import profile_csv
from .implementation.time_series import time_series_operations
from .implementation.memory_optimization import optimize_memory_usage
from .implementation.filtering import filter_data
from .implementation.validation import validate_data, hypothesis_testing


# --- Structured result shapes (drive real MCP outputSchema declarations) ----
#
# Every TypedDict below types the SUCCESS-path dict actually returned by its
# implementation function (traced from the real `return {...}` statements,
# not from docstrings). Tool handlers raise `ToolError` on failure, so the
# error-path shape (`success: False`, `error`, `error_type`, ...) is
# deliberately not modeled here. Fields whose keys are data-dependent (e.g.
# column names) are typed `dict[str, <precise value type>]` where the value
# type is uniform, and fall back to `dict[str, Any]` only where the value
# shape genuinely varies (e.g. a per-test-type hypothesis test_info dict, or
# a raw record dict where each column may hold any type).


class LoadDataInfo(TypedDict):
    """Schema/shape metadata attached to a successful data load."""

    shape: tuple[int, int]
    columns: list[str]
    dtypes: dict[str, str]
    memory_usage: int
    missing_values: dict[str, int]


class LoadDataResult(TypedDict):
    """Structured result for a successful data load."""

    success: Literal[True]
    file_path: str
    file_format: str
    data: list[dict[str, Any]]
    total_rows: int
    info: LoadDataInfo
    message: str


class SaveDataResult(TypedDict):
    """Structured result for a successful data save."""

    success: Literal[True]
    file_path: str
    file_format: str
    file_size_bytes: int
    file_size_mb: float
    rows_saved: int
    columns_saved: int
    message: str


class NormalityTestResult(TypedDict):
    """Shapiro-Wilk normality test result for one numeric column."""

    shapiro_wilk_statistic: float
    shapiro_wilk_p_value: float
    is_normal: bool


class ColumnAdditionalStats(TypedDict):
    """Extra distribution statistics for one numeric column."""

    variance: float
    skewness: float
    kurtosis: float
    median_absolute_deviation: float
    interquartile_range: float
    coefficient_of_variation: float | None
    normality_test: NotRequired[NormalityTestResult]


class ColumnCategoricalStats(TypedDict):
    """Categorical summary statistics for one column."""

    unique_values: int
    most_frequent: str | None
    most_frequent_count: int
    value_counts: dict[str, int]


class MissingDataSummary(TypedDict):
    """Missing-value counts for a dataset."""

    total_missing: int
    missing_by_column: dict[str, int]
    missing_percentage: dict[str, float]


class StatisticalSummaryResult(TypedDict):
    """Structured result for a successful statistical summary."""

    success: Literal[True]
    file_path: str
    shape: tuple[int, int]
    basic_statistics: dict[str, dict[str, Any]]
    additional_statistics: dict[str, ColumnAdditionalStats]
    categorical_statistics: dict[str, ColumnCategoricalStats]
    missing_data: MissingDataSummary
    message: str


class HighCorrelationPair(TypedDict):
    """One strongly correlated variable pair."""

    variable1: str
    variable2: str
    correlation: float
    strength: Literal["strong", "moderate"]


class CorrelationAnalysisResult(TypedDict):
    """Structured result for a successful correlation analysis."""

    success: Literal[True]
    file_path: str
    method: str
    correlation_matrix: dict[str, dict[str, float]]
    high_correlations: list[HighCorrelationPair]
    analyzed_columns: list[str]
    message: str


class HypothesisTestInterpretation(TypedDict):
    """Statistical interpretation shared by every hypothesis test type."""

    statistic: float
    p_value: float
    alpha: float
    is_significant: bool
    conclusion: Literal["Reject null hypothesis", "Fail to reject null hypothesis"]
    effect_size: Literal["large", "medium", "small"]


class HypothesisTestingResult(TypedDict):
    """Structured result for a successful hypothesis test.

    ``test_info`` is a discriminated union keyed by ``test_type`` (t-test,
    chi-square, correlation, ANOVA, ...); each variant has its own field set
    and value types, so it is left as ``dict[str, Any]`` rather than forcing
    a false shared shape.
    """

    success: Literal[True]
    file_path: str
    test_info: dict[str, Any]
    results: HypothesisTestInterpretation
    message: str


class MissingDataInfo(TypedDict):
    """Missing-value counts, plus row-level missing-data coverage."""

    total_missing: int
    missing_by_column: dict[str, int]
    missing_percentage: dict[str, float]
    rows_with_missing: int
    complete_rows: int


class ImputationColumnInfo(TypedDict):
    """Per-column imputation method and outcome."""

    method: str
    fill_value: float | str
    imputed_count: int


class HandleMissingDataResult(TypedDict):
    """Structured result for a successful missing-data handling call.

    Field presence depends on ``strategy``: ``detect`` returns only
    ``original_shape``/``missing_data_info``; ``remove`` and ``impute`` also
    write an output file and add their own strategy-specific fields.
    """

    success: Literal[True]
    file_path: str
    original_shape: tuple[int, int]
    missing_data_info: MissingDataInfo
    message: str
    output_file: NotRequired[str]
    new_shape: NotRequired[tuple[int, int]]
    removed_rows: NotRequired[int]
    imputation_method: NotRequired[str]
    imputation_info: NotRequired[dict[str, ImputationColumnInfo]]


class OutlierColumnInfo(TypedDict):
    """IQR-based outlier statistics for one numeric column."""

    outlier_count: int
    outlier_percentage: float
    lower_bound: float
    upper_bound: float
    outlier_values: list[float]


class CleaningResults(TypedDict):
    """Nested cleaning statistics for a successful clean_data call."""

    original_shape: tuple[int, int]
    original_memory_mb: float
    final_shape: tuple[int, int]
    final_memory_mb: float
    memory_reduction_mb: float
    outliers_info: dict[str, OutlierColumnInfo] | None
    type_changes: dict[str, str] | None
    duplicates_removed: NotRequired[int]


class CleanDataResult(TypedDict):
    """Structured result for a successful data cleaning call."""

    success: Literal[True]
    file_path: str
    output_file: str
    cleaning_results: CleaningResults
    message: str


class GroupByInfo(TypedDict):
    """Parameters and outcome summary of a groupby aggregation."""

    group_by_columns: list[str]
    operations: dict[str, str]
    filter_condition: str | None
    number_of_groups: int
    original_rows: int
    aggregated_columns: list[str]


class GroupByOperationsResult(TypedDict):
    """Structured result for a successful groupby operation."""

    success: Literal[True]
    file_path: str
    output_file: str
    group_info: GroupByInfo
    results: list[dict[str, Any]]
    message: str


class MergeStats(TypedDict):
    """Row/column shape and join-key coverage for a dataset merge."""

    left_shape: tuple[int, int]
    right_shape: tuple[int, int]
    merged_shape: tuple[int, int]
    join_type: str
    left_on: str
    right_on: str
    common_values: int
    left_only_values: int
    right_only_values: int


class MergeDatasetsResult(TypedDict):
    """Structured result for a successful dataset merge."""

    success: Literal[True]
    left_file: str
    right_file: str
    output_file: str
    merge_stats: MergeStats
    merged_data: list[dict[str, Any]]
    message: str


class PivotInfo(TypedDict):
    """Parameters and shape summary for a created pivot table."""

    index_columns: list[str]
    column_headers: list[str] | None
    value_columns: list[str] | None
    aggregation_function: str
    pivot_shape: tuple[int, int]
    original_shape: tuple[int, int]


class PivotTableResult(TypedDict):
    """Structured result for a successful pivot table creation."""

    success: Literal[True]
    file_path: str
    output_file: str
    pivot_info: PivotInfo
    pivot_table: list[dict[str, Any]]
    message: str


class TimeSeriesOperationsResult(TypedDict):
    """Structured result for a successful time-series operation.

    ``operation_info`` varies by ``operation`` (resample/rolling/lag/diff,
    each with its own field set), so it is left as ``dict[str, Any]``.
    """

    success: Literal[True]
    file_path: str
    output_file: str
    operation_info: dict[str, Any]
    results: list[dict[str, Any]]
    message: str


class ValidationSummary(TypedDict):
    """Aggregate pass/fail counts across all validated columns."""

    overall_valid: bool
    total_columns_validated: int
    valid_columns: int
    invalid_columns: int
    total_violations: int


class ValidateDataResult(TypedDict):
    """Structured result for a successful data validation run.

    ``validation_results`` is keyed by column name; each entry's shape
    depends on which rules were violated (different rule types report
    different fields), so its value type is left as ``dict[str, Any]``.
    """

    success: Literal[True]
    file_path: str
    validation_summary: ValidationSummary
    validation_results: dict[str, dict[str, Any]]
    message: str


class FilterStats(TypedDict):
    """Row-count and per-filter statistics for a filter_data call."""

    original_shape: tuple[int, int]
    final_shape: tuple[int, int]
    rows_filtered: int
    filter_percentage: float
    applied_filters: list[dict[str, Any]]


class FilterDataResult(TypedDict):
    """Structured result for a successful data filtering call."""

    success: Literal[True]
    file_path: str
    output_file: str
    filter_stats: FilterStats
    filtered_data: list[dict[str, Any]]
    message: str


class SystemMemoryInfo(TypedDict):
    """Host system memory snapshot taken during an optimize_memory call."""

    total_gb: float
    available_gb: float
    percent_used: float


class MemoryOptimizationSummary(TypedDict):
    """Before/after memory footprint for a successful optimization."""

    initial_memory_mb: float
    final_memory_mb: float
    memory_reduction_mb: float
    memory_reduction_percentage: float
    shape: tuple[int, int]


class ColumnMemoryInfo(TypedDict):
    """Per-column memory footprint after optimization."""

    memory_mb: float
    dtype: str
    percentage_of_total: float


class OptimizationLogEntry(TypedDict):
    """One optimization pass recorded in the optimization log."""

    optimization: str
    changes: dict[str, str]


class OptimizationLog(TypedDict):
    """Log of optimization passes applied to the DataFrame."""

    initial_memory_mb: float
    initial_shape: tuple[int, int]
    optimizations_applied: list[OptimizationLogEntry]


class OptimizeMemoryResult(TypedDict):
    """Structured result for a successful memory optimization call.

    ``chunked_processing`` is only computed when ``chunk_size`` is given, and
    its helper has its own independent success/error shape, so it is left as
    ``dict[str, Any] | None`` rather than a forced single shape.
    """

    success: Literal[True]
    file_path: str
    output_file: str
    system_memory: SystemMemoryInfo
    optimization_results: MemoryOptimizationSummary
    column_memory_usage: dict[str, ColumnMemoryInfo]
    optimization_log: OptimizationLog
    chunked_processing: dict[str, Any] | None
    recommendations: list[str]
    message: str


class ProfileBasicInfo(TypedDict):
    """Shape and dtype snapshot of the profiled dataset."""

    shape: tuple[int, int]
    columns: list[str]
    dtypes: dict[str, str]
    memory_usage_mb: float


class ProfileMissingData(TypedDict):
    """Missing-value counts and affected columns for a profiled dataset."""

    total_missing: int
    missing_by_column: dict[str, int]
    missing_percentage: dict[str, float]
    columns_with_missing: list[str]
    complete_rows: int


class ProfileQualityChecks(TypedDict):
    """Structural data-quality flags found during profiling."""

    duplicate_rows: int
    constant_columns: list[str]
    high_cardinality_columns: list[str]
    mixed_type_columns: list[str]


class ProfileHighCorrelation(TypedDict):
    """One strongly correlated variable pair found during profiling."""

    variable1: str
    variable2: str
    correlation: float


class ProfileCorrelations(TypedDict):
    """Correlation matrix and notable pairs computed during profiling."""

    correlation_matrix: dict[str, dict[str, float]]
    high_correlations: list[ProfileHighCorrelation]


class ProfileSummary(TypedDict):
    """High-level counts summarizing a data profile."""

    total_columns: int
    numeric_columns: int
    categorical_columns: int
    datetime_columns: int
    total_rows: int
    complete_rows: int
    duplicate_rows: int
    memory_usage_mb: float


class ProfileDataResult(TypedDict):
    """Structured result for a successful data profiling call.

    ``column_analysis`` is keyed by column name; each entry's shape depends
    on the column's inferred type (numeric/categorical/datetime), so its
    value type is left as ``dict[str, Any]``.
    """

    success: Literal[True]
    file_path: str
    basic_info: ProfileBasicInfo
    summary: ProfileSummary
    missing_data: ProfileMissingData
    column_analysis: dict[str, dict[str, Any]]
    quality_checks: ProfileQualityChecks
    correlations: ProfileCorrelations | None
    message: str


class CsvNumericSummary(TypedDict):
    """Min/max/mean summary for one numeric CSV column."""

    count: int
    min: float
    max: float
    mean: float


class ProfileCsvResult(TypedDict):
    """Structured result for a successful profile_csv call."""

    success: Literal[True]
    file_path: str
    size_bytes: int
    columns: list[str]
    column_count: int
    row_count: int
    rows_profiled: int
    row_scan_cap: int
    scan_limited: bool
    profile_limited: bool
    dtypes: dict[str, Literal["empty", "integer", "float", "boolean", "string"]]
    null_counts: dict[str, int]
    numeric_summary: dict[str, CsvNumericSummary]
    sample_rows: list[dict[str, str]]
    message: str


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
    title="Load Data",
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
) -> LoadDataResult:
    """Load data from various file formats with comprehensive parsing options."""
    try:
        logger.info(f"Loading data from: {file_path}")
        return cast(
            LoadDataResult,
            load_data_file(
                file_path, file_format, sheet_name, encoding, columns, nrows
            ),
        )
    except Exception as e:
        logger.error(f"Data loading error: {e}")
        raise ToolError(f"Data loading error: {e}") from e


@mcp.tool(
    name="save_data",
    title="Save Data",
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
) -> SaveDataResult:
    """Save data to various file formats with comprehensive export options."""
    try:
        logger.info(f"Saving data to: {file_path}")
        return cast(SaveDataResult, save_data_file(data, file_path, file_format, index))
    except Exception as e:
        logger.error(f"Data saving error: {e}")
        raise ToolError(f"Data saving error: {e}") from e


# ===============================================================================
# STATISTICAL ANALYSIS TOOLS
# ===============================================================================


@mcp.tool(
    name="statistical_summary",
    title="Statistical Summary",
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
) -> StatisticalSummaryResult:
    """Generate comprehensive statistical summary with advanced analytics."""
    try:
        logger.info(f"Generating statistical summary for: {file_path}")
        return cast(
            StatisticalSummaryResult,
            get_statistical_summary(file_path, columns, include_distributions),
        )
    except Exception as e:
        logger.error(f"Statistical analysis error: {e}")
        raise ToolError(f"Statistical analysis error: {e}") from e


@mcp.tool(
    name="correlation_analysis",
    title="Correlation Analysis",
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
) -> CorrelationAnalysisResult:
    """Perform comprehensive correlation analysis with statistical significance testing."""
    try:
        logger.info(f"Performing correlation analysis on: {file_path}")
        return cast(
            CorrelationAnalysisResult,
            get_correlation_analysis(file_path, method, columns),
        )
    except Exception as e:
        logger.error(f"Correlation analysis error: {e}")
        raise ToolError(f"Correlation analysis error: {e}") from e


@mcp.tool(
    name="hypothesis_testing",
    title="Hypothesis Test",
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
) -> HypothesisTestingResult:
    """Perform statistical hypothesis testing with effect size and confidence intervals."""
    try:
        logger.info(f"Performing hypothesis testing on: {file_path}")
        return cast(
            HypothesisTestingResult,
            hypothesis_testing(file_path, test_type, column1, column2, alpha),
        )
    except Exception as e:
        logger.error(f"Hypothesis testing error: {e}")
        raise ToolError(f"Hypothesis testing error: {e}") from e


# ===============================================================================
# DATA CLEANING TOOLS
# ===============================================================================


@mcp.tool(
    name="handle_missing_data",
    title="Fix Missing Data",
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
) -> HandleMissingDataResult:
    """Handle missing data with comprehensive strategies and statistical methods."""
    try:
        logger.info(f"Handling missing data in: {file_path}")
        return cast(
            HandleMissingDataResult,
            handle_missing_data(file_path, strategy, method, columns),
        )
    except Exception as e:
        logger.error(f"Missing data handling error: {e}")
        raise ToolError(f"Missing data handling error: {e}") from e


@mcp.tool(
    name="clean_data",
    title="Clean Data",
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
) -> CleanDataResult:
    """Perform comprehensive data cleaning with advanced quality improvement techniques."""
    try:
        logger.info(f"Cleaning data in: {file_path}")
        return cast(
            CleanDataResult,
            clean_data(file_path, remove_duplicates, detect_outliers, convert_types),
        )
    except Exception as e:
        logger.error(f"Data cleaning error: {e}")
        raise ToolError(f"Data cleaning error: {e}") from e


# ===============================================================================
# DATA TRANSFORMATION TOOLS
# ===============================================================================


@mcp.tool(
    name="groupby_operations",
    title="Group Data",
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
) -> GroupByOperationsResult:
    """Perform sophisticated groupby operations with comprehensive aggregation options."""
    try:
        logger.info(f"Performing groupby operations on: {file_path}")
        return cast(
            GroupByOperationsResult,
            groupby_operations(file_path, group_by, operations, filter_condition),
        )
    except Exception as e:
        logger.error(f"Groupby operations error: {e}")
        raise ToolError(f"Groupby operations error: {e}") from e


@mcp.tool(
    name="merge_datasets",
    title="Merge Datasets",
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
) -> MergeDatasetsResult:
    """Merge and join datasets with comprehensive integration capabilities."""
    try:
        logger.info(f"Merging datasets: {left_file} and {right_file}")
        return cast(
            MergeDatasetsResult,
            merge_datasets(left_file, right_file, join_type, left_on, right_on, on),
        )
    except Exception as e:
        logger.error(f"Dataset merge error: {e}")
        raise ToolError(f"Dataset merge error: {e}") from e


@mcp.tool(
    name="pivot_table",
    title="Pivot Table",
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
) -> PivotTableResult:
    """Create sophisticated pivot tables with comprehensive aggregation options."""
    try:
        logger.info(f"Creating pivot table for: {file_path}")
        return cast(
            PivotTableResult,
            create_pivot_table(file_path, index, columns, values, aggfunc),
        )
    except Exception as e:
        logger.error(f"Pivot table error: {e}")
        raise ToolError(f"Pivot table error: {e}") from e


# ===============================================================================
# TIME SERIES TOOLS
# ===============================================================================


@mcp.tool(
    name="time_series_operations",
    title="Transform Series",
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
) -> TimeSeriesOperationsResult:
    """Perform comprehensive time series operations with advanced temporal analysis."""
    try:
        logger.info(f"Performing time series operations on: {file_path}")
        return cast(
            TimeSeriesOperationsResult,
            time_series_operations(
                file_path, date_column, operation, window_size, frequency
            ),
        )
    except Exception as e:
        logger.error(f"Time series operations error: {e}")
        raise ToolError(f"Time series operations error: {e}") from e


# ===============================================================================
# DATA VALIDATION TOOLS
# ===============================================================================


@mcp.tool(
    name="validate_data",
    title="Validate Data",
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
) -> ValidateDataResult:
    """Perform comprehensive data validation with advanced constraint checking."""
    try:
        logger.info(f"Validating data in: {file_path}")
        return cast(ValidateDataResult, validate_data(file_path, validation_rules))
    except Exception as e:
        logger.error(f"Data validation error: {e}")
        raise ToolError(f"Data validation error: {e}") from e


# ===============================================================================
# DATA FILTERING TOOLS
# ===============================================================================


@mcp.tool(
    name="filter_data",
    title="Filter Data",
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
) -> FilterDataResult:
    """Perform advanced data filtering with boolean indexing and conditional expressions."""
    try:
        logger.info(f"Filtering data in: {file_path}")
        return cast(
            FilterDataResult, filter_data(file_path, filter_conditions, output_file)
        )
    except Exception as e:
        logger.error(f"Data filtering error: {e}")
        raise ToolError(f"Data filtering error: {e}") from e


# ===============================================================================
# MEMORY OPTIMIZATION TOOLS
# ===============================================================================


@mcp.tool(
    name="optimize_memory",
    title="Optimize Memory",
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
) -> OptimizeMemoryResult:
    """Perform advanced memory optimization for large datasets."""
    try:
        logger.info(f"Optimizing memory usage for: {file_path}")
        return cast(
            OptimizeMemoryResult,
            optimize_memory_usage(file_path, optimize_dtypes, chunk_size),
        )
    except Exception as e:
        logger.error(f"Memory optimization error: {e}")
        raise ToolError(f"Memory optimization error: {e}") from e


# ===============================================================================
# DATA PROFILING TOOLS
# ===============================================================================


@mcp.tool(
    name="profile_data",
    title="Profile Data",
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
) -> ProfileDataResult:
    """Perform comprehensive data profiling with statistical analysis and quality assessment."""
    try:
        logger.info(f"Profiling data in: {file_path}")
        return cast(
            ProfileDataResult,
            profile_data(file_path, include_correlations, sample_size),
        )
    except Exception as e:
        logger.error(f"Data profiling error: {e}")
        raise ToolError(f"Data profiling error: {e}") from e


@mcp.tool(
    name="profile_csv",
    title="Profile CSV",
    description="Quickly profile a CSV file: row/column counts, per-column dtype, null counts, and min/max/mean for numeric columns.",
    annotations={
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
    },
    tags={"data-analysis", "profiling", "csv"},
)
async def profile_csv_tool(
    data_path: Annotated[str, Field(description="Absolute path to the CSV file")],
    columns: Annotated[
        Optional[List[str]],
        Field(description="Subset of columns to profile; None profiles all"),
    ] = None,
    max_rows: Annotated[
        Optional[int],
        Field(
            description="Maximum rows to retain for statistics (default 5000, capped at 250000)"
        ),
    ] = None,
) -> ProfileCsvResult:
    """Generate a fast, dependency-light profile of a CSV file."""
    try:
        logger.info(f"Profiling CSV file: {data_path}")
        result = profile_csv(data_path, columns, max_rows)
        if not result.get("success", False):
            raise ToolError(
                f"CSV profiling error: {result.get('error', 'unknown error')}"
            )
        return cast(ProfileCsvResult, result)
    except ToolError:
        raise
    except Exception as e:
        logger.error(f"CSV profiling error: {e}")
        raise ToolError(f"CSV profiling error: {e}") from e


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
