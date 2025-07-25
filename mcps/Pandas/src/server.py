"""
Pandas MCP Server - Comprehensive Data Analysis Implementation

This server provides comprehensive pandas data analysis capabilities through the Model Context Protocol,
enabling users to perform data loading, statistical analysis, cleaning, transformation, and visualization
operations on various data formats.

Following MCP best practices, these tools are designed with a workflow-first approach
rather than direct API mapping, providing intelligent, contextual assistance for
data analysis and processing workflows.
"""

import os
import sys
import logging
from typing import Optional, List, Any, Dict

# Try to import required dependencies with fallbacks
try:
    from fastmcp import FastMCP
except ImportError:
    print("FastMCP not available. Please install with: uv add fastmcp", file=sys.stderr)
    sys.exit(1)

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    print("Warning: python-dotenv not available. Environment variables may not be loaded.", file=sys.stderr)

# Add current directory to path for relative imports
sys.path.insert(0, os.path.dirname(__file__))

# Import implementation modules directly
from implementation.data_io import load_data_file, save_data_file, get_file_info
from implementation.pandas_statistics import get_statistical_summary, get_correlation_analysis
from implementation.data_cleaning import handle_missing_data, clean_data
from implementation.transformations import groupby_operations, merge_datasets, create_pivot_table
from implementation.data_profiling import profile_data
from implementation.time_series import time_series_operations
from implementation.memory_optimization import optimize_memory_usage
from implementation.filtering import filter_data
from implementation.validation import validate_data

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize FastMCP server instance
mcp = FastMCP("Pandas-MCP-DataAnalysis")

# Custom exception for pandas-related errors
class PandasMCPError(Exception):
    """Custom exception for pandas MCP-related errors"""
    pass

# ═══════════════════════════════════════════════════════════════════════════════
# DATA I/O TOOLS
# ═══════════════════════════════════════════════════════════════════════════════

@mcp.tool(
    name="load_data",
    description="""Load and parse data from multiple file formats with advanced options for data ingestion. 

This comprehensive tool supports CSV, Excel, JSON, Parquet, and HDF5 formats with intelligent 
parsing capabilities. It provides customizable encoding detection, selective column loading, 
and efficient data processing for optimal performance.

**Smart Loading Strategy**:
1. Automatically detects file format from extension
2. Performs encoding detection for text files
3. Provides memory-efficient loading with chunking support
4. Validates data integrity during loading
5. Generates comprehensive metadata and quality reports

**Supported Formats**:
- **CSV**: Comma-separated values with customizable delimiters
- **Excel**: .xlsx and .xls files with multi-sheet support
- **JSON**: Structured JSON data with nested object handling
- **Parquet**: High-performance columnar format
- **HDF5**: Hierarchical data format for large datasets

**Performance Optimization**:
- Selective column loading to reduce memory usage
- Row limiting for large dataset sampling
- Automatic data type inference and optimization
- Memory usage reporting and recommendations

**Prerequisites**: File must exist and be readable
**Tools to use after this**: profile_data() for initial analysis, clean_data() for quality improvement

Use this tool when:
- Starting data analysis workflows ("Load my dataset")
- Exploring new datasets for the first time
- Converting between different data formats
- Sampling large datasets for initial analysis
- Validating data structure and quality"""
)
async def load_data_tool(
    file_path: str,
    file_format: Optional[str] = None,
    sheet_name: Optional[str] = None,
    encoding: Optional[str] = None,
    columns: Optional[List[str]] = None,
    nrows: Optional[int] = None
) -> dict:
    """
    Load data from various file formats with comprehensive parsing options.
    
    Args:
        file_path: Absolute path to the data file
        file_format: File format (csv, excel, json, parquet, hdf5) - auto-detected if None
        sheet_name: Excel sheet name or index (for Excel files)
        encoding: Character encoding (utf-8, latin-1, etc.) - auto-detected if None
        columns: List of specific columns to load (None loads all columns)
        nrows: Maximum number of rows to load (None loads all rows)
    
    Returns:
        Dictionary containing:
        - data: Loaded dataset in structured format
        - metadata: File information, data types, and loading statistics
        - data_info: Shape, columns, and data quality metrics
        - loading_stats: Performance metrics and parsing information
    """
    try:
        logger.info(f"Loading data from: {file_path}")
        return load_data_file(file_path, file_format, sheet_name, encoding, columns, nrows)
    except Exception as e:
        logger.error(f"Data loading error: {e}")
        return {
            "content": [{"text": f'{{"success": false, "error": "{str(e)}", "error_type": "DataLoadingError"}}'}],
            "_meta": {"tool": "load_data", "error": "DataLoadingError"},
            "isError": True
        }

@mcp.tool(
    name="save_data",
    description="""Save processed data to multiple file formats with optimization options for storage efficiency.

This tool provides comprehensive data export capabilities with format-specific optimizations,
compression options, and data integrity validation. It supports all major data formats
with intelligent format selection and performance tuning.

**Export Strategy**:
1. Automatically selects optimal format based on data characteristics
2. Applies compression for space efficiency
3. Validates data integrity before and after export
4. Provides detailed export statistics and recommendations
5. Supports incremental updates for large datasets

**Format Optimization**:
- **CSV**: Configurable separators and encoding options
- **Excel**: Multi-sheet support with formatting preservation
- **JSON**: Nested structure handling with compression
- **Parquet**: Columnar compression for analytics workloads
- **HDF5**: Hierarchical storage for complex data structures

**Performance Features**:
- Automatic compression selection based on data type
- Memory-efficient writing for large datasets
- Progress tracking for long-running operations
- Storage space optimization recommendations

**Prerequisites**: Data must be in valid format
**Tools to use before this**: clean_data() for quality assurance, optimize_memory() for large datasets

Use this tool when:
- Exporting processed data for sharing or archival
- Converting between different data formats
- Creating compressed versions of large datasets
- Saving intermediate results in analysis workflows
- Preparing data for external systems or applications"""
)
async def save_data_tool(
    data: dict,
    file_path: str,
    file_format: Optional[str] = None,
    index: bool = True
) -> dict:
    """
    Save data to various file formats with comprehensive export options.
    
    Args:
        data: Data dictionary to save (structured data format)
        file_path: Absolute path where the file will be saved
        file_format: Output format (csv, excel, json, parquet, hdf5) - auto-detected if None
        index: Whether to include row indices in the output file
    
    Returns:
        Dictionary containing:
        - save_info: File save details including size and format
        - compression_stats: Space savings and compression metrics
        - export_stats: Performance metrics and data integrity checks
        - file_details: Output file specifications and validation
    """
    try:
        logger.info(f"Saving data to: {file_path}")
        return save_data_file(data, file_path, file_format, index)
    except Exception as e:
        logger.error(f"Data saving error: {e}")
        return {
            "content": [{"text": f'{{"success": false, "error": "{str(e)}", "error_type": "DataSavingError"}}'}],
            "_meta": {"tool": "save_data", "error": "DataSavingError"},
            "isError": True
        }

