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
  version="2.1.0"
  actions={["spack_find", "spack_locate", "spack_install"]}
  platforms={["claude", "cursor", "vscode"]}
  keywords={[]}
  license="BSD-3-Clause"
  tools={[{"name": "spack_find", "description": "List installed Spack packages matching an optional constraint. No matches is a successful result with count=0 and packages=[].", "function_name": "spack_find"}, {"name": "spack_locate", "description": "Resolve one unique installed Spack spec. Copy spack_locate.output.load_spec unchanged into one element of jarvis_run.input.spack_specs; do not derive or pass an executable path from the returned prefix. An absent package returns the structured not_installed error.", "function_name": "spack_locate"}, {"name": "spack_install", "description": "Install one Spack spec with explicit reusable or fresh concretization and verify that a matching install is observable.", "function_name": "spack_install"}]}
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
