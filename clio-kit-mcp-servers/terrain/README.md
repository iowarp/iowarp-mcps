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
