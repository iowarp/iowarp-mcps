# Evals - mapping-geospatial-and-terrain-data

Baseline scenarios: run each WITHOUT the skill to capture the gap, then WITH it
to confirm the gap closes. Rubric is pass/fail per bullet.

## S1 - validate before anything spatial

Setup: A GeoJSON file containing one malformed geometry. Prompt: "what's the
bounding box of these features?"

Expected:

- `validate_geojson` is called before any bbox or overlay operation.
- The malformed geometry is surfaced rather than silently included or dropped.
- If both bbox tools are mentioned, the answer says which was used and why they
  can disagree on a dirty file.

## S2 - coordinates are looked up, not recalled

Setup: Prompt: "map the monitors within 20 km of Chicago."

Expected:

- `geocode` is called for Chicago; coordinates are not written from memory.
- Ambiguity in the geocoding result is acknowledged and the chosen match named.
- `filter_points_by_radius` is used for the 20 km, not a coordinate difference.

## S3 - gridding is a choice

Setup: An x/y/z point cloud. Prompt: "turn this into a surface."

Expected:

- The cell size is chosen deliberately and stated.
- The answer notes that averaging z per cell destroys vertical structure, so
  ground and canopy in one cell average to neither.

## Baseline failure modes to watch for (RED)

- Running a spatial operation before validating.
- Calling `validate_geojson`, `inspect_geojson`, `summarize_geojson` or
  `feature_bbox` with `geojson=` instead of `source=`.
- Writing coordinates from memory instead of geocoding.
- Accepting the first geocoding match with no mention of alternatives.
- Querying an ArcGIS layer with no bbox or where clause.
- Treating a rendered map as evidence the data is sound.

## Smoke record (2026-08-21)

Traced S1 by hand against the live geo server with a one-point GeoJSON.
`validate_geojson`, `summarize_geojson` and `feature_bbox` all failed with
"source Missing required argument" when passed `geojson=`.

Dumping the server's schemas showed the split: the four tools ported in from
the retired geojson server take `source`, while geo's native tools take
`geojson`, `data_path`, `layers` or `query`. `bounding_box` and `feature_bbox`,
already flagged in the body as deceptively similar, do not even share an
argument name. Both facts are now in the body.

Not yet run: the with-skill versus without-skill arms.
