"""Web MCP server: curated ``fetch`` + ``search`` tools for agentic web access.

This is a proper v1 web-tooling surface for CLIO. Two tools are exposed:

* ``fetch`` -- retrieve an HTTP(S) URL with a streamed size cap and timeout,
  convert HTML to Markdown (trafilatura -> readability -> plain-text strip),
  and either return the content inline or write it to a local file.
* ``search`` -- query a configurable web-search provider (keyless DuckDuckGo by
  default, optional BYO-key Brave / Tavily).

Documented extension points (NOT implemented in v1 -- honest, typed gaps, never
a silent fallback):

* Headless-browser escalation (Playwright) for JS-rendered / Anubis-walled
  pages. When HTML extraction yields nothing, ``fetch`` returns a typed note
  ``reason="js_render_required_browser_unavailable"`` instead of silently
  handing back junk.
* ``(url, prompt)`` small-model extraction. An MCP server has no model access,
  so page-specific extraction stays the agent's job: use ``to_file=True`` and
  let the agent pipe the saved file through its own model.
"""

from __future__ import annotations

import asyncio
import ipaddress
import os
import re
from pathlib import Path
from typing import Annotated, Any
from urllib.parse import urlparse

import httpx
import trafilatura
from dotenv import load_dotenv
from fastmcp import FastMCP
from fastmcp.exceptions import ToolError
from fastmcp.prompts import Message
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict
from readability import Document as ReadabilityDocument

# Environment setup
load_dotenv()


# ---------------------------------------------------------------------------
# Configuration (single source of truth; tests vary CONFIG, not ambient env)
# ---------------------------------------------------------------------------


class Settings(BaseSettings):
    """Runtime configuration for the web MCP server.

    All fields are overridable via ``WEB_``-prefixed environment variables
    (e.g. ``WEB_SEARCH_PROVIDER``, ``WEB_BRAVE_API_KEY``, ``WEB_MAX_BYTES``) or
    a ``.env`` file, but tests should construct ``Settings(...)`` directly so
    behavior is driven by config rather than the ambient environment.
    """

    model_config = SettingsConfigDict(env_prefix="WEB_", env_file=".env", extra="ignore")

    # Search provider selection. Keyless "ddg" is the default so search works
    # out of the box; "brave"/"tavily" are opt-in and require their own key.
    search_provider: str = "ddg"
    brave_api_key: str | None = None
    tavily_api_key: str | None = None

    # Fetch limits.
    max_bytes: int = 5 * 1024 * 1024
    connect_timeout_s: float = 5.0
    read_timeout_s: float = 30.0

    # Default writable root for ``to_file`` output. ``None`` -> current working
    # directory, so a caller that launches the server from a chosen directory
    # controls where artifacts land.
    artifacts_root: str | None = None

    # SSRF guard: when False (default), fetch refuses URLs whose host is a
    # loopback / private / link-local / reserved LITERAL IP (or a localhost
    # name) -- on the initial URL AND every redirect hop -- so the tool is not a
    # confused deputy reaching the cloud-metadata endpoint (169.254.169.254) or
    # an internal service on behalf of injected content. Set True for a
    # deliberately internal fetcher. Deeper DNS-rebinding (a public name that
    # resolves private) is caught at the sandbox egress layer, not here: the
    # confined tool routes through a proxy and must NOT resolve DNS itself
    # (Linux-fence DNS is proxy-only), so the guard is literal-address-based.
    allow_private_hosts: bool = False


# Module-level settings instance. Tests monkeypatch ``server.settings`` with a
# freshly constructed ``Settings(...)`` to exercise alternate configuration.
settings = Settings()


# Search-provider HTTP endpoints (keyed providers).
_BRAVE_ENDPOINT = "https://api.search.brave.com/res/v1/web/search"
_TAVILY_ENDPOINT = "https://api.tavily.com/search"

# Typed extension-point signals (honest gaps, never silent fallbacks).
REASON_JS_RENDER_REQUIRED = "js_render_required_browser_unavailable"
REASON_BINARY_NOT_INLINED = "binary_content_not_inlined"
REASON_BLOCKED_HOST = "blocked_private_host"

# Bounds. Redirects are followed manually so each hop is SSRF-checked before the
# connection; search results are capped so a caller can't request an unbounded page.
_MAX_REDIRECTS = 5
_MAX_SEARCH_COUNT = 25

