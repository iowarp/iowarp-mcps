---
name: choosing-a-storage-format
description: Use when deciding how to write results out, converting between HDF5, BP5, Parquet or CSV, choosing chunking or compression, or explaining why reading an existing file is slow. Triggers on "which format", "chunk size", "should I compress". Calls no tools. Not for judging whether a measured number is bad; use interpreting-io-performance-numbers.
clio-kit:
  bundle: clio-scientific-io
  servers: none
  provenance: designed
  eval-status: scenarios-recorded
---

# Choose a format, and chunk it for how it will be read

The format decides what is cheap later. Almost every slow read is a write-time
decision showing up months afterwards.

## Which format

**Parquet** — tables. Rows of records with named, typed columns: measurements,
catalogues, parameter sweeps, logs. Columnar, so reading two columns of a
hundred reads roughly two columns' worth. Compresses well because a column holds
one kind of value. Not for multidimensional arrays: a 3-D field flattened into a
table loses the very structure that makes it addressable.

**HDF5** — multidimensional arrays in a hierarchy, written once and read many
times. Slicing along any axis, attributes attached to any node, and a directory
tree inside one file. The default for a simulation result someone will analyse
later.

**ADIOS BP5** — arrays produced *during* a run, especially in parallel and
especially as a time series. Its model has steps built in, and it is designed for
many ranks writing concurrently without fighting over one file. Where HDF5 is a
result, BP5 is often a stream of them.

Rough test: **table → Parquet. Array someone will analyse → HDF5. Array being
produced by a running parallel job → BP5.**

## Chunking is the decision that matters

An HDF5 dataset is stored in fixed blocks. Any read fetches whole chunks, even
for one element, so the chunk shape decides which reads are fast and which are
disastrous.

Chunk along the axis that will be read. A `(time, lat, lon)` field chunked as
`(1, lat, lon)` gives cheap whole-maps-per-timestep and expensive time series at
one point. Chunked `(time, 1, 1)`, exactly the reverse. There is no shape that is
good at both — pick the one matching the real question, or store two layouts.

Size the chunk in the region of 100 KB to a few MB. Too small and per-chunk
overhead and metadata dominate; too large and every small read drags a large
block off disk.

`clio-hdf5:get_chunks` reports what an existing file chose, which is the first
thing to check when reads are slow. A **contiguous** dataset — no chunking at
all — cannot be compressed and cannot be extended.

## Compression trades CPU for bytes

Compression is per chunk, so a chunk is the smallest thing that can be
decompressed. Reading one element of a compressed dataset decompresses its whole
chunk.

It is usually worth it: filesystem bandwidth is scarcer than CPU, and smaller
chunks mean less to transfer. It stops being worth it for data that does not
compress — already-compressed content, or high-entropy floats where the low bits
are noise. Lossy precision trimming before compressing is what makes float fields
shrink, and it is a scientific decision, not a storage one.

`clio-compression:compress_file_tool` reports the achieved ratio. On a
representative sample that number tells you whether it is worth enabling at all.

## Converting

`clio-hdf5:export_dataset` writes an HDF5 dataset to another format.
`clio-pandas:load_data` and `save_data` between them read and write CSV, Excel,
JSON, Parquet and HDF5, which covers table-shaped conversions.

Convert for a reason. Every conversion is a copy that can drift from its
original, and going through a table format silently drops attributes — the units
and provenance that made the array interpretable.

## What not to do

- Do not put multidimensional fields in a table format to make them easy to open.
- Do not accept default chunking for data with an obvious read pattern.
- Do not chunk so small that metadata outweighs the data.
- Do not compress data that does not compress, and measure before assuming.
- Do not convert formats without checking the attributes survived.
