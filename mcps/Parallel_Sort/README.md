# Parallel Sort MCP - High-Performance Log File Processing for LLMs
 
 
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
      "args": ["iowarp-mcps", "parallel-sort"]
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
      "args": ["iowarp-mcps", "parallel-sort"]
    }
  }
}
```
 
</details>
 
<details>
<summary><b>Install in Claude Code</b></summary>
 
Run this command. See [Claude Code MCP docs](https://docs.anthropic.com/en/docs/agents-and-tools/claude-code/tutorials#set-up-model-context-protocol-mcp) for more info.
 
```sh
claude mcp add parallel-sort-mcp -- uvx iowarp-mcps parallel-sort
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
      "args": ["iowarp-mcps", "parallel-sort"]
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
uv --directory=$CLONE_DIR/iowarp-mcps/mcps/Parallel_Sort run parallel-sort-mcp --help
```
 
**Windows CMD:**
```cmd
set CLONE_DIR=%cd%
git clone https://github.com/iowarp/iowarp-mcps.git
uv --directory=%CLONE_DIR%\iowarp-mcps\mcps\Parallel_Sort run parallel-sort-mcp --help
```
 
**Windows PowerShell:**
```powershell
$env:CLONE_DIR=$PWD
git clone https://github.com/iowarp/iowarp-mcps.git
uv --directory=$env:CLONE_DIR\iowarp-mcps\mcps\Parallel_Sort run parallel-sort-mcp --help
```
 
</details>
 
## Capabilities

### `sort_log_by_timestamp`
**Description**: Sort log files by timestamp in chronological order with support for standard log formats.

**Parameters**:
- `log_file` (str): Path to input log file
- `output_file` (str, optional): Path for sorted output file
- `reverse` (bool, optional): Sort in descending order (default: False)

**Returns**: dict: Dictionary with sorting results, processed line count, and execution time.

### `parallel_sort_large_file`
**Description**: Sort large log files using parallel processing with chunked approach for memory efficiency.

**Parameters**:
- `log_file` (str): Path to large log file
- `output_file` (str): Path for sorted output file
- `chunk_size_mb` (int, optional): Chunk size in MB (default: 100)
- `num_workers` (int, optional): Number of worker processes (default: CPU count)

**Returns**: dict: Dictionary with sorting results, performance metrics, and memory usage.

### `analyze_log_statistics`
**Description**: Perform comprehensive statistical analysis of log files including temporal patterns and log levels.

**Parameters**:
- `log_file` (str): Path to log file
- `include_patterns` (bool, optional): Include pattern analysis (default: True)

**Returns**: dict: Dictionary with statistics, temporal analysis, log level distribution, and quality metrics.

### `detect_log_patterns`
**Description**: Detect patterns, anomalies, and trends in log files for proactive issue identification.

**Parameters**:
- `log_file` (str): Path to log file
- `pattern_types` (list, optional): Types of patterns to detect
- `sensitivity` (str, optional): Detection sensitivity ('low', 'medium', 'high')

**Returns**: dict: Dictionary with detected patterns, anomalies, error clusters, and trend analysis.

### `filter_logs`
**Description**: Apply multiple filter conditions to log files with complex logical operations.

**Parameters**:
- `log_file` (str): Path to log file
- `filters` (list): List of filter conditions
- `logical_operator` (str, optional): Logical operator between filters ('AND', 'OR')
- `output_file` (str, optional): Path for filtered output

**Returns**: dict: Dictionary with filtered results and applied filter summary.

### `filter_by_time_range`
**Description**: Filter log entries within a specific time range.

**Parameters**:
- `log_file` (str): Path to log file
- `start_time` (str): Start timestamp (YYYY-MM-DD HH:MM:SS)
- `end_time` (str): End timestamp (YYYY-MM-DD HH:MM:SS)
- `output_file` (str, optional): Path for filtered output

**Returns**: dict: Dictionary with filtered entries and time range statistics.

### `filter_by_log_level`
**Description**: Filter log entries by log level (ERROR, WARN, INFO, DEBUG, etc.).

**Parameters**:
- `log_file` (str): Path to log file
- `log_levels` (list): List of log levels to include
- `output_file` (str, optional): Path for filtered output

**Returns**: dict: Dictionary with filtered entries and log level distribution.

### `filter_by_keyword`
**Description**: Filter log entries containing specific keywords with advanced matching options.

**Parameters**:
- `log_file` (str): Path to log file
- `keywords` (list): List of keywords to search for
- `case_sensitive` (bool, optional): Case sensitive matching (default: False)
- `logical_operator` (str, optional): Operator between keywords ('AND', 'OR')
- `output_file` (str, optional): Path for filtered output

**Returns**: dict: Dictionary with filtered entries and keyword match statistics.

### `apply_filter_preset`
**Description**: Apply predefined filter presets for common log analysis scenarios.

**Parameters**:
- `log_file` (str): Path to log file
- `preset_name` (str): Preset name ('errors_only', 'warnings_and_errors', 'connection_issues', etc.)
- `output_file` (str, optional): Path for filtered output

**Returns**: dict: Dictionary with filtered results and preset configuration details.

### `export_to_json`
**Description**: Export results to JSON format.

**Parameters**:
- `data` (dict): Parameter for data
- `include_metadata` (bool, optional): Parameter for include_metadata (default: True)

**Returns**: Dictionary with JSON export results

### `export_to_csv`
**Description**: Export results to CSV format.

**Parameters**:
- `data` (dict): Parameter for data
- `include_headers` (bool, optional): Parameter for include_headers (default: True)

**Returns**: Dictionary with CSV export results

### `export_to_text`
**Description**: Export results to text format.

**Parameters**:
- `data` (dict): Parameter for data
- `include_summary` (bool, optional): Parameter for include_summary (default: True)

**Returns**: Dictionary with text export results

### `generate_summary_report`
**Description**: Generate a summary report.

**Parameters**:
- `data` (dict): Parameter for data

**Returns**: Dictionary with summary report
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
 