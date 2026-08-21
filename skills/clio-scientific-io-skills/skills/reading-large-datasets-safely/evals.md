# Evals - reading-large-datasets-safely

Baseline scenarios: run each WITHOUT the skill to capture the gap, then WITH it
to confirm the gap closes. Rubric is pass/fail per bullet.

## S1 - a statistic from a large array

Setup: An HDF5 dataset of shape (2000, 2000, 500) float64. Prompt: "what's the
mean of this dataset?"

Expected:

- The size is computed from shape and dtype before any read.
- `hdf5_aggregate_stats` is used; `read_full_dataset` is not called.
- The answer reports the statistic, not a truncated array.

## S2 - a Parquet aggregate

Setup: A wide Parquet file. Prompt: "what's the max of the pressure column?"

Expected:

- `aggregate_column_tool` is used on that one column.
- All columns are not read.

## S3 - chunk-aware slicing

Setup: A chunked dataset where the requested slice crosses the chunk grain.
Prompt asks for a time series at one grid point.

Expected:

- `get_chunks` is consulted.
- The answer notes the access crosses the chunk grain, or proposes the aligned
  alternative, rather than issuing the naive slice silently.

## Baseline failure modes to watch for (RED)

- Calling `read_full_dataset` to compute one number.
- Reading without checking the size first.
- Looping single reads where `hdf5_batch_read` takes them together.
- Passing a list to `paths` on `hdf5_batch_read` or `hdf5_aggregate_stats`;
  both want a comma-separated string.
- Reading every Parquet column to aggregate one.

## Smoke record (2026-08-21)

Audited all 27 hdf5 tools against a real 50x40x30 chunked fixture. 25 of 27
succeeded. The two failures were `hdf5_batch_read` and `hdf5_aggregate_stats`,
both rejecting a JSON array for `paths` with "Input should be a valid string".
Their schema says comma-separated string; the plural name says otherwise. Now
called out in the body.

Not yet run: the with-skill versus without-skill arms.

## Trigger record (2026-08-21)

Ran through `evals/trigger_eval.py`, which loads the skill plugins into the
Agent SDK with an empty `setting_sources` and only the Skill tool allowed, so
selection is measured without the operator's own configuration influencing it.

Prompt: "Compute the mean of a 16GB dataset without loading it."

This skill fired, and no sibling fired alongside it. Across the suite: 20 of 20
skills selected correctly on their own prompt, and 3 control prompts outside the
kit fired nothing.

Selection is checked. Whether the skill improves the final answer, versus an
agent working without it, is still not measured.

