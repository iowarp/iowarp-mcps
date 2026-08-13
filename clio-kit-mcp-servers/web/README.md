# Web MCP Server

The Web MCP exposes two stable agent tools—`search` and `fetch`—while fixing the
search provider when each MCP installation starts. The agent cannot switch providers per
call, and it never sees parameters that the selected provider cannot use.

## Installations

DuckDuckGo remains the keyless default:

```bash
claude mcp add web -- uvx clio-kit mcp-server web --provider ddg
```

Use a private SearXNG deployment (or the optional `clio-search` image) with:

```bash
claude mcp add web -- uvx clio-kit mcp-server web \
  -- \
  --provider searxng \
  --address http://10.0.0.102:8089
```

For `searxng`, `--address` is required. When that address is a `clio-search`
installation, it also enables DOI resolution and structured-document conversion. A standalone
SearXNG instance still supports search; document enrichment will fail explicitly if requested.
For a non-SearXNG search provider, document enrichment can be configured separately with
`--document-address`.

Brave and Tavily remain optional bring-your-own-key providers. Their keys are read from
`WEB_BRAVE_API_KEY` and `WEB_TAVILY_API_KEY`; selecting either provider without its key is a
startup error. No paid provider is required by the default or SearXNG installations.

## `search`

Every installation accepts `query` and `count`. A SearXNG installation additionally exposes:

- `category` (`general`, `science`, or `it`)
- `engines`
- `language`
- `time_range`
- `pageno` (1 through 3)
- `safesearch`

Those fields are absent from the MCP schema for DDG, Brave, and Tavily. Results always preserve
`title`, `url`, `snippet`, and provider provenance. SearXNG results also preserve available
scholarly metadata such as authors, DOI, publication date, journal, publisher, document type,
PDF/HTML URLs, tags, citation count, engines, and score. `unresponsive_engines` is diagnostic
secondary-engine information; a successful result set is still a successful search.

## `fetch`

`fetch(target)` accepts an HTTP(S) URL or DOI. HTML is converted to Markdown locally. Text and
structured text pass through. Supported PDFs, Office documents, XML, and images are detected from
headers, URL, and content signatures and sent to the optional document service automatically.
The returned document includes Markdown, normalized structure, metadata, and—where GROBID detects
a scholarly paper—bibliographic references and in-text citation contexts.

Long conversions return `reason="document_conversion_pending"`, a durable `conversion_id`, and a
retry interval. Repeating the same fetch is content-deduplicated by `clio-search`. With
`to_file=True`, converted documents write a Markdown artifact and a JSON metadata companion.
Without a document service, existing HTML/text behavior remains available and unsupported binary
content can still be saved raw.

DOI resolution queries Crossref, falls back to DataCite metadata, and optionally uses Unpaywall
when the private `clio-search` installation has its own contact email configured. It never bypasses
access controls or fabricates an open copy.

## Configuration

CLI arguments define the installed search contract:

| Argument | Meaning |
| --- | --- |
| `--provider {ddg,searxng,brave,tavily}` | Fixed provider for this installation. |
| `--address URL` | Required SearXNG root; also used for document enrichment by default. |
| `--document-address URL` | Optional separate `clio-search` root. |

Runtime limits use `WEB_` environment variables, including `WEB_MAX_BYTES` (5 MiB HTML/text),
`WEB_MAX_DOCUMENT_BYTES` (50 MiB), `WEB_CONNECT_TIMEOUT_S`, `WEB_READ_TIMEOUT_S`,
`WEB_CONVERSION_WAIT_S`, `WEB_ARTIFACTS_ROOT`, and `WEB_ALLOW_PRIVATE_HOSTS`.

Discovery is available at `web://capabilities` and describes only this installation's active
provider and tool parameters; it does not advertise alternative providers to the agent.

## Development

```bash
uv sync
uv run ruff check --fix src tests
uv run ruff format src tests
uv run mypy src
WEB_MCP_LIVE=1 WEB_SEARXNG_BASE_URL=http://10.0.0.102:8089 uv run pytest
```
