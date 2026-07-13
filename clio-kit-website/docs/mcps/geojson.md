---
title: Geojson MCP
description: "MCP server for inspecting, validating, and summarizing GeoJSON documents (stdlib only)"
---

import MCPDetail from '@site/src/components/MCPDetail';

<MCPDetail
  name="Geojson"
  icon="🔧"
  category="Utilities"
  description="MCP server for inspecting, validating, and summarizing GeoJSON documents (stdlib only)"
  version="2.2.3"
  actions={["inspect_geojson", "validate_geojson", "summarize_geojson", "feature_bbox"]}
  platforms={["claude", "cursor", "vscode"]}
  keywords={["MCP", "geojson", "geospatial", "inspection", "validation", "bbox"]}
  license="BSD-3-Clause"
  tools={[{"name": "inspect_geojson", "description": "Inspect a GeoJSON document and report its geometry types and counts, feature count, property keys (schema), bounding box [min_lon, min_lat, max_lon, max_lat], CRS if present, and total vertex count. Accepts a file path or inline GeoJSON.", "function_name": "inspect_geojson"}, {"name": "validate_geojson", "description": "Validate the structural well-formedness of a GeoJSON document: that the top-level type is recognized and every geometry's type and coordinates are well-formed (correct nesting depth, finite numeric positions). Returns {valid, errors}.", "function_name": "validate_geojson"}, {"name": "summarize_geojson", "description": "Produce a compact human-readable summary of a GeoJSON document: counts per geometry type, bounding box, property keys, and a few sample feature property sets. Accepts a file path or inline GeoJSON.", "function_name": "summarize_geojson"}, {"name": "feature_bbox", "description": "Compute the overall bounding box [min_lon, min_lat, max_lon, max_lat] of all features in a GeoJSON document. Accepts a file path or inline GeoJSON. Returns the bbox (or null when there are no coordinates) and the feature count.", "function_name": "feature_bbox"}]}
>


### Basic Usage
```python
# Use Geojson MCP
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
