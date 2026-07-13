---
title: Seismic MCP
description: "MCP server for earthquake-sequence analysis on saved catalogs: completeness magnitude, Gutenberg-Richter b-value, Bath gap, Omori decay, and a three-panel figure"
---

import MCPDetail from '@site/src/components/MCPDetail';

<MCPDetail
  name="Seismic"
  icon="🔧"
  category="Analysis & Visualization"
  description="MCP server for earthquake-sequence analysis on saved catalogs: completeness magnitude, Gutenberg-Richter b-value, Bath gap, Omori decay, and a three-panel figure"
  version="2.2.3"
  actions={["analyze_sequence", "plot_sequence"]}
  platforms={["claude", "cursor", "vscode"]}
  keywords={["MCP", "seismic", "earthquake", "seismology", "gutenberg-richter", "omori", "matplotlib", "numpy"]}
  license="BSD-3-Clause"
  tools={[{"name": "analyze_sequence", "description": "Compute the descriptive statistics of a saved earthquake catalog: completeness magnitude (Mc), the Gutenberg-Richter b-value with uncertainty, the largest event, the Bath-law magnitude gap to the second-largest, the share of events before vs after the largest, the spatial extent, and the Omori post-event rate decay. Returns statistics ONLY - it does not classify the sequence.", "function_name": "analyze_sequence"}, {"name": "plot_sequence", "description": "Render the three-panel earthquake-sequence figure from a saved catalog: (1) an epicenter map sized by magnitude and coloured by time, (2) the Gutenberg-Richter magnitude-frequency distribution with an optional b-value fit line, and (3) the cumulative count over time. Writes a PNG and returns its path; pass mc/b_value to draw the G-R fit line.", "function_name": "plot_sequence"}]}
>


### Basic Usage
```python
# Use Seismic MCP
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
