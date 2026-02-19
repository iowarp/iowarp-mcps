# Parallel Sort MCP Server

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![PyPI version](https://img.shields.io/pypi/v/parallel-sort-mcp.svg)](https://pypi.org/project/parallel-sort-mcp/)
[![Python](https://img.shields.io/badge/Python-3.10%2B-blue)](https://www.python.org/)

**Part of [CLIO Kit](https://toolkit.iowarp.ai/) - Gnosis Research Center**

Parallel Sort MCP is a comprehensive Model Context Protocol (MCP) server that enables Language Learning Models (LLMs) to perform high-performance log file processing and analysis operations. This server provides advanced log sorting, filtering, analysis tools, and scalable data processing capabil...

## Quick Start

```bash
uvx clio-kit mcp-server parallel-sort
```

## Documentation

- **Full Documentation**: [CLIO Kit Website](https://toolkit.iowarp.ai/)
- **Installation Guide**: See [INSTALLATION.md](../../../CLAUDE.md#setup--installation)
- **Contributing**: See [Contribution Guide](https://github.com/iowarp/clio-kit/wiki/Contribution)

---

## Description
 
Parallel Sort MCP is a comprehensive Model Context Protocol (MCP) server that enables Language Learning Models (LLMs) to perform high-performance log file processing and analysis operations. This server provides advanced log sorting, filtering, analysis tools, and scalable data processing capabilities with seamless integration with AI coding assistants.
**Key Features:**
- **Log File Sorting**: Timestamp-based sorting with parallel processing for large log files
- **Advanced Filtering**: Multi-condition filtering by time range, log level, keywords, and custom patterns
- **Pattern Detection**: Anomaly detection, error clustering, and trend analysis
- **Statistical Analysis**: Comprehensive log statistics, temporal patterns, and quality metrics
- **Multiple Export Formats**: Support for JSON, CSV, and text output with metadata
- **Scalable Processing**: Handle large log files with memory-efficient chunked processing
- **MCP Integration**: Full Model Context Protocol compliance for seamless LLM integration
 
 
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
    "parallel-sort-mcp": {
      "command": "uvx",
      "args": ["clio-kit", "mcp-server", "parallel-sort"]
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
    "parallel-sort-mcp": {
      "type": "stdio",
      "command": "uvx",
      "args": ["clio-kit", "mcp-server", "parallel-sort"]
    }
  }
}
```
 
</details>
 
<details>
<summary><b>Install in Claude Code</b></summary>
 
Run this command. See [Claude Code MCP docs](https://docs.anthropic.com/en/docs/agents-and-tools/claude-code/tutorials#set-up-model-context-protocol-mcp) for more info.
 
```sh
claude mcp add parallel-sort-mcp -- uvx clio-kit mcp-server parallel-sort
```
 
</details>
 
<details>
<summary><b>Install in Claude Desktop</b></summary>
 
Add this to your Claude Desktop `claude_desktop_config.json` file. See [Claude Desktop MCP docs](https://modelcontextprotocol.io/quickstart/user) for more info.
 
```json
{
  "mcpServers": {
    "parallel-sort-mcp": {
      "command": "uvx",
      "args": ["clio-kit", "mcp-server", "parallel-sort"]
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
uv --directory=$CLONE_DIR/clio-kit/clio-kit-mcp-servers/parallel-sort run parallel-sort-mcp --help
```
 
**Windows CMD:**
```cmd
set CLONE_DIR=%cd%
git clone https://github.com/iowarp/clio-kit.git
uv --directory=%CLONE_DIR%\clio-kit\clio-kit-mcp-servers\parallel-sort run parallel-sort-mcp --help
```
 
**Windows PowerShell:**
```powershell
$env:CLONE_DIR=$PWD
git clone https://github.com/iowarp/clio-kit.git
uv --directory=$env:CLONE_DIR\clio-kit\clio-kit-mcp-servers\parallel-sort run parallel-sort-mcp --help
```
 
</details>
 
## Capabilities

### `sort_log_by_timestamp`
**Description**: Sort log file lines by timestamps in YYYY-MM-DD HH:MM:SS format.
**Tags**: execution, sort

### `parallel_sort_large_file`
**Description**: Sort large log files using parallel processing with chunked approach.
**Tags**: execution, sort

### `analyze_log_statistics`
**Description**: Generate statistics for log files including temporal patterns and log levels.
**Hints**: read-only, idempotent
**Tags**: monitoring, sort

### `detect_log_patterns`
**Description**: Detect patterns in log files including anomalies and error clusters.
**Hints**: read-only, idempotent
**Tags**: monitoring, sort

### `filter_logs`
**Description**: Filter log entries based on multiple conditions with logical operations.
**Tags**: execution, sort

### `filter_by_time_range`
**Description**: Filter log entries by time range using start and end timestamps.
**Tags**: execution, sort

### `filter_by_log_level`
**Description**: Filter log entries by log level (ERROR, WARN, INFO, DEBUG, etc.).
**Tags**: execution, sort

### `filter_by_keyword`
**Description**: Filter log entries by keywords with support for multiple keywords and logical operations.
**Tags**: execution, sort

### `apply_filter_preset`
**Description**: Apply predefined filter presets like 'errors_only' or 'connection_issues'.
**Tags**: execution, sort

### `export_to_json`
**Description**: Export log processing results to JSON format.
**Hints**: idempotent
**Tags**: configuration, sort

### `export_to_csv`
**Description**: Export log entries to CSV format with structured columns.
**Hints**: idempotent
**Tags**: configuration, sort

### `export_to_text`
**Description**: Export log entries to plain text format.
**Hints**: idempotent
**Tags**: configuration, sort

### `generate_summary_report`
**Description**: Generate a summary report of log processing results with statistics.
**Hints**: read-only, idempotent
**Tags**: monitoring, sort

### Resources

- `parallel-sort://capabilities` - Parallel sort algorithms and configuration options.

### Prompts

- **sort_large_file**: Guided workflow for sorting a large file with optimal settings.

## Claude Code

```bash
claude mcp add clio-parallel-sort -- uvx clio-kit parallel-sort
```

Or install via the CLIO Kit plugin marketplace:

```
/plugin marketplace add iowarp/clio-kit
/plugin install clio-parallel-sort@iowarp-clio-kit
```



## Claude Desktop

Add to your Claude Desktop config (`claude_desktop_config.json`):

```json
{
  "mcpServers": {
    "clio-parallel-sort": {
      "command": "uvx",
      "args": [
        "clio-kit",
        "parallel-sort"
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
    "clio-parallel-sort": {
      "command": "uvx",
      "args": [
        "clio-kit",
        "parallel-sort"
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
 
### 1. Large Log File Sorting and Analysis
```
I have a large application log file at /var/logs/app.log with millions of entries. Sort this log chronologically and analyze the error patterns.
```

**Tools called:**
- `parallel_sort_large_file` - Sort the large log file using parallel processing
- `analyze_log_statistics` - Analyze log statistics and patterns
- `detect_log_patterns` - Detect error patterns and anomalies

This prompt will:
- Use `parallel_sort_large_file` to efficiently sort the large log file with optimal chunk processing
- Analyze log statistics using `analyze_log_statistics` for comprehensive metrics
- Detect patterns using `detect_log_patterns` to identify issues and trends
- Generate sorted output with detailed analysis reports

### 2. Error Log Filtering and Export
```
Filter all ERROR and WARN level entries from /var/logs/system.log from the last 24 hours and export to CSV for analysis.
```

**Tools called:**
- `filter_by_time_range` - Filter logs by time range
- `filter_by_log_level` - Filter by ERROR and WARN levels
- `export_to_csv` - Export filtered results to CSV

This prompt will:
- Filter logs by time range using `filter_by_time_range` for the last 24 hours
- Apply log level filtering using `filter_by_log_level` for ERROR and WARN entries
- Export results using `export_to_csv` with structured columns
- Provide filtered dataset ready for analysis

### 3. Connection Issue Pattern Detection
```
Analyze /var/logs/network.log for connection timeout patterns and generate a comprehensive report with trend analysis.
```

**Tools called:**
- `filter_by_keyword` - Filter for connection-related entries
- `detect_log_patterns` - Detect timeout patterns and trends
- `generate_summary_report` - Create comprehensive analysis report

This prompt will:
- Filter connection-related entries using `filter_by_keyword` with timeout keywords
- Analyze patterns using `detect_log_patterns` for anomaly detection
- Generate comprehensive report using `generate_summary_report`
- Provide trend analysis and proactive issue identification

### 4. Multi-Condition Log Analysis
```
Find all database connection errors in /var/logs/db.log that occurred during business hours (9 AM - 5 PM) and contain "timeout" or "refused".
```

**Tools called:**
- `filter_by_time_range` - Filter for business hours
- `filter_by_keyword` - Filter for timeout and connection refused
- `filter_logs` - Apply complex multi-condition filtering
- `analyze_log_statistics` - Analyze filtered results

This prompt will:
- Apply time-based filtering using `filter_by_time_range` for business hours
- Filter by keywords using `filter_by_keyword` for timeout and refused conditions
- Combine filters using `filter_logs` with logical operators
- Analyze results using `analyze_log_statistics` for comprehensive insights

### 5. Log Quality Assessment and Cleanup
```
Analyze the quality of /var/logs/application.log, identify malformed entries, and generate a clean sorted version with quality metrics.
```

**Tools called:**
- `analyze_log_statistics` - Assess log quality and identify issues
- `sort_log_by_timestamp` - Sort logs chronologically
- `generate_summary_report` - Create quality assessment report

This prompt will:
- Assess log quality using `analyze_log_statistics` with quality metrics
- Sort logs using `sort_log_by_timestamp` for chronological order
- Generate quality report using `generate_summary_report`
- Provide clean dataset with quality improvement recommendations

### 6. Historical Log Trend Analysis
```
Analyze error trends in /var/logs/historic.log over the past month, detect anomalies, and export findings to JSON for dashboard integration.
```

**Tools called:**
- `filter_by_time_range` - Filter for past month
- `detect_log_patterns` - Detect trends and anomalies
- `analyze_log_statistics` - Generate temporal analysis
- `export_to_json` - Export results for dashboard

This prompt will:
- Filter historical data using `filter_by_time_range` for the past month
- Detect trends using `detect_log_patterns` with anomaly detection
- Analyze temporal patterns using `analyze_log_statistics`
- Export findings using `export_to_json` for dashboard integration
 