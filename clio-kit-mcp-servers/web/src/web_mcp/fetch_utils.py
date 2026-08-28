"""Low-level download, content detection, and artifact helpers for Web MCP."""

from __future__ import annotations

import ipaddress
import re
from pathlib import Path
from urllib.parse import urlparse

import httpx
import trafilatura
from fastmcp.exceptions import ToolError
from readability import Document as ReadabilityDocument

from web_mcp.document_service import likely_convertible_url

REASON_BLOCKED_HOST = "blocked_private_host"

_MAX_REDIRECTS = 5
_LOCAL_HOSTNAMES = {"localhost", "localhost.localdomain", "ip6-localhost", "ip6-loopback"}
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
_TAG_RE = re.compile(r"<[^>]+>")
_TITLE_RE = re.compile(r"<title[^>]*>(.*?)</title>", re.IGNORECASE | re.DOTALL)
_WS_RE = re.compile(r"[ \t\r\f\v]+")
_BLANKLINES_RE = re.compile(r"\n{3,}")


def artifacts_root(
    output_dir: str | Path | None = None, *, configured_root: str | None = None
) -> Path:
    """Return and create the configured writable artifact root."""
    explicit = str(output_dir).strip() if output_dir not in (None, "") else ""
    configured = (configured_root or "").strip()
    root = Path(explicit or configured or Path.cwd()).expanduser()
    root.mkdir(parents=True, exist_ok=True)
    return root.resolve()


def validate_output_path(
    candidate: str | Path,
    *,
    default_name: str,
    output_dir: str | Path | None = None,
    configured_root: str | None = None,
) -> Path:
    """Resolve a write path while confining it to the artifact root."""
    root = artifacts_root(output_dir, configured_root=configured_root)
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


def derive_filename(url: str, *, is_html: bool, is_binary: bool) -> str:
    """Derive a safe output filename from a URL and detected content kind."""
    parsed = urlparse(url)
    base = Path(parsed.path).name or parsed.netloc or "page"
    safe = _safe_filename(base, default="page")
    if is_html:
        return f"{Path(safe).stem or 'page'}.md"
    if is_binary:
        return safe
    return safe if "." in safe else f"{safe}.txt"


def split_content_type(content_type: str | None) -> tuple[str, str | None]:
    """Return the lowercased MIME type without params and its charset."""
    if not content_type:
        return "", None
    parts = [part.strip() for part in content_type.split(";")]
    charset: str | None = None
    for param in parts[1:]:
        if param.lower().startswith("charset="):
            charset = param.split("=", 1)[1].strip().strip('"') or None
    return parts[0].lower(), charset


def is_html(mime: str) -> bool:
    """Return whether the MIME type denotes HTML."""
    return mime in {"text/html", "application/xhtml+xml"} or mime.endswith("+html")


def is_text(mime: str) -> bool:
    """Return whether the MIME type denotes inline-able text."""
    if not mime:
        return False
    main, _, subtype = mime.partition("/")
    return main == "text" or subtype in _TEXT_SUBTYPES


def _strip_tags(html: str) -> str:
    """Collapse an HTML fragment to visible plain text."""
    without_head = re.sub(r"<head[^>]*>.*?</head>", " ", html, flags=re.IGNORECASE | re.DOTALL)
    without_script = re.sub(
        r"<(script|style)[^>]*>.*?</\1>",
        " ",
        without_head,
        flags=re.IGNORECASE | re.DOTALL,
    )
    text = _WS_RE.sub(" ", _TAG_RE.sub(" ", without_script))
    text = "\n".join(line.strip() for line in text.splitlines())
    return _BLANKLINES_RE.sub("\n\n", text).strip()


def extract_title(html: str) -> str | None:
    """Extract the document title when present."""
    match = _TITLE_RE.search(html)
    if not match:
        return None
    return _strip_tags(match.group(1)).strip() or None


