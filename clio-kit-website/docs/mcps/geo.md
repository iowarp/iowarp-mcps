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
  version="2.3.0"
  actions={["render_feature_map", "points_in_polygons", "bounding_box", "query_arcgis_features", "geocode", "filter_points_by_radius", "inspect_geojson", "validate_geojson", "summarize_geojson", "feature_bbox"]}
  platforms={["claude", "cursor", "vscode"]}
  keywords={["MCP", "geospatial", "mapping", "geojson", "visualization", "matplotlib", "geopandas"]}
  license="BSD-3-Clause"
  tools={[{"name": "render_feature_map", "description": "Render one or more GeoJSON layers (polygons/lines/points) onto a single map PNG with an optional basemap. Each layer accepts a style with fixed colors or data-driven coloring (color_by + category_colors, an 'epa_aqi' AQI scale, or a matplotlib colormap). Returns the output path and bounds.", "function_name": "render_feature_map"}, {"name": "points_in_polygons", "description": "Spatial overlap: return which GeoJSON points fall within (optionally buffered) GeoJSON polygons \u2014 e.g. which AirNow monitors lie inside the smoke footprint. Accepts inline GeoJSON or file paths. Returns the matched points with their properties and a matched_count.", "function_name": "points_in_polygons"}, {"name": "bounding_box", "description": "Compute the bounding box [min_lon, min_lat, max_lon, max_lat] of the VALID geometry in GeoJSON features (inline or file path), optionally padded by pad_km and rounded to 4 decimal places. Features whose geometry cannot be parsed are skipped, so feature_count reports valid geometries only. Use this to derive an analysis region for mapping or a spatial query; use feature_bbox instead to measure a document's raw coordinate extent including malformed features.", "function_name": "bounding_box"}, {"name": "query_arcgis_features", "description": "Query an ArcGIS FeatureServer layer (with optional lon/lat bbox and where clause) and write the returned features to a local GeoJSON file. The saved FeatureCollection can be fed directly into render_feature_map, points_in_polygons, or bounding_box.", "function_name": "query_arcgis_features"}, {"name": "geocode", "description": "Look up a free-text place name or location and return real coordinates from OpenStreetMap Nominatim (a lookup, not a model guess). Each match carries lat/lon, a [min_lon, min_lat, max_lon, max_lat] bbox, type, importance, and a provenance source so the region can be grounded and cited.", "function_name": "geocode"}, {"name": "filter_points_by_radius", "description": "Filter/rank any table of points by great-circle distance to a center. Reads a CSV (or GeoJSON points) of locations, computes the haversine distance from (center_lat, center_lon) to each row, and returns the rows within radius_km sorted ascending by distance, each annotated with distance_km. Latitude/longitude columns are auto-detected from common names (latitude/lat, longitude/lon/long) when not given. Domain-neutral: works for sensors, sites, cities, samples, or any lon/lat table.", "function_name": "filter_points_by_radius"}, {"name": "inspect_geojson", "description": "Inspect a GeoJSON document and report its geometry types and counts, feature count, property keys (schema), bounding box [min_lon, min_lat, max_lon, max_lat], CRS if present, and total vertex count. Reads the document as written, without a geometry engine, so it reports what the file actually contains. Accepts a file path or inline GeoJSON.", "function_name": "inspect_geojson"}, {"name": "validate_geojson", "description": "Validate the structural well-formedness of a GeoJSON document: that the top-level type is recognized and every geometry's type and coordinates are well-formed (correct nesting depth, finite numeric positions). Returns {valid, errors}. Run this before a rendering or overlap tool, which silently skip geometry they cannot parse.", "function_name": "validate_geojson"}, {"name": "summarize_geojson", "description": "Produce a compact human-readable summary of a GeoJSON document: counts per geometry type, bounding box, property keys, and a few sample feature property sets. Accepts a file path or inline GeoJSON.", "function_name": "summarize_geojson"}, {"name": "feature_bbox", "description": "Compute the bounding box [min_lon, min_lat, max_lon, max_lat] of EVERY coordinate in a GeoJSON document, without validating geometry and without rounding. feature_count counts all features in the document, including malformed ones. Use this to inspect a file's raw extent; use bounding_box instead for the extent of valid geometry, padded and rounded, when feeding a map render or spatial query.", "function_name": "feature_bbox"}]}
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
