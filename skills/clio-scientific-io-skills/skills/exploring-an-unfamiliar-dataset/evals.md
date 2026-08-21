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
- Calling `open_file` with `file_path`; it takes `path`.
- Treating the "No file currently open" that follows a failed open as
  evidence the file is empty.
- Opening a second HDF5 file without closing the first.
- Passing a relative path to `list_bp5`.
- Reading an ADIOS variable without naming a step.
- Skipping attributes, leaving numbers without units.

## Smoke record (2026-08-21)

Ran the full S1 and S3 chain as one live session per server, 14 steps, against
a real chunked HDF5 file, a real BP5 store and a real Parquet file.

First run: 6 of 14. `open_file` was called with `file_path` and failed, and
every subsequent HDF5 step then returned "No file currently open". That cascade
is the finding: one wrong argument at the first step makes the rest report an
empty file rather than a failed open.

After correcting to the server's real names (`path` for the file, `path` and
`name` for an attribute, `start`/`count` as comma-separated strings): 14 of 14.
The argument table in the body comes from that run.

Not yet run: the with-skill versus without-skill arms.
