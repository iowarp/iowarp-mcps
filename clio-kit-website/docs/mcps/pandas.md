---
title: Pandas MCP
description: "Pandas MCP - Advanced Data Analysis for LLMs with comprehensive pandas operations"
---

import MCPDetail from '@site/src/components/MCPDetail';

<MCPDetail
  name="Pandas"
  icon="🐼"
  category="Data Processing"
  description="Pandas MCP - Advanced Data Analysis for LLMs with comprehensive pandas operations"
  version="2.2.3"
  actions={["load_data", "save_data", "statistical_summary", "correlation_analysis", "hypothesis_testing", "handle_missing_data", "clean_data", "groupby_operations", "merge_datasets", "pivot_table", "time_series_operations", "validate_data", "filter_data", "optimize_memory", "profile_data", "profile_csv"]}
  platforms={["claude", "cursor", "vscode"]}
  keywords={["pandas", "data-analysis", "statistical-analysis", "data-science", "data-manipulation", "time-series", "data-cleaning", "data-transformation", "mcp", "llm-integration"]}
  license="BSD-3-Clause"
  tools={[{"name": "load_data", "description": "Load and parse data from CSV, Excel, JSON, Parquet, or HDF5 files with optional column selection and row limiting.", "function_name": "load_data"}, {"name": "save_data", "description": "Save data to CSV, Excel, JSON, Parquet, or HDF5 with auto-detected format and optional index inclusion.", "function_name": "save_data"}, {"name": "statistical_summary", "description": "Compute descriptive statistics, distribution analysis, and outlier detection for numerical and categorical columns.", "function_name": "statistical_summary"}, {"name": "correlation_analysis", "description": "Compute correlation matrices (Pearson, Spearman, or Kendall) with significance testing and strong-correlation detection.", "function_name": "correlation_analysis"}, {"name": "hypothesis_testing", "description": "Run statistical hypothesis tests (t-test, chi-square, ANOVA, normality, Mann-Whitney) with p-values and effect sizes.", "function_name": "hypothesis_testing"}, {"name": "handle_missing_data", "description": "Detect, impute, or remove missing values using strategies like mean/median/mode fill, forward/backward fill, or interpolation.", "function_name": "handle_missing_data"}, {"name": "clean_data", "description": "Remove duplicates, detect outliers via IQR/Z-score, and optimize data types in a single pass.", "function_name": "clean_data"}, {"name": "groupby_operations", "description": "Group data by columns and apply aggregations (sum, mean, count, min, max, std, median) with optional pre-filter.", "function_name": "groupby_operations"}, {"name": "merge_datasets", "description": "Join two datasets using inner, outer, left, or right joins on specified key columns.", "function_name": "merge_datasets"}, {"name": "pivot_table", "description": "Create pivot tables with configurable row index, column headers, value columns, and aggregation function.", "function_name": "pivot_table"}, {"name": "time_series_operations", "description": "Resample, compute rolling statistics, create lag features, or difference a time series.", "function_name": "time_series_operations"}, {"name": "validate_data", "description": "Validate columns against rules for min/max range, data type, nullability, uniqueness, and regex patterns.", "function_name": "validate_data"}, {"name": "filter_data", "description": "Filter rows using comparison, membership, pattern-matching, and null-check operators across multiple columns.", "function_name": "filter_data"}, {"name": "optimize_memory", "description": "Analyze and reduce DataFrame memory usage through automatic dtype optimization and chunked-processing recommendations.", "function_name": "optimize_memory"}, {"name": "profile_data", "description": "Generate a full dataset profile: shape, types, missing values, distributions, quality checks, and optional correlations.", "function_name": "profile_data"}, {"name": "profile_csv", "description": "Quickly profile a CSV file: row/column counts, per-column dtype, null counts, and min/max/mean for numeric columns.", "function_name": "profile_csv"}]}
>

### 1. Data Loading and Profiling
```
I have a large CSV file with sales data that I need to load and get a comprehensive profile including data types, missing values, and basic statistics.
```

**Tools called:**
- `load_data` - Load CSV file with intelligent format detection
- `profile_data` - Get comprehensive data profile and quality metrics
- `statistical_summary` - Generate descriptive statistics and distributions

### 2. Data Cleaning and Quality Assessment
```
My dataset has missing values and outliers that need to be handled. I also want to remove duplicates and validate the data quality.
```

**Tools called:**
- `handle_missing_data` - Impute missing values with appropriate strategies
- `clean_data` - Remove outliers, duplicates, and optimize data types
- `validate_data` - Apply business rules and data quality checks

### 3. Statistical Analysis and Correlation
```
Analyze the relationships between different variables in my dataset and perform hypothesis testing to validate my assumptions.
```

**Tools called:**
- `correlation_analysis` - Calculate correlation matrices with different methods
- `hypothesis_testing` - Perform t-tests, ANOVA, and normality tests
- `statistical_summary` - Generate comprehensive statistical insights

### 4. Data Transformation and Aggregation
```
I need to group my sales data by region and product category, then create pivot tables for cross-analysis and merge with customer data.
```

**Tools called:**
- `groupby_operations` - Group data and perform multiple aggregations
- `pivot_table` - Create pivot tables with multi-level indexing
- `merge_datasets` - Join datasets using different merge strategies

### 5. Time Series Analysis and Filtering
```
Analyze my time series data by resampling to different frequencies, calculating rolling averages, and filtering specific date ranges.
```

**Tools called:**
- `time_series_operations` - Resample, rolling windows, and lag features
- `filter_data` - Apply complex time-based filtering conditions
- `statistical_summary` - Analyze time series patterns and trends

### 6. Data Export and Memory Optimization
```
Optimize memory usage of my large dataset and export the cleaned data to multiple formats for different teams.
```

**Tools called:**
- `optimize_memory` - Reduce memory usage with dtype optimization
- `save_data` - Export to CSV, Excel, Parquet, and JSON formats
- `profile_data` - Verify optimization results and final data quality

</MCPDetail>
