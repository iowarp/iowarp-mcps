---
name: working-with-coordinate-systems
description: Use when combining spatial datasets, computing distances or areas, interpreting coordinates, or when spatial results look subtly misplaced. Triggers on "lat lon", "projection", "CRS", "UTM", "why is this offset". Calls no tools.
clio-kit:
  bundle: clio-geoscience
  servers: none
  provenance: designed
  eval-status: scenarios-recorded
---

# Coordinate systems fail quietly

Nothing here raises an error. Data in the wrong reference system plots, computes
distances, and returns bounding boxes — just in the wrong place. This is the
class of bug that survives review because every step succeeded.

## Longitude first, in GeoJSON

GeoJSON positions are `[longitude, latitude]`. Bounding boxes are
`[min_lon, min_lat, max_lon, max_lat]`.

Almost everything a human writes is the other way round — "41.8, -87.6" for
Chicago is lat, lon. Reversed coordinates near the equator land in the ocean off
Africa; at mid-latitudes they land somewhere plausible-looking, which is worse.

Sanity check any position before trusting it: **longitude is in [-180, 180],
latitude in [-90, 90]**. A first value beyond ±90 is definitely longitude. Both
under 90 and it is ambiguous — check against a known landmark.

## Geographic degrees are not a distance

Latitude and longitude are angles. One degree of latitude is about 111 km
everywhere; one degree of longitude is 111 km at the equator, about 78 km at 45°,
and zero at the pole.

So Euclidean distance on lon/lat is wrong, and wrong by a factor that changes
with where you are. Compare two things at different latitudes with it and the
comparison is meaningless.

`clio-geo:filter_points_by_radius` computes **great-circle** distance, which is
the correct thing on a sphere. Use it rather than differencing coordinates. When
`clio-geo:bounding_box` pads by `buffer_km` it is doing the same conversion; a
padded box is not a fixed number of degrees on every side.

Area is worse. A polygon's area in square degrees is not a physical quantity at
all, and cannot be converted by one factor because the factor varies across the
polygon.

## Geographic versus projected

- **Geographic** (WGS84, EPSG:4326) — angles on the globe. What GPS and GeoJSON
  give you. Good for storing and sharing position, bad for measuring.
- **Projected** (UTM, State Plane, and so on) — metres on a flat plane, accurate
  within a defined zone and degrading outside it. Good for measuring, bad for
  spanning large areas.

Distances and areas want a projection appropriate to the region. Storage and
interchange want WGS84.

## Combining datasets is where this bites

Two files in different reference systems have coordinates that look equally
valid. Overlay them and features land near each other but offset — the shift is
often small enough to look like a data-quality issue rather than a projection
mismatch.

Before combining, check that the bounding boxes are in the same units and the
same range. Two boxes where one is in the hundreds of thousands and the other in
the tens are not the same system, whatever the file says.

A UTM coordinate misread as lon/lat is out of range and will be caught. A UTM
coordinate in the low hundreds of thousands read as metres in a *different* zone
will not be.

## Elevation is a third axis with its own datum

Height is measured either above the ellipsoid (a mathematical surface) or above
the geoid (mean sea level). The two differ by tens of metres, varying by
location. A DEM combined with GPS heights on the wrong datum produces a
consistent offset that looks like a calibration problem.

## Rendering hides all of it

`clio-geo:render_feature_map` draws whatever coordinates it is given. A basemap
under misprojected features makes the result look authoritative. The map is not
the check — validate and inspect the bounding box first. See
`mapping-geospatial-and-terrain-data`.

## What not to do

- Do not write positions as lat, lon in GeoJSON.
- Do not compute distance by differencing coordinates.
- Do not report an area in square degrees.
- Do not overlay two datasets without checking their bounding boxes agree in
  units and range.
- Do not combine elevation sources without knowing their vertical datum.
- Do not treat a plausible-looking map as confirmation the projection is right.
