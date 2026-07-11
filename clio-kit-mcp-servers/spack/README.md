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

Run the default server with:

```bash
uvx clio-kit mcp-server spack
```

When Spack is not on the service PATH, configure the audited executable
explicitly instead of modifying the worker environment:

```bash
uvx clio-kit mcp-server spack --spack-command /path/to/spack
# Equivalent standalone package entry point:
uvx --from spack-mcp spack-mcp --spack-command /path/to/spack
```

The path must resolve to an executable file. `SPACK_MCP_COMMAND` provides the
equivalent site-level override; an explicit CLI argument takes precedence.

An operator-only diagnostic can return the structured environment without
claiming to mutate future processes:

```bash
uvx --from spack-mcp spack-admin-mcp
```

Every successful tool returns a versioned Pydantic result. Command failures are
MCP error results whose text is a JSON `spack.mcp.error.v1` document. Specs are
passed as subprocess arguments rather than shell text, output is bounded, and
install timeouts terminate the process group.
