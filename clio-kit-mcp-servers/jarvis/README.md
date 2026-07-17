# Jarvis MCP

Jarvis MCP exposes JARVIS-CD pipeline work to agents through a small user
surface and a separate admin surface. This server requires Python 3.11 or newer;
the root CLIO Kit launcher resolves that requirement from the shipped lock.

## User server

Use this for normal agent workflows:

```bash
uv tool install 'clio-kit==2.3.0'
clio-kit mcp-server jarvis
```

When Spack is outside the service PATH, pass its audited executable explicitly:

```bash
clio-kit mcp-server jarvis -- \
  --spack-command /path/to/spack
```

The path must resolve to an executable file and is used only when
`jarvis_run(spack_specs=[...])` materializes the runtime environment.
`JARVIS_MCP_SPACK_COMMAND` is the equivalent site-level override; the explicit
CLI argument takes precedence.

Materializing `spack load --sh` also requires Bash. POSIX systems resolve Bash
from `PATH`. Native Windows resolves Bash from the installed Git for Windows
tree and deliberately rejects the legacy `System32\bash.exe` WSL launcher,
which can exist without an installed WSL distribution. Sites with another
audited Bash can set `JARVIS_MCP_BASH_COMMAND` to its executable path.

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
jarvis_get_execution
```

`jarvis_edit_step(operation="edit", config={...})` updates a step.
`jarvis_edit_step(operation="remove")` unlinks it while preserving package
files. Removal intentionally updates only pipeline membership: it does not invoke
package cleanup or delete installed or generated package files.

`jarvis_add_step` always runs package-owned configuration and validation on the
user surface. Use the canonical setting names returned by
`jarvis_describe(target="package")`; only aliases explicitly listed there are
also accepted. JSON documents may be passed directly as objects or lists under
their exact setting name and are canonically serialized before JARVIS validates
them. The lower-level admin `append_pkg` tool retains its explicit
`do_configure` compatibility control.

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
clio-kit mcp-server jarvis -- --profile admin
```

The admin server exposes the lower-level JARVIS and JarvisManager operations,
including repository management, environment rebuilding, raw package editing,
pipeline destruction, and other maintenance commands.

The compatibility profile that combines user and admin tools is also available:

```bash
clio-kit mcp-server jarvis -- --profile all
```

## Agent workflow

A normal agent should work at the pipeline level:

1. `jarvis_create_pipeline`
2. `jarvis_describe(target="packages")`
3. `jarvis_add_step`
4. `jarvis_edit_step`
5. `jarvis_describe(target="pipeline")`
6. `jarvis_run`
7. Query the returned handle with `jarvis_get_execution`

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
pipeline environment. Every run returns a JARVIS `execution_handle` and the
current durable `execution_record`. Direct runs pass `wait` through to
`Pipeline.run`; with `wait=false` the handle remains nonterminal and can be
queried later with `jarvis_get_execution`. Scheduler runs use the handle
returned by `Pipeline.submit`. The authoritative scheduler fields are
`scheduler_provider`, nullable `scheduler_native_id`, and nullable `cluster`.
`scheduler_job_id` remains a temporary relay compatibility alias and is never
inferred from application stdout.

### Runtime, progress, and artifact contracts

Every authoritative `jarvis_run` result carries producer schema
`jarvis.runtime.v1`. A claimed scheduler identity is accompanied by
`details.scheduler_submission` using `jarvis.scheduler.submission.v1`; its
provider and job id match the runtime record, `submitted` is true, and
`identity_source` is `scheduler_submit_api`. Consumers must treat a missing or
different schema as compatibility data, not scheduler ownership proof.

When the MCP client supplies a standard progress token, `jarvis_run` polls
`Pipeline.get_execution_progress(execution_id)` and forwards changed snapshots
through MCP `notifications/progress`. The notification message is the exact
serialized `jarvis.execution.progress.v1` document. The MCP `progress` number
is a strictly increasing transport sequence and `total` remains null; workload
counts and totals exist only inside the JARVIS snapshot, so transport metadata
is never presented as an application percentage. JARVIS-CD owns package
discovery, application output interpretation, identity validation, sequence
numbers, and durable JSONL storage. The MCP does not scrape JARVIS or
application stdout. Notifications are capped at 64 KiB each, 10,000 per run,
and 4 MiB total. Reporter failure does not orphan the JARVIS operation: the
operation is awaited before the error is returned.

`jarvis_get_execution(pipeline_id=..., execution_id=...)` is the single durable
query for an execution. It always returns the exact handle, latest record, and
runtime metadata, and includes the generic package progress snapshot by
default. Set `include_progress=false` when only lifecycle state is needed.

Execution-owned network services are also selectable through this same query,
not a separate tool. Set `include_service_runtimes=true` to receive the exact
`jarvis.execution.service-runtimes.v1` snapshot, including durable lifecycle,
service instance identity, private endpoint metadata, and the intrinsic
`jarvis.dataset-descriptor.v1`. JARVIS owns and validates these records; the MCP
does not scrape stdout or infer a service from process text. Private cluster
endpoints are routing inputs for clio-relay, not browser URLs.

Artifacts are opt-in so routine polling stays compact. Pass `artifacts={}` for
the default bounded page, or provide exact `package_id`, `role`, `state`, and
`artifact_id` filters plus `page_size` and `cursor`. The page size defaults to
50 and cannot exceed 100. Follow `next_cursor` with the same filters. The opaque
cursor is bound to the filtered producer snapshot and fails explicitly if
artifact or execution state changed between pages. References include opaque
artifact IDs, lifecycle state, role, structure, ownership, metadata, and
transport-neutral locations. The MCP does not read or transfer artifact
content or interpret application-specific formats. The fixed response always
contains nullable `progress`, `artifact_page`, and `service_runtimes` keys, so
selecting less data does not change its shape. `include_progress=false`
suppresses only the progress snapshot; runtime paths and package provenance
remain available.

The query retries boundedly if execution state changes while JARVIS is reading
the record, progress, and artifact manifests, so one response cannot mix
running and completed lifecycle states. Expected artifact failures use the
machine-readable `jarvis.error.v1` envelope. Cursor errors distinguish invalid,
filter-mismatched, and stale cursors; stale cursors set `retryable=true` so the
agent can restart pagination from the first page without parsing prose. This
works for direct executions with no scheduler, scheduler executions before or
after allocation, and terminal executions.
Successful `jarvis_run` results use `clio-kit.jarvis-run.v1`; unified execution
queries use `clio-kit.jarvis-execution.v2`.

## Claude Code

```bash
claude mcp add clio-jarvis -- clio-kit mcp-server jarvis
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
      "command": "clio-kit",
      "args": [
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
**Description**: Add and configure a package-backed step using exact package-owned settings returned by `jarvis_describe`; user-level validation cannot be bypassed.
**Tags**: jarvis, pipeline, user

### `jarvis_edit_step`
**Description**: Edit or remove a step. `config` is required only for `operation="edit"`.
**Tags**: jarvis, pipeline, user

### `jarvis_run`
**Description**: Run a configured JARVIS pipeline, optionally persisting the runtime environment for `spack_specs`, and return structured execution metadata.
**Tags**: jarvis, pipeline, user

### `jarvis_get_execution`
**Description**: Query a durable JARVIS execution, optionally including package progress, execution-owned service runtimes, and one bounded page of generated-artifact references.
**Hints**: read-only, idempotent
**Tags**: jarvis, pipeline, execution, user

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
      "command": "clio-kit",
      "args": [
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
