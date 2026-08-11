---
title: Sac MCP
description: "MCP server for analyzing SAC seismic-waveform files and TAR archives: inspect members, compute per-trace statistics, and plot traces"
---

import MCPDetail from '@site/src/components/MCPDetail';

<MCPDetail
  name="Sac"
  icon="🔧"
  category="Analysis & Visualization"
  description="MCP server for analyzing SAC seismic-waveform files and TAR archives: inspect members, compute per-trace statistics, and plot traces"
  version="2.3.0"
  actions={["inspect_archive", "compute_trace_statistics", "plot_traces", "analyze_sequence", "plot_sequence"]}
  platforms={["claude", "cursor", "vscode"]}
  keywords={["MCP", "seismic", "sac", "waveform", "geophysics", "matplotlib", "numpy"]}
  license="BSD-3-Clause"
  tools={[{"name": "inspect_archive", "description": "Inspect a staged SAC file or TAR archive and summarize its SAC waveform members: count, a sample of member names and sizes, and the inferred stations and phases. Read-only; a good first step before computing statistics or plotting.", "function_name": "inspect_archive"}, {"name": "compute_trace_statistics", "description": "Compute per-trace amplitude statistics (min, max, mean, std, peak_abs) plus header metadata (npts, delta_s, begin_s, end_s) for SAC traces in a file or archive. Read-only; bounded by max_traces.", "function_name": "compute_trace_statistics"}, {"name": "plot_traces", "description": "Plot selected SAC traces from a file or archive to a PNG artifact. Traces are amplitude-normalized and vertically offset. Writes a file; returns the output path, plotted member names, and render duration.", "function_name": "plot_traces"}, {"name": "analyze_sequence", "description": "Compute the descriptive statistics of a saved earthquake catalog: completeness magnitude (Mc), the Gutenberg-Richter b-value with uncertainty, the largest event, the Bath-law magnitude gap to the second-largest, the share of events before vs after the largest, the spatial extent, and the Omori post-event rate decay. Returns statistics ONLY - it does not classify the sequence.", "function_name": "analyze_sequence"}, {"name": "plot_sequence", "description": "Render the three-panel earthquake-sequence figure from a saved catalog: (1) an epicenter map sized by magnitude and coloured by time, (2) the Gutenberg-Richter magnitude-frequency distribution with an optional b-value fit line, and (3) the cumulative count over time. Writes a PNG and returns its path; pass mc/b_value to draw the G-R fit line.", "function_name": "plot_sequence"}]}
>


### Basic Usage
```python
# Use Sac MCP
result = perform_operation("input_data")
print(f"Result: {result}")
```

### Advanced Usage
```python
# Chain multiple operations
data = load_input("source")
processed = process_data(data)
final_result = finalize_output(processed)
```


</MCPDetail>