# Host names that always denote the local machine (checked before literal-IP parse).
_LOCAL_HOSTNAMES = {"localhost", "localhost.localdomain", "ip6-localhost", "ip6-loopback"}


# Initialize FastMCP server instance.
mcp: FastMCP = FastMCP(
    "web",
    instructions=(
        "Provides agentic web access. Use fetch to retrieve a URL and convert "
        "HTML to Markdown (optionally saving it to a local file with "
        "to_file=True so raw pages never bloat context), and search to query a "
        "configurable web-search provider for candidate URLs."
    ),
    list_page_size=10,
)


# ---------------------------------------------------------------------------
# Output-path helpers (self-contained allowed-root confinement)
# ---------------------------------------------------------------------------


def artifacts_root(output_dir: str | Path | None = None) -> Path:
    """Return the writable root for fetched-to-file content.

    Precedence: an explicit ``output_dir`` wins; otherwise ``settings.
    artifacts_root``; otherwise the current working directory. No destination
    is hardcoded and nothing is rerouted.
    """
    explicit = str(output_dir).strip() if output_dir not in (None, "") else ""
    configured = (settings.artifacts_root or "").strip()
    if explicit:
        root = Path(explicit).expanduser()
    elif configured:
        root = Path(configured).expanduser()
    else:
        root = Path.cwd()
    root.mkdir(parents=True, exist_ok=True)
    return root.resolve()


def _validate_output_path(
    candidate: str | Path, *, default_name: str, output_dir: str | Path | None = None
) -> Path:
    """Resolve an output path, confining writes to the resolved artifacts root.

    A relative path, bare filename, or any path outside that root is relocated
    under it using only its filename -- a self-contained allowed-root check.
    """
    root = artifacts_root(output_dir)
    raw = Path(str(candidate)).expanduser() if candidate else Path(default_name)
    name = raw.name or default_name
    if raw.is_absolute():
        try:
            resolved = raw.resolve()
            resolved.relative_to(root)
            resolved.parent.mkdir(parents=True, exist_ok=True)
            return resolved
        except (ValueError, OSError):
            pass
    target = (root / name).resolve()
    target.parent.mkdir(parents=True, exist_ok=True)
    return target


def _safe_filename(value: str, *, default: str) -> str:
    """Return a conservative filesystem name for saved content."""
    cleaned = "".join(ch if ch.isalnum() or ch in "._-" else "_" for ch in value.strip())
    cleaned = cleaned.strip("._-")
    return cleaned[:120] or default


def _derive_filename(url: str, *, is_html: bool, is_binary: bool) -> str:
    """Derive a safe output filename from a URL and the detected content kind."""
    parsed = urlparse(url)
    base = Path(parsed.path).name or parsed.netloc or "page"
    safe = _safe_filename(base, default="page")
    if is_html:
        # HTML is converted to Markdown; give it a .md extension.
        stem = Path(safe).stem or "page"
        return f"{stem}.md"
    if is_binary:
        return safe
    if "." not in safe:
        return f"{safe}.txt"
    return safe


# ---------------------------------------------------------------------------
# Content-type detection and HTML -> Markdown conversion
# ---------------------------------------------------------------------------

_TEXT_SUBTYPES = {
    "json",
    "xml",
    "xhtml+xml",
    "javascript",
    "ecmascript",
    "x-yaml",
    "yaml",
    "csv",
    "tab-separated-values",
    "markdown",
    "plain",
}


def _split_content_type(content_type: str | None) -> tuple[str, str | None]:
    """Return the lowercased mime type (without params) and its charset."""
    if not content_type:
        return "", None
    parts = [p.strip() for p in content_type.split(";")]
    mime = parts[0].lower()
    charset: str | None = None
    for param in parts[1:]:
        if param.lower().startswith("charset="):
            charset = param.split("=", 1)[1].strip().strip('"') or None
    return mime, charset


def _is_html(mime: str) -> bool:
    """True when the mime type denotes HTML."""
    return mime in {"text/html", "application/xhtml+xml"} or mime.endswith("+html")


def _is_text(mime: str) -> bool:
    """True when the mime type denotes inline-able text."""
    if not mime:
        return False
    main, _, sub = mime.partition("/")
    if main == "text":
        return True
    return sub in _TEXT_SUBTYPES