# ═══════════════════════════════════════════════════════════════════════════════
# STATISTICAL ANALYSIS TOOLS
# ═══════════════════════════════════════════════════════════════════════════════

@mcp.tool(
    name="statistical_summary",
    description="""Generate comprehensive statistical summaries with descriptive statistics, distribution analysis, and data profiling.

This tool provides detailed insights into data characteristics including central tendencies,
variability, and distribution shapes. It goes beyond basic statistics to provide actionable
insights for data analysis and decision-making.

**Analysis Strategy**:
1. Computes comprehensive descriptive statistics
2. Analyzes data distributions and normality
3. Identifies outliers and anomalies
4. Provides data quality assessments
5. Generates actionable insights and recommendations

**Statistical Measures**:
- **Central Tendency**: Mean, median, mode with confidence intervals
- **Variability**: Standard deviation, variance, range, IQR
- **Distribution**: Skewness, kurtosis, normality tests
- **Outlier Detection**: Z-score, IQR-based, and statistical methods
- **Data Quality**: Missing values, duplicates, consistency checks

**Advanced Features**:
- Distribution fitting and goodness-of-fit tests
- Correlation analysis between variables
- Seasonal pattern detection for time series
- Categorical variable analysis and frequency distributions
- Statistical significance testing for group comparisons

**Prerequisites**: Data must be loaded and accessible
**Tools to use after this**: correlation_analysis() for relationships, hypothesis_testing() for inference

Use this tool when:
- Exploring new datasets for the first time
- Understanding data characteristics and quality
- Identifying patterns and anomalies in data
- Preparing data for modeling or analysis
- Generating reports for stakeholders"""
)
async def statistical_summary_tool(
    file_path: str,
    columns: Optional[List[str]] = None,
    include_distributions: bool = False
) -> dict:
    """
    Generate comprehensive statistical summary with advanced analytics.
    
    Args:
        file_path: Absolute path to the data file
        columns: List of specific columns to analyze (None analyzes all numerical columns)
        include_distributions: Whether to include distribution analysis and normality tests
    
    Returns:
        Dictionary containing:
        - descriptive_stats: Mean, median, mode, standard deviation, and percentiles
        - distribution_analysis: Skewness, kurtosis, and normality test results
        - data_profiling: Data types, missing values, and unique value counts
        - outlier_detection: Outlier identification and statistical anomalies
    """
    try:
        logger.info(f"Generating statistical summary for: {file_path}")
        return get_statistical_summary(file_path, columns, include_distributions)
    except Exception as e:
        logger.error(f"Statistical analysis error: {e}")
        return {
            "content": [{"text": f'{{"success": false, "error": "{str(e)}", "error_type": "StatisticalAnalysisError"}}'}],
            "_meta": {"tool": "statistical_summary", "error": "StatisticalAnalysisError"},
            "isError": True
        }

@mcp.tool(
    name="correlation_analysis",
    description="""Perform comprehensive correlation analysis with multiple correlation methods and significance testing.

This tool provides detailed insights into variable relationships, dependency patterns, and 
statistical significance of correlations. It supports multiple correlation methods and 
provides actionable insights for feature selection and data understanding.

**Correlation Methods**:
- **Pearson**: Linear relationships between continuous variables
- **Spearman**: Monotonic relationships and ordinal data
- **Kendall**: Rank-based correlation for non-parametric data

**Analysis Features**:
1. Computes correlation matrices with significance testing
2. Identifies strong positive and negative correlations
3. Provides p-values and confidence intervals
4. Detects multicollinearity issues
5. Generates correlation insights and recommendations

**Advanced Capabilities**:
- Partial correlation analysis controlling for confounding variables
- Time-lagged correlation for temporal data
- Categorical variable association measures
- Correlation stability analysis across data subsets
- Feature importance ranking based on correlations

**Visualization Support**:
- Correlation heatmap data preparation
- Network graph data for correlation relationships
- Scatter plot recommendations for strong correlations
- Hierarchical clustering of correlated variables

**Prerequisites**: Data must contain numerical variables
**Tools to use before this**: statistical_summary() for data overview
**Tools to use after this**: hypothesis_testing() for statistical inference

Use this tool when:
- Exploring relationships between variables
- Feature selection for machine learning
- Identifying redundant or highly correlated features
- Understanding data structure and dependencies
- Detecting multicollinearity in regression analysis"""
)
async def correlation_analysis_tool(
    file_path: str,
    method: str = "pearson",
    columns: Optional[List[str]] = None
) -> dict:
    """
    Perform comprehensive correlation analysis with statistical significance testing.
    
    Args:
        file_path: Absolute path to the data file
        method: Correlation method (pearson, spearman, kendall) for different data types
        columns: List of specific columns to analyze (None analyzes all numerical columns)
    
    Returns:
        Dictionary containing:
        - correlation_matrix: Full correlation matrix with coefficient values
        - significance_tests: P-values and statistical significance indicators
        - correlation_insights: Strong correlations and dependency patterns
        - visualization_data: Data formatted for correlation heatmaps and plots
    """
    try:
        logger.info(f"Performing correlation analysis on: {file_path}")
        return get_correlation_analysis(file_path, method, columns)
    except Exception as e:
        logger.error(f"Correlation analysis error: {e}")
        return {
            "content": [{"text": f'{{"success": false, "error": "{str(e)}", "error_type": "CorrelationAnalysisError"}}'}],
            "_meta": {"tool": "correlation_analysis", "error": "CorrelationAnalysisError"},
            "isError": True
        }

