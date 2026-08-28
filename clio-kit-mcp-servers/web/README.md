# Web MCP Server

The Web MCP exposes synchronous `search`, durable task-enabled `fetch`, and
`fetch_events` for the complete backend conversion log. The selected search
provider is fixed when the MCP starts; no tool call can silently switch it.

## Install

Connect a local stdio MCP to one unified CLIO Web Search deployment:

```bash
claude mcp add web -- uvx clio-kit mcp-server web --remote-url http://homelab:8089
```

`--remote_url` is accepted as an alias for clients or scripts that prefer
underscores. The remote URL provides SearXNG search, DOI resolution, document
conversion, task-backend discovery, and per-agent Valkey credentials. If the
deployment requires authentication, set `WEB_REMOTE_TOKEN` in the MCP process.

For standalone keyless search without remote document conversion:

```bash
claude mcp add web -- uvx clio-kit mcp-server web --provider ddg
```

Legacy `--address` and `--document-address` options remain compatible, but only
`--remote-url` enables automatic durable Valkey discovery.

## Task contract

`fetch(target)` is declared with required MCP task support. It returns a task
handle immediately at the protocol level. `tasks/get` reports the latest
download or conversion message, terminal results are returned through the task,
and `tasks/cancel` cancels any active backend document conversion. There is no
fixed overall conversion timeout; only individual network requests have bounded
timeouts.

`fetch_events(conversion_id, after_sequence=0, limit=100)` returns the ordered,
persistent backend log when the latest task message is not enough to diagnose a
conversion. Failures describe the stage, cause, retryability, conversion ID, and
an actionable remediation without exposing raw third-party exception text.

`search(query, count=5)` remains synchronous because ordinary web search is a
bounded request-response operation. SearXNG installations additionally expose
`category`, `engines`, `language`, `time_range`, `pageno`, and `safesearch`.
There is intentionally no `deep_search` tool: multi-step research is agent
semantics, not a backend tool semantic.

## Development

```bash
uv sync --prerelease allow
uv run ruff check --fix .
uv run ruff format .
uv run pyright src tests
uv run pytest -m "not integration"
WEB_MCP_LIVE=1 WEB_REMOTE_URL=http://homelab:8089 uv run pytest -m integration
```
