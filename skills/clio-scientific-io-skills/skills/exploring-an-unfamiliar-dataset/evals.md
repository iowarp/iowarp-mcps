# Evals - exploring-an-unfamiliar-dataset

Baseline scenarios: run each WITHOUT the skill to capture the gap, then WITH it
to confirm the gap closes. Rubric is pass/fail per bullet.

## S1 - structure before data

Setup: An HDF5 file with several large datasets. Prompt: "what's in this file?"

Expected:

- `open_file` then `list_keys` / `analyze_dataset_structure`; no dataset is read
  before `get_shape` and `get_dtype` are known.
- `list_attributes` / `read_attribute` are called, and units or provenance are
  reported rather than bare arrays.
- `close_file` is called when finished.

## S2 - the stateful trap

Setup: Two HDF5 files. Prompt: "compare the temperature dataset in these two
files."

Expected:

- The first file is closed before the second is opened, or `get_filename` is
  used to confirm which file is current.
- Results are not attributed to the wrong file.

## S3 - format dispatch

Setup: A directory holding a `.bp` store and a `.parquet` file, plus a `.gz`.

Expected:

- `list_bp5` is called with an absolute path.
- An ADIOS variable is read at a named step, not without one.
- The `.gz` is decompressed before any format tool is pointed at it.
- Parquet is read with column projection rather than all columns.

## Baseline failure modes to watch for (RED)

- Reading a dataset before checking its shape and dtype.
- Opening a second HDF5 file without closing the first.
- Passing a relative path to `list_bp5`.
- Reading an ADIOS variable without naming a step.
- Skipping attributes, leaving numbers without units.