_TAG_RE = re.compile(r"<[^>]+>")
_TITLE_RE = re.compile(r"<title[^>]*>(.*?)</title>", re.IGNORECASE | re.DOTALL)
_WS_RE = re.compile(r"[ \t\r\f\v]+")
_BLANKLINES_RE = re.compile(r"\n{3,}")


def _strip_tags(html: str) -> str:
    """Collapse an HTML fragment to readable plain text.

    ``<head>`` (with its ``<title>``/meta) and ``<script>``/``<style>`` blocks
    are dropped first so only body-visible text remains -- a page whose body is
    an empty SPA shell then strips to nothing, which is the signal used to raise
    the headless-browser extension point.
    """
    without_head = re.sub(r"<head[^>]*>.*?</head>", " ", html, flags=re.IGNORECASE | re.DOTALL)
    without_script = re.sub(
        r"<(script|style)[^>]*>.*?</\1>", " ", without_head, flags=re.IGNORECASE | re.DOTALL
    )
    text = _TAG_RE.sub(" ", without_script)
    text = _WS_RE.sub(" ", text)
    text = "\n".join(line.strip() for line in text.splitlines())
    return _BLANKLINES_RE.sub("\n\n", text).strip()


def _extract_title(html: str) -> str | None:
    """Extract the document ``<title>`` when present."""
    match = _TITLE_RE.search(html)
    if not match:
        return None
    title = _strip_tags(match.group(1)).strip()
    return title or None


def _html_to_markdown(html: str) -> tuple[str | None, str | None]:
    """Convert HTML to Markdown; return ``(content, extractor)``.

    Falls back trafilatura -> readability-lxml -> plain-text strip, and NAMES which extractor
    produced the content (``"trafilatura"``/``"readability"``/``"plaintext"``) so a quality
    DOWNGRADE is visible to the caller rather than silent (clio's no-silent-fallback rule).
    ``(None, None)`` when nothing meaningful can be extracted -- the signal used to raise the
    headless-browser extension point rather than return junk.
    """
    try:
        markdown = trafilatura.extract(
            html,
            output_format="markdown",
            include_links=True,
            favor_recall=True,
        )
    except Exception:  # noqa: BLE001 - any parse failure falls through to readability
        markdown = None
    if markdown and markdown.strip():
        return markdown.strip(), "trafilatura"

    try:
        document = ReadabilityDocument(html)
        summary_html = document.summary(html_partial=True)
        readable = _strip_tags(summary_html)
    except Exception:  # noqa: BLE001 - readability failure falls through to strip
        readable = ""
    if readable.strip():
        return readable.strip(), "readability"

    stripped = _strip_tags(html)
    return (stripped, "plaintext") if stripped else (None, None)


def _decode(body: bytes, charset: str | None) -> str:
    """Decode fetched bytes to text using the advertised charset when valid."""
    if charset:
        try:
            return body.decode(charset, errors="replace")
        except LookupError:
            pass
    return body.decode("utf-8", errors="replace")


def _looks_like_text(body: bytes) -> bool:
    """Heuristic content-sniff for a body served with NO content-type header.

    A NUL byte or a high share of UTF-8 replacement chars in the leading sample denotes binary;
    otherwise it is treated as text (returned) rather than withheld. Boundary-cut multibyte
    chars are tolerated (decode with ``replace``), so valid text is never misread as binary.
    """
    if not body:
        return True
    sample = body[:8192]
    if b"\x00" in sample:
        return False
    decoded = sample.decode("utf-8", errors="replace")
    if not decoded:
        return False
    return decoded.count("�") / len(decoded) < 0.05


# ---------------------------------------------------------------------------
# Tool 1: fetch
# ---------------------------------------------------------------------------


def _host_is_blocked(host: str) -> bool:
    """True when ``host`` is a local/private/reserved LITERAL address or a localhost name.

    A hostname that is not a literal IP returns False here (not blocked by the tool) --
    resolving it would require client-side DNS the confined proxy tier does not provide, so
    DNS-rebinding to a private IP is caught at the sandbox egress layer, not here.
    """
    h = host.strip().strip("[]").lower()
    if not h:
        return True
    if h in _LOCAL_HOSTNAMES or h.endswith(".localhost"):
        return True
    try:
        ip = ipaddress.ip_address(h)
    except ValueError:
        return False  # a hostname, not a literal IP -- allowed at the tool layer
    return (
        ip.is_loopback
        or ip.is_private
        or ip.is_link_local  # covers 169.254.0.0/16 incl. the 169.254.169.254 metadata addr
        or ip.is_reserved
        or ip.is_multicast
        or ip.is_unspecified
    )


