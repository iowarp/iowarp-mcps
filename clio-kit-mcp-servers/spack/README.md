# Spack MCP

Spack MCP exposes a compact, structured package-management surface:

```text
spack_find
spack_locate
spack_search
spack_info
spack_install
```

The default server intentionally has no stateful `spack_load` tool. Each MCP
call runs in its own process context, so changing that process environment would
not affect a later agent or scheduler job. Pass installed specs to JARVIS through
`jarvis_run(spack_specs=[...])`; JARVIS captures a filtered environment delta,
persists it in the pipeline, and reloads it inside direct or scheduled execution.
`spack_locate` returns a canonical `load_spec` in `/<dag_hash>` form; pass that
value to `jarvis_run` so a later install cannot make the runtime selection
ambiguous. `spack_install` echoes the same `load_spec` on success, so a caller
never has to re-locate what it just installed.

An ordinary `spack_find` query with no installed matches is successful typed
data: `count` is `0` and `packages` is `[]`. Calling `spack_locate` for an absent
package instead returns the structured `not_installed` semantic, enriched with
whether a recipe is available to install (and in which repo) or exists in no
registered repo at all, so an agent can decide whether its policy permits
`spack_install` without a separate lookup. Other nonzero Spack invocations
remain structured MCP errors.

## Recipe discovery

`spack_find`/`spack_locate` only see what is already **installed**.
`spack_search(query)` and `spack_info(package)` answer the broader question of
recipe **availability**:

- `spack_search` enumerates every repo registered with `spack repo list` and
  walks each repo's recipe directory directly (never `spack list`, which
  is broken on at least one deployment this server targets) to fuzzy-match the
  query against real recipe names -- matching normalizes `-`/`_` and case, so
  a query like `py-numpy` matches a `py_numpy` repo directory (Spack's modern
  Python-module-safe layout) exactly, not merely as a fuzzy guess. Each match
  reports which repo(s) declare it and whether it is already installed. A repo
  whose recipe directory cannot be read (missing path, permission denied, ...)
  degrades that one repo's contribution -- named in `repos_unreadable` -- but
  never empties out or fails the rest of the search. Results beyond the
  25-match cap set `truncated: true` with the real `total_matches`. If `spack
  find` itself fails, only the installed-state half of the answer degrades
  (`installed_state_degraded` + `installed_state_degraded_reason`); recipe
  availability is unaffected.
- `spack_info` describes one recipe's versions, variants, and description.
  It probes `spack info` first; if that subcommand is unavailable, fails, or
  returns an incomplete parse (a missing expected section), it falls back to
  statically parsing the recipe's `package.py` (never imported or executed,
  only read as source) and marks the result `degraded: true` with a
  `degraded_reason` naming the actual cause -- never silently.

## Install concretization

`spack_install` always selects the Spack concretization policy explicitly:

- `spack_install(spec, reuse=true)` runs `spack install --reuse <spec>` and may
  reuse compatible installed packages or buildcaches while concretizing.
- `spack_install(spec, reuse=false)` runs `spack install --fresh <spec>` and
  excludes installed packages and buildcaches while concretizing.

Fresh concretization does not mean "blindly reinstall an existing concrete
hash." Agents should first call `spack_find`, install only when the required
software is absent, then call `spack_locate` and pass its canonical `load_spec`
to `jarvis_run`.

`spack_install` runs synchronously today (streaming/task augmentation is
deferred to the kit tasks-semantics slice, SEP-2663) with a configurable
`timeout_seconds`. The full build log is captured to disk -- unbounded, not
just the response's bounded tail -- under `SPACK_MCP_INSTALL_LOG_DIR` (default
a `spack-mcp/install-logs` directory under the system temp dir). On success the
result carries `prefix`, `load_spec`, `log_path`, and a bounded `log_tail`.
Failure is one of several typed, distinguishable errors, each naming the
recovery affordance:

- `recipe_not_found` -- every registered repo was successfully read and none
  declares this package; `detail` lists the repos searched (composes with
  `spack_search`'s discovery). Spack is never even invoked in this case.
- `availability_unknown` -- the catalog found no match, but at least one
  registered repo could not be read; `detail` names which repo(s), so the
  install is refused without guessing rather than silently trusting an
  unverified negative. Spack is not invoked here either.
- `build_failure` -- Spack ran and exited nonzero; `detail` carries the log
  path and a tail of the failure.
- `timed_out` -- exceeded `timeout_seconds`; `detail` carries the log path so
  progress can be inspected without re-running the install.
- `capture_failed` -- the bounded subprocess capture itself failed after
  Spack was launched; `detail` carries the log path.
- `log_unwritable` -- the install log directory or file could not be
  created/opened; Spack is never invoked in this case.

### Breaking change in the v2.1 -> v2.2 registry contract

`spack_install`'s output shape changed: v2.1's `packages` (a list) and
`stdout_excerpt` are **removed**, replaced by `package` (one object),
`prefix`, `load_spec`, `log_path`, and `log_tail`. This is a breaking change
to the tool's output schema, not an additive one -- an external agent bound
to `spack_install.output.packages`/`.stdout_excerpt` must update. No consumer
inside this repository (or the `clio-agent-marketplace` submodule) read
either removed field at the time of the v2.2 release.

Run the default server with:

```bash
uv tool install 'clio-kit==2.5.10'
clio-kit mcp-server spack
```

When Spack is not on the service PATH, configure the audited executable
explicitly instead of modifying the worker environment:

```bash
clio-kit mcp-server spack -- \
  --spack-command /path/to/spack
```

The path must resolve to an executable file. `SPACK_MCP_COMMAND` provides the
equivalent site-level override; an explicit CLI argument takes precedence.

Environment diagnostics persist only a conservative path/toolchain allowlist.
Sites can add exact non-secret variable names with the comma-separated
`CLIO_SPACK_ENV_ALLOWLIST` or `SPACK_MCP_ENV_ALLOWLIST`; sensitive and transient
names remain rejected even when configured.

An operator-only diagnostic can return the structured environment without
claiming to mutate future processes:

```bash
clio-kit mcp-server spack -- --profile admin
```

Every successful tool returns a versioned Pydantic result. Command failures are
MCP error results whose text is a JSON `spack.mcp.error.v1` document. Specs are
passed as subprocess arguments rather than shell text, output is bounded, and
install timeouts terminate the process group.
