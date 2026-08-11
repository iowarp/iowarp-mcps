# CLIO Web MCP server — tool reference

Two curated tools for agentic web access. Runs as a confined fleet child under CLIO's sandbox,
so all egress is recorded through the network chokepoint.

## `fetch(url, *, to_file=False, output_dir=None, max_bytes=None, timeout=None)`

Retrieve an HTTP(S) URL. HTML is converted to Markdown (trafilatura → readability → plain-text
strip; the `extractor` field names which ran, so a quality downgrade is never silent). Returns
inline `content`, or — with `to_file=True` — writes it under the artifacts root and returns
`local_path` so raw pages never bloat context.

- **Size cap** (default 5 MiB, `WEB_MAX_BYTES`): enforced on `Content-Length` *and* mid-stream.
- **SSRF guard** (default on; `WEB_ALLOW_PRIVATE_HOSTS=true` to disable): refuses loopback /
  private / link-local literal hosts (incl. the cloud-metadata address `169.254.169.254`) and
  `localhost` names, on the initial URL **and every redirect hop** (redirects are followed
  manually so each hop is checked before connecting). `final_url` reports the resolved URL.
- **Typed gaps (honest, never junk):** an empty extraction returns
  `reason="js_render_required_browser_unavailable"` (headless-browser escalation is the
  follow-on); binary without `to_file` returns `reason="binary_content_not_inlined"`.
- **`(url, prompt)` extraction** is the agent's job (an MCP server has no model access): use
  `to_file=True` and pipe the saved file through the agent's own model.

## `search(query, *, provider=None, count=5, category=None, engines=None, language=None, time_range=None, pageno=None, safesearch=None)`

Search via a configurable provider. Keyless **DuckDuckGo** (`ddg`) is the default;
self-hosted **SearXNG** (`searxng`) uses `WEB_SEARXNG_BASE_URL`; optional **Brave**
and **Tavily** retain their BYO-key configuration. Selecting an unconfigured provider is a
typed error — never a silent fallback to `ddg`. `count` is capped at 25. Returns
`{title, url, snippet}` results.

SearXNG accepts native `category` (`general`, `science`, or `it`), exact `engines`,
`language`, `time_range` (`day`, `month`, or `year`), `pageno` (1 through 3), and
`safesearch` (0 through 2) selectors. Its response also includes `engines_answered` and
normalized `unresponsive_engines`. An explicit `engines` list takes precedence over
`category`, avoiding SearXNG's broader union of both selectors. Passing these selectors to
another provider is an error.

## Configuration (`WEB_`-prefixed env or a `.env`)

`WEB_SEARCH_PROVIDER`, `WEB_SEARXNG_BASE_URL`, `WEB_BRAVE_API_KEY`, `WEB_TAVILY_API_KEY`,
`WEB_MAX_BYTES`, `WEB_CONNECT_TIMEOUT_S`, `WEB_READ_TIMEOUT_S`, `WEB_ARTIFACTS_ROOT`,
`WEB_ALLOW_PRIVATE_HOSTS`.

For the LAN deployment, set `WEB_SEARCH_PROVIDER=searxng` and
`WEB_SEARXNG_BASE_URL=http://10.0.0.102:8088`. No paid-provider credential is required.
