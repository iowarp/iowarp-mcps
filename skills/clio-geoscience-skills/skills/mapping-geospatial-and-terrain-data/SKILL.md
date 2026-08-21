---
name: mapping-geospatial-and-terrain-data
description: Use when working with GeoJSON, place names, bounding boxes, elevation grids or point clouds, or when asked to produce a map. Triggers on "geojson", "render a map", "coordinates for", "DEM". Not for projections; use working-with-coordinate-systems. Not for waveforms or earthquake catalogs; use analyzing-seismic-waveforms.
clio-kit:
  bundle: clio-geoscience
  servers: clio-geo, clio-terrain
  provenance: designed
  eval-status: smoke-checked
---

# Work with geospatial data without silently getting it wrong

Spatial mistakes do not raise errors. A bounding box computed over malformed
features, or a place name the model invented coordinates for, produces a map that
renders perfectly and is wrong.

## Validate before anything spatial

`clio-geo:validate_geojson` checks that the top-level type is recognised and
every geometry's type and coordinates are well formed. Run it first, always. Every
tool downstream assumes what it verifies.

Then `clio-geo:inspect_geojson` for geometry types and counts, feature count,
property keys and bounding box in one call — the fastest way to find out what a
file actually holds. `clio-geo:summarize_geojson` gives the readable version
with sample properties.

## Two bounding-box tools, and they can disagree

`clio-geo:feature_bbox` and `clio-geo:bounding_box` both return
`[min_lon, min_lat, max_lon, max_lat]`.

On a clean file they agree. On a file with malformed geometries they need not,
because they differ in what they include. Validate first and the question does
not arise; skip validation and you have a box you cannot account for.

They do not even take the same argument. `feature_bbox` wants `source`;
`bounding_box` wants `geojson`. That split runs through the whole server: the
four tools ported in from the old geojson server (`inspect_geojson`,
`validate_geojson`, `summarize_geojson`, `feature_bbox`) take `source`, while
geo's own tools take `geojson`, `data_path`, `layers` or `query`. Passing the
wrong one returns a missing-required-argument error that reads as though the
file were absent.

`clio-geo:bounding_box` also takes `buffer_km` for padding, which is what you want
when the box is being used to query a region rather than describe one.

## Never guess coordinates

`clio-geo:geocode` looks a place name up against OpenStreetMap Nominatim and
returns real coordinates. Writing coordinates from memory is a fabricated result
that looks exactly like a real one.

Geocoding is ambiguous by nature — several matches come back for a name. Pick
using the returned metadata, and say which one was used.

## Spatial relationships

- `clio-geo:points_in_polygons` — which points fall inside which polygons, with
  optional buffering. The buffer is in the tool for a reason: a point exactly on
  a boundary is not reliably "inside" in floating point.
- `clio-geo:filter_points_by_radius` — rank or filter a table of points by
  great-circle distance from a centre. Reads CSV or GeoJSON points.
- `clio-geo:query_arcgis_features` — pull features from an ArcGIS FeatureServer
  with an optional bbox and where clause, writing a local GeoJSON file. Bound the
  query; an unfiltered layer can be enormous.

## Terrain

`clio-terrain:dem_terrain` analyses an elevation grid for elevation, slope,
aspect and site suitability, from CSV numeric grids, NPY, or NPZ with a `dem`
array.

`clio-terrain:pointcloud_read` grids an x/y/z point cloud into a DEM-like surface
by averaging z per cell. Two things follow from "averaging": the cell size is a
real choice — too fine and cells are empty, too coarse and features vanish — and
averaging destroys vertical structure. Ground and canopy in the same cell average
to neither. LAS/LAZ input needs extra support and is not read directly.

## Render last

`clio-geo:render_feature_map` draws one or more GeoJSON layers onto a single PNG
with an optional basemap and per-layer styling. Do this after the data is
verified: a map is the least reliable place to notice bad geometry, because it
looks like a map either way.

## What not to do

- Do not run a spatial operation before validating the GeoJSON.
- Do not mix the two bbox tools within one analysis without saying which.
- Do not assume one argument name across this server; the ported geojson
  tools take `source` and the rest do not.
- Do not write coordinates from memory — geocode them.
- Do not accept the first geocoding match without checking the alternatives.
- Do not query an ArcGIS layer without a bbox or where clause.
- Do not grid a point cloud without choosing the cell size deliberately.
- Do not treat a rendered map as evidence the data is sound.
