# Spack MCP

Spack MCP exposes a compact, structured package-management surface:

```text
spack_find
spack_locate
spack_install
```

The default server intentionally has no stateful `spack_load` tool. Each MCP
call runs in its own process context, so changing that process environment would
not affect a later agent or scheduler job. Pass installed specs to JARVIS through
`jarvis_run(spack_specs=[...])`; JARVIS captures a filtered environment delta,
persists it in the pipeline, and reloads it inside direct or scheduled execution.
`spack_locate` returns a canonical `load_spec` in `/<dag_hash>` form; pass that
value to `jarvis_run` so a later install cannot make the runtime selection
ambiguous.

An ordinary `spack_find` query with no installed matches is successful typed
data: `count` is `0` and `packages` is `[]`. Calling `spack_locate` for an absent
package instead returns the structured `not_installed` semantic so an agent can
decide whether its policy permits `spack_install`. Other nonzero Spack
invocations remain structured MCP errors.

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