@mcp.tool(
    name="hypothesis_testing",
    description="""Perform comprehensive statistical hypothesis testing with multiple test types and advanced analysis.

This tool supports a wide range of statistical tests including t-tests, chi-square tests, 
ANOVA, and normality tests. It provides statistical inference with confidence intervals,
p-values, and effect size calculations for robust decision-making.

**Supported Test Types**:
- **t_test**: One-sample, two-sample, and paired t-tests
- **chi_square**: Independence tests for categorical variables
- **anova**: One-way and two-way analysis of variance
- **normality**: Shapiro-Wilk, Kolmogorov-Smirnov tests
- **mann_whitney**: Non-parametric alternative to t-test

**Statistical Inference**:
1. Computes test statistics and p-values
2. Provides confidence intervals for parameters
3. Calculates effect sizes (Cohen's d, eta-squared)
4. Performs power analysis and sample size recommendations
5. Generates statistical interpretation and conclusions

**Advanced Features**:
- Multiple comparison corrections (Bonferroni, FDR)
- Assumption checking and validation
- Bootstrap confidence intervals
- Bayesian hypothesis testing alternatives
- Practical significance assessment

**Result Interpretation**:
- Statistical significance vs practical significance
- Effect size interpretation guidelines
- Power analysis and sample size adequacy
- Assumption violation warnings and alternatives
- Actionable conclusions and recommendations

**Prerequisites**: Data must be appropriate for the chosen test
**Tools to use before this**: statistical_summary() for data exploration
**Tools to use after this**: Additional analysis based on test results

Use this tool when:
- Testing specific hypotheses about your data
- Comparing groups or treatments
- Validating assumptions for modeling
- Making statistical inferences and decisions
- Preparing results for publication or reporting"""
)
async def hypothesis_testing_tool(
    file_path: str,
    test_type: str,
    column1: str,
    column2: Optional[str] = None,
    alpha: float = 0.05
) -> dict:
    """
    Perform comprehensive statistical hypothesis testing with multiple test types and advanced analysis.
    
    Args:
        file_path: Absolute path to the data file
        test_type: Type of hypothesis test (t_test, chi_square, anova, normality, mann_whitney)
        column1: Primary column for testing (numerical or categorical based on test type)
        column2: Secondary column for two-sample tests (None for single-sample tests)
        alpha: Significance level for hypothesis testing (typically 0.05, 0.01, or 0.10)
    
    Returns:
        Dictionary containing:
        - test_results: Statistical test results including test statistic and p-value
        - effect_size: Effect size measures and practical significance assessment
        - confidence_intervals: Confidence intervals for parameters and differences
        - interpretation: Statistical interpretation and practical conclusions
    """
    try:
        logger.info(f"Performing hypothesis testing on: {file_path}")
        return get_statistical_summary(file_path, test_type, column1, column2, alpha)
    except Exception as e:
        logger.error(f"Hypothesis testing error: {e}")
        return {
            "content": [{"text": f'{{"success": false, "error": "{str(e)}", "error_type": "HypothesisTestingError"}}'}],
            "_meta": {"tool": "hypothesis_testing", "error": "HypothesisTestingError"},
            "isError": True
        }

# ═══════════════════════════════════════════════════════════════════════════════
# DATA CLEANING TOOLS
# ═══════════════════════════════════════════════════════════════════════════════

@mcp.tool(
    name="handle_missing_data",
    description="""Comprehensive missing data handling with multiple strategies for detection, imputation, and removal.

This tool provides sophisticated approaches to data completeness including statistical 
imputation methods, missing data pattern analysis, and intelligent handling strategies
based on data characteristics and analysis requirements.

**Missing Data Strategies**:
- **detect**: Comprehensive missing data analysis and pattern identification
- **impute**: Statistical imputation using various methods
- **remove**: Intelligent removal of missing data with impact analysis
- **analyze**: Deep analysis of missing data patterns and mechanisms

**Imputation Methods**:
- **mean/median/mode**: Central tendency imputation for numerical/categorical data
- **forward_fill/backward_fill**: Temporal imputation for time series
- **interpolate**: Mathematical interpolation for smooth data
- **regression**: Predictive imputation using other variables
- **knn**: K-nearest neighbors imputation

**Pattern Analysis**:
1. Identifies missing data patterns (MCAR, MAR, MNAR)
2. Analyzes correlation between missingness and other variables
3. Provides recommendations for optimal handling strategies
4. Assesses impact of different imputation methods
5. Validates imputation quality and bias assessment

**Quality Assurance**:
- Before/after comparison of data completeness
- Imputation quality metrics and validation
- Bias assessment and correction recommendations
- Impact analysis on downstream analysis
- Alternative strategy suggestions

**Prerequisites**: Data must be loaded and accessible
**Tools to use after this**: clean_data() for additional quality improvements, validate_data() for verification

Use this tool when:
- Dealing with incomplete datasets
- Preparing data for analysis or modeling
- Understanding missing data patterns and mechanisms
- Choosing optimal imputation strategies
- Validating data completeness requirements"""
)
async def handle_missing_data_tool(
    file_path: str,
    strategy: str = "detect",
    method: Optional[str] = None,
    columns: Optional[List[str]] = None
) -> dict:
    """
    Handle missing data with comprehensive strategies and statistical methods.
    
    Args:
        file_path: Absolute path to the data file
        strategy: Missing data strategy (detect, impute, remove, analyze)
        method: Imputation method (mean, median, mode, forward_fill, backward_fill, interpolate)
        columns: List of specific columns to process (None processes all columns)
    
    Returns:
        Dictionary containing:
        - missing_data_report: Detailed analysis of missing data patterns
        - imputation_results: Results of imputation with quality metrics
        - data_completeness: Before/after comparison of data completeness
        - strategy_recommendations: Suggested approaches for optimal data handling
    """
    try:
        logger.info(f"Handling missing data in: {file_path}")
        return handle_missing_data(file_path, strategy, method, columns)
    except Exception as e:
        logger.error(f"Missing data handling error: {e}")
        return {
            "content": [{"text": f'{{"success": false, "error": "{str(e)}", "error_type": "MissingDataError"}}'}],
            "_meta": {"tool": "handle_missing_data", "error": "MissingDataError"},
            "isError": True
        }

