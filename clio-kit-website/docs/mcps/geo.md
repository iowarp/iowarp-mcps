---
title: Geo MCP
description: "MCP server for rendering GeoJSON vector layers into map images with basemaps"
---

import MCPDetail from '@site/src/components/MCPDetail';

<MCPDetail
  name="Geo"
  icon="🔧"
  category="Data Processing"
  description="MCP server for rendering GeoJSON vector layers into map images with basemaps"
  version="2.2.3"
  actions={["render_feature_map", "points_in_polygons", "bounding_box", "query_arcgis_features", "geocode", "filter_points_by_radius"]}
  platforms={["claude", "cursor", "vscode"]}
  keywords={["MCP", "geospatial", "mapping", "geojson", "visualization", "matplotlib", "geopandas"]}
  license="BSD-3-Clause"
  tools={[{"name": "render_feature_map", "description": "Render one or more GeoJSON layers (polygons/lines/points) onto a single map PNG with an optional basemap. Each layer accepts a style with fixed colors or data-driven coloring (color_by + category_colors, an 'epa_aqi' AQI scale, or a matplotlib colormap). Returns the output path and bounds.", "function_name": "render_feature_map"}, {"name": "points_in_polygons", "description": "Spatial overlap: return which GeoJSON points fall within (optionally buffered) GeoJSON polygons \u2014 e.g. which AirNow monitors lie inside the smoke footprint. Accepts inline GeoJSON or file paths. Returns the matched points with their properties and a matched_count.", "function_name": "points_in_polygons"}, {"name": "bounding_box", "description": "Compute the bounding box [min_lon, min_lat, max_lon, max_lat] of GeoJSON features (inline or file path), optionally padded by buffer_km. A deterministic geometry op for deriving an analysis region from a fire perimeter.", "function_name": "bounding_box"}, {"name": "query_arcgis_features", "description": "Query an ArcGIS FeatureServer layer (with optional lon/lat bbox and where clause) and write the returned features to a local GeoJSON file. The saved FeatureCollection can be fed directly into render_feature_map, points_in_polygons, or bounding_box.", "function_name": "query_arcgis_features"}, {"name": "geocode", "description": "Look up a free-text place name or location and return real coordinates from OpenStreetMap Nominatim (a lookup, not a model guess). Each match carries lat/lon, a [min_lon, min_lat, max_lon, max_lat] bbox, type, importance, and a provenance source so the region can be grounded and cited.", "function_name": "geocode"}, {"name": "filter_points_by_radius", "description": "Filter/rank any table of points by great-circle distance to a center. Reads a CSV (or GeoJSON points) of locations, computes the haversine distance from (center_lat, center_lon) to each row, and returns the rows within radius_km sorted ascending by distance, each annotated with distance_km. Latitude/longitude columns are auto-detected from common names (latitude/lat, longitude/lon/long) when not given. Domain-neutral: works for sensors, sites, cities, samples, or any lon/lat table.", "function_name": "filter_points_by_radius"}]}
>


### Basic Usage
```python
# Load and process data with Geo
data = load_data("input_file")
processed_data = process_data(data)
save_data(processed_data, "output_file")
```

### Integration Example
```python
# Use Geo in a data pipeline
for file in data_files:
    data = load_data(file)
    result = analyze_data(data)
    export_results(result, f"analysis_{file}")
```


</MCPDetail>
