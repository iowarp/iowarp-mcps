---
name: reading-large-datasets-safely
description: Use when a dataset is too large to read, when asked for a mean, max or other summary of array data, or when a read has failed or would exhaust context. Triggers on "the file is huge", "average of", "out of memory". Not for a first look at structure; use exploring-an-unfamiliar-dataset.
clio-kit:
  bundle: clio-scientific-io
  servers: clio-hdf5, clio-parquet, clio-adios
  provenance: designed
  eval-status: eval-run
---

# Get answers from data too big to read

The expensive mistake in this kit is reading a whole dataset to compute one
number. It is slow, it can fail outright, and the result would have been
identical from a call that moved almost nothing.

Rule: **push the computation to the server**. Move the answer, not the data.

## Work out the size first

From `get_shape` and `get_dtype`: multiply the dimensions, multiply by the item
size. A `(2000, 2000, 500)` array of float64 is 16 GB. That number decides
everything below, and it costs one call to get.

## If you want a statistic, do not read the data

| Question | Tool |
|---|---|
| Mean/min/max over HDF5 datasets | `clio-hdf5:hdf5_aggregate_stats` |
| Aggregate over a Parquet column | `clio-parquet:aggregate_column_tool` |
| Same statistic over many files | `clio-hdf5:hdf5_parallel_scan` |

These compute where the data is. `clio-hdf5:read_full_dataset` followed by
arithmetic gives the same answer having moved everything, and is the failure this
skill exists to prevent.

## If you genuinely need values, take a bounded piece

- `clio-hdf5:read_partial_dataset` — slice it. A slice for a sanity check should
  be small: a few hundred elements shows you the units, the sign, and whether it
  is full of NaN.
- `clio-parquet:read_slice_tool` — a row range with only the columns you need.
- `clio-parquet:get_column_preview_tool` — paginated values from one column.
- `clio-adios:read_variable_at_step` — one variable at one step, which is already
  bounded by construction.

## Reading a lot, deliberately

- `clio-hdf5:hdf5_batch_read` — several datasets in parallel, one call rather
  than a serial loop.

> `hdf5_batch_read` and `hdf5_aggregate_stats` both take `paths` as a
> **comma-separated string**, not a list, despite the plural name. Passing a
> JSON array fails with "Input should be a valid string".
- `clio-hdf5:hdf5_stream_data` — large data with memory management, when it has
  to be processed rather than summarised.
- `clio-hdf5:read_full_dataset` — chunked internally, and the right call when the
  whole array is genuinely needed and fits. Check the size first; do not arrive
  here by default.

## Align reads to the chunks

`clio-hdf5:get_chunks` reports the on-disk chunk shape. Reading across the chunk
grain makes the library fetch and decompress whole chunks to hand back a sliver.
A slice along the chunked dimension can be many times faster than the same number
of elements taken across it.

`clio-hdf5:optimize_access_pattern` will suggest a better shape for a pattern you
describe, and `clio-hdf5:identify_io_bottlenecks` inspects the file's own layout.

> That last name also exists on the darshan server, where it means something
> different — a finished job's profile rather than a file's layout. Use the
> fully qualified name.

## What not to do

- Do not call `read_full_dataset` to compute a statistic.
- Do not read a dataset without checking its size first.
- Do not loop single reads where `hdf5_batch_read` takes them together.
- Do not read every Parquet column to aggregate one.
- Do not slice across the chunk grain when the same data can be taken along it.
