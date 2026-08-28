"""Deterministic wire-level checks for the MCP v2 fetch task lifecycle."""

from __future__ import annotations

import asyncio
from pathlib import Path

import httpx
import pytest
from fastmcp import Client, FastMCP
from fastmcp.exceptions import ToolError
from fastmcp_tasks.client import call_tool_task
from pytest_httpx import HTTPXMock

from web_mcp.server import Settings, create_mcp

from .helpers import parse_result

_SERVICE = "http://clio-search.test:8080"
_SOURCE = "https://papers.test/task.pdf"
_PDF = b"%PDF-1.7\ntask protocol test"


def _task_mcp(tmp_path: Path) -> FastMCP:
    """Create an isolated in-memory task server for one protocol test."""

    return create_mcp(
        Settings(
            search_provider="ddg",
            document_service_url=_SERVICE,
            artifacts_root=str(tmp_path),
            conversion_poll_s=0.1,
            state_dir=str(tmp_path / "state"),
        )
    )


@pytest.mark.asyncio
async def test_fetch_task_exposes_live_progress_and_terminal_result(
    httpx_mock: HTTPXMock, tmp_path: Path
) -> None:
    """A client can query working state, see progress, and retrieve the result."""

    events_requested = asyncio.Event()
    release_events = asyncio.Event()
    httpx_mock.add_response(
        method="GET",
        url=_SOURCE,
        content=_PDF,
        headers={"content-type": "application/pdf"},
    )
    httpx_mock.add_response(
        method="POST",
        url=f"{_SERVICE}/v1/documents",
        status_code=202,
        json={"id": "task-1", "status": "queued", "stage": "queued"},
    )

    async def progress_response(_request: httpx.Request) -> httpx.Response:
        events_requested.set()
        await release_events.wait()
        return httpx.Response(
            200,
            json={
                "events": [
                    {
                        "sequence": 1,
                        "progress": 70,
                        "stage": "layout",
                        "level": "info",
                        "message": "Reading page layout",
                    }
                ]
            },
        )

    httpx_mock.add_callback(
        progress_response,
        method="GET",
        url=f"{_SERVICE}/v1/documents/task-1/events?after_sequence=0&limit=100",
    )
    httpx_mock.add_response(
        method="GET",
        url=f"{_SERVICE}/v1/documents/task-1",
        json={
            "id": "task-1",
            "status": "complete",
            "result": {"markdown": "# Task result", "document": {"profile": "general"}},
        },
    )

    async with Client(_task_mcp(tmp_path)) as client:
        task = await call_tool_task(client, "fetch", {"target": _SOURCE})
        await asyncio.wait_for(events_requested.wait(), timeout=5)
        working = await task.status()
        assert working.status == "working"
        assert working.status_message is not None
        assert "task-1" in working.status_message

        release_events.set()
        terminal = await task.wait(timeout=5)
        assert terminal.status == "completed"
        result = parse_result(await task.result())

    assert result["conversion_id"] == "task-1"
    assert result["content"] == "# Task result"


@pytest.mark.asyncio
async def test_fetch_task_cancellation_reaches_backend(
    httpx_mock: HTTPXMock, tmp_path: Path
) -> None:
    """Native tasks/cancel cooperatively cancels the backend conversion."""

    events_requested = asyncio.Event()
    never_release = asyncio.Event()
    cancel_requested = asyncio.Event()
    httpx_mock.add_response(
        method="GET",
        url=_SOURCE,
        content=_PDF,
        headers={"content-type": "application/pdf"},
    )
    httpx_mock.add_response(
        method="POST",
        url=f"{_SERVICE}/v1/documents",
        status_code=202,
        json={"id": "task-cancel", "status": "running", "stage": "conversion"},
    )

    async def blocked_progress(_request: httpx.Request) -> httpx.Response:
        events_requested.set()
        await never_release.wait()
        return httpx.Response(200, json={"events": []})

    async def cancel_response(_request: httpx.Request) -> httpx.Response:
        cancel_requested.set()
        return httpx.Response(200, json={"id": "task-cancel", "status": "cancelled"})

    httpx_mock.add_callback(
        blocked_progress,
        method="GET",
        url=(f"{_SERVICE}/v1/documents/task-cancel/events?after_sequence=0&limit=100"),
    )
    httpx_mock.add_callback(
        cancel_response,
        method="POST",
        url=f"{_SERVICE}/v1/documents/task-cancel/cancel",
    )

    async with Client(_task_mcp(tmp_path)) as client:
        task = await call_tool_task(client, "fetch", {"target": _SOURCE})
        await asyncio.wait_for(events_requested.wait(), timeout=5)
        await task.cancel()
        terminal = await task.wait(timeout=5)
        assert terminal.status == "cancelled"
        await asyncio.wait_for(cancel_requested.wait(), timeout=5)
        with pytest.raises(ToolError, match="was cancelled"):
            await task.result()


@pytest.mark.asyncio
async def test_search_rejects_task_execution(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Ordinary search preserves its synchronous tool contract."""

    async def deterministic_search(
        _configured: Settings, query: str, count: int = 5
    ) -> dict[str, object]:
        return {"ok": True, "query": query, "count": count, "results": []}

    monkeypatch.setattr("web_mcp.server.search_common", deterministic_search)
    async with Client(_task_mcp(tmp_path)) as client:
        with pytest.raises(ToolError, match="did not run as a task"):
            await call_tool_task(client, "search", {"query": "clio"})
