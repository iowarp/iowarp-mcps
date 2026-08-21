---
name: managing-software-environments
description: Use when asked what software a machine has, which compiler or library version is available, how to switch versions, or when a run fails because software was not found. Triggers on "module avail", "is X installed", "what MPI do we have". Not for getting software into a run; use running-a-simulation-on-a-cluster.
clio-kit:
  bundle: clio-hpc
  servers: clio-lmod, clio-spack
  provenance: designed
  eval-status: scenarios-recorded
---

# Find out what software a machine has

Two servers answer overlapping questions about available software, and they
answer different ones. Reaching for the wrong one gives a confidently wrong
answer rather than an error.

## The trap: loading a module does not persist

`clio-lmod:module_load`, `clio-lmod:module_unload` and `clio-lmod:module_swap`
each run `module <verb>` in a **child process** with a copied environment. The
child exits and the change goes with it.

They report success. `module_load` returns
`{"success": true, "message": "Successfully loaded openmpi"}` while nothing is
loaded for anything that follows — not the next tool call, not a job, not a
pipeline. This is a silently wrong result, not an error you will see.

So: never use them to prepare an environment for work. To get software into a
run, resolve it with `clio-spack:spack_locate` and pass `output.load_spec` to
`clio-jarvis:jarvis_run` in `input.spack_specs`, which does persist for the
execution. See `running-a-simulation-on-a-cluster`.

## Which tool answers which question

**"What is loaded right now?"** — `clio-lmod:module_list`. Reflects the server's
own environment, which is only meaningful if something loaded it there.

**"Does this machine offer X?"** — `clio-lmod:module_avail` with a name pattern.
It searches what is currently visible in `MODULEPATH`.

**"Really, does it offer X anywhere?"** — `clio-lmod:module_spider`. Searches the
entire module tree, including modules hidden behind a compiler or MPI hierarchy
that `module_avail` cannot see until a prerequisite is loaded. When `module_avail`
comes back empty, this is the one that finds it.

**"What does this module actually set?"** — `clio-lmod:module_show`. Use it before
depending on a module for anything: it reveals the prerequisites and the
variables it sets.

**"Is this package installed under Spack?"** — `clio-spack:spack_find`. Only sees
what is already built. Zero matches is a successful result, not an error.

**"Does a recipe for it exist at all?"** — `clio-spack:spack_search`. Broader than
`spack_find`: it answers whether a recipe exists, in which repo, and whether it
happens to be installed. Use it before concluding software is unavailable.

**"What versions and variants does that recipe have?"** — `clio-spack:spack_info`.
Note that on deployments where `spack info` is unavailable it falls back to
parsing the recipe statically and marks the result as such — treat a
statically-parsed answer as less authoritative.

## Saved collections

`clio-lmod:module_save`, `module_restore` and `module_savelist` manage named
collections on disk. Saving writes a real file and does persist. Restoring has
the same limitation as loading: it applies to a child process that then exits.
A collection is a record of an intended environment, not a way to establish one.

## What not to do

- Do not report a module as loaded because `module_load` returned success.
- Do not conclude software is unavailable from `module_avail` alone — try
  `module_spider` before saying no.
- Do not conclude it is unavailable from `spack_find` alone — that only covers
  what is already built; try `spack_search`.
- Do not mix the two systems in one answer without saying which is which. A
  module named `openmpi/4.1.5` and a Spack spec `openmpi@4.1.5` are different
  installations that happen to share a version number.
