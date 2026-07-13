---
title: Hdf5 MCP
description: "HDF5 FastMCP - Scientific Data Access for AI Agents | CLIO Kit MCP Server"
---

import MCPDetail from '@site/src/components/MCPDetail';

<MCPDetail
  name="Hdf5"
  icon="🗂️"
  category="Data Processing"
  description="HDF5 FastMCP - Scientific Data Access for AI Agents | CLIO Kit MCP Server"
  version="2.2.3"
  actions={["open_file", "close_file", "get_filename", "get_mode", "get_by_path", "list_keys", "visit", "read_full_dataset", "read_partial_dataset", "get_shape", "get_dtype", "get_size", "get_chunks", "read_attribute", "list_attributes", "hdf5_parallel_scan", "hdf5_batch_read", "hdf5_stream_data", "hdf5_aggregate_stats", "analyze_dataset_structure", "find_similar_datasets", "suggest_next_exploration", "identify_io_bottlenecks", "optimize_access_pattern", "refresh_hdf5_resources", "list_available_hdf5_files", "export_dataset"]}
  platforms={["claude", "cursor", "vscode"]}
  keywords={["hdf5", "scientific-data", "hierarchical-data", "data-analysis", "scientific-computing", "mcp", "llm-integration", "data-structures"]}
  license="BSD-3-Clause"
  tools={[{"name": "open_file", "description": "Open an HDF5 file for operations.", "function_name": "open_file"}, {"name": "close_file", "description": "Close the current HDF5 file.\n\nReturns:\n    Status message", "function_name": "close_file"}, {"name": "get_filename", "description": "Get the current file's path.\n\nReturns:\n    File path", "function_name": "get_filename"}, {"name": "get_mode", "description": "Get the current file's access mode.\n\nReturns:\n    File mode", "function_name": "get_mode"}, {"name": "get_by_path", "description": "Get a dataset or group by path.", "function_name": "get_by_path"}, {"name": "list_keys", "description": "List keys in a group.", "function_name": "list_keys"}, {"name": "visit", "description": "Visit all nodes recursively.", "function_name": "visit"}, {"name": "read_full_dataset", "description": "Read an entire dataset with efficient chunked reading for large datasets.", "function_name": "read_full_dataset"}, {"name": "read_partial_dataset", "description": "Read a portion of a dataset with slicing.", "function_name": "read_partial_dataset"}, {"name": "get_shape", "description": "Get the shape of a dataset.", "function_name": "get_shape"}, {"name": "get_dtype", "description": "Get the data type of a dataset.", "function_name": "get_dtype"}, {"name": "get_size", "description": "Get the size of a dataset.", "function_name": "get_size"}, {"name": "get_chunks", "description": "Get chunk information for a dataset.", "function_name": "get_chunks"}, {"name": "read_attribute", "description": "Read an attribute from an object.", "function_name": "read_attribute"}, {"name": "list_attributes", "description": "List all attributes of an object.", "function_name": "list_attributes"}, {"name": "hdf5_parallel_scan", "description": "Fast multi-file scanning with parallel processing.", "function_name": "hdf5_parallel_scan"}, {"name": "hdf5_batch_read", "description": "Read multiple datasets in parallel.", "function_name": "hdf5_batch_read"}, {"name": "hdf5_stream_data", "description": "Stream large datasets efficiently with memory management.", "function_name": "hdf5_stream_data"}, {"name": "hdf5_aggregate_stats", "description": "Parallel statistics computation across multiple datasets.", "function_name": "hdf5_aggregate_stats"}, {"name": "analyze_dataset_structure", "description": "Analyze and understand file organization and data patterns with AI insights.", "function_name": "analyze_dataset_structure"}, {"name": "find_similar_datasets", "description": "Find datasets with similar characteristics to a reference dataset with AI analysis.", "function_name": "find_similar_datasets"}, {"name": "suggest_next_exploration", "description": "Suggest interesting data to explore next based on current location with AI recommendations.", "function_name": "suggest_next_exploration"}, {"name": "identify_io_bottlenecks", "description": "Identify potential I/O bottlenecks and performance issues with AI recommendations.", "function_name": "identify_io_bottlenecks"}, {"name": "optimize_access_pattern", "description": "Suggest better approaches for data access based on usage patterns.", "function_name": "optimize_access_pattern"}, {"name": "refresh_hdf5_resources", "description": "Re-scan client roots and update available HDF5 resources.\n\nFastMCP automatically sends notifications/resources/list_changed to clients.\n\nReturns:\n    Summary of refreshed resources", "function_name": "refresh_hdf5_resources"}, {"name": "list_available_hdf5_files", "description": "List all registered HDF5 files with resource URIs for Claude Code @ mentions.\n\nReturns:\n    List of available files with resource URIs", "function_name": "list_available_hdf5_files"}, {"name": "export_dataset", "description": "Export dataset to various formats with user format selection.", "function_name": "export_dataset"}]}
>


### Basic Usage
```python
# Load and process data with Hdf5
data = load_data("input_file")
processed_data = process_data(data)
save_data(processed_data, "output_file")
```

### Integration Example
```python
# Use Hdf5 in a data pipeline
for file in data_files:
    data = load_data(file)
    result = analyze_data(data)
    export_results(result, f"analysis_{file}")
```


</MCPDetail>
