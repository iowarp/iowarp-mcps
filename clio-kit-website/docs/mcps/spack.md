---
title: Spack MCP
description: "Structured Spack discovery and installation tools for scientific agents"
---

import MCPDetail from '@site/src/components/MCPDetail';

<MCPDetail
  name="Spack"
  icon="🔧"
  category="Utilities"
  description="Structured Spack discovery and installation tools for scientific agents"
  version="2.2.0"
  actions={["spack_find", "spack_locate", "spack_search", "spack_info", "spack_install"]}
  platforms={["claude", "cursor", "vscode"]}
  keywords={[]}
  license="BSD-3-Clause"
  tools={[{"name": "spack_find", "description": "List installed Spack packages matching an optional constraint. No matches is a successful result with count=0 and packages=[].", "function_name": "spack_find"}, {"name": "spack_locate", "description": "Resolve one unique installed Spack spec and return its exact prefix. An absent package returns the structured not_installed error, enriched with recipe availability.", "function_name": "spack_locate"}, {"name": "spack_search", "description": "Search recipe availability across every registered Spack repo, broader than find/locate which only see what is installed.", "function_name": "spack_search"}, {"name": "spack_info", "description": "Describe one recipe's versions, variants, and description; falls back to parsing package.py when spack info is unavailable.", "function_name": "spack_info"}, {"name": "spack_install", "description": "Install one Spack spec with explicit reusable or fresh concretization, a full on-disk build log, and the install prefix on success.", "function_name": "spack_install"}]}
>


### Basic Usage
```python
# Use Spack MCP
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
