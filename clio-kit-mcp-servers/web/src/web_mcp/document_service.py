"""Client for an optional CLIO Search document-enrichment service."""

from __future__ import annotations

import asyncio
import time
from pathlib import Path
from typing import Any, cast
from urllib.parse import urlparse

import httpx
from fastmcp.exceptions import ToolError

_CONVERTIBLE_SUFFIXES = {
    ".pdf",
    ".docx",
    ".pptx",
    ".xlsx",
    ".xml",
    ".png",
    ".jpg",
    ".jpeg",
    ".tif",
    ".tiff",
    ".bmp",
    ".webp",
}
_CONVERTIBLE_MIMES = {
    "application/pdf",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "application/vnd.openxmlformats-officedocument.presentationml.presentation",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "application/xml",
    "text/xml",
}


def service_endpoint(value: str | None, path: str) -> str:
    """Build a validated CLIO Search endpoint URL."""

    base = (value or "").strip()
    parsed = urlparse(base)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        raise ToolError(
            "Document enrichment requires an absolute CLIO Search address. "
            "Set --document-address or WEB_DOCUMENT_SERVICE_URL."
        )
    if parsed.query or parsed.fragment:
        raise ToolError("The CLIO Search address must not contain a query or fragment.")
    return f"{base.rstrip('/')}{path}"


def is_convertible_document(body: bytes, content_type: str | None, url: str) -> bool:
    """Return whether CLIO Search can structure the fetched content."""

    mime = (content_type or "").split(";", 1)[0].strip().lower()
    suffix = Path(urlparse(url).path).suffix.lower()
    return (
        body.startswith(b"%PDF-")
        or mime in _CONVERTIBLE_MIMES
        or mime.startswith("image/")
        or suffix in _CONVERTIBLE_SUFFIXES
    )


def likely_convertible_url(content_type: str | None, url: str) -> bool:
    """Classify a response before its body has been downloaded."""

    return is_convertible_document(b"", content_type, url)


async def resolve_doi(
    doi: str,
    *,
    service_url: str | None,
    timeout: httpx.Timeout,
) -> dict[str, Any]:
    """Resolve a DOI through the configured CLIO Search installation."""

    endpoint = service_endpoint(service_url, "/v1/doi/resolve")
    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.post(endpoint, json={"doi": doi})
            response.raise_for_status()
            payload = response.json()
    except (httpx.HTTPError, ValueError) as exc:
        raise ToolError(f"Could not resolve DOI through CLIO Search at {endpoint}: {exc}") from exc
    if not isinstance(payload, dict) or not isinstance(payload.get("candidates"), list):
        raise ToolError("CLIO Search returned a malformed DOI-resolution response.")
    return cast(dict[str, Any], payload)


async def convert_document(
    body: bytes,
    *,
    filename: str,
    content_type: str | None,
    source_url: str,
    doi: str | None,
    service_url: str | None,
    timeout: httpx.Timeout,
    wait_s: float,
    poll_s: float,
) -> dict[str, Any]:
    """Submit a document and return completion or a durable pending handle."""

    submit_url = service_endpoint(service_url, "/v1/documents")
    fields = {"source_url": source_url}
    if doi:
        fields["doi"] = doi
    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.post(
                submit_url,
                data=fields,
                files={"file": (filename, body, content_type or "application/octet-stream")},
            )
            response.raise_for_status()
            payload = response.json()
            if not isinstance(payload, dict) or not payload.get("id"):
                raise ToolError("CLIO Search returned a malformed document submission.")
            deadline = time.monotonic() + max(wait_s, 0)
            while payload.get("status") in {"queued", "running"} and time.monotonic() < deadline:
                await asyncio.sleep(max(poll_s, 0.1))
                response = await client.get(f"{submit_url}/{payload['id']}")
                response.raise_for_status()
                payload = response.json()
    except ToolError:
        raise
    except (httpx.HTTPError, ValueError) as exc:
        raise ToolError(f"Could not convert document through CLIO Search: {exc}") from exc
    if payload.get("status") == "failed":
        error = payload.get("error")
        message = error.get("message") if isinstance(error, dict) else error
        raise ToolError(f"CLIO Search document conversion failed: {message or 'unknown error'}")
    return cast(dict[str, Any], payload)
