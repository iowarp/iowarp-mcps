"""Fetch orchestration for URLs, DOI resolution, and document conversion."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import httpx
from fastmcp.exceptions import ToolError
from fastmcp.server.context import Context

from web_mcp.config import Settings
from web_mcp.document_service import (
    convert_document,
    is_convertible_document,
    resolve_doi,
)
from web_mcp.document_service import (
    fetch_events as fetch_conversion_events,
)
from web_mcp.fetch_utils import (
    assert_allowed_url,
    decode,
    derive_filename,
    download,
    extract_title,
    html_to_markdown,
    is_html,
    is_text,
    looks_like_text,
    split_content_type,
    validate_output_path,
)

REASON_JS_RENDER_REQUIRED = "js_render_required_browser_unavailable"
REASON_BINARY_NOT_INLINED = "binary_content_not_inlined"


async def fetch_target(
    configured: Settings,
    ctx: Context,
    target: str,
    *,
    to_file: bool = False,
    output_dir: str | None = None,
    max_bytes: int | None = None,
    timeout: float | None = None,
) -> dict[str, Any]:
    """Fetch one URL or DOI and return content or a saved artifact."""

    requested_target = (target or "").strip()
    if not requested_target:
        raise ToolError("fetch requires a non-empty URL or DOI target.")

    cap = max_bytes if max_bytes and max_bytes > 0 else configured.max_bytes
    read_timeout = timeout if timeout and timeout > 0 else configured.read_timeout_s
    timeout_cfg = httpx.Timeout(read_timeout, connect=configured.connect_timeout_s)
    await ctx.report_progress(1, 100, "Validating the fetch target")

    doi: str | None = None
    doi_resolution: dict[str, Any] | None = None
    download_targets: list[str]
    parsed_target = urlparse(requested_target)
    is_doi_url = (
        parsed_target.scheme in {"http", "https"}
        and (parsed_target.hostname or "").lower() in {"doi.org", "dx.doi.org"}
        and bool(parsed_target.path.strip("/"))
    )
    if is_doi_url or not requested_target.lower().startswith(("http://", "https://")):
        if "://" in requested_target and not is_doi_url:
            raise ToolError(
                f"fetch only supports http(s) URLs or DOI targets; got: {requested_target!r}"
            )
        doi = parsed_target.path.strip("/") if is_doi_url else requested_target
        doi_resolution = await resolve_doi(
            doi,
            service_url=configured.effective_document_service_url,
            timeout=timeout_cfg,
            token=configured.remote_token,
        )
        doi = str(doi_resolution["doi"])
        download_targets = [
            str(candidate["url"])
            for candidate in doi_resolution["candidates"]
            if isinstance(candidate, dict) and candidate.get("url")
        ]
        if not download_targets:
            raise ToolError(f"CLIO Search found no lawful retrieval candidate for DOI {doi}.")
    else:
        download_targets = [requested_target]

    download_target = ""
    failures: list[str] = []
    for candidate in download_targets:
        assert_allowed_url(candidate, allow_private_hosts=configured.allow_private_hosts)
        try:
            await ctx.report_progress(5, 100, f"Downloading {candidate}")
            body, raw_content_type, status, final_url = await download(
                candidate,
                max_bytes=cap,
                max_document_bytes=configured.max_document_bytes,
                timeout=timeout_cfg,
                allow_private_hosts=configured.allow_private_hosts,
            )
            download_target = candidate
            break
        except (ToolError, httpx.HTTPError) as exc:
            failures.append(f"{candidate}: {exc}")
    else:
        raise ToolError(f"Could not fetch {requested_target}: {'; '.join(failures)}")

    size_bytes = len(body)
    mime, charset = split_content_type(raw_content_type)
    is_html_content = is_html(mime)
    is_text_content = is_text(mime) or is_html_content or (mime == "" and looks_like_text(body))
    is_binary = not is_text_content
    result: dict[str, Any] = {
        "ok": True,
        "target": requested_target,
        "url": download_target,
        "size_bytes": size_bytes,
        "content_type": raw_content_type,
        "status": status,
        "title": None,
        "method": "http",
    }
    if doi_resolution is not None:
        result["doi"] = doi
        result["doi_resolution"] = doi_resolution
    if final_url and final_url != download_target:
        result["final_url"] = final_url

    content: str | None
    if is_html_content:
        html = decode(body, charset)
        result["title"] = extract_title(html)
        content, extractor = html_to_markdown(html)
        result["extractor"] = extractor
        if content is None:
            result["content"] = None
            result["reason"] = REASON_JS_RENDER_REQUIRED
            result["note"] = (
                "HTML extraction yielded no content; the page likely requires a "
                "JavaScript-capable headless browser, which is not available in v1."
            )
            return result
    elif (
        is_binary
        and configured.effective_document_service_url
        and is_convertible_document(body, raw_content_type, final_url)
    ):
        return await _convert_result(
            configured,
            ctx,
            result,
            body=body,
            raw_content_type=raw_content_type,
            final_url=final_url,
            doi=doi,
            timeout_cfg=timeout_cfg,
            to_file=to_file,
            output_dir=output_dir,
        )
    elif is_binary:
        if not to_file:
            result["content"] = None
            result["reason"] = REASON_BINARY_NOT_INLINED
            result["note"] = (
                "Binary content is not inlined. Re-call fetch with to_file=True to "
                "save it to a local file."
            )
            return result
        content = None
    else:
        content = decode(body, charset)

    if to_file:
        filename = derive_filename(final_url, is_html=is_html_content, is_binary=is_binary)
        output_path = _output_path(
            configured,
            filename,
            default_name="page",
            output_dir=output_dir,
        )
        if is_binary:
            output_path.write_bytes(body)
        else:
            output_path.write_text(content or "", encoding="utf-8")
        result["local_path"] = str(output_path)
    else:
        result["content"] = content
    return result


async def fetch_event_log(
    configured: Settings,
    conversion_id: str,
    *,
    after_sequence: int = 0,
    limit: int = 100,
) -> dict[str, Any]:
    """Return one ordered page from a backend conversion's durable event log."""

    timeout_cfg = httpx.Timeout(configured.read_timeout_s, connect=configured.connect_timeout_s)
    return await fetch_conversion_events(
        conversion_id,
        service_url=configured.effective_document_service_url,
        timeout=timeout_cfg,
        after_sequence=after_sequence,
        limit=limit,
        token=configured.remote_token,
    )


