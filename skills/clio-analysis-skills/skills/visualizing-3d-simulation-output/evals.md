# Evals - visualizing-3d-simulation-output

Baseline scenarios: run each WITHOUT the skill to capture the gap, then WITH it
to confirm the gap closes. Rubric is pass/fail per bullet.

## S1 - an isosurface that is not empty

Setup: A VTK volume. Prompt: "show me an isosurface of the density field."

Expected:

- `get_available_arrays` is called; the field name is not guessed.
- `get_histogram` informs the isovalue rather than a value being invented.
- A screenshot is produced only after `reset_camera`.

## S2 - the active source

Setup: A pipeline where a slice was created after an isosurface. Prompt: "colour
the isosurface by temperature."

Expected:

- `get_pipeline` or `get_active_source_names_by_type` is consulted, and
  `set_active_source` selects the isosurface before colouring.
- The colouring is not applied to whatever happened to be active.

## S3 - a measurement with a precondition

Setup: A loaded volume, no surface extracted. Prompt: "what's the surface area?"

Expected:

- The answer establishes that `compute_surface_area` needs a surface mesh, and
  extracts one first rather than calling it on the volume.

## Baseline failure modes to watch for (RED)

- Guessing array names instead of listing them.
- Choosing an isovalue without the histogram, producing an empty surface with
  no error.
- Applying a filter without checking what is active.
- Using a rainbow colour map for continuous scalar data.
- Screenshotting before resetting the camera.

## Trigger record (2026-08-21)

Ran through `evals/trigger_eval.py`, which loads the skill plugins into the
Agent SDK with an empty `setting_sources` and only the Skill tool allowed, so
selection is measured without the operator's own configuration influencing it.

Prompt: "Make an isosurface of the density field in this VTK file and screenshot it."

This skill fired, and no sibling fired alongside it. Across the suite: 20 of 20
skills selected correctly on their own prompt, and 3 control prompts outside the
kit fired nothing.

Selection is checked. Whether the skill improves the final answer, versus an
agent working without it, is still not measured.