@mcp.tool(
    name="clean_data",
    description="""Comprehensive data cleaning with advanced outlier detection, duplicate removal, and intelligent type conversion.

This tool provides sophisticated data quality improvement with statistical validation
and automated data standardization. It combines multiple cleaning techniques to ensure
data integrity and consistency for downstream analysis.

**Cleaning Operations**:
- **Duplicate Detection**: Intelligent duplicate identification and removal
- **Outlier Detection**: Statistical outlier identification using IQR and Z-score methods
- **Type Conversion**: Automatic data type optimization and correction
- **Standardization**: Data format standardization and normalization
- **Validation**: Data integrity checks and quality assurance

**Outlier Detection Methods**:
- **IQR Method**: Interquartile range-based outlier detection
- **Z-Score**: Standard deviation-based outlier identification
- **Isolation Forest**: Machine learning-based anomaly detection
- **Local Outlier Factor**: Density-based outlier detection
- **Statistical Tests**: Grubbs test and other statistical methods

**Quality Improvements**:
1. Removes exact and near-duplicate records
2. Standardizes data formats and representations
3. Corrects data type inconsistencies
4. Validates data integrity and consistency
5. Provides detailed cleaning reports and recommendations

**Performance Optimization**:
- Memory-efficient processing for large datasets
- Parallel processing for computationally intensive operations
- Progress tracking for long-running cleaning operations
- Optimization recommendations for future data processing

**Prerequisites**: Data must be loaded and accessible
**Tools to use before this**: handle_missing_data() for completeness
**Tools to use after this**: validate_data() for quality verification

Use this tool when:
- Preparing data for analysis or modeling
- Improving data quality and consistency
- Removing noise and anomalies from datasets
- Standardizing data formats and types
- Ensuring data integrity before processing"""
)
async def clean_data_tool(
    file_path: str,
    remove_duplicates: bool = False,
    detect_outliers: bool = False,
    convert_types: bool = False
) -> dict:
    """
    Perform comprehensive data cleaning with advanced quality improvement techniques.
    
    Args:
        file_path: Absolute path to the data file
        remove_duplicates: Whether to identify and remove duplicate records
        detect_outliers: Whether to detect outliers using statistical methods (IQR, Z-score)
        convert_types: Whether to automatically convert data types for optimization
    
    Returns:
        Dictionary containing:
        - cleaning_report: Detailed summary of cleaning operations performed
        - data_quality_metrics: Before/after data quality comparison
        - outlier_analysis: Outlier detection results and recommendations
        - type_conversion_log: Data type changes and optimization results
    """
    try:
        logger.info(f"Cleaning data in: {file_path}")
        return clean_data(file_path, remove_duplicates, detect_outliers, convert_types)
    except Exception as e:
        logger.error(f"Data cleaning error: {e}")
        return {
            "content": [{"text": f'{{"success": false, "error": "{str(e)}", "error_type": "DataCleaningError"}}'}],
            "_meta": {"tool": "clean_data", "error": "DataCleaningError"},
            "isError": True
        }

# ═══════════════════════════════════════════════════════════════════════════════
# DATA TRANSFORMATION TOOLS
# ═══════════════════════════════════════════════════════════════════════════════

@mcp.tool(
    name="groupby_operations",
    description="""Perform sophisticated groupby operations with aggregations, transformations, and filtering.

This tool provides comprehensive data grouping capabilities with multiple aggregation
functions and advanced analytical operations. It enables complex data summarization
and analysis patterns commonly used in business intelligence and data analysis.

**Grouping Strategy**:
1. Groups data by specified columns with intelligent handling
2. Applies multiple aggregation functions simultaneously
3. Supports custom aggregation logic and calculations
4. Provides group-level statistics and insights
5. Enables hierarchical grouping and multi-level analysis

**Aggregation Functions**:
- **sum**: Total values within groups
- **mean**: Average values with confidence intervals
- **count**: Record counts and frequency analysis
- **min/max**: Extreme values and range analysis
- **std/var**: Variability measures within groups
- **median**: Robust central tendency measures
- **custom**: User-defined aggregation functions

**Advanced Features**:
- Multi-level grouping with hierarchical analysis
- Conditional aggregation based on filters
- Group-wise transformations and calculations
- Statistical significance testing between groups
- Performance optimization for large datasets

**Filtering Integration**:
- Pre-grouping filters for data subset analysis
- Post-aggregation filters for result refinement
- Dynamic filtering based on group characteristics
- Conditional logic for complex business rules

**Prerequisites**: Data must be loaded with grouping columns present
**Tools to use after this**: statistical_summary() for group analysis, pivot_table() for cross-tabulation

Use this tool when:
- Summarizing data by categories or segments
- Calculating group-wise statistics and metrics
- Analyzing patterns across different data segments
- Creating aggregated reports and dashboards
- Performing business intelligence analysis"""
)
async def groupby_operations_tool(
    file_path: str,
    group_by: List[str],
    operations: Dict[str, str],
    filter_condition: Optional[str] = None
) -> dict:
    """
    Perform sophisticated groupby operations with comprehensive aggregation options.
    
    Args:
        file_path: Absolute path to the data file
        group_by: List of columns to group by
        operations: Dictionary of column:operation pairs (sum, mean, count, min, max, std)
        filter_condition: Optional filter condition to apply before grouping
    
    Returns:
        Dictionary containing:
        - grouped_results: Results of groupby operations with aggregated data
        - group_statistics: Statistics about group sizes and distributions
        - aggregation_summary: Summary of all aggregation operations performed
        - performance_metrics: Groupby operation performance and optimization insights
    """
    try:
        logger.info(f"Performing groupby operations on: {file_path}")
        return groupby_operations(file_path, group_by, operations, filter_condition)
    except Exception as e:
        logger.error(f"Groupby operations error: {e}")
        return {
            "content": [{"text": f'{{"success": false, "error": "{str(e)}", "error_type": "GroupbyOperationsError"}}'}],
            "_meta": {"tool": "groupby_operations", "error": "GroupbyOperationsError"},
            "isError": True
        }

