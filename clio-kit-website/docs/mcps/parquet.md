---
title: Parquet MCP
description: "MCP server for Apache Parquet files"
---

import MCPDetail from '@site/src/components/MCPDetail';

<MCPDetail
  name="Parquet"
  icon="📋"
  category="Data Processing"
  description="MCP server for Apache Parquet files"
  version="2.2.3"
  actions={["summarize_tool", "read_slice_tool", "get_column_preview_tool", "aggregate_column_tool"]}
  platforms={["claude", "cursor", "vscode"]}
  keywords={["parquet", "columnar-data", "data-analysis", "scientific-computing", "mcp", "llm-integration", "apache-arrow"]}
  license="BSD-3-Clause"
  tools={[{"name": "summarize_tool", "description": "Return Parquet schema, row count, and file size.", "function_name": "summarize_tool"}, {"name": "read_slice_tool", "description": "Read a row slice from a Parquet file with optional column projection and filtering.", "function_name": "read_slice_tool"}, {"name": "get_column_preview_tool", "description": "Preview values from a specific column with pagination.", "function_name": "get_column_preview_tool"}, {"name": "aggregate_column_tool", "description": "Compute aggregate statistics (min, max, mean, etc.) on a Parquet column.", "function_name": "aggregate_column_tool"}]}
>


### Basic Usage
```python
# Load and process data with Parquet
data = load_data("input_file")
processed_data = process_data(data)
save_data(processed_data, "output_file")
```

### Integration Example
```python
# Use Parquet in a data pipeline
for file in data_files:
    data = load_data(file)
    result = analyze_data(data)
    export_results(result, f"analysis_{file}")
```


</MCPDetail>
