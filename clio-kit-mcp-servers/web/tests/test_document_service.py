"""Document-service and DOI behavior through the real MCP tool contract."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import httpx
import pytest
from fastmcp import Client, FastMCP
from fastmcp.exceptions import ToolError
from pytest_httpx import HTTPXMock

from web_mcp.document_service import convert_document, resolve_doi, service_endpoint
from web_mcp.server import Settings, create_mcp

from .helpers import parse_result

_SERVICE = "http://clio-search.test:8080"
_PDF = b"%PDF-1.7\nstructured test"


def _document_mcp(tmp_path: Path) -> FastMCP:
    return create_mcp(
        Settings(
            search_provider="ddg",
            document_service_url=_SERVICE,
            artifacts_root=str(tmp_path),
            conversion_poll_s=0.1,
        )
    )


@pytest.mark.asyncio
async def test_fetch_pdf_returns_structured_conversion(
    httpx_mock: HTTPXMock, tmp_path: Path
) -> None:
    """A detected PDF is automatically routed through CLIO Search."""

    source = "https://papers.test/work.pdf"
    httpx_mock.add_response(url=source, content=_PDF, headers={"content-type": "application/pdf"})
    httpx_mock.add_response(
        method="POST",
        url=f"{_SERVICE}/v1/documents",
        json={
            "id": "job-1",
            "status": "complete",
            "result": {
                "markdown": "# Parsed paper",
                "document": {
                    "profile": "scholarly",
                    "metadata": {"title": "Parsed paper"},
                    "references": [{"title": "Prior work"}],
                    "citation_contexts": [],
                    "structure": {"texts": [{"text": "Parsed paper"}], "tables": []},
                },
            },
        },
    )

    async with Client(_document_mcp(tmp_path)) as client:
        result = await client.call_tool("fetch", {"target": source})
    data = parse_result(result)

    assert data["method"] == "clio-search"
    assert data["content"] == "# Parsed paper"
    assert data["document"]["profile"] == "scholarly"
    assert "structure" not in data["document"]
    assert data["document"]["structure_available"] is True
    assert data["document"]["structure_summary"] == {"tables": 0, "texts": 1}
    assert data["conversion_id"] == "job-1"


@pytest.mark.asyncio
async def test_fetch_pdf_to_file_writes_markdown_and_metadata(
    httpx_mock: HTTPXMock, tmp_path: Path
) -> None:
    """Structured output writes Markdown plus a JSON metadata companion."""

    source = "https://papers.test/work.pdf"
    document = {
        "profile": "general",
        "metadata": {},
        "references": [],
        "structure": {"texts": [{"text": "converted"}]},
    }
    httpx_mock.add_response(url=source, content=_PDF, headers={"content-type": "application/pdf"})
    httpx_mock.add_response(
        method="POST",
        url=f"{_SERVICE}/v1/documents",
        json={
            "id": "job-2",
            "status": "complete",
            "result": {"markdown": "converted", "document": document},
        },
    )

    async with Client(_document_mcp(tmp_path)) as client:
        result = await client.call_tool("fetch", {"target": source, "to_file": True})
    data = parse_result(result)

    assert Path(data["local_path"]).read_text(encoding="utf-8") == "converted"
    assert json.loads(Path(data["metadata_path"]).read_text(encoding="utf-8")) == document
    assert data["structure_saved_to"] == data["metadata_path"]
    assert "structure" not in data["document"]


@pytest.mark.asyncio
async def test_fetch_doi_resolves_then_downloads_candidate(
    httpx_mock: HTTPXMock, tmp_path: Path
) -> None:
    """Bare DOI fetch uses CLIO Search metadata and lawful candidate ordering."""

    doi = "10.1234/example"
    landing = "https://repository.test/article"
    httpx_mock.add_response(
        method="POST",
        url=f"{_SERVICE}/v1/doi/resolve",
        json={
            "doi": doi,
            "metadata": {"title": "Example"},
            "candidates": [{"url": landing, "source": "unpaywall"}],
            "sources_queried": ["crossref", "unpaywall"],
            "warnings": [],
        },
    )
    httpx_mock.add_response(
        url=landing,
        content=b"open copy",
        headers={"content-type": "text/plain"},
    )

    async with Client(_document_mcp(tmp_path)) as client:
        result = await client.call_tool("fetch", {"target": doi})
    data = parse_result(result)

    assert data["doi"] == doi
    assert data["url"] == landing
    assert data["content"] == "open copy"
    assert data["doi_resolution"]["sources_queried"] == ["crossref", "unpaywall"]


@pytest.mark.asyncio
async def test_fetch_doi_url_uses_same_resolution_contract(
    httpx_mock: HTTPXMock, tmp_path: Path
) -> None:
    """A doi.org URL is semantic DOI input rather than an ordinary landing-page URL."""

    doi = "10.1234/example"
    landing = "https://repository.test/article"
    httpx_mock.add_response(
        method="POST",
        url=f"{_SERVICE}/v1/doi/resolve",
        json={
            "doi": doi,
            "metadata": {},
            "candidates": [{"url": landing, "source": "datacite"}],
            "sources_queried": ["crossref", "datacite"],
            "warnings": [],
        },
    )
    httpx_mock.add_response(
        url=landing,
        content=b"resolved",
        headers={"content-type": "text/plain"},
    )

    async with Client(_document_mcp(tmp_path)) as client:
        result = await client.call_tool("fetch", {"target": f"https://doi.org/{doi}"})

    assert parse_result(result)["doi"] == doi


@pytest.mark.asyncio
async def test_fetch_document_waits_for_terminal_backend_state(
    httpx_mock: HTTPXMock, tmp_path: Path
) -> None:
    """A long conversion remains a live MCP task until the backend completes."""

    source = "https://papers.test/work.pdf"
    httpx_mock.add_response(url=source, content=_PDF, headers={"content-type": "application/pdf"})
    httpx_mock.add_response(
        method="POST",
        url=f"{_SERVICE}/v1/documents",
        status_code=202,
        json={"id": "job-pending", "status": "queued", "retry_after_s": 2},
    )
    httpx_mock.add_response(
        method="GET",
        url=(f"{_SERVICE}/v1/documents/job-pending/events?after_sequence=0&limit=100"),
        json={
            "events": [
                {
                    "sequence": 1,
                    "progress": 45,
                    "stage": "layout",
                    "level": "info",
                    "message": "Reading page layout",
                }
            ]
        },
    )
    httpx_mock.add_response(
        method="GET",
        url=f"{_SERVICE}/v1/documents/job-pending",
        json={
            "id": "job-pending",
            "status": "complete",
            "result": {"markdown": "# Finished", "document": {"profile": "general"}},
        },
    )

    async with Client(_document_mcp(tmp_path)) as client:
        result = await client.call_tool("fetch", {"target": source})
    data = parse_result(result)

    assert data["content"] == "# Finished"
    assert data["conversion_id"] == "job-pending"


@pytest.mark.parametrize(
    ("address", "message"),
    [
        ("not-a-url", "absolute CLIO Web Search address"),
        ("https://search.test/?tenant=x", "query or fragment"),
    ],
)
def test_service_endpoint_rejects_ambiguous_addresses(address: str, message: str) -> None:
    """Document-service configuration is validated before any request is sent."""

    with pytest.raises(ToolError, match=message):
        service_endpoint(address, "/v1/documents")


@pytest.mark.asyncio
async def test_resolve_doi_rejects_malformed_service_payload(httpx_mock: HTTPXMock) -> None:
    """A successful HTTP response still must satisfy the DOI response contract."""

    httpx_mock.add_response(
        method="POST",
        url=f"{_SERVICE}/v1/doi/resolve",
        json={"doi": "10.1234/example", "candidates": "not-a-list"},
    )
    with pytest.raises(ToolError, match="malformed DOI-resolution data"):
        await resolve_doi(
            "10.1234/example",
            service_url=_SERVICE,
            timeout=httpx.Timeout(2),
        )


@pytest.mark.asyncio
async def test_resolve_doi_wraps_service_failure(httpx_mock: HTTPXMock) -> None:
    """DOI service transport failures identify the failing endpoint."""

    httpx_mock.add_exception(
        httpx.ConnectError("offline"),
        method="POST",
        url=f"{_SERVICE}/v1/doi/resolve",
    )
    with pytest.raises(
        ToolError,
        match="Fetch failed during DOI resolution.*Retryable: yes.*Fix:",
    ):
        await resolve_doi(
            "10.1234/example",
            service_url=_SERVICE,
            timeout=httpx.Timeout(2),
        )


@pytest.mark.asyncio
async def test_convert_document_polls_and_sends_doi(httpx_mock: HTTPXMock) -> None:
    """Queued conversion is polled to completion and preserves DOI provenance."""

    httpx_mock.add_response(
        method="POST",
        url=f"{_SERVICE}/v1/documents",
        status_code=202,
        json={"id": "poll-1", "status": "queued"},
    )
    httpx_mock.add_response(
        method="GET",
        url=f"{_SERVICE}/v1/documents/poll-1/events?after_sequence=0&limit=100",
        json={
            "events": [
                {
                    "sequence": 1,
                    "progress": 80,
                    "stage": "serialize",
                    "level": "info",
                    "message": "Writing Markdown",
                }
            ]
        },
    )
    httpx_mock.add_response(
        method="GET",
        url=f"{_SERVICE}/v1/documents/poll-1",
        json={"id": "poll-1", "status": "complete", "result": {"markdown": "done"}},
    )
    progress: list[dict[str, Any]] = []

    async def report(event: dict[str, Any]) -> None:
        progress.append(event)

    payload = await convert_document(
        _PDF,
        filename="paper.pdf",
        content_type="application/pdf",
        source_url="https://papers.test/paper.pdf",
        doi="10.1234/example",
        service_url=_SERVICE,
        timeout=httpx.Timeout(2),
        poll_s=0,
        on_progress=report,
    )

    assert payload["status"] == "complete"
    request_body = httpx_mock.get_requests()[0].content
    assert b"10.1234/example" in request_body
    assert [event["stage"] for event in progress] == ["queued", "serialize"]


@pytest.mark.asyncio
async def test_convert_document_rejects_malformed_submission(httpx_mock: HTTPXMock) -> None:
    """A document submission without a durable id is rejected."""

    httpx_mock.add_response(
        method="POST",
        url=f"{_SERVICE}/v1/documents",
        json={"status": "queued"},
    )

    async def report(_event: dict[str, Any]) -> None:
        return None

    with pytest.raises(ToolError, match="without returning a conversion ID"):
        await convert_document(
            _PDF,
            filename="paper.pdf",
            content_type="application/pdf",
            source_url="https://papers.test/paper.pdf",
            doi=None,
            service_url=_SERVICE,
            timeout=httpx.Timeout(2),
            poll_s=0,
            on_progress=report,
        )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("error", "message"),
    [
        ({"message": "parser unavailable."}, "parser unavailable"),
        (None, "without structured diagnostics"),
    ],
)
async def test_convert_document_surfaces_typed_failure(
    httpx_mock: HTTPXMock, error: object, message: str
) -> None:
    """Failed conversion returns the service's reason without hiding it."""

    httpx_mock.add_response(
        method="POST",
        url=f"{_SERVICE}/v1/documents",
        json={"id": "failed-1", "status": "failed", "error": error},
    )

    async def report(_event: dict[str, Any]) -> None:
        return None

    with pytest.raises(ToolError, match=message) as captured:
        await convert_document(
            _PDF,
            filename="paper.pdf",
            content_type="application/pdf",
            source_url="https://papers.test/paper.pdf",
            doi=None,
            service_url=_SERVICE,
            timeout=httpx.Timeout(2),
            poll_s=0,
            on_progress=report,
        )
    assert ".." not in str(captured.value)