@mcp.tool(
    name="merge_datasets",
    description="""Merge and join datasets with sophisticated join operations and relationship analysis.

This tool supports all SQL-style joins (inner, outer, left, right) with comprehensive
data integration capabilities and merge conflict resolution. It provides intelligent
handling of data relationships and quality assessment of merged results.

**Join Types**:
- **inner**: Only matching records from both datasets
- **outer**: All records from both datasets with null filling
- **left**: All records from left dataset with matching from right
- **right**: All records from right dataset with matching from left

**Merge Strategy**:
1. Analyzes data relationships and key distributions
2. Validates merge keys and identifies potential issues
3. Performs intelligent duplicate handling
4. Provides merge statistics and quality assessment
5. Offers optimization suggestions for large datasets

**Quality Assurance**:
- Pre-merge validation of key columns
- Duplicate detection and handling strategies
- Data type compatibility checking
- Merge result validation and quality metrics
- Performance optimization for large datasets

**Relationship Analysis**:
- One-to-one, one-to-many, many-to-many detection
- Key distribution analysis and cardinality assessment
- Merge effectiveness evaluation
- Data overlap and coverage analysis
- Referential integrity validation

**Advanced Features**:
- Fuzzy matching for approximate joins
- Multi-column merge key support
- Custom merge logic and transformations
- Incremental merge support for large datasets
- Conflict resolution strategies

**Prerequisites**: Both datasets must be accessible and contain merge keys
**Tools to use before this**: profile_data() for key analysis
**Tools to use after this**: validate_data() for merge quality assessment

Use this tool when:
- Combining data from multiple sources
- Enriching datasets with additional information
- Creating comprehensive analytical datasets
- Integrating related data tables
- Performing data warehouse-style operations"""
)
async def merge_datasets_tool(
    left_file: str,
    right_file: str,
    join_type: str = "inner",
    left_on: Optional[str] = None,
    right_on: Optional[str] = None,
    on: Optional[str] = None
) -> dict:
    """
    Merge and join datasets with comprehensive integration capabilities.
    
    Args:
        left_file: Absolute path to the left dataset file
        right_file: Absolute path to the right dataset file
        join_type: Type of join operation (inner, outer, left, right)
        left_on: Column name in left dataset for joining
        right_on: Column name in right dataset for joining
        on: Common column name for joining (if same in both datasets)
    
    Returns:
        Dictionary containing:
        - merged_data: Results of the merge operation
        - merge_statistics: Statistics about the merge operation and data overlap
        - data_quality_report: Quality assessment of the merged dataset
        - relationship_analysis: Analysis of data relationships and join effectiveness
    """
    try:
        logger.info(f"Merging datasets: {left_file} and {right_file}")
        return merge_datasets(left_file, right_file, join_type, left_on, right_on, on)
    except Exception as e:
        logger.error(f"Dataset merge error: {e}")
        return {
            "content": [{"text": f'{{"success": false, "error": "{str(e)}", "error_type": "DatasetMergeError"}}'}],
            "_meta": {"tool": "merge_datasets", "error": "DatasetMergeError"},
            "isError": True
        }

@mcp.tool(
    name="pivot_table",
    description="""Create sophisticated pivot tables and cross-tabulations with advanced aggregation capabilities.

This tool provides comprehensive data summarization with multiple aggregation functions
and hierarchical data organization. It enables complex data reshaping and analysis
patterns commonly used in business reporting and data exploration.

**Pivot Strategy**:
1. Reshapes data from long to wide format
2. Creates cross-tabulations with multiple dimensions
3. Applies aggregation functions to summarize data
4. Handles missing values and edge cases intelligently
5. Provides hierarchical indexing for complex analysis

**Aggregation Functions**:
- **mean**: Average values with statistical significance
- **sum**: Total values with subtotals and grand totals
- **count**: Frequency analysis and contingency tables
- **min/max**: Extreme value analysis
- **std/var**: Variability measures across dimensions
- **median**: Robust central tendency measures
- **custom**: User-defined aggregation logic

**Advanced Features**:
- Multi-level row and column indexing
- Percentage calculations and ratios
- Marginal totals and subtotals
- Missing value handling strategies
- Performance optimization for large datasets

**Cross-Tabulation Analysis**:
- Contingency table creation and analysis
- Chi-square tests for independence
- Percentage breakdowns by row/column/total
- Statistical significance testing
- Association strength measures

**Visualization Support**:
- Data formatting for heatmaps and charts
- Hierarchical data structure for tree maps
- Time series pivot for trend analysis
- Categorical analysis for bar charts

**Prerequisites**: Data must contain categorical columns for pivoting
**Tools to use before this**: groupby_operations() for preliminary analysis
**Tools to use after this**: statistical_summary() for pivot result analysis

Use this tool when:
- Creating summary reports and dashboards
- Analyzing data across multiple dimensions
- Performing cross-tabulation analysis
- Reshaping data for visualization
- Creating business intelligence reports"""
)
async def pivot_table_tool(
    file_path: str,
    index: List[str],
    columns: Optional[List[str]] = None,
    values: Optional[List[str]] = None,
    aggfunc: str = "mean"
) -> dict:
    """
    Create sophisticated pivot tables with comprehensive aggregation options.
    
    Args:
        file_path: Absolute path to the data file
        index: List of columns to use as row index
        columns: List of columns to use as column headers (None for simple aggregation)
        values: List of columns to aggregate (None uses all numerical columns)
        aggfunc: Aggregation function (mean, sum, count, min, max, std, var)
    
    Returns:
        Dictionary containing:
        - pivot_results: The pivot table with aggregated data
        - summary_statistics: Statistical summary of the pivot operation
        - data_insights: Key insights and patterns from the pivot analysis
        - visualization_data: Data formatted for pivot table visualization
    """
    try:
        logger.info(f"Creating pivot table for: {file_path}")
        return create_pivot_table(file_path, index, columns, values, aggfunc)
    except Exception as e:
        logger.error(f"Pivot table error: {e}")
        return {
            "content": [{"text": f'{{"success": false, "error": "{str(e)}", "error_type": "PivotTableError"}}'}],
            "_meta": {"tool": "pivot_table", "error": "PivotTableError"},
            "isError": True
        }

