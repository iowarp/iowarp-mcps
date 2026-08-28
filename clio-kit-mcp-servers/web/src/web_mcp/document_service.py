"""Typed client for CLIO Web Search DOI and document-conversion APIs."""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from pathlib import Path
from typing import Any, cast
from urllib.parse import urlparse

import httpx
from fastmcp.exceptions import ToolError

ProgressReporter = Callable[[dict[str, Any]], Awaitable[None]]

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
    """Build a validated CLIO Web Search endpoint URL."""

    base = (value or "").strip()
    parsed = urlparse(base)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        raise ToolError(
            "Document enrichment requires an absolute CLIO Web Search address. "
            "Set --remote-url, --document-address, or WEB_REMOTE_URL."
        )
    if parsed.query or parsed.fragment:
        raise ToolError("The CLIO Web Search address must not contain a query or fragment.")
    return f"{base.rstrip('/')}{path}"


def is_convertible_document(body: bytes, content_type: str | None, url: str) -> bool:
    """Return whether CLIO Web Search can structure the fetched content."""

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
    token: str | None = None,
) -> dict[str, Any]:
    """Resolve a DOI through the configured CLIO Web Search installation."""

    endpoint = service_endpoint(service_url, "/v1/doi/resolve")
    try:
        async with _client(timeout, token) as client:
            response = await client.post(endpoint, json={"doi": doi})
            payload = _response_payload(response, stage="DOI resolution")
    except ToolError:
        raise
    except httpx.HTTPError as exc:
        raise _network_error("DOI resolution", endpoint, exc) from exc
    if not isinstance(payload.get("candidates"), list):
        raise ToolError(
            "CLIO Web Search returned malformed DOI-resolution data. "
            "Fix: upgrade or repair the remote service before retrying."
        )
    return payload


async def convert_document(
    body: bytes,
    *,
    filename: str,
    content_type: str | None,
    source_url: str,
    doi: str | None,
    service_url: str | None,
    timeout: httpx.Timeout,
    poll_s: float,
    on_progress: ProgressReporter,
    token: str | None = None,
) -> dict[str, Any]:
    """Convert a document to terminal state without an overall elapsed timeout."""

    submit_url = service_endpoint(service_url, "/v1/documents")
    fields = {"source_url": source_url}
    if doi:
        fields["doi"] = doi
    conversion_id: str | None = None
    try:
        async with _client(timeout, token) as client:
            response = await client.post(
                submit_url,
                data=fields,
                files={"file": (filename, body, content_type or "application/octet-stream")},
            )
            payload = _response_payload(response, stage="document submission")
            conversion_id = _conversion_id(payload)
            await on_progress(
                {
                    "sequence": 0,
                    "progress": int(payload.get("progress", 0)),
                    "stage": str(payload.get("stage") or "queued"),
                    "level": "info",
                    "message": str(payload.get("message") or "Conversion accepted"),
                    "conversion_id": conversion_id,
                }
            )
            after_sequence = 0
            while payload.get("status") in {"queued", "running"}:
                await asyncio.sleep(max(poll_s, 0.1))
                events_response = await client.get(
                    f"{submit_url}/{conversion_id}/events",
                    params={"after_sequence": after_sequence, "limit": 100},
                )
                events_payload = _response_payload(
                    events_response,
                    stage="conversion progress",
                    conversion_id=conversion_id,
                )
                events = events_payload.get("events")
                emitted = False
                if isinstance(events, list):
                    for event in events:
                        if not isinstance(event, dict):
                            continue
                        event["conversion_id"] = conversion_id
                        await on_progress(cast(dict[str, Any], event))
                        after_sequence = max(after_sequence, int(event.get("sequence", 0)))
                        emitted = True
                state_response = await client.get(f"{submit_url}/{conversion_id}")
                payload = _response_payload(
                    state_response,
                    stage="conversion status",
                    conversion_id=conversion_id,
                )
                if not emitted and payload.get("status") in {"queued", "running"}:
                    await on_progress(
                        {
                            "sequence": after_sequence,
                            "progress": int(payload.get("progress", 0)),
                            "stage": str(payload.get("stage") or payload["status"]),
                            "level": "info",
                            "message": str(
                                payload.get("message") or "Document conversion is still running"
                            ),
                            "conversion_id": conversion_id,
                        }
                    )
    except asyncio.CancelledError:
        if conversion_id is not None:
            await asyncio.shield(
                cancel_document(
                    conversion_id,
                    service_url=service_url,
                    timeout=timeout,
                    token=token,
                )
            )
        raise
    except ToolError:
        raise
    except httpx.HTTPError as exc:
        raise _network_error(
            "document conversion", submit_url, exc, conversion_id=conversion_id
        ) from exc
    if payload.get("status") == "failed":
        raise ToolError(_conversion_failure(payload, conversion_id))
    if payload.get("status") == "cancelled":
        raise asyncio.CancelledError
    if payload.get("status") != "complete":
        raise ToolError(
            _agent_message(
                stage="conversion status",
                cause=f"the backend returned unexpected state {payload.get('status')!r}",
                remediation="Query fetch_events, then retry the fetch if the backend is healthy.",
                retryable=True,
                conversion_id=conversion_id,
            )
        )
    return payload


