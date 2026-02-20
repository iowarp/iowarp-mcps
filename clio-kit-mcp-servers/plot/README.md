# Plot MCP Server

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![PyPI version](https://img.shields.io/pypi/v/plot-mcp.svg)](https://pypi.org/project/plot-mcp/)
[![Python](https://img.shields.io/badge/Python-3.10%2B-blue)](https://www.python.org/)

**Part of [CLIO Kit](https://toolkit.iowarp.ai/) - Gnosis Research Center**

Plot MCP is a Model Context Protocol server that enables LLMs to create professional data visualizations from CSV and Excel files with intelligent data processing capabilities. The server automatically handles data cleaning, type inference, and missing value processing while supporting multiple v...

## Quick Start

```bash
uvx clio-kit mcp-server plot
```

## Documentation

- **Full Documentation**: [CLIO Kit Website](https://toolkit.iowarp.ai/)
- **Installation Guide**: See [INSTALLATION.md](../../../CLAUDE.md#setup--installation)
- **Contributing**: See [Contribution Guide](https://github.com/iowarp/clio-kit/wiki/Contribution)

---

## Description

Plot MCP is a Model Context Protocol server that enables LLMs to create professional data visualizations from CSV and Excel files with intelligent data processing capabilities. The server automatically handles data cleaning, type inference, and missing value processing while supporting multiple visualization types including line plots, bar charts, scatter plots, histograms, and correlation heatmaps.


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
    "plot-mcp": {
      "command": "uvx",
      "args": ["clio-kit", "mcp-server", "plot"]
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
    "plot-mcp": {
      "type": "stdio",
      "command": "uvx",
      "args": ["clio-kit", "mcp-server", "plot"]
    }
  }
}
```

</details>

<details>
<summary><b>Install in Claude Code</b></summary>

Run this command. See [Claude Code MCP docs](https://docs.anthropic.com/en/docs/agents-and-tools/claude-code/tutorials#set-up-model-context-protocol-mcp) for more info.

```sh
claude mcp add plot-mcp -- uvx clio-kit mcp-server plot
```

</details>

<details>
<summary><b>Install in Claude Desktop</b></summary>

Add this to your Claude Desktop `claude_desktop_config.json` file. See [Claude Desktop MCP docs](https://modelcontextprotocol.io/quickstart/user) for more info.

```json
{
  "mcpServers": {
    "plot-mcp": {
      "command": "uvx",
      "args": ["clio-kit", "mcp-server", "plot"]
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
uv --directory=$CLONE_DIR/clio-kit/clio-kit-mcp-servers/plot run plot-mcp --help
```

**Windows CMD:**
```cmd
set CLONE_DIR=%cd%
git clone https://github.com/iowarp/clio-kit.git
uv --directory=%CLONE_DIR%\clio-kit\clio-kit-mcp-servers\plot run plot-mcp --help
```

**Windows PowerShell:**
```powershell
$env:CLONE_DIR=$PWD
git clone https://github.com/iowarp/clio-kit.git
uv --directory=$env:CLONE_DIR\clio-kit\clio-kit-mcp-servers\plot run plot-mcp --help
```

</details>

## Capabilities

### `line_plot`
**Description**: Create a line plot from CSV or Excel data with customizable styling.
**Hints**: destructive, idempotent
**Tags**: line-chart, plot, visualization

### `bar_plot`
**Description**: Create a bar chart from CSV or Excel data with categorical grouping.
**Hints**: destructive, idempotent
**Tags**: bar-chart, plot, visualization

### `scatter_plot`
**Description**: Create a scatter plot from CSV or Excel data for correlation analysis.
**Hints**: destructive, idempotent
**Tags**: plot, scatter-plot, visualization

### `histogram_plot`
**Description**: Create a histogram from CSV or Excel data showing value distribution.
**Hints**: destructive, idempotent
**Tags**: histogram, plot, visualization

### `heatmap_plot`
**Description**: Create a correlation heatmap from numeric columns in CSV or Excel data.
**Hints**: destructive, idempotent
**Tags**: heatmap, plot, visualization

### `data_info`
**Description**: Get schema, column types, and summary statistics for a CSV or Excel file.
**Hints**: read-only, idempotent
**Tags**: analysis, data, visualization

### Resources

- `plot://styles` - Available matplotlib plot styles and color palettes.

### Prompts

- **create_visualization**: Guided workflow for creating a data visualization.
## Claude Code

```bash
claude mcp add clio-plot -- uvx clio-kit plot
```

Or install via the CLIO Kit plugin marketplace:

```
/plugin marketplace add iowarp/clio-kit
/plugin install clio-plot@iowarp-clio-kit
```
## Claude Desktop

Add to your Claude Desktop config (`claude_desktop_config.json`):

```json
{
  "mcpServers": {
    "clio-plot": {
      "command": "uvx",
      "args": [
        "clio-kit",
        "plot"
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
    "clio-plot": {
      "command": "uvx",
      "args": [
        "clio-kit",
        "plot"
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

### 1. Data Exploration and Analysis
```
I have a CSV file at /data/sales_data.csv with sales information. Can you first analyze the data structure and then create appropriate visualizations to show sales trends over time?
```

**Tools called:**
- `data_info` - Analyze the dataset structure
- `line_plot` - Create time-series plots showing sales trends

This prompt will:
- Use `data_info` to analyze the dataset structure
- Create time-series plots using `line_plot` showing sales trends
- Provide statistical insights about the data

<!-- **Output:** -->
<!-- Add your output images here -->
<!-- ![Data Info Output](images/example1_data_info.png) -->
<!-- ![Sales Trends Line Plot](images/example1_sales_trends.png) -->

### 2. Comparative Analysis with Multiple Charts
```
Using the file /data/survey_results.csv, create a comprehensive analysis showing:
1. Age distribution of respondents (histogram)
2. Correlation between satisfaction scores (heatmap)  
3. Department vs average salary comparison (bar chart)
```

**Tools called:**
- `histogram_plot` - Age distribution of respondents
- `heatmap_plot` - Correlation between satisfaction scores
- `bar_plot` - Department vs average salary comparison

This prompt will:
- Generate multiple complementary visualizations
- Provide statistical analysis for each chart type
- Show data relationships and distributions
- Create professional publication-ready plots

<!-- **Output:** -->
<!-- Add your output images here -->
<!-- ![Age Distribution Histogram](images/example2_age_histogram.png) -->
<!-- ![Satisfaction Scores Heatmap](images/example2_satisfaction_heatmap.png) -->
<!-- ![Department Salary Comparison](images/example2_department_salary.png) -->

### 3. Scientific Data Visualization
```
I have temperature measurement data in /data/temperature.csv. Create a scatter plot showing the relationship between ambient temperature and device performance, and add a trend analysis.
```

**Tools called:**
- `scatter_plot` - Relationship between ambient temperature and device performance

This prompt will:
- Create correlation analysis between variables using `scatter_plot`
- Generate scatter plot with trend lines
- Provide statistical correlation metrics
- Include uncertainty analysis if applicable

<!-- **Output:** -->
<!-- Add your output images here -->
<!-- ![Temperature vs Performance Scatter Plot](images/example3_temperature_scatter.png) -->

### 4. Business Intelligence Dashboard
```
From /data/quarterly_metrics.xlsx, create visualizations showing:
- Revenue trends by quarter (line plot)
- Performance metrics distribution (histogram)
- Regional comparison (bar chart)
```

**Tools called:**
- `line_plot` - Revenue trends by quarter
- `histogram_plot` - Performance metrics distribution
- `bar_plot` - Regional comparison

This prompt will:
- Handle Excel file format automatically
- Create multiple business-focused visualizations
- Provide executive summary statistics
- Generate dashboard-style layouts

<!-- **Output:** -->
<!-- Add your output images here -->
<!-- ![Revenue Trends Line Plot](images/example4_revenue_trends.png) -->
<!-- ![Performance Metrics Histogram](images/example4_performance_histogram.png) -->
<!-- ![Regional Comparison Bar Chart](images/example4_regional_comparison.png) -->

### 5. Research Data Publication
```
Using /data/experiment_results.csv, create publication-quality figures showing experimental conditions vs outcomes with proper error handling and statistical annotations.
```

**Tools called:**
- `data_info` - Analyze experimental data structure and quality
- `scatter_plot` - Show relationship between experimental conditions and outcomes
- `heatmap_plot` - Display correlation matrix of experimental variables

This prompt will:
- Use `data_info` to analyze data structure and handle missing values
- Generate `scatter_plot` for condition-outcome relationships
- Create `heatmap_plot` for correlation analysis
- Generate publication-ready 300 DPI plots
- Include proper statistical annotations

<!-- **Output:** -->
<!-- Add your output images here -->
<!-- ![Data Quality Report](images/example5_data_quality.png) -->
<!-- ![Experimental Conditions vs Outcomes](images/example5_experiment_scatter.png) -->
<!-- ![Correlation Matrix Heatmap](images/example5_correlation_heatmap.png) -->

### 6. Quick Data Quality Check
```
I need to quickly assess the quality of my dataset at /data/customer_data.csv - show me data completeness, distributions, and suggest the best visualization approaches.
```

**Tools called:**
- `data_info` - Comprehensive data quality assessment

This prompt will:
- Use `data_info` to perform comprehensive data quality assessment
- Identify missing values and data issues
- Suggest optimal visualization strategies
- Provide data cleaning recommendations

<!-- **Output:** -->
<!-- Add your output images here -->
<!-- ![Data Quality Assessment](images/example6_data_quality.png) -->
<!-- ![Data Completeness Report](images/example6_completeness_report.png) -->