def _assert_allowed_url(url: str) -> None:
    """Raise ToolError if ``url``'s host is a blocked literal address (unless configured open)."""
    if settings.allow_private_hosts:
        return
    host = urlparse(url).hostname or ""
    if _host_is_blocked(host):
        raise ToolError(
            f"fetch blocked host {host!r}: refusing a loopback/private/link-local address "
            f"(reason={REASON_BLOCKED_HOST}). Set WEB_ALLOW_PRIVATE_HOSTS=true to permit "
            "internal fetches."
        )


async def _download(
    url: str, *, max_bytes: int, timeout: httpx.Timeout
) -> tuple[bytes, str | None, int, str]:
    """Stream a URL with a hard size cap; return (body, content_type, status, final_url).

    Redirects are followed MANUALLY (up to :data:`_MAX_REDIRECTS`) so each hop's host is
    SSRF-checked with :func:`_assert_allowed_url` BEFORE the connection -- a public page can
    otherwise 30x-redirect into an internal service. The size cap is enforced both against an
    advertised ``content-length`` and while streaming, so an oversized body raises before it is
    fully buffered. ``final_url`` is the last (non-redirect) URL actually fetched.
    """
    async with httpx.AsyncClient(timeout=timeout, follow_redirects=False) as client:
        current = httpx.URL(url)
        for _hop in range(_MAX_REDIRECTS + 1):
            _assert_allowed_url(str(current))
            async with client.stream("GET", current) as response:
                if response.is_redirect and "location" in response.headers:
                    current = current.join(response.headers["location"])
                    continue
                response.raise_for_status()
                content_type = response.headers.get("content-type")
                content_length = response.headers.get("content-length")
                if content_length:
                    try:
                        advertised = int(content_length)
                    except ValueError:
                        advertised = 0
                    if advertised > max_bytes:
                        raise ToolError(
                            f"Resource is {advertised} bytes, which exceeds the fetch size "
                            f"limit of {max_bytes} bytes. Increase max_bytes intentionally "
                            "or select a smaller resource."
                        )
                chunks: list[bytes] = []
                total = 0
                async for chunk in response.aiter_bytes(chunk_size=64 * 1024):
                    if not chunk:
                        continue
                    total += len(chunk)
                    if total > max_bytes:
                        raise ToolError(
                            f"Resource exceeded the fetch size limit of {max_bytes} bytes "
                            "while downloading. Increase max_bytes intentionally or select "
                            "a smaller resource."
                        )
                    chunks.append(chunk)
                return b"".join(chunks), content_type, response.status_code, str(response.url)
    raise ToolError(f"fetch exceeded {_MAX_REDIRECTS} redirects for {url!r}.")


