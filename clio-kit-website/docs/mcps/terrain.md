---
title: Terrain MCP
description: "MCP server for terrain analysis: DEM slope/aspect/suitability and point-cloud reading/gridding"
---

import MCPDetail from '@site/src/components/MCPDetail';

<MCPDetail
  name="Terrain"
  icon="🔧"
  category="Analysis & Visualization"
  description="MCP server for terrain analysis: DEM slope/aspect/suitability and point-cloud reading/gridding"
  version="2.2.3"
  actions={["dem_terrain", "pointcloud_read"]}
  platforms={["claude", "cursor", "vscode"]}
  keywords={["MCP", "terrain", "dem", "slope", "aspect", "point-cloud", "geospatial", "numpy"]}
  license="BSD-3-Clause"
  tools={[{"name": "dem_terrain", "description": "Analyze a Digital Elevation Model grid for elevation, slope, aspect, and site suitability. Accepts CSV numeric grids, NPY, and NPZ (with a 'dem' array); GeoTIFF requires the optional rasterio extra. Returns grid shape, summary statistics, suitability counts, and representative suitable cells.", "function_name": "dem_terrain"}, {"name": "pointcloud_read", "description": "Read an x/y/z point cloud and grid it into a DEM-like surface by averaging z per cell. Accepts CSV with x,y,z columns, NPY, and NPZ; LAS/LAZ requires the optional laspy extra. Optionally writes the gridded surface to a CSV DEM for downstream dem_terrain analysis. Returns point/grid stats and bounds.", "function_name": "pointcloud_read"}]}
>


### Basic Usage
```python
# Use Terrain MCP
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
