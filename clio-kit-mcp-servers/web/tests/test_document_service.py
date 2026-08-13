"""Document-service and DOI behavior through the real MCP tool contract."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from fastmcp import Client, FastMCP
from pytest_httpx import HTTPXMock

from web_mcp.server import Settings, create_mcp

from .helpers import parse_result

_SERVICE = "http://clio-search.test:8080"
_PDF = b"%PDF-1.7\nstructured test"


def _document_mcp(tmp_path: Path, *, wait_s: float = 0) -> FastMCP:
    return create_mcp(
        Settings(
            search_provider="ddg",
            document_service_url=_SERVICE,
            artifacts_root=str(tmp_path),
            conversion_wait_s=wait_s,
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
async def test_fetch_document_returns_durable_pending_handle(
    httpx_mock: HTTPXMock, tmp_path: Path
) -> None:
    """A long conversion returns an honest retry handle rather than hiding work."""

    source = "https://papers.test/work.pdf"
    httpx_mock.add_response(url=source, content=_PDF, headers={"content-type": "application/pdf"})
    httpx_mock.add_response(
        method="POST",
        url=f"{_SERVICE}/v1/documents",
        status_code=202,
        json={"id": "job-pending", "status": "queued", "retry_after_s": 2},
    )

    async with Client(_document_mcp(tmp_path)) as client:
        result = await client.call_tool("fetch", {"target": source})
    data = parse_result(result)

    assert data["reason"] == "document_conversion_pending"
    assert data["conversion_id"] == "job-pending"
    assert data["retry_after_s"] == 2
