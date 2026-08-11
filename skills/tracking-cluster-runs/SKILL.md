---
name: tracking-cluster-runs
description: Starts a JARVIS pipeline on a cluster and follows it to completion through the Slurm queue, keeping the pipeline handle and the scheduler job distinct. Use when a run must go to a cluster rather than the local host, when the user asks whether a job is queued, running, or finished, or when they mention squeue, partitions, pending jobs, or cancelling a run.
category: HPC
servers: clio-jarvis, clio-slurm, clio-node-hardware
tools: clio-jarvis:jarvis_run, clio-jarvis:jarvis_get_execution, clio-slurm:slurm_cluster, clio-slurm:slurm_list, clio-slurm:slurm_describe, clio-slurm:slurm_cancel, clio-node-hardware:get_remote_node_info
---

# Tracking a cluster run

Two different identifiers are in play and confusing them is the main failure
mode. `clio-jarvis:jarvis_run` returns a **pipeline execution handle**; Slurm
returns a **scheduler job ID**. The handle tracks the workload's lifecycle; the
job ID tracks its place in the queue. Neither answers the other's question.

## Workflow

```
- [ ] 1. Check the partition can take the job
- [ ] 2. Start the run with cluster intent
- [ ] 3. Follow the execution handle
- [ ] 4. Use Slurm when the handle says "queued"
- [ ] 5. Report state, not completion
```

## 1. Check the partition first

`clio-slurm:slurm_cluster` returns partitions and queue depth. A run submitted
into a saturated partition is not broken, it is waiting — and knowing that
before starting prevents diagnosing a queue as a failure.

## 2. Start with cluster intent

`clio-jarvis:jarvis_run` with execution intent set to cluster. It returns
immediately with a durable handle and does **not** wait for the workload.

Treating the return of `jarvis_run` as completion is the most common error this
skill prevents.

## 3. Follow the handle

`clio-jarvis:jarvis_get_execution` with the pipeline id and the handle. This is
the authoritative view of the workload: lifecycle state, progress, and runtime
metadata.

Poll it. Do not infer completion from elapsed time.

## 4. Drop to Slurm only for queue questions

When the handle reports the work as queued or not yet started, the useful
question is a scheduler question:

- `clio-slurm:slurm_list` — bounded listing, filter by user, state or partition
- `clio-slurm:slurm_describe` — one job's scheduler state and properties
- `clio-node-hardware:get_remote_node_info` with `host` — whether the allocated
  node is actually healthy, when a job is running but producing nothing

Go back to the JARVIS handle for anything about the workload itself. Slurm knows
the job is running; it does not know whether the pipeline step succeeded.

## 5. Cancelling

`clio-slurm:slurm_cancel` requires `confirm_job_id` to repeat `job_id` exactly.
That is a deliberate guard on a destructive action — do not work around it by
guessing an id, and confirm the job is the intended one with
`clio-slurm:slurm_describe` first.

## Reporting

Report the state and the source. "Queued in partition X, position unknown"
is a useful answer. "Running" without saying which identifier it came from is
not, because the two can disagree: a Slurm job can be running while the pipeline
step it hosts has already failed.

## What not to do

- Do not report a run as finished because `clio-jarvis:jarvis_run` returned.
- Do not pass a Slurm job ID where a pipeline handle is expected, or the
  reverse.
- Do not poll in a tight loop; these are cluster-scale operations.
- Do not cancel without confirming the job is the intended one.
