# Web MCP Server

[![Python](https://img.shields.io/badge/Python-3.10%2B-blue)](https://www.python.org/)

**Part of [CLIO Kit](https://docs.iowarp.ai/) - Gnosis Research Center**

The Web MCP server provides two curated, high-level tools for agentic web
access. It is the seed of CLIO's web tooling and the test instrument for the
sandbox campaign's egress recording.

## Tools

### `fetch`

Retrieve an HTTP(S) URL, convert HTML to Markdown, and return it inline or save
it to a local file.

- **Agent story:** "I found a promising URL and need its actual content." The
  agent calls `fetch` to pull the page, get clean Markdown (links preserved),
  and read the title. For large or binary resources it passes `to_file=True` so
  the raw page is written to disk and only a `local_path` comes back — raw pages
  never bloat the context window. The agent can then pipe that file through its
  own model for `(url, prompt)`-style extraction.
- **Behavior:** streamed download with a hard size cap (default 5 MiB, enforced
  on `Content-Length` and mid-stream) and configurable timeouts;
  `follow_redirects=True`; HTML → Markdown via trafilatura, falling back to
  readability-lxml then a plain-text strip; non-HTML text returned as-is; binary
  content only materialized when `to_file=True`.
- **Returns:** `{ok, url, content | local_path, size_bytes, content_type,
  status, title, method: "http"}`. The `url` key always carries the fetched
  source URL verbatim — CLIO's provenance layer keys the web source off it.

### `search`

Query a configurable web-search provider and return ranked results.

- **Agent story:** "I need candidate URLs for a question." The agent calls
  `search` and gets back a small list of `{title, url, snippet}` rows to triage
  and then `fetch`.
- **Providers:** keyless **DuckDuckGo** (`ddg`, default, via the `ddgs`
  package); self-hosted **SearXNG** (`searxng`); optional BYO-key **Brave** and
  **Tavily**. Selecting an unconfigured provider raises a typed error naming
  the missing config — it never silently falls back to `ddg`.
- **SearXNG selectors:** `category` (`general` / `science` / `it`), exact
  `engines`, `language`, `time_range`, `pageno`, and `safesearch`. These are
  rejected for other providers instead of being silently discarded. An exact
  `engines` list takes precedence over `category`, because SearXNG otherwise
  treats the two selectors as a broader union.
- **Returns:** `{ok, provider, query, results: [{title, url, snippet}], count}`.

## Configuration

Configuration is a single `pydantic-settings` `Settings` model. All fields are
overridable via `WEB_`-prefixed environment variables or a `.env` file, but the
recommended path is a single source of config with clear defaults.

| Field | Env var | Default | Meaning |
| --- | --- | --- | --- |
| `search_provider` | `WEB_SEARCH_PROVIDER` | `"ddg"` | Active search provider (`ddg` / `searxng` / `brave` / `tavily`). |
| `searxng_base_url` | `WEB_SEARXNG_BASE_URL` | `None` | Root URL of the self-hosted SearXNG instance (required for `searxng`). |
| `brave_api_key` | `WEB_BRAVE_API_KEY` | `None` | Brave Search API key (required for `brave`). |
| `tavily_api_key` | `WEB_TAVILY_API_KEY` | `None` | Tavily API key (required for `tavily`). |
| `max_bytes` | `WEB_MAX_BYTES` | `5242880` | Fetch size cap in bytes (5 MiB). |
| `connect_timeout_s` | `WEB_CONNECT_TIMEOUT_S` | `5.0` | HTTP connect timeout. |
| `read_timeout_s` | `WEB_READ_TIMEOUT_S` | `30.0` | HTTP read timeout. |
| `artifacts_root` | `WEB_ARTIFACTS_ROOT` | `None` (→ CWD) | Default directory for `to_file` output. |

## Documented extension points (not yet available in v1)

These are honest, typed gaps — the follow-on campaign's remainder — not silent
failures:

- **Headless-browser escalation (Playwright)** for JS-rendered / Anubis-walled
  pages. When HTML extraction yields nothing, `fetch` returns a typed note
  `reason="js_render_required_browser_unavailable"` instead of returning junk.
- **`(url, prompt)` small-model extraction.** An MCP server has no model access,
  so page-specific extraction stays the agent's job: `fetch` with
  `to_file=True`, then let the agent pipe the saved file through its own model.

## Development

```bash
uv sync
uv run pytest -q            # network-mocked suite (default)
uv run ruff check src/ tests/
uv run mypy src/
```

Real-network checks are opt-in and skipped by default:

```bash
WEB_MCP_LIVE=1 uv run pytest -m integration
```

To make the self-hosted instance the active backend:

```bash
WEB_SEARCH_PROVIDER=searxng \
WEB_SEARXNG_BASE_URL=http://10.0.0.102:8088 \
uv run web-mcp
```

No paid-provider credential is needed for SearXNG. The server forwards native
selectors to the deployment and returns `engines_answered` plus normalized
`unresponsive_engines` alongside the stable `{title, url, snippet}` rows.