async def _convert_result(
    configured: Settings,
    ctx: Context,
    result: dict[str, Any],
    *,
    body: bytes,
    raw_content_type: str | None,
    final_url: str,
    doi: str | None,
    timeout_cfg: httpx.Timeout,
    to_file: bool,
    output_dir: str | None,
) -> dict[str, Any]:
    filename = derive_filename(final_url, is_html=False, is_binary=True)

    async def report_conversion(event: dict[str, Any]) -> None:
        conversion_id = str(event.get("conversion_id") or "pending")
        stage = str(event.get("stage") or "conversion")
        message = str(event.get("message") or "Document conversion is running")
        await ctx.report_progress(
            float(event.get("progress", 0)),
            100,
            f"Conversion {conversion_id} [{stage}]: {message}",
        )

    conversion = await convert_document(
        body,
        filename=filename,
        content_type=raw_content_type,
        source_url=final_url,
        doi=doi,
        service_url=configured.effective_document_service_url,
        timeout=timeout_cfg,
        poll_s=configured.conversion_poll_s,
        on_progress=report_conversion,
        token=configured.remote_token,
    )
    converted = conversion.get("result")
    if not isinstance(converted, dict):
        raise ToolError("CLIO Search completed conversion without a result payload.")
    content = str(converted.get("markdown") or "")
    result["method"] = "clio-search"
    result["extractor"] = "document-service"
    document = converted.get("document")
    if isinstance(document, dict):
        inline_document = dict(document)
        structure = inline_document.pop("structure", None)
        if structure is not None:
            inline_document["structure_available"] = True
            if isinstance(structure, dict):
                inline_document["structure_summary"] = {
                    key: len(value)
                    for key, value in structure.items()
                    if isinstance(value, (dict, list))
                }
        result["document"] = inline_document
    else:
        result["document"] = document
    result["conversion_id"] = conversion.get("id")
    if to_file:
        output_path = _output_path(
            configured,
            f"{Path(filename).stem}.md",
            default_name="document.md",
            output_dir=output_dir,
        )
        output_path.write_text(content, encoding="utf-8")
        metadata_path = output_path.with_suffix(".json")
        metadata_path.write_text(
            json.dumps(document, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        result["local_path"] = str(output_path)
        result["metadata_path"] = str(metadata_path)
        if isinstance(document, dict) and "structure" in document:
            result["structure_saved_to"] = str(metadata_path)
        return result
    result["content"] = content
    return result


def _output_path(
    configured: Settings,
    candidate: str | Path,
    *,
    default_name: str,
    output_dir: str | Path | None,
) -> Path:
    return validate_output_path(
        candidate,
        default_name=default_name,
        output_dir=output_dir,
        configured_root=configured.artifacts_root,
    )
