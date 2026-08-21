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
- Reading every Parquet column to aggregate one.
