# Evals - running-a-simulation-on-a-cluster

Baseline scenarios: run each WITHOUT the skill to capture the gap, then WITH it
to confirm the gap closes. Rubric is pass/fail per bullet.

## S1 - package-backed run end to end

Setup: A cluster with the Spack, JARVIS, Slurm and node-hardware servers
attached. Prompt: "run the ior benchmark on the cluster and tell me when it
finishes."

Expected:

- `spack_find` is called before `spack_install`, and a zero-match result is
  treated as a successful answer rather than retried.
- `spack_locate`'s `output.load_spec` is passed into `jarvis_run`'s
  `input.spack_specs` byte-for-byte, with no path derived from the prefix.
- `jarvis_describe(target='package')` is called before `jarvis_add_step`.
- The run is not reported complete on `jarvis_run` returning;
  `jarvis_get_execution` is polled until the lifecycle record is terminal.

## S2 - route selection

Setup: Prompt: "I have a batch script at ./run.sh, get it onto the cluster."

Expected:

- `slurm_submit` is used directly; no JARVIS pipeline is created.
- The inverse case (a Spack package) is not submitted through `slurm_submit`.

## S3 - environment preparation

Setup: Prompt: "load openmpi and then run my pipeline."

Expected:

- No module-loading tool is sought or called; lmod is read-only.
- The answer states that a load inside a tool call would not persist, and
  routes the software through `spack_locate` -> `jarvis_run` instead.

## Baseline failure modes to watch for (RED)

- Searching for a `spack_load` tool, or inventing one.
- Building an executable path from `spack_locate`'s prefix, silently dropping
  the hash that makes the environment reproducible.
- Guessing JARVIS config key names instead of calling `jarvis_describe`.
- Reporting the workload finished because `jarvis_run` returned a handle.
- Submitting a JARVIS pipeline through `slurm_submit`.
