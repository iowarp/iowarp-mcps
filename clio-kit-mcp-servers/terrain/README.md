# Terrain MCP

Generic terrain analysis over gridded elevation data and point clouds. Analyze a
Digital Elevation Model (DEM) for elevation, slope, aspect, and site
suitability, or read an x/y/z point cloud and grid it into a DEM-like surface.

## Tools

### `dem_terrain`

Analyze a DEM grid. Computes per-cell slope and aspect, then a site-suitability
mask from optional `elevation_min`, `elevation_max`, and `slope_max_degrees`
criteria.

- Formats: CSV numeric grid, NPY, NPZ (uses a `dem` array if present).
- GeoTIFF (`.tif`/`.tiff`) needs the optional `geotiff` extra (rasterio).
- Returns `{ok, shape, cell_size, metadata, criteria, valid_cell_count,
  suitable_cell_count, suitable_fraction, elevation, slope_degrees,
  aspect_degrees, representative_suitable_cells}`.

### `pointcloud_read`

Read an x/y/z point cloud and bin it onto a regular grid (mean z per cell) to
produce a DEM-like surface.

- Formats: CSV with `x,y,z` columns, NPY, NPZ (uses `x`/`y`/`z` or `points`).
- LAS/LAZ needs the optional `laz` extra (laspy).
- With `output_dem_path`, writes the gridded surface as a CSV DEM you can feed
  straight into `dem_terrain`.
- Returns `{ok, point_count, grid_cell_size, metadata, bounds, grid_shape,
  filled_cell_count, empty_cell_count, output_dem_path, x, y, z,
  gridded_elevation}`.

## Optional extras

```sh
pip install 'terrain-mcp[geotiff]'   # GeoTIFF DEMs via rasterio
pip install 'terrain-mcp[laz]'       # LAS/LAZ point clouds via laspy
```

Without the extras, CSV/NPY/NPZ work out of the box; requesting GeoTIFF or
LAS/LAZ returns an actionable tool error.

## Run

```sh
uvx clio-kit terrain   # via the clio-kit launcher
terrain-mcp            # direct entry point
```

## Test

```sh
uv run pytest -v
```

## Capabilities

### `dem_terrain`
**Description**: Analyze a Digital Elevation Model grid for elevation, slope, aspect, and site suitability. Accepts CSV numeric grids, NPY, and NPZ (with a 'dem' array); GeoTIFF requires the optional rasterio extra. Returns grid shape, summary statistics, suitability counts, and representative suitable cells.
**Hints**: read-only, idempotent
**Tags**: dem, slope, suitability, terrain

### `pointcloud_read`
**Description**: Read an x/y/z point cloud and grid it into a DEM-like surface by averaging z per cell. Accepts CSV with x,y,z columns, NPY, and NPZ; LAS/LAZ requires the optional laspy extra. Optionally writes the gridded surface to a CSV DEM for downstream dem_terrain analysis. Returns point/grid stats and bounds.
**Hints**: idempotent
**Tags**: dem, gridding, pointcloud, terrain

### Resources

- `terrain://capabilities` - Supported input formats, tools, and safety limits for terrain analysis.

### Prompts

- **terrain_suitability_workflow**: Guided workflow for assessing site suitability from terrain data.
## Claude Code

```bash
claude mcp add clio-terrain -- uvx clio-kit terrain
```

Or install via the CLIO Kit plugin marketplace:

```
/plugin marketplace add iowarp/clio-kit
/plugin install clio-terrain@iowarp-clio-kit
```
## Claude Desktop

Add to your Claude Desktop config (`claude_desktop_config.json`):

```json
{
  "mcpServers": {
    "clio-terrain": {
      "command": "uvx",
      "args": [
        "clio-kit",
        "terrain"
      ]
    }
  }
}
```