async def fetch_events(
    conversion_id: str,
    *,
    service_url: str | None,
    timeout: httpx.Timeout,
    after_sequence: int = 0,
    limit: int = 100,
    token: str | None = None,
) -> dict[str, Any]:
    """Return one ordered page of persistent backend conversion events."""

    endpoint = service_endpoint(service_url, f"/v1/documents/{conversion_id}/events")
    try:
        async with _client(timeout, token) as client:
            response = await client.get(
                endpoint,
                params={"after_sequence": after_sequence, "limit": limit},
            )
            return _response_payload(
                response, stage="conversion event lookup", conversion_id=conversion_id
            )
    except ToolError:
        raise
    except httpx.HTTPError as exc:
        raise _network_error(
            "conversion event lookup", endpoint, exc, conversion_id=conversion_id
        ) from exc


async def cancel_document(
    conversion_id: str,
    *,
    service_url: str | None,
    timeout: httpx.Timeout,
    token: str | None = None,
) -> dict[str, Any]:
    """Cancel a backend conversion and return its durable state."""

    endpoint = service_endpoint(service_url, f"/v1/documents/{conversion_id}/cancel")
    try:
        async with _client(timeout, token) as client:
            response = await client.post(endpoint)
            return _response_payload(
                response, stage="conversion cancellation", conversion_id=conversion_id
            )
    except ToolError:
        raise
    except httpx.HTTPError as exc:
        raise _network_error(
            "conversion cancellation", endpoint, exc, conversion_id=conversion_id
        ) from exc


def _client(timeout: httpx.Timeout, token: str | None) -> httpx.AsyncClient:
    headers = {"Authorization": f"Bearer {token}"} if token else None
    return httpx.AsyncClient(timeout=timeout, headers=headers)


def _response_payload(
    response: httpx.Response,
    *,
    stage: str,
    conversion_id: str | None = None,
) -> dict[str, Any]:
    try:
        payload = response.json()
    except ValueError as exc:
        raise ToolError(
            _agent_message(
                stage=stage,
                cause=f"the service returned non-JSON HTTP {response.status_code}",
                remediation="Check that --remote-url points to CLIO Web Search 0.3.0 or newer.",
                retryable=False,
                conversion_id=conversion_id,
            )
        ) from exc
    if not isinstance(payload, dict):
        raise ToolError(
            _agent_message(
                stage=stage,
                cause="the service returned a malformed response object",
                remediation="Upgrade or repair the CLIO Web Search service.",
                retryable=False,
                conversion_id=conversion_id,
            )
        )
    typed = cast(dict[str, Any], payload)
    if response.is_error:
        raise ToolError(_service_failure(typed, response.status_code, stage, conversion_id))
    return typed


def _service_failure(
    payload: dict[str, Any],
    status_code: int,
    stage: str,
    conversion_id: str | None,
) -> str:
    message = payload.get("message")
    remediation = payload.get("remediation")
    retryable = bool(payload.get("retryable"))
    return _agent_message(
        stage=str(payload.get("stage") or stage),
        cause=str(message or f"the service returned HTTP {status_code}"),
        remediation=str(remediation or "Check service readiness and retry."),
        retryable=retryable,
        conversion_id=str(payload.get("conversion_id") or conversion_id or "") or None,
    )


def _conversion_failure(payload: dict[str, Any], conversion_id: str | None) -> str:
    error = payload.get("error")
    if not isinstance(error, dict):
        return _agent_message(
            stage=str(payload.get("stage") or "conversion"),
            cause="the document pipeline failed without structured diagnostics",
            remediation="Query fetch_events and inspect the service log before retrying.",
            retryable=True,
            conversion_id=conversion_id,
        )
    return _agent_message(
        stage=str(error.get("stage") or payload.get("stage") or "conversion"),
        cause=str(error.get("message") or "the document pipeline failed"),
        remediation=str(error.get("remediation") or "Query fetch_events before retrying."),
        retryable=bool(error.get("retryable")),
        conversion_id=str(error.get("conversion_id") or conversion_id or "") or None,
    )


def _network_error(
    stage: str,
    endpoint: str,
    exc: httpx.HTTPError,
    *,
    conversion_id: str | None = None,
) -> ToolError:
    return ToolError(
        _agent_message(
            stage=stage,
            cause=f"{type(exc).__name__} while contacting {urlparse(endpoint).netloc}",
            remediation="Verify network access and service readiness, then retry.",
            retryable=True,
            conversion_id=conversion_id,
        )
    )


def _agent_message(
    *,
    stage: str,
    cause: str,
    remediation: str,
    retryable: bool,
    conversion_id: str | None,
) -> str:
    identity = f" Conversion ID: {conversion_id}." if conversion_id else ""
    normalized_cause = cause.strip()
    cause_suffix = "" if normalized_cause.endswith((".", "!", "?")) else "."
    return (
        f"Fetch failed during {stage}. Cause: {normalized_cause}{cause_suffix}{identity} "
        f"Retryable: {'yes' if retryable else 'no'}. Fix: {remediation}"
    )


def _conversion_id(payload: dict[str, Any]) -> str:
    value = payload.get("id")
    if not isinstance(value, str) or not value:
        raise ToolError(
            "CLIO Web Search accepted a document without returning a conversion ID. "
            "Fix: upgrade or repair the remote service before retrying."
        )
    return value
