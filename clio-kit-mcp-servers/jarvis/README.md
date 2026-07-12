# Jarvis MCP

Jarvis MCP exposes JARVIS-CD pipeline work to agents through a small user
surface and a separate admin surface. This server requires Python 3.11 or newer;
the root CLIO Kit launcher resolves that requirement from the shipped lock.

## User server

Use this for normal agent workflows:

```bash
uvx --from clio-kit==3.0.0 clio-kit mcp-server jarvis
```

When Spack is outside the service PATH, pass its audited executable explicitly:

```bash
uvx --from clio-kit==3.0.0 clio-kit mcp-server jarvis -- \
  --spack-command /path/to/spack
```

The path must resolve to an executable file and is used only when
`jarvis_run(spack_specs=[...])` materializes the runtime environment.
`JARVIS_MCP_SPACK_COMMAND` is the equivalent site-level override; the explicit
CLI argument takes precedence.

Spack materialization persists only a conservative path/toolchain allowlist.
Sites can add exact non-secret package variables with comma-separated
`CLIO_SPACK_ENV_ALLOWLIST` or `JARVIS_MCP_SPACK_ENV_ALLOWLIST`; sensitive and
transient names remain rejected. Pipeline IDs are bounded path-safe names, and
mutations are serialized per pipeline across MCP processes.

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
uvx --from clio-kit==3.0.0 clio-kit mcp-server jarvis -- --profile admin
```

The admin server exposes the lower-level JARVIS and JarvisManager operations,
including repository management, environment rebuilding, raw package editing,
pipeline destruction, and other maintenance commands.

The compatibility profile that combines user and admin tools is also available:

```bash
uvx --from clio-kit==3.0.0 clio-kit mcp-server jarvis -- --profile all
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
scheduler execution. Each scheduler submission seals an execution-scoped input
and runtime copy of `pipeline.yaml` and `environment.yaml`, plus unique script
and hostfile paths, so later edits to the named pipeline cannot change a queued
job. The structured Spack metadata always records a disposition: a run with no
requested specs and no prior owned environment reports `not_requested` rather
than `null`; reuse is accepted only when the persisted digest still matches the
pipeline environment. Scheduler runs return a JARVIS-owned
`runtime_metadata.scheduler_job_id` parsed from the scheduler's structured
submission API. The relay must not infer that identity from application stdout.

### Runtime and progress contracts

Every authoritative `jarvis_run` result carries producer schema
`jarvis.runtime.v1`. A claimed scheduler identity is accompanied by
`details.scheduler_submission` using `jarvis.scheduler.submission.v1`; its
provider and job id match the runtime record, `submitted` is true, and
`identity_source` is `scheduler_submit_api`. Consumers must treat a missing or
different schema as compatibility data, not scheduler ownership proof.

When the MCP client supplies a standard progress token, `jarvis_run` binds the
selected package provider from the
`clio_relay.package_progress_adapters` entry-point group and emits
`clio-kit.jarvis-package-progress.v1` envelopes through MCP
`notifications/progress`. Each envelope identifies the JARVIS execution,
pipeline, provider entry point and distribution, monotonic notification
sequence, selected source authority, and bounded JSON progress record.
The entry-point group is the generic relay-consumer extension protocol, not an
application-ownership claim. The recorded entry-point value and distribution
identity provide runtime provenance, not a cryptographic attestation; the
built-in LAMMPS provider is
`jarvis_cd.progress.lammps:adapter_from_package` from `jarvis-cd`. Package logs
are authoritative when the provider declares one; otherwise the server
uses its serialized JARVIS-stdout fallback. Notifications are capped at 64 KiB
each, 10,000 per run, and 4 MiB total. Provider or reporter failure does not
orphan the underlying JARVIS operation: the operation remains owned and is
awaited before the error is returned.

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
