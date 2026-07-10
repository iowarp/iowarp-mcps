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
claude mcp add clio-jarvis -- uvx clio-kit jarvis
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
**Description**: Edit the configuration of a step in a JARVIS pipeline.
**Tags**: jarvis, pipeline, user

### `jarvis_remove_step`
**Description**: Remove a step from a JARVIS pipeline without deleting package files.
**Tags**: jarvis, pipeline, user

### `jarvis_run`
**Description**: Run a configured JARVIS pipeline. Optional execution intent selects local, cluster, or hostfile mode without exposing scheduler internals.
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