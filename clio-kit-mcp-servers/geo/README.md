# Geo MCP

Renders GeoJSON vector layers into map images. Any tool that returns GeoJSON
features — catalog feature queries, file inspection, analysis output — can be
visualized as a single layered map with an optional web-tile basemap.

## Tool: `render_feature_map`

Render one or more layers (polygons, lines, points) to a PNG.

Each layer:

```jsonc
{
  "name": "fire perimeter",
  "geojson": { /* FeatureCollection | Feature | geometry | list | JSON string | path */ },
  "style": {
    "facecolor": "red", "edgecolor": "darkred", "alpha": 0.55, "linewidth": 2,
    "color": "...",            // points / single-color fill
    "markersize": 45,          // points
    "zorder": 5,               // draw order
    "color_by": "AQI",         // property to color by
    "scale": "epa_aqi",        // EPA AQI bands, or a matplotlib colormap name
    "category_colors": { "3 - 25": "#ccc" },  // explicit value -> color
    "legend": true
  }
}
```

Top-level args: `output_path`, `title`, `basemap` (CartoDB Positron, needs
network; degrades gracefully if tiles are unavailable), and an optional
`bbox` view window `[min_lon, min_lat, max_lon, max_lat]`.

Returns `{status, output_path, size_bytes, bounds, basemap, layers}`.

### Example — wildfire downwind brief

Three layers from live feature queries: a fire perimeter polygon (red), NWS
smoke-forecast polygons colored by concentration class, and AirNow monitors
colored by `epa_aqi`. One call produces the full situational map.

## Run

```sh
uvx clio-kit geo          # via the clio-kit launcher
geo-mcp                   # direct entry point
```

## Test

```sh
uv run --extra dev pytest
```

Tests disable the basemap so they run without network access.

## Capabilities

### `render_feature_map`
**Description**: Render one or more GeoJSON layers (polygons/lines/points) onto a single map PNG with an optional basemap. Each layer accepts a style with fixed colors or data-driven coloring (color_by + category_colors, an 'epa_aqi' AQI scale, or a matplotlib colormap). Returns the output path and bounds.
**Hints**: destructive, idempotent
**Tags**: geojson, geospatial, map, visualization

### `points_in_polygons`
**Description**: Spatial overlap: return which GeoJSON points fall within (optionally buffered) GeoJSON polygons — e.g. which AirNow monitors lie inside the smoke footprint. Accepts inline GeoJSON or file paths. Returns the matched points with their properties and a matched_count.
**Hints**: read-only, idempotent
**Tags**: geojson, geospatial, overlap, spatial-join

### `bounding_box`
**Description**: Compute the bounding box [min_lon, min_lat, max_lon, max_lat] of GeoJSON features (inline or file path), optionally padded by buffer_km. A deterministic geometry op for deriving an analysis region from a fire perimeter.
**Hints**: read-only, idempotent
**Tags**: bbox, geojson, geospatial, region

### `query_arcgis_features`
**Description**: Query an ArcGIS FeatureServer layer (with optional lon/lat bbox and where clause) and write the returned features to a local GeoJSON file. The saved FeatureCollection can be fed directly into render_feature_map, points_in_polygons, or bounding_box.
**Hints**: read-only, idempotent
**Tags**: arcgis, features, geojson, geospatial, retrieval

### `geocode`
**Description**: Look up a free-text place name or location and return real coordinates from OpenStreetMap Nominatim (a lookup, not a model guess). Each match carries lat/lon, a [min_lon, min_lat, max_lon, max_lat] bbox, type, importance, and a provenance source so the region can be grounded and cited.
**Hints**: read-only, idempotent
**Tags**: coordinates, geocoding, location

### `filter_points_by_radius`
**Description**: Filter/rank any table of points by great-circle distance to a center. Reads a CSV (or GeoJSON points) of locations, computes the haversine distance from (center_lat, center_lon) to each row, and returns the rows within radius_km sorted ascending by distance, each annotated with distance_km. Latitude/longitude columns are auto-detected from common names (latitude/lat, longitude/lon/long) when not given. Domain-neutral: works for sensors, sites, cities, samples, or any lon/lat table.
**Hints**: read-only, idempotent
**Tags**: distance, filter, geospatial, haversine, proximity

### Resources

- `geo://capabilities` - Describe what the geo MCP server can do.

### Prompts

- **map_arcgis_layer**: Guided workflow: retrieve an ArcGIS layer and render it on a map.
## Claude Code

```bash
claude mcp add clio-geo -- uvx clio-kit geo
```

Or install via the CLIO Kit plugin marketplace:

```
/plugin marketplace add iowarp/clio-kit
/plugin install clio-geo@iowarp-clio-kit
```
## Claude Desktop

Add to your Claude Desktop config (`claude_desktop_config.json`):

```json
{
  "mcpServers": {
    "clio-geo": {
      "command": "uvx",
      "args": [
        "clio-kit",
        "geo"
      ]
    }
  }
}
```
## Gemini CLI

Add to `~/.gemini/settings.json`:

```json
{
  "mcpServers": {
    "clio-geo": {
      "command": "uvx",
      "args": [
        "clio-kit",
        "geo"
      ]
    }
  }
}
```

Or install the CLIO Kit extension:

```bash
gemini extensions install https://github.com/iowarp/clio-kit
```