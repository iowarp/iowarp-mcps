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
  version="3.6.1"
  actions={["jarvis_create_pipeline", "jarvis_describe", "jarvis_add_step", "jarvis_edit_step", "jarvis_run", "jarvis_get_execution"]}
  platforms={["claude", "cursor", "vscode"]}
  keywords={["jarvis", "pipeline-management", "high-performance-computing", "hpc", "workflow", "data-pipelines", "scientific-computing", "mcp", "package-management"]}
  license="BSD-3-Clause"
  tools={[{"name": "jarvis_create_pipeline", "description": "Create a JARVIS pipeline. Optionally pass execution intent such as local, cluster, or hostfile mode; backend details are resolved where the MCP server runs.", "function_name": "jarvis_create_pipeline"}, {"name": "jarvis_describe", "description": "Describe JARVIS packages, one package, a pipeline, or one pipeline step. For a named application, first use target='package' with its unique short name or fully qualified package name. Use target='package_search' for bounded discovery, then describe the selected canonical name. target='packages' is an exhaustive legacy inventory with every package's settings and can be large; use it only when the complete installed catalog is explicitly required.", "function_name": "jarvis_describe"}, {"name": "jarvis_add_step", "description": "Add and configure a package-backed step in a JARVIS pipeline. First use jarvis_describe(target='package') for the selected package; config keys must use its canonical setting names exactly, except for aliases explicitly listed there. User-level step configuration is always validated and cannot be bypassed.", "function_name": "jarvis_add_step"}, {"name": "jarvis_edit_step", "description": "Edit or remove a step in a JARVIS pipeline. Use operation='edit' with config, or operation='remove' without config.", "function_name": "jarvis_edit_step"}, {"name": "jarvis_run", "description": "Start a configured JARVIS pipeline and return its durable execution handle without waiting for workload completion. Optional execution intent selects local, cluster, or hostfile mode without exposing scheduler internals. Optional spack_specs are resolved into a filtered environment that JARVIS persists before direct or scheduler execution. Use jarvis_get_execution with the returned pipeline_id and execution_id to query lifecycle, progress, artifacts, and execution-owned service runtimes.", "function_name": "jarvis_run"}, {"name": "jarvis_get_execution", "description": "Query one JARVIS execution handle, durable lifecycle record, and runtime metadata. Progress is included by default and can be omitted. Set include_service_runtimes=true to include execution-owned network services such as an interactive ParaView runtime; authenticated services expose only a non-secret bearer token SHA-256 fingerprint. Set artifacts to {} or filters to include one bounded artifact page; omit artifacts to avoid querying the artifact manifest.", "function_name": "jarvis_get_execution"}]}
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
