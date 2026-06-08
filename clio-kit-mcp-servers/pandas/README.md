# Pandas MCP Server

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![PyPI version](https://img.shields.io/pypi/v/pandas-mcp.svg)](https://pypi.org/project/pandas-mcp/)
[![Python](https://img.shields.io/badge/Python-3.10%2B-blue)](https://www.python.org/)

**Part of [CLIO Kit](https://docs.iowarp.ai/) - Gnosis Research Center**

Pandas MCP is a Model Context Protocol server that enables LLMs to perform advanced data analysis and manipulation using the powerful Pandas library, featuring comprehensive statistical analysis, data cleaning and transformation, time series operations, multi-format data I/O (CSV, Excel, JSON, Pa...

## Quick Start

```bash
uvx clio-kit mcp-server pandas
```

## Documentation

- **Full Documentation**: [CLIO Kit Website](https://docs.iowarp.ai/)
- **Installation Guide**: See [INSTALLATION.md](../../../CLAUDE.md#setup--installation)
- **Contributing**: See [Contribution Guide](https://github.com/iowarp/clio-kit/wiki/Contribution)

---

## Description

Pandas MCP is a Model Context Protocol server that enables LLMs to perform advanced data analysis and manipulation using the powerful Pandas library, featuring comprehensive statistical analysis, data cleaning and transformation, time series operations, multi-format data I/O (CSV, Excel, JSON, Parquet, HDF5), and intelligent data quality assessment for seamless data science workflows.



## 🛠️ Installation

### Requirements

- Python 3.10 or higher
- [uv](https://docs.astral.sh/uv/) package manager (recommended)

<details>
<summary><b>Install in Cursor</b></summary>

Go to: `Settings` -> `Cursor Settings` -> `MCP` -> `Add new global MCP server`

Pasting the following configuration into your Cursor `~/.cursor/mcp.json` file is the recommended approach. You may also install in a specific project by creating `.cursor/mcp.json` in your project folder. See [Cursor MCP docs](https://docs.cursor.com/context/model-context-protocol) for more info.

```json
{
  "mcpServers": {
    "pandas-mcp": {
      "command": "uvx",
      "args": ["clio-kit", "mcp-server", "pandas"]
    }
  }
}
```

</details>

<details>
<summary><b>Install in VS Code</b></summary>

Add this to your VS Code MCP config file. See [VS Code MCP docs](https://code.visualstudio.com/docs/copilot/chat/mcp-servers) for more info.

```json
"mcp": {
  "servers": {
    "pandas-mcp": {
      "type": "stdio",
      "command": "uvx",
      "args": ["clio-kit", "mcp-server", "pandas"]
    }
  }
}
```

</details>

<details>
<summary><b>Install in Claude Code</b></summary>

Run this command. See [Claude Code MCP docs](https://docs.anthropic.com/en/docs/agents-and-tools/claude-code/tutorials#set-up-model-context-protocol-mcp) for more info.

```sh
claude mcp add pandas-mcp -- uvx clio-kit mcp-server pandas
```

</details>

<details>
<summary><b>Install in Claude Desktop</b></summary>

Add this to your Claude Desktop `claude_desktop_config.json` file. See [Claude Desktop MCP docs](https://modelcontextprotocol.io/quickstart/user) for more info.

```json
{
  "mcpServers": {
    "pandas-mcp": {
      "command": "uvx",
      "args": ["clio-kit", "mcp-server", "pandas"]
    }
  }
}
```

</details>

<details>
<summary><b>Manual Setup</b></summary>

**Linux/macOS:**
```bash
CLONE_DIR=$(pwd)
git clone https://github.com/iowarp/clio-kit.git
uv --directory=$CLONE_DIR/clio-kit/clio-kit-mcp-servers/pandas run pandas-mcp --help
```

**Windows CMD:**
```cmd
set CLONE_DIR=%cd%
git clone https://github.com/iowarp/clio-kit.git
uv --directory=%CLONE_DIR%\clio-kit\clio-kit-mcp-servers\pandas run pandas-mcp --help
```

**Windows PowerShell:**
```powershell
$env:CLONE_DIR=$PWD
git clone https://github.com/iowarp/clio-kit.git
uv --directory=$env:CLONE_DIR\clio-kit\clio-kit-mcp-servers\pandas run pandas-mcp --help
```

</details>

## Capabilities

### `load_data`
**Description**: Load and parse data from CSV, Excel, JSON, Parquet, or HDF5 files with optional column selection and row limiting.
**Hints**: read-only, idempotent
**Tags**: data-analysis, io

### `save_data`
**Description**: Save data to CSV, Excel, JSON, Parquet, or HDF5 with auto-detected format and optional index inclusion.
**Hints**: idempotent
**Tags**: data-analysis, io

### `statistical_summary`
**Description**: Compute descriptive statistics, distribution analysis, and outlier detection for numerical and categorical columns.
**Hints**: read-only, idempotent
**Tags**: data-analysis, statistics

### `correlation_analysis`
**Description**: Compute correlation matrices (Pearson, Spearman, or Kendall) with significance testing and strong-correlation detection.
**Hints**: read-only, idempotent
**Tags**: data-analysis, statistics

### `hypothesis_testing`
**Description**: Run statistical hypothesis tests (t-test, chi-square, ANOVA, normality, Mann-Whitney) with p-values and effect sizes.
**Hints**: read-only, idempotent
**Tags**: data-analysis, statistics

### `handle_missing_data`
**Description**: Detect, impute, or remove missing values using strategies like mean/median/mode fill, forward/backward fill, or interpolation.
**Hints**: read-only, idempotent
**Tags**: cleaning, data-analysis

### `clean_data`
**Description**: Remove duplicates, detect outliers via IQR/Z-score, and optimize data types in a single pass.
**Hints**: read-only, idempotent
**Tags**: cleaning, data-analysis

### `groupby_operations`
**Description**: Group data by columns and apply aggregations (sum, mean, count, min, max, std, median) with optional pre-filter.
**Hints**: read-only, idempotent
**Tags**: data-analysis, transformation

### `merge_datasets`
**Description**: Join two datasets using inner, outer, left, or right joins on specified key columns.
**Hints**: read-only, idempotent
**Tags**: data-analysis, transformation

### `pivot_table`
**Description**: Create pivot tables with configurable row index, column headers, value columns, and aggregation function.
**Hints**: read-only, idempotent
**Tags**: data-analysis, transformation

### `time_series_operations`
**Description**: Resample, compute rolling statistics, create lag features, or difference a time series.
**Hints**: read-only, idempotent
**Tags**: data-analysis, time-series

### `validate_data`
**Description**: Validate columns against rules for min/max range, data type, nullability, uniqueness, and regex patterns.
**Hints**: read-only, idempotent
**Tags**: data-analysis, validation

### `filter_data`
**Description**: Filter rows using comparison, membership, pattern-matching, and null-check operators across multiple columns.
**Hints**: read-only, idempotent
**Tags**: data-analysis, filtering

### `optimize_memory`
**Description**: Analyze and reduce DataFrame memory usage through automatic dtype optimization and chunked-processing recommendations.
**Hints**: read-only, idempotent
**Tags**: data-analysis, optimization

### `profile_data`
**Description**: Generate a full dataset profile: shape, types, missing values, distributions, quality checks, and optional correlations.
**Hints**: read-only, idempotent
**Tags**: data-analysis, profiling

### `profile_csv`
**Description**: Quickly profile a CSV file: row/column counts, per-column dtype, null counts, and min/max/mean for numeric columns.
**Hints**: read-only, idempotent
**Tags**: csv, data-analysis, profiling

### Resources

- `pandas://capabilities` - Supported pandas operations and file formats.

### Prompts

- **analyze_dataset**: Guided workflow for exploring and analyzing a dataset.
## Claude Code

```bash
claude mcp add clio-pandas -- uvx clio-kit pandas
```

Or install via the CLIO Kit plugin marketplace:

```
/plugin marketplace add iowarp/clio-kit
/plugin install clio-pandas@iowarp-clio-kit
```
## Claude Desktop

Add to your Claude Desktop config (`claude_desktop_config.json`):

```json
{
  "mcpServers": {
    "clio-pandas": {
      "command": "uvx",
      "args": [
        "clio-kit",
        "pandas"
      ]
    }
  }
}
```
## Gemini CLI

Add to `~/.gemini/settings.json`:

```json
{
  "mcpServers": {
    "clio-pandas": {
      "command": "uvx",
      "args": [
        "clio-kit",
        "pandas"
      ]
    }
  }
}
```

Or install the CLIO Kit extension:

```bash
gemini extensions install https://github.com/iowarp/clio-kit
```
## Examples

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

