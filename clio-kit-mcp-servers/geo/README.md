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