def html_to_markdown(html: str) -> tuple[str | None, str | None]:
    """Convert HTML through named, quality-visible extraction fallbacks."""
    try:
        markdown = trafilatura.extract(
            html,
            output_format="markdown",
            include_links=True,
            favor_recall=True,
        )
    except Exception:  # noqa: BLE001 - parser failure advances to the explicit fallback
        markdown = None
    if markdown and markdown.strip():
        return markdown.strip(), "trafilatura"
    try:
        readable = _strip_tags(ReadabilityDocument(html).summary(html_partial=True))
    except Exception:  # noqa: BLE001 - parser failure advances to the explicit fallback
        readable = ""
    if readable.strip():
        return readable.strip(), "readability"
    stripped = _strip_tags(html)
    return (stripped, "plaintext") if stripped else (None, None)


def decode(body: bytes, charset: str | None) -> str:
    """Decode bytes using the advertised charset when valid, then UTF-8."""
    if charset:
        try:
            return body.decode(charset, errors="replace")
        except LookupError:
            pass
    return body.decode("utf-8", errors="replace")


def looks_like_text(body: bytes) -> bool:
    """Sniff content without a MIME type for likely UTF-8 text."""
    if not body:
        return True
    sample = body[:8192]
    if b"\x00" in sample:
        return False
    decoded = sample.decode("utf-8", errors="replace")
    return bool(decoded) and decoded.count("\ufffd") / len(decoded) < 0.05


def assert_allowed_url(url: str, *, allow_private_hosts: bool) -> None:
    """Reject local and non-routable literal targets unless explicitly allowed."""
    if allow_private_hosts:
        return
    host = (urlparse(url).hostname or "").strip().strip("[]").lower()
    blocked = not host or host in _LOCAL_HOSTNAMES or host.endswith(".localhost")
    if not blocked:
        try:
            ip = ipaddress.ip_address(host)
        except ValueError:
            ip = None
        blocked = bool(
            ip
            and (
                ip.is_loopback
                or ip.is_private
                or ip.is_link_local
                or ip.is_reserved
                or ip.is_multicast
                or ip.is_unspecified
            )
        )
    if blocked:
        raise ToolError(
            f"fetch blocked host {host!r}: refusing a loopback/private/link-local address "
            f"(reason={REASON_BLOCKED_HOST}). Set WEB_ALLOW_PRIVATE_HOSTS=true to permit "
            "internal fetches."
        )


async def download(
    url: str,
    *,
    max_bytes: int,
    max_document_bytes: int,
    timeout: httpx.Timeout,
    allow_private_hosts: bool,
) -> tuple[bytes, str | None, int, str]:
    """Stream a URL within size limits while validating every redirect hop."""
    async with httpx.AsyncClient(timeout=timeout, follow_redirects=False) as client:
        current = httpx.URL(url)
        for _hop in range(_MAX_REDIRECTS + 1):
            assert_allowed_url(str(current), allow_private_hosts=allow_private_hosts)
            async with client.stream("GET", current) as response:
                if response.is_redirect and "location" in response.headers:
                    current = current.join(response.headers["location"])
                    continue
                response.raise_for_status()
                content_type = response.headers.get("content-type")
                mime, _ = split_content_type(content_type)
                effective_cap = (
                    max_document_bytes
                    if likely_convertible_url(content_type, str(response.url))
                    or (mime and not is_html(mime) and not is_text(mime))
                    else max_bytes
                )
                content_length = response.headers.get("content-length")
                if content_length:
                    try:
                        advertised = int(content_length)
                    except ValueError:
                        advertised = 0
                    if advertised > effective_cap:
                        raise ToolError(
                            f"Resource is {advertised} bytes, which exceeds the fetch size "
                            f"limit of {effective_cap} bytes. Increase max_bytes intentionally "
                            "or select a smaller resource."
                        )
                chunks: list[bytes] = []
                total = 0
                async for chunk in response.aiter_bytes(chunk_size=64 * 1024):
                    if not chunk:
                        continue
                    total += len(chunk)
                    if total > effective_cap:
                        raise ToolError(
                            f"Resource exceeded the fetch size limit of {effective_cap} bytes "
                            "while downloading. Increase max_bytes intentionally or select "
                            "a smaller resource."
                        )
                    chunks.append(chunk)
                return b"".join(chunks), content_type, response.status_code, str(response.url)
    raise ToolError(f"fetch exceeded {_MAX_REDIRECTS} redirects for {url!r}.")
