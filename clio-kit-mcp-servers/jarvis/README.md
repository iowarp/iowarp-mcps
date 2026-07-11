# Jarvis MCP

Jarvis MCP exposes JARVIS-CD pipeline work to agents through a small user
surface and a separate admin surface. This server requires Python 3.11 or newer;
the root CLIO Kit launcher resolves that requirement from the shipped lock.

## User server

Use this for normal agent workflows:

```bash
uvx clio-kit mcp-server jarvis
```

or run the package entry point directly:

```bash
uvx --from jarvis-mcp jarvis-mcp
```

When Spack is outside the service PATH, pass its audited executable explicitly:

```bash
uvx clio-kit mcp-server jarvis -- --spack-command /path/to/spack
# Equivalent standalone package entry point:
uvx --from jarvis-mcp jarvis-mcp --spack-command /path/to/spack
```

The path must resolve to an executable file and is used only when
`jarvis_run(spack_specs=[...])` materializes the runtime environment.
`JARVIS_MCP_SPACK_COMMAND` is the equivalent site-level override; the explicit
CLI argument takes precedence.

The default user server exposes only:

```text
jarvis_create_pipeline
jarvis_describe
jarvis_add_step
jarvis_edit_step
jarvis_run
```

`jarvis_edit_step(operation="edit", config={...})` updates a step.
`jarvis_edit_step(operation="remove")` unlinks it while preserving package
files. Removal intentionally updates only pipeline membership: it does not invoke
package cleanup or delete installed or generated package files.

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
uvx clio-kit mcp-server jarvis -- --profile admin
uvx clio-kit mcp-server jarvis -- --profile all
```

## Agent workflow

A normal agent should work at the pipeline level:

1. `jarvis_create_pipeline`
2. `jarvis_describe(target="packages")`
3. `jarvis_add_step`
4. `jarvis_edit_step`
5. `jarvis_describe(target="pipeline")`
6. `jarvis_run`

If the agent needs to remove a pipeline step, call
`jarvis_edit_step(operation="remove")`. Do not use raw `remove_pkg` from the
admin server unless the operator explicitly wants package deletion semantics.
`remove_pkg` fails rather than silently unlinking when the installed JARVIS-CD
does not provide a destructive removal API.

`jarvis_run(spack_specs=[...])` asks JARVIS to resolve a filtered Spack
environment, merge it into the named pipeline, and persist it before direct or
scheduler execution. Scheduler runs return a JARVIS-owned
`runtime_metadata.scheduler_job_id` parsed from the scheduler's structured
submission API. The relay must not infer that identity from application stdout.

## Claude Code

```bash
claude mcp add clio-jarvis -- uvx clio-kit mcp-server jarvis
```

Or install via the CLIO Kit plugin marketplace:

```
/plugin marketplace add iowarp/clio-kit
/plugin install clio-jarvis@iowarp-clio-kit
```
## Claude Desktop

Add to your Claude Desktop config (`claude_desktop_config.json`):

```json
{
  "mcpServers": {
    "clio-jarvis": {
      "command": "uvx",
      "args": [
        "clio-kit",
        "mcp-server",
        "jarvis"
      ]
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

## Capabilities

### `jarvis_create_pipeline`
**Description**: Create a JARVIS pipeline. Optionally pass execution intent such as local, cluster, or hostfile mode; backend details are resolved where the MCP server runs.
**Tags**: jarvis, pipeline, user

### `jarvis_describe`
**Description**: Describe JARVIS packages, one package, a pipeline, or one pipeline step.
**Hints**: read-only, idempotent
**Tags**: jarvis, pipeline, user

### `jarvis_add_step`
**Description**: Add a package-backed step to a JARVIS pipeline and optionally configure that step with package-owned settings.
**Tags**: jarvis, pipeline, user

### `jarvis_edit_step`
**Description**: Edit or remove a step. `config` is required only for `operation="edit"`.
**Tags**: jarvis, pipeline, user

### `jarvis_run`
**Description**: Run a configured JARVIS pipeline, optionally persisting the runtime environment for `spack_specs`, and return structured execution metadata.
**Tags**: jarvis, pipeline, user

### Resources

- `jarvis://capabilities` - JARVIS data pipeline capabilities.

### Prompts

- **create_pipeline_workflow**: Guided workflow for creating and deploying a JARVIS pipeline.
## Gemini CLI

Add to `~/.gemini/settings.json`:

```json
{
  "mcpServers": {
    "clio-jarvis": {
      "command": "uvx",
      "args": [
        "clio-kit",
        "mcp-server",
        "jarvis"
      ]
    }
  }
}
```

Or install the CLIO Kit extension:

```bash
gemini extensions install https://github.com/iowarp/clio-kit
```
