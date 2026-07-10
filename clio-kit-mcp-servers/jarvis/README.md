# Jarvis MCP

Jarvis MCP exposes JARVIS-CD pipeline work to agents through a small user
surface and a separate admin surface.

## User server

Use this for normal agent workflows:

```bash
uvx clio-kit mcp-server jarvis
```

or run the package entry point directly:

```bash
uvx --from jarvis-mcp jarvis-mcp
```

The default user server exposes only:

```text
jarvis_create_pipeline
jarvis_describe
jarvis_add_step
jarvis_edit_step
jarvis_remove_step
jarvis_run
```

`jarvis_remove_step` unlinks a package step from a pipeline while preserving
package files. It is normal pipeline editing, not package deletion.

`jarvis_describe` supports:

```text
target="packages"
target="package"
target="pipeline"
target="step"
```

It intentionally does not expose repository administration through the user
surface.

## Admin server

Use this only for operator or maintenance workflows:

```bash
uvx --from jarvis-mcp jarvis-admin-mcp
```

The admin server exposes the lower-level JARVIS and JarvisManager operations,
including repository management, environment rebuilding, raw package editing,
pipeline destruction, and other maintenance commands.

The compatibility form is also available:

```bash
uvx clio-kit mcp-server jarvis --profile admin
uvx clio-kit mcp-server jarvis --profile all
```

## Agent workflow

A normal agent should work at the pipeline level:

1. `jarvis_create_pipeline`
2. `jarvis_describe(target="packages")`
3. `jarvis_add_step`
4. `jarvis_edit_step`
5. `jarvis_describe(target="pipeline")`
6. `jarvis_run`

If the agent needs to remove a pipeline step, call `jarvis_remove_step`. Do not
use raw `remove_pkg` from the admin server unless the operator explicitly wants
package deletion semantics.

## Claude Code

```bash
claude mcp add jarvis-mcp -- uvx clio-kit mcp-server jarvis
```

For admin work:

```bash
claude mcp add jarvis-admin-mcp -- uvx --from jarvis-mcp jarvis-admin-mcp
```

## Claude Desktop

```json
{
  "mcpServers": {
    "jarvis-mcp": {
      "command": "uvx",
      "args": ["clio-kit", "mcp-server", "jarvis"]
    }
  }
}
```

## Local development

```bash
uv --directory clio-kit-mcp-servers/jarvis run jarvis-mcp --help
uv --directory clio-kit-mcp-servers/jarvis run jarvis-admin-mcp --help
uv --directory clio-kit-mcp-servers/jarvis run pytest -q
```
