---
title: Jarvis MCP
description: "JARVIS-CD MCP with a compact user pipeline contract and explicit admin compatibility profiles"
---

import MCPDetail from '@site/src/components/MCPDetail';

<MCPDetail
  name="Jarvis"
  icon="🤖"
  category="Data Processing"
  description="JARVIS-CD MCP with a compact user pipeline contract and explicit admin compatibility profiles"
  version="3.0.0"
  actions={["jarvis_create_pipeline", "jarvis_describe", "jarvis_add_step", "jarvis_edit_step", "jarvis_run", "jarvis_get_execution"]}
  platforms={["claude", "cursor", "vscode"]}
  keywords={["jarvis", "pipeline-management", "high-performance-computing", "hpc", "workflow", "data-pipelines", "scientific-computing", "mcp", "package-management"]}
  license="BSD-3-Clause"
  tools={[{"name": "jarvis_create_pipeline", "description": "Create a JARVIS pipeline. Optionally pass execution intent such as local, cluster, or hostfile mode; backend details are resolved where the MCP server runs.", "function_name": "jarvis_create_pipeline"}, {"name": "jarvis_describe", "description": "Describe JARVIS packages, one package, a pipeline, or one pipeline step.", "function_name": "jarvis_describe"}, {"name": "jarvis_add_step", "description": "Add a package-backed step to a JARVIS pipeline and optionally configure that step with package-owned settings.", "function_name": "jarvis_add_step"}, {"name": "jarvis_edit_step", "description": "Edit or remove a step in a JARVIS pipeline. Use operation='edit' with config, or operation='remove' without config.", "function_name": "jarvis_edit_step"}, {"name": "jarvis_run", "description": "Run a configured JARVIS pipeline. Optional execution intent selects local, cluster, or hostfile mode without exposing scheduler internals. Optional spack_specs are resolved into a filtered environment that JARVIS persists before direct or scheduler execution.", "function_name": "jarvis_run"}, {"name": "jarvis_get_execution", "description": "Query one JARVIS execution handle, durable lifecycle record, and runtime metadata. Progress is included by default and can be omitted. Set artifacts to {} or filters to include one bounded artifact page; omit artifacts to avoid querying the artifact manifest.", "function_name": "jarvis_get_execution"}]}
>


### Basic Usage
```python
# Load and process data with Jarvis
data = load_data("input_file")
processed_data = process_data(data)
save_data(processed_data, "output_file")
```

### Integration Example
```python
# Use Jarvis in a data pipeline
for file in data_files:
    data = load_data(file)
    result = analyze_data(data)
    export_results(result, f"analysis_{file}")
```


</MCPDetail>
