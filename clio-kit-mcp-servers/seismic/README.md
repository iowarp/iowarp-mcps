# Seismic MCP

Characterizes an earthquake sequence from a catalog you already have on disk.
Point it at a saved **GeoJSON** (a USGS-FDSN-style `FeatureCollection` or an
`{"events": [...]}` wrapper) or a **CSV** (columns `mag`/`time`/`lon`/`lat`,
plus optional `depth`/`place`/`id`) and it will compute the descriptive
statistics a seismologist reads and render a three-panel figure. It does **not**
retrieve or download any data — acquisition is a separate retrieval MCP's job.

The statistics use NumPy and plotting uses Matplotlib. There is no network
access.

> Design rule: these tools produce *data*. They compute the statistics and draw
> the figure. They do **not** decide whether the activity is an aftershock
> sequence, a swarm, or background, and they do **not** declare which event is
> "the mainshock". That classification is the agent's judgment, made by
> reasoning over the statistics these tools return.

## Tools

### `analyze_sequence`

Compute the descriptive statistics of a saved catalog: completeness magnitude
(Mc, maximum-curvature), the Gutenberg-Richter b-value (Aki MLE with Shi & Bolt
uncertainty), the largest event, the Bath-law magnitude gap to the
second-largest, the share of events before vs after the largest, the spatial
extent, and the Omori post-event rate decay. Read-only; returns statistics only.

```jsonc
{ "catalog_path": "catalog.geojson", "mag_bin": 0.1 }
```

Returns `{ok, event_count, catalog_path, statistics}` where `statistics`
includes `completeness_mc`, `b_value`, `b_uncertainty`, `a_value`,
`largest_event`, `second_largest_magnitude`, `bath_gap`,
`events_before_largest`, `events_after_largest`, `fraction_after_largest`,
`spatial_extent_km`, `magnitude_min/max`, and `temporal_decay`
(rate buckets + `omori_p_estimate`).

### `plot_sequence`

Render the three-panel figure: (1) an epicenter map sized by magnitude and
coloured by time, (2) the Gutenberg-Richter magnitude-frequency distribution
with an optional b-value fit line, and (3) the cumulative count over time. Pass
the `mc` and `b_value` from `analyze_sequence` to draw the G-R fit line.

```jsonc
{ "catalog_path": "catalog.geojson", "title": "Sequence", "mc": 3.0, "b_value": 1.0, "output_path": "sequence.png" }
```

Returns `{ok, figure_path, event_count, panels}`.

## Run

```sh
uvx clio-kit seismic      # via the clio-kit launcher
seismic-mcp               # direct entry point
```

## Test

```sh
uv run --extra dev pytest
```

Tests run against synthetic Gutenberg-Richter and mainshock-aftershock catalogs,
so they need no network access.
