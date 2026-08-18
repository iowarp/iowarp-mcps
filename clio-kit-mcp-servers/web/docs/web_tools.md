# CLIO Web MCP tool reference

## `fetch`

`fetch(target, to_file=False, output_dir=None, max_bytes=None, timeout=None)`
retrieves an HTTP(S) URL or DOI as a required MCP task. HTML becomes Markdown;
plain text is returned directly; supported PDFs, Office documents, XML, and
images are sent to CLIO Web Search for structured conversion.

Task progress contains the backend conversion ID, stage, percentage, and a
human-readable message. The task stays alive until completion, explicit
cancellation, or a descriptive terminal failure. Cancellation is propagated to
`POST /v1/documents/{conversion_id}/cancel`.

Downloads enforce size limits and validate every redirect against the SSRF
policy. Empty HTML extraction reports
`js_render_required_browser_unavailable`; unsupported binary content reports
`binary_content_not_inlined` unless `to_file=True`.

## `fetch_events`

`fetch_events(conversion_id, after_sequence=0, limit=100)` retrieves a cursor
page from the persistent backend conversion log. Use it when the latest
`tasks/get` status message is insufficient. It is a synchronous read-only tool.

## `search`

`search(query, count=5)` is deliberately synchronous. DuckDuckGo is the keyless
default. SearXNG, Brave, and Tavily are selected at MCP startup. SearXNG exposes
its bounded native selectors; other providers expose only `query` and `count`.

## Unified configuration

`WEB_REMOTE_URL` or `--remote-url` points the local MCP at one CLIO Web Search
deployment. On startup, the MCP calls `/v1/capabilities` and
`/v1/task-backend/session`, persists a stable local agent ID and task encryption
key, and configures Docket with the returned per-agent Valkey queue and
credentials. `WEB_REMOTE_TOKEN` supplies the deployment bearer token when one
is configured.
