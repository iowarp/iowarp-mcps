---
name: run-spack-package-in-jarvis
description: Resolve a Spack-installed package and run it as a JARVIS pipeline, carrying the exact spec across both servers.
servers: spack, jarvis
tools: spack_find, spack_install, spack_locate, jarvis_create_pipeline, jarvis_describe, jarvis_add_step, jarvis_run, jarvis_get_execution
---

# Run a Spack package as a JARVIS pipeline

Use this when a workload needs software from Spack and has to run through
JARVIS. It spans two servers, and the handoff between them is the part that goes
wrong: the Spack server deliberately refuses to load anything into an
environment, because a load performed inside a tool call dies with that call.
JARVIS owns the runtime environment instead.

`spack://capabilities` states this directly — `stateful_load_exposed: false`,
`runtime_owner: jarvis_run`.

## Steps

**1. Find out whether the package is already installed.**

Call `spack_find` with the constraint. No matches is a *successful* result with
`count=0`, not an error — do not retry it as if the call failed.

**2. Install only if it is missing.**

Call `spack_install` with an explicit concretization choice. Skip this step
entirely when step 1 already found a match; installing is slow and reinstalling
a present package wastes a scheduler slot.

**3. Resolve the exact spec.**

Call `spack_locate`. Its `output.load_spec` is the value the next step needs.

> Copy `spack_locate.output.load_spec` **unchanged**. Do not build a path from
> the returned prefix, do not append `/bin/<binary>`, do not simplify the spec
> string. The hash in it is what makes the environment reproducible, and a
> derived path silently drops it.

**4. Create the pipeline.**

Call `jarvis_create_pipeline` with a `pipeline_id` you choose. Pass execution
intent here if the workload needs a cluster rather than the local host.

**5. Inspect the package before configuring it.**

Call `jarvis_describe` with `target='package'` for the package you intend to
add. Its configuration keys are the canonical ones; guessing key names is the
most common way step 6 fails.

**6. Add the step.**

Call `jarvis_add_step` with the `pipeline_id`, the package, and a config built
from the keys step 5 returned.

**7. Run it, passing the Spack spec.**

Call `jarvis_run` with the `pipeline_id`, putting the `load_spec` string from
step 3 into one element of `input.spack_specs`. JARVIS persists that runtime
environment for the execution.

`jarvis_run` returns a durable execution handle and does **not** wait for the
workload to finish.

**8. Follow the execution.**

Call `jarvis_get_execution` with the `pipeline_id` and the handle. Poll it
rather than assuming the run completed when `jarvis_run` returned.

## What not to do

- Do not look for a `spack_load` tool. There isn't one, on purpose.
- Do not treat `spack_find` returning zero packages as a failure.
- Do not pass an executable path where `spack_specs` expects a load spec.
- Do not skip `jarvis_describe` and guess configuration keys.
- Do not report the workload as finished because `jarvis_run` succeeded — it
  returns a handle, not a result.