@mcp.tool(
    name="fetch",
    title="Fetch URL",
    description=(
        "Fetch an HTTP(S) URL with a streamed size cap and timeout, convert "
        "HTML to Markdown, and return the content inline or (to_file=True) "
        "write it to a local file and return its path."
    ),
    annotations={"readOnlyHint": True, "destructiveHint": False, "idempotentHint": True},
    tags={"web", "fetch", "http"},
)
async def fetch(
    url: Annotated[str, Field(description="The http(s) URL to fetch.")],
    to_file: Annotated[
        bool,
        Field(
            description=(
                "Write the (converted) content to a local file and return "
                "local_path instead of inline content. Use for large or binary "
                "resources so raw pages never bloat context; the agent can then "
                "pipe the saved file through its own model for (url, prompt) "
                "extraction."
            )
        ),
    ] = False,
    output_dir: Annotated[
        str | None,
        Field(
            description=(
                "Destination directory when to_file=True. Defaults to the "
                "configured artifacts_root or the current working directory."
            )
        ),
    ] = None,
    max_bytes: Annotated[
        int | None,
        Field(description="Override the size cap in bytes (default from config: 5 MiB)."),
    ] = None,
    timeout: Annotated[
        float | None,
        Field(description="Override the read timeout in seconds (default from config)."),
    ] = None,
) -> dict[str, Any]:
    """Fetch a URL and return Markdown/text content or a saved file path.

    An MCP server has no model access, so page-specific ``(url, prompt)``
    extraction is intentionally left to the agent: fetch to a file and pipe it
    through the agent's own model.
    """
    target = (url or "").strip()
    if not target.lower().startswith(("http://", "https://")):
        raise ToolError(f"fetch only supports http(s) URLs; got: {target!r}")

    cap = max_bytes if max_bytes and max_bytes > 0 else settings.max_bytes
    read_timeout = timeout if timeout and timeout > 0 else settings.read_timeout_s
    timeout_cfg = httpx.Timeout(read_timeout, connect=settings.connect_timeout_s)

    # Guard the initial URL up front (each redirect hop is re-checked inside _download).
    _assert_allowed_url(target)
    try:
        body, raw_content_type, status, final_url = await _download(
            target, max_bytes=cap, timeout=timeout_cfg
        )
    except ToolError:
        raise
    except httpx.HTTPError as exc:
        raise ToolError(f"Could not fetch {target}: {exc}") from exc

    size_bytes = len(body)
    mime, charset = _split_content_type(raw_content_type)
    is_html = _is_html(mime)
    # A response with NO content-type is content-sniffed: decodable-as-UTF-8 text is treated as
    # text (returned), not withheld as binary. Only genuinely undecodable bytes stay binary.
    is_text = _is_text(mime) or is_html or (mime == "" and _looks_like_text(body))
    is_binary = not is_text

    result: dict[str, Any] = {
        "ok": True,
        "url": target,
        "size_bytes": size_bytes,
        "content_type": raw_content_type,
        "status": status,
        "title": None,
        "method": "http",
    }
    if final_url and final_url != target:
        result["final_url"] = final_url  # the resolved URL after redirects (url stays verbatim)

    content: str | None
    if is_html:
        html = _decode(body, charset)
        result["title"] = _extract_title(html)
        content, extractor = _html_to_markdown(html)
        result["extractor"] = extractor  # which extractor ran (downgrade is visible)
        if content is None:
            # Extraction produced nothing usable: almost always a JS-rendered
            # or challenge-walled page. Signal the headless-browser extension
            # point instead of returning junk.
            result["content"] = None
            result["reason"] = REASON_JS_RENDER_REQUIRED
            result["note"] = (
                "HTML extraction yielded no content; the page likely requires a "
                "JavaScript-capable headless browser, which is not available in v1."
            )
            return result
    elif is_binary:
        if not to_file:
            # Never inline a giant binary blob; hand back a typed note.
            result["content"] = None
            result["reason"] = REASON_BINARY_NOT_INLINED
            result["note"] = (
                "Binary content is not inlined. Re-call fetch with to_file=True to "
                "save it to a local file."
            )
            return result
        content = None  # binary is written raw below
    else:
        content = _decode(body, charset)

    if to_file:
        filename = _derive_filename(target, is_html=is_html, is_binary=is_binary)
        output_path = _validate_output_path(filename, default_name="page", output_dir=output_dir)
        if is_binary:
            output_path.write_bytes(body)
        else:
            output_path.write_text(content or "", encoding="utf-8")
        result["local_path"] = str(output_path)
    else:
        result["content"] = content

    return result


# ---------------------------------------------------------------------------
# Tool 2: search (provider abstraction, config-selected)
# ---------------------------------------------------------------------------


def _ddgs_search(query: str, count: int) -> list[dict[str, str]]:
    """Keyless DuckDuckGo search via the ``ddgs`` package (sync)."""
    from ddgs import DDGS

    results: list[dict[str, str]] = []
    with DDGS() as ddgs:
        for item in ddgs.text(query, max_results=count):
            results.append(
                {
                    "title": str(item.get("title") or ""),
                    "url": str(item.get("href") or item.get("url") or ""),
                    "snippet": str(item.get("body") or item.get("snippet") or ""),
                }
            )
    return results


async def _search_ddg(query: str, count: int) -> list[dict[str, str]]:
    """Run the synchronous DDG search off the event loop."""
    return await asyncio.to_thread(_ddgs_search, query, count)


async def _search_brave(query: str, count: int) -> list[dict[str, str]]:
    """BYO-key Brave Search adapter."""
    if not settings.brave_api_key:
        raise ToolError(
            "search provider 'brave' requires an API key. Set WEB_BRAVE_API_KEY "
            "(Settings.brave_api_key) or choose a different provider."
        )
    headers = {"X-Subscription-Token": settings.brave_api_key, "Accept": "application/json"}
    params: dict[str, str | int] = {"q": query, "count": count}
    async with httpx.AsyncClient(timeout=httpx.Timeout(settings.read_timeout_s)) as client:
        response = await client.get(_BRAVE_ENDPOINT, headers=headers, params=params)
        response.raise_for_status()
        payload = response.json()
    web = payload.get("web") or {}
    results: list[dict[str, str]] = []
    for item in (web.get("results") or [])[:count]:
        results.append(
            {
                "title": str(item.get("title") or ""),
                "url": str(item.get("url") or ""),
                "snippet": str(item.get("description") or ""),
            }
        )
    return results


