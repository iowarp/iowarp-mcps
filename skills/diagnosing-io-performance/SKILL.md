---
name: diagnosing-io-performance
description: Traces a slow HPC job from its Darshan log to the specific dataset layout and node conditions causing the stall. Use when a run was slower than expected, when the user has a Darshan log or mentions I/O bottlenecks, POSIX or MPI-IO behaviour, small-write patterns, or chunking, or when a job's wall time is dominated by reads and writes rather than compute.
category: Performance
servers: clio-darshan, clio-hdf5, clio-adios, clio-node-hardware
tools: clio-darshan:load_darshan_log, clio-darshan:get_job_summary, clio-darshan:identify_io_bottlenecks, clio-darshan:get_io_performance_metrics, clio-darshan:analyze_file_access_patterns, clio-darshan:analyze_posix_operations, clio-darshan:analyze_mpiio_operations, clio-darshan:get_timeline_analysis, clio-darshan:compare_darshan_logs, clio-hdf5:get_chunks, clio-hdf5:get_shape, clio-adios:inspect_variables, clio-node-hardware:get_disk_info, clio-node-hardware:get_remote_node_info, clio-hdf5:identify_io_bottlenecks
---

# Diagnosing I/O performance

A Darshan log says *what* the I/O looked like. It cannot say *why* the file was
laid out that way, and it cannot see the node the job ran on. The diagnosis is
only complete when the trace, the file layout, and the hardware agree on a
story.

Note that `identify_io_bottlenecks` exists on two servers and they mean
different things. `clio-darshan:identify_io_bottlenecks` analyses a captured
trace; `clio-hdf5:identify_io_bottlenecks` inspects a file. Always qualify it.

## Workflow

```
- [ ] 1. Load the trace and read the job summary
- [ ] 2. Find where the time went
- [ ] 3. Classify the access pattern
- [ ] 4. Check the file layout that produced it
- [ ] 5. Rule the hardware in or out
- [ ] 6. Report cause, evidence, and one change
```

## 1. Load the trace

`clio-darshan:load_darshan_log`, then `clio-darshan:get_job_summary` for
runtime, process count and total I/O volume.

Compute the ratio of I/O time to wall time before going further. If I/O is a
small fraction of the run, stop and say so — the job is not I/O bound and the
rest of this workflow will produce a confident answer to the wrong question.

## 2. Find where the time went

`clio-darshan:identify_io_bottlenecks` first, then
`clio-darshan:get_io_performance_metrics` for bandwidth, IOPS and request
sizes.

Small mean request size with high operation count is the signature worth
chasing: many small writes rather than few large ones.

## 3. Classify the access pattern

`clio-darshan:analyze_file_access_patterns` for sequential versus random, then
the interface-specific view:

- `clio-darshan:analyze_posix_operations` — plain reads and writes
- `clio-darshan:analyze_mpiio_operations` — collective versus independent

Independent MPI-IO where collective was available is a common and fixable
cause. `clio-darshan:get_timeline_analysis` shows whether the cost is spread
across the run or concentrated in one phase.

## 4. Check the layout that produced the pattern

The trace shows small reads; the file explains them.

- HDF5: `clio-hdf5:get_chunks` and `clio-hdf5:get_shape`. A chunk shape
  orthogonal to the access pattern turns one logical read into many physical
  ones. This is the single most common finding.
- ADIOS: `clio-adios:inspect_variables` for shape and step count. Per-step reads
  across many steps behave like small-request I/O regardless of variable size.

## 5. Rule the hardware in or out

`clio-node-hardware:get_disk_info` on the node that ran the job, or
`clio-node-hardware:get_remote_node_info` with `host` for a remote one.

This step exists to prevent a wrong conclusion, not to find one: a saturated
local disk or a full filesystem produces the same trace signature as a bad
chunk layout, and the fix is entirely different.

## 6. Report

State the cause, the evidence from at least two of the three sources above, and
**one** change. If a previous log exists, `clio-darshan:compare_darshan_logs`
turns the recommendation into a measurement.

## What not to do

- Do not recommend a chunk shape without reading the current one.
- Do not conclude "slow disk" from the trace alone; check the node.
- Do not report more than one change at a time — two simultaneous changes make
  the follow-up comparison unreadable.
- Do not use the unqualified `identify_io_bottlenecks`; two servers define it.
