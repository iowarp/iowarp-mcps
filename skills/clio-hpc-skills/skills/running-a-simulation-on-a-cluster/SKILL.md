---
name: running-a-simulation-on-a-cluster
description: Resolves Spack-provided software and runs it as a JARVIS pipeline, carrying the exact load spec across both servers and following the execution to completion. Use when a workload needs software that Spack provides, when a package must be run rather than merely located, or when the user mentions spack specs, module loading for a run, JARVIS pipelines, or submitting work to a cluster.
---

# Run a simulation on a cluster

Use this when a workload needs software from Spack and has to run somewhere
other than the current shell. It spans two servers, and the handoff between them
is the part that goes wrong.

The Spack server deliberately refuses to load anything into an environment,
because a load performed inside a tool call dies with that call. JARVIS owns the
runtime environment instead — `spack://capabilities` says so directly:
`stateful_load_exposed: false`, `runtime_owner: jarvis_run`.

## Pick the route first

There are two ways work reaches a cluster, and they are alternatives, not steps:

- **Package-backed workload** — a Spack package, run through a JARVIS pipeline.
  `clio-jarvis:jarvis_run` takes execution intent (`local`, `cluster`, `hostfile`)
  and resolves the scheduler itself. This is the path below.
- **A batch script you wrote yourself** — `clio-slurm:slurm_submit`, which returns
  a scheduler-native job ID.

Do not submit a JARVIS pipeline with `clio-slurm:slurm_submit`. Pass the cluster
intent to `clio-jarvis:jarvis_run` and let it own the scheduler.

## Steps

**1. Size the request against the machine.**

Call `clio-node-hardware:get_cpu_info` and, for anything GPU-backed,
`clio-node-hardware:get_gpu_info`. Asking for more ranks than the node has is a
job that pends indefinitely rather than one that fails fast.

**2. Find out whether the package is already installed.**

Call `clio-spack:spack_find` with the constraint. No matches is a *successful*
result with `count=0`, not an error — do not retry it as if the call failed.

If it returns nothing, `clio-spack:spack_search` answers a different question:
whether a recipe exists at all, in which repo, and whether it is already
installed. Reach for it before concluding the software is unavailable.

**3. Install only if it is missing.**

Call `clio-spack:spack_install` with an explicit concretization choice. Skip this
entirely when step 2 already found a match — installing is slow and runs
synchronously, and reinstalling a package that is present wastes the wait.

**4. Resolve the exact spec.**

Call `clio-spack:spack_locate`. Its `output.load_spec` is the value the run needs.

> Copy `spack_locate.output.load_spec` **unchanged**. Do not build a path from
> the returned prefix, do not append `/bin/<binary>`, do not simplify the spec
> string. The hash in it is what makes the environment reproducible, and a
> derived path silently drops it.

**5. Create the pipeline.**

Call `clio-jarvis:jarvis_create_pipeline` with a `pipeline_id` you choose. Pass
execution intent here when the workload needs a cluster rather than the local
host.

**6. Inspect the package before configuring it.**

Call `clio-jarvis:jarvis_describe` with `target='package'` for the package you
intend to add. The keys it returns are the canonical configuration names.
Guessing key names is the most common way the next step fails.

**7. Add the step.**

Call `clio-jarvis:jarvis_add_step` with the `pipeline_id`, the package, and a
config built from the keys step 6 returned.

**8. Run it, passing the Spack spec.**

Call `clio-jarvis:jarvis_run` with the `pipeline_id`, putting the `load_spec`
string from step 4 into one element of `input.spack_specs`. JARVIS persists that
runtime environment for the execution.

`clio-jarvis:jarvis_run` returns a durable execution handle and does **not** wait
for the workload to finish.

**9. Follow the execution.**

Call `clio-jarvis:jarvis_get_execution` with the `pipeline_id` and the handle.
Poll it. The run is finished when the lifecycle record says so, not when
`jarvis_run` returned.

## What not to do

- Do not look for a `spack_load` tool. There isn't one, on purpose.
- Do not treat `clio-spack:spack_find` returning zero packages as a failure.
- Do not pass an executable path where `spack_specs` expects a load spec.
- Do not skip `clio-jarvis:jarvis_describe` and guess configuration keys.
- Do not report the workload as finished because `clio-jarvis:jarvis_run`
  succeeded — it returns a handle, not a result.
- Do not use `clio-lmod:module_load` to prepare the environment for a run. It
  does not persist. See `managing-software-environments`.
