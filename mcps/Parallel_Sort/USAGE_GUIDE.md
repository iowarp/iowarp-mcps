# Parallel Sort MCP Server - Usage Guide

## Quick Start Commands

### 1. Installation & Setup
```bash
# Navigate to the project directory
cd /path/to/scientific-mcps/Parallel_Sort

# Install dependencies
uv sync

# Run tests to verify installation
uv run pytest tests/ -v
```

### 2. Starting the MCP Server

```bash
# Start with stdio transport (default for MCP clients)
uv run parallel-sort-mcp

# Or start directly
uv run python -m parallel_sort.server

# Start with SSE transport for web clients
MCP_TRANSPORT=sse MCP_SSE_HOST=0.0.0.0 MCP_SSE_PORT=8000 uv run parallel-sort-mcp
```

### 3. Available MCP Tools

#### Basic Sorting
- `sort_log_by_timestamp(file_path)` - Sort log file by timestamps
- `parallel_sort_large_file(file_path, chunk_size_mb=100, max_workers=None)` - Parallel sort for large files

#### Analysis & Statistics  
- `analyze_log_statistics(file_path)` - Generate comprehensive log statistics
- `detect_log_patterns(file_path, detection_config=None)` - Detect patterns and anomalies

#### Filtering
- `filter_by_time_range(file_path, start_time, end_time)` - Filter by time range
- `filter_by_log_level(file_path, levels, exclude=False)` - Filter by log levels
- `filter_by_keyword(file_path, keywords, case_sensitive=False, match_all=False)` - Filter by keywords
- `apply_filter_preset(file_path, preset_name)` - Apply predefined filters

#### Export Options
- `export_to_json(data, include_metadata=True)` - Export to JSON format
- `export_to_csv(data, include_headers=True)` - Export to CSV format  
- `export_to_text(data, include_summary=True)` - Export to plain text
- `generate_summary_report(data)` - Generate comprehensive report

## Sample Data Files

The repository includes sample log files for testing:

- `sample_data/application.log` - Application server logs with various levels
- `sample_data/web_server.log` - Web server logs with HTTP requests and errors
- `sample_data/unsorted.log` - Unsorted log entries for sorting demonstrations

## Example Usage Scenarios

### 1. Sort an unsorted log file
```python
# Input: sample_data/unsorted.log (timestamps out of order)
# Tool: sort_log_by_timestamp
# Result: Lines sorted chronologically by timestamp
```

### 2. Analyze application performance
```python
# Input: sample_data/application.log
# Tool: analyze_log_statistics  
# Result: Detailed statistics including temporal patterns, log levels, quality metrics
```

### 3. Find error patterns
```python
# Input: sample_data/web_server.log
# Tool: detect_log_patterns
# Result: Error clusters, anomalies, trending issues
```

### 4. Filter for security events
```python
# Input: sample_data/web_server.log
# Tool: filter_by_keyword
# Keywords: "authentication", "security", "failed"
# Result: Security-related log entries only
```

### 5. Export filtered results
```python
# Process: Filter logs → Export to CSV
# Tools: filter_by_log_level("ERROR") → export_to_csv
# Result: CSV file with only error entries
```

## Filter Presets

Available predefined filter presets:

- `errors_only` - Show only ERROR, FATAL, and CRITICAL entries
- `warnings_and_errors` - Show WARNING and error level entries  
- `exclude_debug` - Exclude DEBUG and TRACE entries
- `connection_issues` - Find connection-related problems
- `authentication_events` - Find authentication-related events

## Integration with MCP Clients

### Claude Desktop Configuration
Add to your Claude Desktop config file:

```json
{
  "mcpServers": {
    "parallel-sort-mcp": {
      "command": "uv",
      "args": [
        "--directory", "/path/to/scientific-mcps/Parallel_Sort",
        "run", "parallel-sort-mcp"
      ]
    }
  }
}
```

### Environment Variables

- `MCP_TRANSPORT` - Transport type: `stdio` (default) or `sse`
- `MCP_SSE_HOST` - Host for SSE transport (default: `0.0.0.0`)
- `MCP_SSE_PORT` - Port for SSE transport (default: `8000`)

## Performance Features

### For Large Files (>100MB)
- Use `parallel_sort_large_file` instead of `sort_log_by_timestamp`
- Configurable chunk sizes and worker processes
- Memory-efficient streaming processing

### Memory Optimization
- Adjust `chunk_size_mb` parameter for available memory
- Use `max_workers` to control CPU usage
- Temporary files automatically cleaned up

## Testing Your Installation

```bash
# Run all tests
uv run pytest

# Test specific functionality
uv run pytest tests/test_sort_handler.py -v
uv run pytest tests/test_export_handler.py -v
uv run pytest tests/test_filter_handler.py -v

# Test with verbose output
uv run pytest -v -s
```

## Common Use Cases

1. **DevOps Log Analysis** - Sort and analyze application logs for debugging
2. **Security Monitoring** - Filter and detect security-related events  
3. **Performance Monitoring** - Analyze response times and error patterns
4. **Data Processing** - Process large log datasets for analytics
5. **Compliance Reporting** - Generate structured reports from log data

## Troubleshooting

### Server Won't Start
- Check Python version (>=3.10 required)
- Verify dependencies: `uv sync`
- Check environment variables

### Import Errors
- Run tests to verify installation: `uv run pytest`
- Check file paths are correct
- Ensure you're in the Parallel_Sort directory

### Performance Issues
- For large files, use `parallel_sort_large_file`
- Adjust `chunk_size_mb` and `max_workers` parameters
- Monitor system memory usage

### File Not Found Errors
- Use absolute file paths
- Verify sample data files exist in `sample_data/` directory
- Check file permissions