# ═══════════════════════════════════════════════════════════════════════════════
# TIME SERIES TOOLS
# ═══════════════════════════════════════════════════════════════════════════════

@mcp.tool(
    name="time_series_operations",
    description="""Perform comprehensive time series operations with advanced temporal analysis capabilities.

This tool supports resampling, rolling windows, lag features, trend analysis, and
seasonality detection for temporal data insights. It provides sophisticated time
series analysis capabilities for forecasting and pattern recognition.

**Time Series Operations**:
- **resample**: Aggregate data at different time frequencies
- **rolling_mean**: Moving averages with customizable windows
- **lag**: Create lagged features for predictive modeling
- **trend**: Trend analysis and decomposition
- **seasonality**: Seasonal pattern detection and analysis

**Temporal Analysis**:
1. Automatic datetime parsing and validation
2. Time series decomposition (trend, seasonal, residual)
3. Stationarity testing and transformation
4. Autocorrelation and partial autocorrelation analysis
5. Seasonal pattern identification and quantification

**Resampling Capabilities**:
- **D**: Daily aggregation with business day handling
- **W**: Weekly aggregation with customizable week start
- **M**: Monthly aggregation with period-end alignment
- **Q**: Quarterly analysis for business reporting
- **Y**: Annual aggregation for long-term trends

**Advanced Features**:
- Missing timestamp handling and interpolation
- Irregular time series processing
- Multi-variate time series analysis
- Change point detection
- Anomaly detection in temporal data

**Forecasting Support**:
- Trend extrapolation and projection
- Seasonal adjustment and normalization
- Feature engineering for time series modeling
- Cross-validation for temporal data
- Performance metrics for forecasting accuracy

**Prerequisites**: Data must contain datetime column
**Tools to use before this**: load_data() with proper datetime parsing
**Tools to use after this**: statistical_summary() for temporal pattern analysis

Use this tool when:
- Analyzing temporal patterns and trends
- Preparing data for forecasting models
- Detecting seasonal patterns and cycles
- Creating time-based features for modeling
- Performing time series decomposition and analysis"""
)
async def time_series_operations_tool(
    file_path: str,
    date_column: str,
    operation: str,
    window_size: Optional[int] = None,
    frequency: Optional[str] = None
) -> dict:
    """
    Perform comprehensive time series operations with advanced temporal analysis.
    
    Args:
        file_path: Absolute path to the data file
        date_column: Column name containing datetime information
        operation: Time series operation (resample, rolling_mean, lag, trend, seasonality)
        window_size: Window size for rolling operations (required for rolling operations)
        frequency: Frequency for resampling (D, W, M, Q, Y) (required for resampling)
    
    Returns:
        Dictionary containing:
        - time_series_results: Results of the time series operation
        - temporal_analysis: Trend and seasonality analysis
        - statistical_summary: Time series statistical properties
        - forecasting_insights: Patterns and insights for forecasting applications
    """
    try:
        logger.info(f"Performing time series operations on: {file_path}")
        return time_series_operations(file_path, date_column, operation, window_size, frequency)
    except Exception as e:
        logger.error(f"Time series operations error: {e}")
        return {
            "content": [{"text": f'{{"success": false, "error": "{str(e)}", "error_type": "TimeSeriesError"}}'}],
            "_meta": {"tool": "time_series_operations", "error": "TimeSeriesError"},
            "isError": True
        }

# ═══════════════════════════════════════════════════════════════════════════════
# DATA VALIDATION TOOLS
# ═══════════════════════════════════════════════════════════════════════════════

@mcp.tool(
    name="validate_data",
    description="""Comprehensive data validation with advanced constraint checking and quality assessment.

This tool performs range validation, consistency checks, business rule validation,
and data integrity verification with detailed validation reports and error identification.
It ensures data quality and compliance with specified requirements.

**Validation Types**:
- **Range Validation**: Min/max value constraints for numerical data
- **Type Validation**: Data type consistency and format checking
- **Pattern Validation**: Regex pattern matching for structured data
- **Uniqueness Validation**: Duplicate detection and uniqueness constraints
- **Completeness Validation**: Missing value detection and null constraints
- **Referential Integrity**: Foreign key and relationship validation

**Business Rule Validation**:
1. Custom validation rules and logic
2. Cross-field validation and dependencies
3. Conditional validation based on data context
4. Industry-specific validation patterns
5. Compliance checking for regulatory requirements

**Quality Assessment**:
- Data quality scoring and metrics
- Validation violation severity assessment
- Impact analysis of data quality issues
- Recommendations for quality improvement
- Trend analysis of data quality over time

**Validation Rules Structure**:
```
{
    "column_name": {
        "min": minimum_value,
        "max": maximum_value,
        "type": expected_data_type,
        "regex": pattern_string,
        "not_null": boolean,
        "unique": boolean,
        "in_list": [allowed_values]
    }
}
```

**Error Reporting**:
- Detailed violation reports with row-level errors
- Statistical summary of validation results
- Severity classification and prioritization
- Actionable recommendations for error resolution
- Export capabilities for validation reports

**Prerequisites**: Data must be loaded and validation rules defined
**Tools to use before this**: clean_data() for basic quality improvement
**Tools to use after this**: Additional cleaning based on validation results

Use this tool when:
- Ensuring data quality and integrity
- Validating data against business rules
- Preparing data for critical applications
- Monitoring data quality over time
- Compliance checking and auditing"""
)
async def validate_data_tool(
    file_path: str,
    validation_rules: Dict[str, Dict[str, Any]]
) -> dict:
    """
    Perform comprehensive data validation with advanced constraint checking and quality assessment.
    
    Args:
        file_path: Absolute path to the data file
        validation_rules: Dictionary of validation rules with structure:
                         {column_name: {rule_type: rule_value}}
                         Supported rules: min, max, type, regex, not_null, unique, in_list
    
    Returns:
        Dictionary containing:
        - validation_results: Detailed validation results for each column and rule
        - data_quality_score: Overall data quality score and assessment
        - violation_summary: Summary of validation violations and error patterns
        - recommendations: Suggested actions for data quality improvement
    """
    try:
        logger.info(f"Validating data in: {file_path}")
        return validate_data(file_path, validation_rules)
    except Exception as e:
        logger.error(f"Data validation error: {e}")
        return {
            "content": [{"text": f'{{"success": false, "error": "{str(e)}", "error_type": "DataValidationError"}}'}],
            "_meta": {"tool": "validate_data", "error": "DataValidationError"},
            "isError": True
        }

