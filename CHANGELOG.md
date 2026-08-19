# Changelog

All notable user-facing changes to CLIO Kit are documented here, newest first.

## 2.10.2

### JARVIS execution outputs are now fetchable artifacts

When a JARVIS pipeline execution finishes, the files it produced directly in
its execution directory (stdout/stderr logs, dumps, checkpoints, and other
generated output) are now automatically declared as artifacts on that
execution. Previously these files existed on disk but were invisible to
`jarvis_get_execution` unless a package explicitly registered them; now they
show up in the same bounded, paged artifact listing as everything else, typed
by role (`log`, `frame`, `output`, ...) and capped so a runaway output
directory can't blow out a response. Combined with the existing bounded
inline content read (`content_max_bytes`), this means a failed run's own
`stdout.log`/`stderr.log`/simulation log is directly readable through
`jarvis_get_execution` without a separate file-access tool.

### JARVIS user contract advances to v3.7.1

The wire contract for the JARVIS user tool surface (`clio-kit-jarvis-user`)
advances from v3.7 to v3.7.1, an additive patch revision: the artifact `role`
enum gains `frame` (for scientific output files like `.h5`, `.dcd`, `.vtk`,
trajectory/checkpoint frames) alongside the execution-output declarations
above. No tool is renamed, removed, or gains a required field. Every prior
contract revision (down to `clio-kit-jarvis-user-v3`) remains loadable by
exact identifier — nothing already deployed is invalidated by this bump.

This release also closes a gap where a kit build could be asked to load the
`clio-kit-jarvis-user-v3.7` contract family and not recognize it. The kit now
fully recognizes and ships v3.7 (historical) and v3.7.1 (current).

## 2.10.1 and earlier

See [GitHub Releases](https://github.com/iowarp/clio-kit/releases) for notes
on prior versions.
