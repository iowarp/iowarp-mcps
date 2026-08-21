# Evals - choosing-a-storage-format

Baseline scenarios: run each WITHOUT the skill to capture the gap, then WITH it
to confirm the gap closes. Rubric is pass/fail per bullet.

## S1 - format selection

Setup: Prompt: "I have a 4-D field from a simulation and a table of run
parameters. How should I store them?"

Expected:

- The field goes to HDF5 (or BP5 if written by a running parallel job); the
  table goes to Parquet.
- The answer does not flatten the field into a table format for convenience.

## S2 - chunking follows the read pattern

Setup: Prompt: "a (time, lat, lon) field, mostly read as whole maps per
timestep. How should I chunk it?"

Expected:

- Chunking along `(1, lat, lon)` is recommended and tied to the stated read.
- The answer states that the opposite access (a time series at one point) would
  then be expensive, rather than claiming one layout is good for both.
- A chunk size in the ~100 KB to few-MB region is named.

## S3 - compression honesty

Setup: Prompt: "should I compress this float field?"

Expected:

- The answer conditions on measured ratio rather than asserting compression is
  always worth it, and names `compress_file_tool` on a sample as the check.
- It notes decompression happens per chunk.

## Baseline failure modes to watch for (RED)

- Recommending CSV or Parquet for multidimensional arrays.
- Accepting default chunking for a known read pattern.
- Claiming a chunk layout is good for all access patterns.
- Asserting compression benefit without measuring.
- Converting formats without noting that attributes can be dropped.
