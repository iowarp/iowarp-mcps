# Parquet MCP Server

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python](https://img.shields.io/badge/Python-3.10%2B-blue)](https://www.python.org/)

**Part of [CLIO Kit](https://docs.iowarp.ai/) - Gnosis Research Center**

Model Context Protocol (MCP) server for Apache Parquet files. Provides metadata extraction, column-based operations, and data filtering for AI agents.

## Quick Start

```bash
uvx clio-kit mcp-server parquet
```

## Key Features

- **Full Documentation**: [CLIO Kit Website](https://docs.iowarp.ai/)
- **Installation Guide**: See [INSTALLATION.md](../../../CLAUDE.md#setup--installation)
- **Contributing**: See [Contribution Guide](https://github.com/iowarp/clio-kit/wiki/Contribution)
- 16KB payload limit with error messages and suggested slice sizes
- JSON filtering with compound/nested operations (AND/OR/NOT, comparisons, NULL checks, IN clauses)
- Column projection and pagination
- 7 aggregation operations (min, max, mean, sum, count, std, count_distinct)
- Structured JSON error responses
- Tested on 131M+ row datasets
- 192 tests

## Installation

### Requirements

- Python 3.10 or higher
- [uv](https://docs.astral.sh/uv/) package manager (recommended)
- PyArrow library for Parquet file processing

### Setup and Run

Go to: `Settings` -> `Cursor Settings` -> `MCP` -> `Add new global MCP server`

Pasting the following configuration into your Cursor `~/.cursor/mcp.json` file is the recommended approach. You may also install in a specific project by creating `.cursor/mcp.json` in your project folder. See [Cursor MCP docs](https://docs.cursor.com/context/model-context-protocol) for more info.

```json
{
  "mcpServers": {
    "parquet-mcp": {
      "command": "uvx",
      "args": ["clio-kit", "mcp-server", "parquet"]
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
      "args": ["clio-kit", "mcp-server", "parquet"]
    }
  }
}
```

</details>

<details>
<summary><b>Install in Claude Code</b></summary>

Run this command. See [Claude Code MCP docs](https://docs.anthropic.com/en/docs/agents-and-tools/claude-code/tutorials#set-up-model-context-protocol-mcp) for more info.

```sh
claude mcp add parquet-mcp -- uvx clio-kit mcp-server parquet
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
      "args": ["clio-kit", "mcp-server", "parquet"]
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
uv --directory=$CLONE_DIR/clio-kit/clio-kit-mcp-servers/parquet run parquet-mcp --help
```

**Windows CMD:**
```cmd
set CLONE_DIR=%cd%
git clone https://github.com/iowarp/clio-kit.git
uv --directory=%CLONE_DIR%\clio-kit\clio-kit-mcp-servers\parquet run parquet-mcp --help
```

**Windows PowerShell:**
```powershell
$env:CLONE_DIR=$PWD
git clone https://github.com/iowarp/clio-kit.git
uv --directory=$env:CLONE_DIR\clio-kit\clio-kit-mcp-servers\parquet run parquet-mcp --help
```

</details>

## Available Tools

### 1. summarize_tool

Get metadata about a Parquet file without loading data.

**Parameters:**
- `file_path` (str): Path to the Parquet file

**Returns:** JSON with schema, row count, row groups, and file size

### 2. read_slice_tool

Read a horizontal slice of rows with optional column projection and advanced filtering.

**Parameters:**
- `file_path` (str): Path to the Parquet file
- `start_row` (int): Starting row index (inclusive, 0-based)
- `end_row` (int): Ending row index (exclusive)
- `columns` (list[str], optional): List of columns to include
- `filter_json` (str, optional): JSON filter specification

**16KB Context Protection:** If the slice exceeds 16KB, returns error with suggested safe parameters.

### 3. get_column_preview_tool

Preview values from a specific column with pagination support.

**Parameters:**
- `file_path` (str): Path to the Parquet file
- `column_name` (str): Name of the column to preview
- `start_index` (int, optional): Starting index for pagination (default: 0)
- `max_items` (int, optional): Maximum items to return (default: 100, max: 100)

### 4. aggregate_column_tool

Compute statistical aggregations on columns with optional filtering and row ranges.

**Parameters:**
- `file_path` (str): Path to the Parquet file
- `column_name` (str): Column to aggregate
- `operation` (str): One of: min, max, mean, sum, count, std, count_distinct
- `filter_json` (str, optional): JSON filter specification
- `start_row` (int, optional): Starting row for range constraint
- `end_row` (int, optional): Ending row for range constraint

## Filter Format

JSON-based filtering.

### Simple Filters

```json
{"column": "temperature", "op": "less", "value": 25.0}
{"column": "sensor_id", "op": "equal", "value": 42}
{"column": "status", "op": "in", "values": ["active", "pending"]}
{"column": "error_code", "op": "is_null"}
```

### Compound Filters

```json
{
  "and": [
    {"column": "temperature", "op": "greater", "value": 20.0},
    {"column": "temperature", "op": "less", "value": 30.0}
  ]
}
```

### Supported Operations

| Operation | Description |
|-----------|-------------|
| equal | Equals |
| not_equal | Not equals |
| less | Less than |
| less_equal | Less than or equal |
| greater | Greater than |
| greater_equal | Greater than or equal |
| in, is_in | Value in list |
| is_null | Column is NULL |
| is_not_null, is_valid | Column is not NULL |
| and | Logical AND |
| or | Logical OR |
| not | Logical NOT |

## Testing

192 tests.

```bash
# Run all tests
uv run pytest tests/ -v

# Quick smoke test (exclude slow tests)
uv run pytest tests/ -v -m "not slow"

# Test specific suite
uv run pytest tests/test_filtering.py -v
```

**Note on Test Datasets**: The repository includes trimmed datasets for basic testing. Tests requiring the full IceCube datasets are automatically skipped.

## Evaluation

The `evaluation.xml` file contains 10 validation questions that test advanced filtering and aggregation capabilities. To run the full evaluation and get expected outputs, download the complete IceCube Neutrino datasets:

- `batch_1.parquet` through `batch_6.parquet` (~160MB each)
- `train_meta.parquet` (~3.5GB)

**Dataset Source**: [IceCube Neutrino Path Least Squares - Kaggle](https://www.kaggle.com/code/solverworld/icecube-neutrino-path-least-squares-1-214/input)

Place these files in the `datasets/` directory to enable full evaluation testing.

## Architecture

```
parquet/                              # clio-kit-mcp-servers/parquet/
├── src/parquet_mcp/
│   ├── server.py                     # FastMCP server with @mcp.tool decorators
│   └── capabilities/
│       └── parquet_handler.py        # Core implementations
├── tests/                            # 192 tests
├── datasets/                         # Test Parquet files (44KB trimmed)
├── pyproject.toml                    # Package configuration
└── README.md                         # This file
```

## Performance

Tested on IceCube Neutrino dataset (131M+ rows, 830MB):

| Operation | Time | Notes |
|-----------|------|-------|
| Summarize | <1s | Metadata only |
| Read slice (100 rows) | <1s | Direct offset |
| Filtered slice | 2-5s | Depends on selectivity |
| Aggregation (min/max) | <10s | Full scan |

## License

MIT License - see LICENSE for details

## Resources

- **CLIO Kit Website**: https://docs.iowarp.ai/
- **Model Context Protocol**: https://modelcontextprotocol.io/
- **Apache Parquet**: https://parquet.apache.org/
- **PyArrow Documentation**: https://arrow.apache.org/docs/python/

## Support

- **Zulip Chat**: https://iowarp.zulipchat.com/#narrow/channel/543872-Agent-Toolkit
- **Zulip Invitation**: https://iowarp.zulipchat.com/join/e4wh24du356e4y2iw6x6jeay/
- **GitHub Issues**: https://github.com/iowarp/clio-kit/issues
- **Email**: grc@illinoistech.edu

## Capabilities

### `summarize_tool`
**Description**: Return Parquet schema, row count, and file size.
**Hints**: read-only, idempotent
**Tags**: data-analysis, parquet

### `read_slice_tool`
**Description**: Read a row slice from a Parquet file with optional column projection and filtering.
**Hints**: read-only, idempotent
**Tags**: data-analysis, parquet

### `get_column_preview_tool`
**Description**: Preview values from a specific column with pagination.
**Hints**: read-only, idempotent
**Tags**: data-analysis, parquet

### `aggregate_column_tool`
**Description**: Compute aggregate statistics (min, max, mean, etc.) on a Parquet column.
**Hints**: read-only, idempotent
**Tags**: data-analysis, parquet, statistics

### Resources

- `parquet://formats` - Supported Parquet features and capabilities.

### Prompts

- **analyze_parquet**: Guided workflow for analyzing a Parquet file.
## Claude Code

```bash
claude mcp add clio-parquet -- uvx clio-kit parquet
```

Or install via the CLIO Kit plugin marketplace:

```
/plugin marketplace add iowarp/clio-kit
/plugin install clio-parquet@iowarp-clio-kit
```
## Claude Desktop

Add to your Claude Desktop config (`claude_desktop_config.json`):

```json
{
  "mcpServers": {
    "clio-parquet": {
      "command": "uvx",
      "args": [
        "clio-kit",
        "parquet"
      ]
    }
  }
}
```
