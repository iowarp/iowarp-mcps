---
name: writing-slurm-job-scripts
description: Use when an sbatch script would be written without first checking the machine's real limits, which is what leaves a job pending forever or killed at the wall clock. Covers partitions, --mem, job arrays and dependencies. Triggers on "sbatch", "why is my job pending", "job array", "--mem". Not for running a Spack package through JARVIS; use running-a-simulation-on-a-cluster.
clio-kit:
  bundle: clio-hpc
  servers: clio-slurm, clio-node-hardware
  provenance: designed
  eval-status: eval-run
---

# Write a Slurm job script that actually starts

This is about what goes *in* the request and how to read what comes back. For
running a Spack package through JARVIS instead of a hand-written script, see
`running-a-simulation-on-a-cluster`.

## Size the request against a real machine

Look before guessing. `clio-node-hardware:get_cpu_info` gives core counts,
`get_memory_info` gives RAM, `get_gpu_info` gives GPUs. Then
`clio-slurm:slurm_cluster` gives the partitions and their limits.

A request larger than any node in the partition never starts. It does not fail —
it pends forever, which is much harder to notice.

## The shape of a batch script

```bash
#!/bin/bash
#SBATCH --job-name=run1
#SBATCH --partition=<from slurm_cluster>
#SBATCH --nodes=1
#SBATCH --ntasks-per-node=16
#SBATCH --cpus-per-task=1
#SBATCH --mem=32G
#SBATCH --time=02:00:00
#SBATCH --output=run1-%j.out
#SBATCH --error=run1-%j.err

srun ./my_binary
```

Points that matter more than they look:

- **`--time` is a hard kill, not an estimate.** The job is terminated at the
  limit, mid-write if necessary. But a shorter limit schedules sooner, because
  it fits in backfill gaps. Ask for what the run needs plus margin, not the
  partition maximum.
- **`--ntasks` vs `--cpus-per-task`.** Tasks are MPI ranks; cpus-per-task is
  threads within a rank. An MPI+OpenMP code that sets both wrong runs at a
  fraction of its speed while looking healthy.
- **`--mem` is per node; `--mem-per-cpu` is per allocated CPU.** Setting both is
  an error. Getting `--mem` wrong is the most common cause of a job killed
  partway through with no obvious message.
- **`%j` in output paths** expands to the job ID. Without it, an array or a
  resubmission overwrites its own logs and the evidence is gone.
- **`srun` inside the script**, not a bare call. It inherits the allocation;
  running the binary directly gets you one rank on one node regardless of what
  was requested.

## Arrays

An array submits many similar jobs under one ID. Use it instead of a submit
loop — the scheduler handles it as one object, and it stays inside job-count
limits that a loop would blow through.

```bash
#SBATCH --array=0-99%10        # 100 tasks, at most 10 running at once
```

`$SLURM_ARRAY_TASK_ID` selects the per-task input. The `%10` throttle matters on
a shared cluster: without it, one array can occupy the queue.

Pass `array` to `clio-slurm:slurm_submit` only for an array submission — setting
it on an ordinary job changes what is submitted.

## Dependencies

```bash
#SBATCH --dependency=afterok:<jobid>
```

`afterok` runs only if the prior job succeeded; `afterany` runs regardless. Use
`afterok` for a real chain — `afterany` on a post-processing step means it will
happily process the output of a job that crashed.

A dependency on a job that never succeeds leaves the dependent job pending
forever with reason `DependencyNeverSatisfied`. That is a terminal state
dressed as a waiting one.

## Reading why a job has not started

`clio-slurm:slurm_describe` gives the lifecycle state, whether it is terminal,
and optional bounded stdout/stderr tails. The pending reason is the useful field:

- `Resources` — the request is legal, the machine is busy. Waiting is correct.
- `Priority` — legal, but other jobs are ahead. Also waiting.
- `PartitionNodeLimit`, `PartitionTimeLimit` — the request exceeds what the
  partition allows. This will never start. Fix the request and resubmit.
- `QOSMaxJobsPerUserLimit` — you are at your own limit; earlier jobs must finish.
- `DependencyNeverSatisfied` — the chain is broken. Cancel and resubmit.

`clio-slurm:slurm_list` filters by user, state and partition, and reports
explicit truncation — a truncated list is not the whole queue, so do not draw
conclusions about totals from it.

## Cancelling

`clio-slurm:slurm_cancel` requires `confirm_job_id` to repeat `job_id` exactly.
A missing or mismatched confirmation is rejected before `scancel` is called at
all. This is deliberate: cancellation is not recoverable, and the echo is what
stops a wrong ID from ending someone else's run.

## What not to do

- Do not request the partition's maximum time by default; it delays scheduling.
- Do not submit in a loop what an array expresses in one line.
- Do not call the binary directly instead of through `srun`.
- Do not read a pending job as "working" without checking the reason — several
  reasons mean it will never start.
- Do not treat a truncated `slurm_list` as a complete picture of the queue.
