---
name: interpreting-io-performance-numbers
description: Use when a profiler has returned bandwidth, IOPS, request-size or MPI-IO figures and the question is whether they are good or bad, or when explaining why an I/O pattern is slow. Triggers on "is 40 MB/s bad", "collective vs independent", "small writes". Calls no tools. Not for choosing a format, chunking or compression; use choosing-a-storage-format.
clio-kit:
  bundle: clio-performance
  servers: none
  provenance: designed
  eval-status: eval-run
---

# Read I/O performance numbers

A profiler hands back numbers. Nothing in the output says whether they are good.
This is the missing half.

## Bandwidth is not the headline number

Bandwidth answers "how much moved per second", which only matters if the job
moves a lot. A run doing 40 MB/s is catastrophic if it writes a terabyte and
irrelevant if it writes 200 MB.

Do the division first: **total I/O volume ÷ runtime**. If I/O is a small fraction
of the runtime, the job is not I/O bound and tuning it will change nothing.

Rough orders of magnitude for a parallel filesystem, per node:

| Observed | Reading |
|---|---|
| GB/s | at or near hardware — nothing to fix |
| 100s of MB/s | reasonable for mixed work |
| 10s of MB/s | suspicious unless the volume is small |
| < 10 MB/s at scale | almost always small requests or metadata, not bandwidth |

These are shapes, not thresholds. A shared filesystem under load legitimately
gives less.

## Request size explains most bad numbers

This is the field to look at first. Each request carries fixed overhead —
network round trip, lock acquisition, metadata — that is the same whether it
moves 4 KB or 4 MB.

- **Under ~64 KB**: overhead dominates. The fix is buffering, not a faster disk.
- **Around 1 MB and up**: overhead amortises. Bandwidth becomes the real limit.

A job with excellent bandwidth *per request* and terrible aggregate throughput is
making too many requests. Ten thousand 4 KB writes and forty 1 MB writes move the
same bytes and are not the same job.

## IOPS and bandwidth trade against each other

High IOPS with low bandwidth means many small operations — the small-request
problem above. Low IOPS with high bandwidth means large sequential transfers,
which is the healthy shape. Reading either alone gives the wrong answer.

## Sequential versus random

Sequential access lets the filesystem read ahead. Random access defeats it, and
each read pays full latency. On a parallel filesystem, "random" often means
strided — each rank stepping through a shared file at an offset — which looks
random to the storage even though every rank is orderly.

## Collective versus independent MPI-IO

This is the one that most often has a real fix behind it.

- **Independent**: every rank issues its own requests. With 1,000 ranks writing
  small pieces of one file, the storage sees 1,000 uncoordinated small writes.
- **Collective**: the MPI library aggregates across ranks, so a few processes
  issue large well-aligned writes on everyone's behalf.

A profile dominated by independent operations, with small request sizes and many
ranks, is the classic fixable case: switching to collective calls can change
throughput by an order of magnitude without touching the science.

Independent is not always wrong. Ranks writing to genuinely separate files have
nothing to aggregate.

## Metadata

Thousands of opens, stats and closes with little data moved is a metadata-bound
job. Bandwidth tuning does nothing for it — the fix is fewer files. A run
creating one file per rank per timestep is the usual culprit, and it gets worse
with scale, not better.

## What not to do

- Do not call a bandwidth number bad without knowing the volume and runtime.
- Do not tune I/O for a job that spends most of its time computing.
- Do not read IOPS or bandwidth in isolation — the pair is the signal.
- Do not treat strided access as sequential because each rank is orderly.
- Do not recommend collective I/O for ranks writing to separate files.
