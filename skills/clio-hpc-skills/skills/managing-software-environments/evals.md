# Evals - managing-software-environments

Baseline scenarios: run each WITHOUT the skill to capture the gap, then WITH it
to confirm the gap closes. Rubric is pass/fail per bullet.

## S1 - the load that does not exist

Setup: Prompt: "load the openmpi module so the next step can use it."

Expected:

- No attempt is made to find or call a module-loading tool; the answer states
  the lmod server is read-only.
- It explains that a load performed inside a tool call dies with that call, so
  the capability is absent by design rather than missing.
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

- Claiming a module was loaded, or inventing a tool that would load one.
- Concluding software is unavailable from `module_avail` alone.
- Concluding a package does not exist from `spack_find` alone.
- Presenting module and Spack results as one merged inventory.

## Trigger record (2026-08-21)

Ran through `evals/trigger_eval.py`, which loads the skill plugins into the
Agent SDK with an empty `setting_sources` and only the Skill tool allowed, so
selection is measured without the operator's own configuration influencing it.

Prompt: "What MPI versions does this machine have?"

This skill fired, and no sibling fired alongside it. Across the suite: 20 of 20
skills selected correctly on their own prompt, and 3 control prompts outside the
kit fired nothing.

Selection is checked. Whether the skill improves the final answer, versus an
agent working without it, is still not measured.

