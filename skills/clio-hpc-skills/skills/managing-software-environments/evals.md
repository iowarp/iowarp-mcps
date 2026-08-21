# Evals - managing-software-environments

Baseline scenarios: run each WITHOUT the skill to capture the gap, then WITH it
to confirm the gap closes. Rubric is pass/fail per bullet.

## S1 - the load that does not persist

Setup: Prompt: "load the openmpi module so the next step can use it."

Expected:

- The answer does not claim openmpi is loaded for subsequent work.
- It states that `module_load` runs in a child process whose environment dies
  with the call, and that the tool reports success regardless.
- It offers the persistent route: `spack_locate` -> `jarvis_run` `spack_specs`.

## S2 - availability, asked correctly

Setup: Prompt: "does this machine have hdf5 with parallel support?"

Expected:

- `module_avail` is tried, and an empty result is followed by `module_spider`
  rather than concluding it is unavailable.
- On the Spack side, an empty `spack_find` is followed by `spack_search` before
  concluding a recipe does not exist.
- The answer distinguishes "not installed" from "no recipe exists".

## S3 - two systems, one answer

Setup: Prompt: "what versions of openmpi are available?" on a machine with both
lmod modules and Spack installs.

Expected:

- Module results and Spack results are reported as separate installations, not
  merged into one list.
- A module `openmpi/4.1.5` and a spec `openmpi@4.1.5` are not treated as the
  same thing.

## Baseline failure modes to watch for (RED)

- Reporting a module as loaded because `module_load` returned success.
- Concluding software is unavailable from `module_avail` alone.
- Concluding a package does not exist from `spack_find` alone.
- Presenting module and Spack results as one merged inventory.
