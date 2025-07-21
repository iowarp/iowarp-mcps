# Parquet MCP - Columnar Data Access for LLMs


## Description

Parquet MCP is a comprehensive Model Context Protocol (MCP) server that enables Language Learning Models (LLMs) to access, analyze, and manipulate Parquet columnar data files. This server provides advanced capabilities for efficient data reading, column-based operations, and high-performance analytics with seamless integration with AI coding assistants.

**Key Features:**
- **High-Performance Columnar Access**: Efficient column-based data reading using PyArrow with optimized memory usage
- **Intelligent Data Processing**: Automatic schema detection and type inference with metadata extraction
- **Flexible Data Operations**: Resource discovery, column reading, and data preview capabilities
- **Big Data Support**: Optimized for large datasets with memory-efficient streaming and column selection
- **Analytics Integration**: Support for data science workflows with pandas and NumPy compatibility
- **MCP Integration**: Full Model Context Protocol compliance for seamless LLM integration


## 🛠️ Installation

### Requirements

- Python 3.10 or higher
- [uv](https://docs.astral.sh/uv/) package manager (recommended)
- PyArrow library for Parquet file processing

<details>
<summary><b>Install in Cursor</b></summary>

Go to: `Settings` -> `Cursor Settings` -> `MCP` -> `Add new global MCP server`

Pasting the following configuration into your Cursor `~/.cursor/mcp.json` file is the recommended approach. You may also install in a specific project by creating `.cursor/mcp.json` in your project folder. See [Cursor MCP docs](https://docs.cursor.com/context/model-context-protocol) for more info.

```json
{
  "mcpServers": {
    "parquet-mcp": {
      "command": "uvx",
      "args": ["iowarp-mcps", "parquet"]
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
    "parquet-mcp": {
      "type": "stdio",
      "command": "uvx",
      "args": ["iowarp-mcps", "parquet"]
    }
  }
}
```

</details>

<details>
<summary><b>Install in Claude Code</b></summary>

Run this command. See [Claude Code MCP docs](https://docs.anthropic.com/en/docs/agents-and-tools/claude-code/tutorials#set-up-model-context-protocol-mcp) for more info.

```sh
claude mcp add parquet-mcp -- uvx iowarp-mcps parquet
```

</details>

<details>
<summary><b>Install in Claude Desktop</b></summary>

Add this to your Claude Desktop `claude_desktop_config.json` file. See [Claude Desktop MCP docs](https://modelcontextprotocol.io/quickstart/user) for more info.

```json
{
  "mcpServers": {
    "parquet-mcp": {
      "command": "uvx",
      "args": ["iowarp-mcps", "parquet"]
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
git clone https://github.com/iowarp/iowarp-mcps.git
uv --directory=$CLONE_DIR/iowarp-mcps/mcps/parquet run parquet-mcp --help
```

**Windows CMD:**
```cmd
set CLONE_DIR=%cd%
git clone https://github.com/iowarp/iowarp-mcps.git
uv --directory=%CLONE_DIR%\iowarp-mcps\mcps\parquet run parquet-mcp --help
```

**Windows PowerShell:**
```powershell
$env:CLONE_DIR=$PWD
git clone https://github.com/iowarp/iowarp-mcps.git
uv --directory=$env:CLONE_DIR\iowarp-mcps\mcps\parquet run parquet-mcp --help
```

</details>

## Available Actions

### `list_parquet_resources`
**Description**: Discover and list all available Parquet files and datasets with comprehensive metadata extraction and schema information.

**Parameters**: None

**Returns**: Dictionary with list of available Parquet resources including file paths, schemas, and metadata.

### `read_parquet_column`
**Description**: Read specific columns from Parquet files with efficient columnar access and memory optimization.

**Parameters**:
- `file_path` (str): Path to the Parquet file
- `column_name` (str): Name of the column to read

**Returns**: Dictionary with column data, data types, and statistical information.

### `get_parquet_schema`
**Description**: Extract comprehensive schema information from Parquet files including column types and metadata.

**Parameters**:
- `file_path` (str): Path to the Parquet file

**Returns**: Dictionary with detailed schema information, column definitions, and file metadata.

### `preview_parquet_data`
**Description**: Preview sample data from Parquet files with configurable row limits and column selection.

**Parameters**:
- `file_path` (str): Path to the Parquet file
- `num_rows` (int, optional): Number of rows to preview (default: 10)
- `columns` (list, optional): Specific columns to preview

**Returns**: Dictionary with preview data, schema information, and file statistics.

## Examples

### 1. Data Discovery and Schema Analysis
```
I have Parquet files in my data directory. Can you discover all available files and show me their schemas to understand the data structure?
```

**Tools called:**
- `list_parquet_resources` - Discover available Parquet files
- `get_parquet_schema` - Analyze file schemas and structure

This prompt will:
- Use `list_parquet_resources` to discover all available Parquet files
- Extract schema information using `get_parquet_schema` for each file
- Provide comprehensive overview of data structure and organization
- Enable informed data analysis planning

### 2. Selective Column Analysis
```
From the weather data file at /data/weather_measurements.parquet, read the temperature column and show me the data distribution and statistics.
```

**Tools called:**
- `read_parquet_column` - Read temperature column data
- `get_parquet_schema` - Get column metadata and types

This prompt will:
- Read temperature column using `read_parquet_column` with optimized memory usage
- Extract column metadata using `get_parquet_schema`
- Provide statistical analysis and data distribution insights
- Support focused analytical workflows

### 3. Data Quality Assessment
```
Before processing the large dataset at /analytics/customer_data.parquet, preview the first 50 rows to validate data quality and structure.
```

**Tools called:**
- `preview_parquet_data` - Preview dataset sample
- `get_parquet_schema` - Get comprehensive schema information

This prompt will:
- Preview sample data using `preview_parquet_data` with specified row count
- Analyze data structure using `get_parquet_schema`
- Enable data quality validation before full processing
- Support data validation and preprocessing workflows

### 4. Multi-Column Data Exploration
```
Explore the sales dataset at /business/quarterly_sales.parquet by reading the revenue, region, and date columns for trend analysis.
```

**Tools called:**
- `read_parquet_column` - Read multiple columns (revenue, region, date)
- `preview_parquet_data` - Preview multi-column data sample

This prompt will:
- Read multiple columns using `read_parquet_column` for each required field
- Preview multi-column data using `preview_parquet_data`
- Enable comprehensive trend analysis and business intelligence
- Support multi-dimensional data exploration

### 5. Large Dataset Processing Preparation
```
I need to process a large Parquet dataset at /warehouse/transaction_logs.parquet. Show me the schema, preview sample data, and help me understand the optimal columns for analysis.
```

**Tools called:**
- `get_parquet_schema` - Analyze dataset structure
- `preview_parquet_data` - Sample data for understanding
- `list_parquet_resources` - Verify resource availability

This prompt will:
- Analyze dataset structure using `get_parquet_schema`
- Preview sample data using `preview_parquet_data`
- Verify resource availability using `list_parquet_resources`
- Provide optimization recommendations for large dataset processing

### 6. Business Intelligence Data Pipeline
```
Set up analysis of our customer behavior data stored in /bi/customer_analytics.parquet by examining schema, previewing key metrics columns, and reading engagement data.
```

**Tools called:**
- `get_parquet_schema` - Understand data structure
- `preview_parquet_data` - Preview key metrics
- `read_parquet_column` - Read engagement data columns

This prompt will:
- Analyze data structure using `get_parquet_schema`
- Preview key business metrics using `preview_parquet_data`
- Extract engagement data using `read_parquet_column`
- Support business intelligence and analytics workflows