# Evals - diagnosing-a-slow-job

Baseline scenarios: run each WITHOUT the skill to capture the gap, then WITH it
to confirm the gap closes. Rubric is pass/fail per bullet.

## S1 - load before anything else

Setup: A Darshan log on disk. Prompt: "why did this run take 3 hours?"

Expected:

- `load_darshan_log` is the first darshan call; no other darshan tool is
  attempted before it.
- Volume divided by runtime is computed before deeper analysis, and if the job
  is not I/O bound the answer says so instead of tuning I/O anyway.
- Request size is examined, not bandwidth alone.

## S2 - the right layer for an MPI code

Setup: An MPI application's log showing high POSIX operation counts.

Expected:

- `analyze_mpiio_operations` is consulted, and collective vs independent is
  named as the actionable layer.
- Raw POSIX syscall counts are not reported as the cause without the MPI-IO
  layer being checked first.

## S3 - the ambiguous tool name

Setup: Both the darshan and hdf5 servers are attached. Prompt asks to identify
I/O bottlenecks in a finished job.

Expected:

- `clio-darshan:identify_io_bottlenecks` is used, not the HDF5 tool of the same
  name, and the choice is stated.

## Baseline failure modes to watch for (RED)

- Calling a darshan analysis tool before `load_darshan_log`.
- Naming a cause from bandwidth alone, with no request-size or timeline check.
- Confusing the two `identify_io_bottlenecks` tools.
- Reaching for ChronoLog to explain job runtime.
- Loading two logs in sequence instead of using `compare_darshan_logs`.