async def _search_tavily(query: str, count: int) -> list[dict[str, str]]:
    """BYO-key Tavily Search adapter."""
    if not settings.tavily_api_key:
        raise ToolError(
            "search provider 'tavily' requires an API key. Set WEB_TAVILY_API_KEY "
            "(Settings.tavily_api_key) or choose a different provider."
        )
    body = {
        "api_key": settings.tavily_api_key,
        "query": query,
        "max_results": count,
    }
    async with httpx.AsyncClient(timeout=httpx.Timeout(settings.read_timeout_s)) as client:
        response = await client.post(_TAVILY_ENDPOINT, json=body)
        response.raise_for_status()
        payload = response.json()
    results: list[dict[str, str]] = []
    for item in (payload.get("results") or [])[:count]:
        results.append(
            {
                "title": str(item.get("title") or ""),
                "url": str(item.get("url") or ""),
                "snippet": str(item.get("content") or ""),
            }
        )
    return results


@mcp.tool(
    name="search",
    title="Search Web",
    description=(
        "Search the web via a configurable provider (keyless DuckDuckGo by "
        "default; optional BYO-key Brave or Tavily) and return ranked results."
    ),
    annotations={"readOnlyHint": True, "destructiveHint": False, "idempotentHint": False},
    tags={"web", "search"},
)
async def search(
    query: Annotated[str, Field(description="The search query.")],
    provider: Annotated[
        str | None,
        Field(description="Override the configured provider: 'ddg', 'brave', or 'tavily'."),
    ] = None,
    count: Annotated[int, Field(description="Maximum number of results to return.")] = 5,
) -> dict[str, Any]:
    """Search the web and return ``{title, url, snippet}`` results.

    The provider is selected by config (``Settings.search_provider``, keyless
    ``ddg`` by default). Selecting a keyed provider without its key raises a
    typed error naming the missing configuration -- never a silent fallback.
    """
    text = (query or "").strip()
    if not text:
        raise ToolError("A non-empty query is required.")
    effective_count = min(count if count and count > 0 else 5, _MAX_SEARCH_COUNT)
    selected = (provider or settings.search_provider or "ddg").lower()

    if selected == "ddg":
        results = await _search_ddg(text, effective_count)
    elif selected == "brave":
        results = await _search_brave(text, effective_count)
    elif selected == "tavily":
        results = await _search_tavily(text, effective_count)
    else:
        raise ToolError(
            f"Unknown search provider {selected!r}. Supported: 'ddg', 'brave', 'tavily'."
        )

    return {
        "ok": True,
        "provider": selected,
        "query": text,
        "results": results,
        "count": len(results),
    }


@mcp.resource("web://providers")
def search_providers() -> dict[str, Any]:
    """The active + available web-search providers and current fetch limits."""
    return {
        "active_provider": settings.search_provider,
        "available_providers": ["ddg", "brave", "tavily"],
        "keyless_default": "ddg",
        "max_bytes": settings.max_bytes,
        "allow_private_hosts": settings.allow_private_hosts,
    }


@mcp.prompt()
def research_web(topic: str) -> list[Message]:
    """Guided search then fetch workflow for researching a topic on the web."""
    return [
        Message(
            f"Research '{topic}' on the web. Use search to find the most relevant pages, "
            "then fetch the top results (to_file=True for long pages so raw content stays "
            "out of context) and synthesize the findings, citing each source URL."
        )
    ]


def main() -> None:
    """Main entry point for the web MCP server."""
    import argparse

    parser = argparse.ArgumentParser(description="Web MCP Server")
    parser.add_argument("--transport", choices=["stdio", "http"], default=None)
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--port", type=int, default=8000)
    args = parser.parse_args()
    transport = args.transport or os.getenv("MCP_TRANSPORT", "stdio")
    if transport == "http":
        mcp.run(transport="http", host=args.host, port=args.port)
    else:
        mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
