# Evals - writing-slurm-job-scripts

Baseline scenarios: run each WITHOUT the skill to capture the gap, then WITH it
to confirm the gap closes. Rubric is pass/fail per bullet.

## S1 - a request that can actually schedule

Setup: Prompt: "write me an sbatch script for a 16-rank MPI run of ./solver,
about 90 minutes."

Expected:

- Node and partition limits are checked (`get_cpu_info`, `slurm_cluster`) before
  numbers are chosen, not after.
- `--time` is set to the need plus margin, not the partition maximum, and the
  script says why.
- The binary is invoked through `srun`, not called directly.
- Output paths carry `%j`.

## S2 - a job that will never start

Setup: A job is pending with reason `PartitionNodeLimit`. Prompt: "my job has
been queued for an hour, is that normal?"

Expected:

- `slurm_describe` is called and the pending reason is read.
- The answer says this job will never start and the request must change,
  distinguishing it from `Resources` or `Priority`, which mean waiting is
  correct.

## S3 - many similar runs

Setup: Prompt: "I need to run this over 100 input files."

Expected:

- A job array is proposed, not a submit loop.
- A concurrency throttle (`%N`) is included or its absence justified.
- `array` is passed to `slurm_submit` only for the array submission.

## Baseline failure modes to watch for (RED)

- Requesting the partition maximum walltime by default.
- Setting both `--mem` and `--mem-per-cpu`.
- Calling the binary directly instead of through `srun`.
- Reading any pending job as "working" without checking the reason.
- Looping `slurm_submit` where an array expresses the same thing.
