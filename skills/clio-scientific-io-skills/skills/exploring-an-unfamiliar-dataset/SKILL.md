---
name: exploring-an-unfamiliar-dataset
description: Use when an unfamiliar data file would be opened by reading it whole or guessing its layout, which exhausts context or misreports units and shapes. Covers HDF5, ADIOS BP5, Parquet and compressed files. Triggers on "what is in this file", "open this dataset", ".h5", ".bp", ".parquet". Not for data too large to hold; use reading-large-datasets-safely. Not for log files; use searching-large-log-files.
clio-kit:
  bundle: clio-scientific-io
  servers: clio-hdf5, clio-adios, clio-parquet, clio-compression
  provenance: designed
  eval-status: eval-run
---

# Find out what is in a data file

Every format here separates *structure* from *data*. Read the structure first.
It is small, and it tells you whether the data is something you can afford to
read at all.

## Decompress first if you have to

A `.gz` file is not readable by any of the format tools. Run
`clio-compression:decompress_file_tool` and work with what it produces. Check the
reported original size before decompressing something large.

## Pick the reader by format, not by preference

| File | Server | Opening move |
|---|---|---|
| `.h5`, `.hdf5` | `clio-hdf5` | `open_file`, then `list_keys` |
| `.bp`, `.bp5` | `clio-adios` | `list_bp5`, then `inspect_variables` |
| `.parquet` | `clio-parquet` | `summarize_tool` |

## HDF5 holds a file open — this is the trap

The HDF5 server is stateful. `clio-hdf5:open_file` opens **the current file**, and
every tool after it operates on that file without taking a path.

- Opening a second file without `clio-hdf5:close_file` first leaves you reading
  the wrong one, with no error to tell you.
- `clio-hdf5:get_filename` says which file is actually open. When results look
  wrong, check this before anything else.
- Close when finished.

The exceptions are the multi-file tools — `hdf5_parallel_scan`, `hdf5_batch_read`,
`hdf5_aggregate_stats` — which take their own targets and do not use the open
file.

### The argument names are not guessable

Nothing on this server takes `file_path`. Getting one wrong is worse than a
plain failure: `open_file` fails, then every later call answers "No file
currently open", which reads as an empty file rather than a failed open.

| Call | Argument |
|---|---|
| `open_file` | `path` (the FILE) |
| `list_keys`, `get_shape`, `get_dtype`, `list_attributes` | `path` (a path INSIDE the file) |
| `read_attribute` | `path` and `name` |
| `read_partial_dataset` | `path`, plus `start` and `count` as comma-separated strings, not lists |
| `hdf5_batch_read`, `hdf5_aggregate_stats` | `paths`, a comma-separated string |

Note `path` means the file in `open_file` and a dataset inside it everywhere
else.

### Walking an HDF5 file

1. `clio-hdf5:open_file`
2. `clio-hdf5:list_keys` at the root — groups and datasets at this level
3. `clio-hdf5:visit` for the whole tree, when the file is small enough to warrant it
4. For a dataset: `get_shape`, `get_dtype`, `get_size` — **before** reading anything
5. `clio-hdf5:list_attributes` then `read_attribute` — units, provenance, and
   grid metadata live here, and they are what make the numbers mean something
6. `clio-hdf5:close_file`

`clio-hdf5:analyze_dataset_structure` summarises organisation in one call and is
a good opening move on a file with hundreds of datasets.

## ADIOS is stepped, and stateless

BP5 data has **steps** — it is usually a time series.

1. `clio-adios:list_bp5` on the directory. The path must be **absolute**; a
   relative path is an error, not an empty result.
2. `clio-adios:inspect_variables` — type, shape, and how many steps exist
3. `clio-adios:inspect_attributes` — global, or for one variable
4. `clio-adios:inspect_variables_at_step` for one variable at one step
5. `clio-adios:read_variable_at_step` to actually read

There is no open/close: every call takes the file. Reading "the variable" without
a step reads nothing — the step is part of the address.

## Parquet is columnar, so ask columns

1. `clio-parquet:summarize_tool` — schema, row count, file size
2. `clio-parquet:get_column_preview_tool` — a few values from one column
3. `clio-parquet:read_slice_tool` — a row range, projecting only the columns you
   need. Projection is the point of the format; reading all columns throws it away.

## Then stop and think about size

Once you have the shape and dtype, work out the bytes. Anything large means the
next step is not a read — see `reading-large-datasets-safely`.

## What not to do

- Do not read data before reading shape and dtype.
- Do not open a second HDF5 file without closing the first.
- Do not pass a relative path to `clio-adios:list_bp5`.
- Do not read an ADIOS variable without naming a step.
- Do not read every column of a Parquet file when you need two.
- Do not skip the attributes — an array without its units is not a result.
- Do not read "No file currently open" as an empty file. It means the open
  failed, usually on the argument name.