# ═══════════════════════════════════════════════════════════════════════════════
# DATA FILTERING TOOLS
# ═══════════════════════════════════════════════════════════════════════════════

@mcp.tool(
    name="filter_data",
    description="""Advanced data filtering with sophisticated boolean indexing and conditional expressions.

This tool supports complex multi-condition filtering, logical operations, range-based
filtering, and pattern matching with flexible query syntax for precise data selection.
It provides powerful data subsetting capabilities for analysis and reporting.

**Filtering Capabilities**:
- **Comparison Operators**: eq, ne, gt, lt, ge, le for numerical comparisons
- **Membership Operators**: in, not_in for categorical filtering
- **Pattern Matching**: contains, regex for text-based filtering
- **Logical Operators**: AND, OR, NOT for complex conditions
- **Range Filtering**: Between, outside range for numerical data
- **Null Filtering**: is_null, not_null for missing value handling

**Advanced Features**:
1. Multi-condition filtering with logical operators
2. Dynamic filtering based on statistical thresholds
3. Percentile-based filtering for outlier removal
4. Time-based filtering for temporal data
5. Categorical filtering with fuzzy matching

**Filter Condition Structure**:
```
{
    "column_name": {
        "operator": "value"
    }
}
# or simple format:
{
    "column_name": "value"  # defaults to equality
}
```

**Performance Optimization**:
- Efficient indexing for large datasets
- Query optimization and execution planning
- Memory-efficient filtering for large files
- Parallel processing for complex filters
- Progress tracking for long-running operations

**Quality Assurance**:
- Filter validation and syntax checking
- Result set statistics and summaries
- Data quality assessment of filtered results
- Performance metrics and optimization suggestions
- Export capabilities for filtered datasets

**Prerequisites**: Data must be loaded and accessible
**Tools to use before this**: profile_data() for filter planning
**Tools to use after this**: statistical_summary() for filtered data analysis

Use this tool when:
- Selecting specific data subsets for analysis
- Removing outliers and anomalies
- Creating focused datasets for reporting
- Implementing business logic and rules
- Preparing data for specific analytical tasks"""
)
async def filter_data_tool(
    file_path: str,
    filter_conditions: Dict[str, Any],
    output_file: Optional[str] = None
) -> dict:
    """
    Perform advanced data filtering with sophisticated boolean indexing and conditional expressions.
    
    Args:
        file_path: Absolute path to the data file
        filter_conditions: Dictionary of filtering conditions with structure:
                          {column_name: {operator: value}} or {column_name: value}
                          Supported operators: eq, ne, gt, lt, ge, le, in, not_in, contains, regex
        output_file: Optional absolute path to save filtered data (None returns in memory)
    
    Returns:
        Dictionary containing:
        - filtered_data: Results of filtering operation with matching records
        - filter_statistics: Summary of filtering results including row counts
        - data_quality_report: Quality assessment of filtered dataset
        - performance_metrics: Filtering operation performance and efficiency
    """
    try:
        logger.info(f"Filtering data in: {file_path}")
        return filter_data(file_path, filter_conditions, output_file)
    except Exception as e:
        logger.error(f"Data filtering error: {e}")
        return {
            "content": [{"text": f'{{"success": false, "error": "{str(e)}", "error_type": "DataFilteringError"}}'}],
            "_meta": {"tool": "filter_data", "error": "DataFilteringError"},
            "isError": True
        }

# ═══════════════════════════════════════════════════════════════════════════════
# MEMORY OPTIMIZATION TOOLS
# ═══════════════════════════════════════════════════════════════════════════════

