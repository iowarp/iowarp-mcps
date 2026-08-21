---
title: Scientific-Catalog MCP
description: "Operator-owned scientific dataset discovery for remote agents"
---

import MCPDetail from '@site/src/components/MCPDetail';

<MCPDetail
  name="Scientific-Catalog"
  icon="🔧"
  category="Data Processing"
  description="Operator-owned scientific dataset discovery for remote agents"
  version="1.1.2"
  actions={["scientific_dataset_search", "scientific_dataset_describe"]}
  platforms={["claude", "cursor", "vscode"]}
  keywords={[]}
  license="BSD-3-Clause"
  tools={[{"name": "scientific_dataset_search", "description": "Search operator-registered scientific datasets and return bounded intrinsic summaries.", "function_name": "scientific_dataset_search"}, {"name": "scientific_dataset_describe", "description": "Return one exact operator catalog record plus a top-level dataset_descriptor. Pass dataset_descriptor unchanged as jarvis_add_step config.dataset_descriptor; do not pass the surrounding dataset record.", "function_name": "scientific_dataset_describe"}]}
>


### Basic Usage
```python
# Load and process data with Scientific-Catalog
data = load_data("input_file")
processed_data = process_data(data)
save_data(processed_data, "output_file")
```

### Integration Example
```python
# Use Scientific-Catalog in a data pipeline
for file in data_files:
    data = load_data(file)
    result = analyze_data(data)
    export_results(result, f"analysis_{file}")
```


</MCPDetail>
