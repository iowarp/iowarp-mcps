# GeoJSON MCP

Domain-neutral GeoJSON inspection tooling. Reads, validates, summarizes, and
measures the extent of GeoJSON documents (FeatureCollection / Feature / bare
geometry) supplied as a file path or inline GeoJSON. Built with the Python
standard library only (`json` + `math`) — no geopandas/shapely required.

## Tools

### `inspect_geojson`

Full structural report: geometry types and counts, feature count, property keys
(schema), bounding box `[min_lon, min_lat, max_lon, max_lat]`, CRS if present,
and total vertex count. Accepts a file path or inline GeoJSON.

Returns `{geojson_type, feature_count, geometry_types, property_keys, bbox,
crs, total_vertices, sample_features}`.

### `validate_geojson`

Checks structural well-formedness — the top-level `type` is recognized and every
geometry's type and coordinates are well-formed (correct nesting depth, finite
numeric positions).

Returns `{valid, errors}`.

### `summarize_geojson`

A compact human-readable summary: counts per geometry type, bounding box,
property keys, and a few sample feature property sets.

Returns `{summary, feature_count, geometry_types, bbox, property_keys,
sample_features}`.

### `feature_bbox`

The overall bounding box `[min_lon, min_lat, max_lon, max_lat]` of all features
(reuses the same shared bbox helper as the other tools).

Returns `{bbox, feature_count}`.

## Input forms

Every tool accepts the `source` argument as either:

- a path to a `.geojson`/JSON file, or
- inline GeoJSON as a JSON string (`FeatureCollection`, `Feature`, or a bare
  geometry object).

Coordinates are assumed lon/lat (WGS84) unless a `crs` member says otherwise.

## Run

```sh
uvx clio-kit geojson      # via the clio-kit launcher
geojson-mcp               # direct entry point
```

## Test

```sh
uv run --extra dev pytest
```

Tests run against small temporary `.geojson` fixtures only — no network access.

## Capabilities

### `inspect_geojson`
**Description**: Inspect a GeoJSON document and report its geometry types and counts, feature count, property keys (schema), bounding box [min_lon, min_lat, max_lon, max_lat], CRS if present, and total vertex count. Accepts a file path or inline GeoJSON.
**Hints**: read-only, idempotent
**Tags**: geojson, inspection, metadata, schema

### `validate_geojson`
**Description**: Validate the structural well-formedness of a GeoJSON document: that the top-level type is recognized and every geometry's type and coordinates are well-formed (correct nesting depth, finite numeric positions). Returns {valid, errors}.
**Hints**: read-only, idempotent
**Tags**: geojson, linting, validation

### `summarize_geojson`
**Description**: Produce a compact human-readable summary of a GeoJSON document: counts per geometry type, bounding box, property keys, and a few sample feature property sets. Accepts a file path or inline GeoJSON.
**Hints**: read-only, idempotent
**Tags**: geojson, inspection, summary

### `feature_bbox`
**Description**: Compute the overall bounding box [min_lon, min_lat, max_lon, max_lat] of all features in a GeoJSON document. Accepts a file path or inline GeoJSON. Returns the bbox (or null when there are no coordinates) and the feature count.
**Hints**: read-only, idempotent
**Tags**: bbox, geojson, region

### Resources

- `geojson://capabilities` - Describe what the geojson MCP server can do.

### Prompts

- **inspect_workflow**: Guided workflow: validate, then inspect and summarize a GeoJSON document.
## Claude Code

```bash
claude mcp add clio-geojson -- uvx clio-kit geojson
```

Or install via the CLIO Kit plugin marketplace:

```
/plugin marketplace add iowarp/clio-kit
/plugin install clio-geojson@iowarp-clio-kit
```
## Claude Desktop

Add to your Claude Desktop config (`claude_desktop_config.json`):

```json
{
  "mcpServers": {
    "clio-geojson": {
      "command": "uvx",
      "args": [
        "clio-kit",
        "geojson"
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
    "clio-geojson": {
      "command": "uvx",
      "args": [
        "clio-kit",
        "geojson"
      ]
    }
  }
}
```

Or install the CLIO Kit extension:

```bash
gemini extensions install https://github.com/iowarp/clio-kit
```