@mcp.tool(
    name="optimize_memory",
    description="""Advanced memory optimization for large datasets with intelligent type conversion and chunking strategies.

This tool provides automatic dtype optimization, memory usage analysis, sparse data
handling, and efficient memory allocation for optimal performance with large datasets.
It enables processing of datasets that exceed available memory.

**Optimization Strategies**:
- **Dtype Optimization**: Automatic conversion to memory-efficient data types
- **Sparse Data Handling**: Efficient storage for datasets with many zeros/nulls
- **Chunking**: Process large datasets in manageable chunks
- **Memory Mapping**: Use memory-mapped files for very large datasets
- **Compression**: Apply compression for storage and memory efficiency

**Memory Analysis**:
1. Detailed memory usage profiling by column and data type
2. Identification of memory optimization opportunities
3. Impact assessment of different optimization strategies
4. Performance benchmarking before and after optimization
5. Recommendations for optimal memory configuration

**Chunking Strategies**:
- **Fixed Size**: Process data in fixed-size chunks
- **Adaptive**: Dynamic chunk sizing based on memory availability
- **Column-wise**: Process columns independently for wide datasets
- **Time-based**: Chunk temporal data by time periods
- **Stratified**: Maintain data distribution across chunks

**Performance Features**:
- Parallel processing for chunk operations
- Progress tracking for long-running optimizations
- Memory usage monitoring and alerts
- Automatic garbage collection and cleanup
- Performance metrics and benchmarking

**Optimization Results**:
- Memory usage reduction statistics
- Processing speed improvements
- Storage space savings
- Optimal configuration recommendations
- Performance comparison metrics

**Prerequisites**: Data must be accessible and memory usage must be a concern
**Tools to use before this**: profile_data() for memory analysis
**Tools to use after this**: Continue with optimized data processing

Use this tool when:
- Working with large datasets that exceed memory
- Optimizing data processing performance
- Reducing memory footprint for applications
- Preparing data for memory-constrained environments
- Improving overall system efficiency"""
)
async def optimize_memory_tool(
    file_path: str,
    optimize_dtypes: bool = True,
    chunk_size: Optional[int] = None
) -> dict:
    """
    Perform advanced memory optimization for large datasets with intelligent strategies.
    
    Args:
        file_path: Absolute path to the data file
        optimize_dtypes: Whether to automatically optimize data types for memory efficiency
        chunk_size: Chunk size for processing large files (None for automatic sizing)
    
    Returns:
        Dictionary containing:
        - memory_optimization_results: Before/after memory usage comparison
        - dtype_optimization_log: Details of data type changes and memory savings
        - chunking_strategy: Optimal chunking recommendations for large datasets
        - performance_metrics: Speed and efficiency improvements achieved
    """
    try:
        logger.info(f"Optimizing memory usage for: {file_path}")
        return optimize_memory_usage(file_path, optimize_dtypes, chunk_size)
    except Exception as e:
        logger.error(f"Memory optimization error: {e}")
        return {
            "content": [{"text": f'{{"success": false, "error": "{str(e)}", "error_type": "MemoryOptimizationError"}}'}],
            "_meta": {"tool": "optimize_memory", "error": "MemoryOptimizationError"},
            "isError": True
        }

# ═══════════════════════════════════════════════════════════════════════════════
# DATA PROFILING TOOLS
# ═══════════════════════════════════════════════════════════════════════════════

@mcp.tool(
    name="profile_data",
    description="""Comprehensive data profiling with detailed statistical analysis and quality assessment.

This tool provides dataset overview including shape, data types, missing values,
value distributions, statistical summaries, and data quality metrics for thorough
data exploration and understanding.

**Profiling Components**:
- **Dataset Overview**: Shape, size, memory usage, and basic statistics
- **Column Analysis**: Data types, unique values, missing values, and distributions
- **Data Quality**: Completeness, consistency, validity, and accuracy metrics
- **Statistical Summary**: Descriptive statistics and distribution analysis
- **Correlation Analysis**: Variable relationships and dependencies (optional)
- **Pattern Detection**: Common patterns and anomalies in the data

**Quality Assessment**:
1. Data completeness analysis and missing value patterns
2. Data consistency checks and validation
3. Outlier detection and anomaly identification
4. Duplicate analysis and record uniqueness
5. Data freshness and currency assessment

**Distribution Analysis**:
- Frequency distributions for categorical variables
- Histogram analysis for numerical variables
- Percentile analysis and quartile distributions
- Skewness and kurtosis measurements
- Normality testing and distribution fitting

**Advanced Features**:
- Correlation matrix computation and analysis
- Principal component analysis for dimensionality insight
- Clustering analysis for pattern identification
- Time series profiling for temporal data
- Text analysis for string columns

**Sampling Strategy**:
- Intelligent sampling for large datasets
- Stratified sampling to maintain data distribution
- Random sampling with statistical validity
- Time-based sampling for temporal data
- Quality-preserving sampling techniques

**Prerequisites**: Data must be loaded and accessible
**Tools to use after this**: Based on profiling results, use appropriate cleaning or analysis tools

Use this tool when:
- Exploring new datasets for the first time
- Understanding data characteristics and quality
- Planning data analysis and modeling strategies
- Documenting data for stakeholders
- Identifying data quality issues and opportunities"""
)
async def profile_data_tool(
    file_path: str,
    include_correlations: bool = False,
    sample_size: Optional[int] = None
) -> dict:
    """
    Perform comprehensive data profiling with detailed statistical analysis and quality assessment.
    
    Args:
        file_path: Absolute path to the data file
        include_correlations: Whether to include correlation analysis between variables
        sample_size: Number of rows to sample for large datasets (None uses full dataset)
    
    Returns:
        Dictionary containing:
        - data_profile: Comprehensive dataset overview including shape, types, and statistics
        - column_analysis: Detailed analysis of each column including distributions
        - data_quality_metrics: Missing values, duplicates, and data quality indicators
        - correlation_matrix: Variable correlations (if include_correlations is True)
    """
    try:
        logger.info(f"Profiling data in: {file_path}")
        return profile_data(file_path, include_correlations, sample_size)
    except Exception as e:
        logger.error(f"Data profiling error: {e}")
        return {
            "content": [{"text": f'{{"success": false, "error": "{str(e)}", "error_type": "DataProfilingError"}}'}],
            "_meta": {"tool": "profile_data", "error": "DataProfilingError"},
            "isError": True
        }

def main():
    """
    Main entry point to start the FastMCP server using the specified transport.
    Chooses between stdio and SSE based on MCP_TRANSPORT environment variable.
    """
    transport = os.getenv("MCP_TRANSPORT", "stdio").lower()
    
    if transport == "sse":
        host = os.getenv("MCP_SSE_HOST", "0.0.0.0")
        port = int(os.getenv("MCP_SSE_PORT", "8000"))
        print(f"Starting Pandas MCP Data Analysis Server on {host}:{port}", file=sys.stderr)
        mcp.run(transport="sse", host=host, port=port)
    else:
        print("Starting Pandas MCP Data Analysis Server with stdio transport", file=sys.stderr)
        mcp.run(transport="stdio")

if __name__ == "__main__":
    main()
