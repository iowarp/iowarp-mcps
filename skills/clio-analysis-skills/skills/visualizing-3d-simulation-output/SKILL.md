---
name: visualizing-3d-simulation-output
description: Renders mesh and volume data in ParaView by loading it, finding its arrays, applying the right filter, and capturing a screenshot, tracking which pipeline object is active throughout. Use when visualizing simulation output, making an isosurface, slice, or streamlines, or producing an image from VTK, EXODUS, or BP5 data.
---

# Visualise a simulation field

ParaView is a pipeline with an **active source**. Almost every tool acts on
whichever object is active, not on one you name. Losing track of that is how you
end up colouring the wrong object or screenshotting an empty view.

## The active source is state you must track

Every filter you create becomes the new active source. So a slice of an
isosurface of the data is what you get if you build them in that order without
resetting.

- `clio-paraview:get_pipeline` — what exists and how it is connected
- `clio-paraview:get_active_source_names_by_type` — the names you can select
- `clio-paraview:set_active_source` — go back to a named object

When a filter produces nothing, check what was active before assuming the filter
failed.

## Steps

**1. Load.** `clio-paraview:load_scientific_data` — VTK, EXODUS, CSV, RAW, BP5,
with format detection.

**2. Find out what fields exist.** `clio-paraview:get_available_arrays`. Do this
before choosing a filter. Array names are exact; guessing one is the most common
failure, and the shape matters — an isosurface needs a scalar, streamlines need a
vector.

**3. Find a value worth contouring.** `clio-paraview:get_histogram` on the field.
An isovalue picked without looking is usually outside the data range, and
produces an empty surface with no error.

**4. Apply the filter that matches the question.**

| Want | Tool | Needs |
|---|---|---|
| Surface at a constant value | `generate_isosurface` | scalar field + isovalue |
| Cut plane through the volume | `create_data_slice` | plane position |
| Flow paths | `generate_flow_streamlines` | vector field |
| Values along a line | `plot_over_line` | two points |
| Displacement by a vector | `warp_by_vector` | vector field |
| Whole volume | `configure_volume_display` | + opacity function |

**5. Colour it.** `clio-paraview:apply_field_coloring` by field, then
`clio-paraview:set_color_map_preset` for a named preset such as Viridis, or
`set_color_map` / `edit_volume_opacity` for a custom transfer function.

Preset choice is not decoration. A rainbow map invents banding that is not in the
data; a perceptually uniform map does not. See `choosing-the-right-chart`.

**6. Frame it.** `clio-paraview:reset_camera` to fit everything, then
`clio-paraview:rotate_camera` by azimuth and elevation. Reset first — rotating
from an unknown camera is guesswork.

**7. Capture.** `clio-paraview:take_viewport_screenshot` writes a timestamped
PNG. `clio-paraview:show_screenshot_preview` gives an inline look, which is what
you want while iterating.

Preview while adjusting, save when it is right.

## Surfaces and geometry

`clio-paraview:compute_surface_area` requires the active source to be a **surface
mesh** — an isosurface or extracted surface, not a volume. On a volume it fails
rather than approximating.

`clio-paraview:set_representation_type` switches between Surface, Wireframe and
Points. Points on a large mesh renders when Surface is too slow to iterate on.

`clio-paraview:save_contour_as_stl` exports the active contour for use elsewhere.

## When ParaView is the wrong tool

If the data is a table, this is the wrong server — `clio-plot` reads CSV and
Excel directly and needs none of this. See `summarizing-and-plotting-results`.

## What not to do

- Do not apply a filter without checking what is active.
- Do not guess array names; list them.
- Do not pick an isovalue without looking at the histogram.
- Do not use a rainbow colour map for continuous scalar data.
- Do not screenshot before resetting the camera.
- Do not compute surface area on a volume.
