"""Integration tests for job API validation endpoints and /metrics."""

from __future__ import annotations

import asyncio
from pathlib import Path

import pytest
from httpx import ASGITransport, AsyncClient

from clio_agentic_search.api.app import app


@pytest.mark.asyncio
async def test_submit_index_job_unknown_namespace() -> None:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post("/jobs/index", json={"namespace": "nonexistent"})
        assert response.status_code == 404


@pytest.mark.asyncio
async def test_get_job_not_found() -> None:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/jobs/nonexistent")
        assert response.status_code == 404


@pytest.mark.asyncio
async def test_cancel_nonexistent_job() -> None:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.delete("/jobs/nonexistent")
        assert response.status_code == 404


@pytest.mark.asyncio
async def test_metrics_endpoint() -> None:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/metrics")
        assert response.status_code == 200
        text = response.text
        assert "query_count" in text
        assert "query_latency_seconds" in text
        assert "index_duration_seconds" in text


@pytest.mark.asyncio
async def test_submit_index_job_completes(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    docs_dir = tmp_path / "docs"
    docs_dir.mkdir()
    (docs_dir / "alpha.txt").write_text("background job indexing test", encoding="utf-8")
    monkeypatch.setenv("CLIO_LOCAL_ROOT", str(docs_dir))
    monkeypatch.setenv("CLIO_STORAGE_PATH", str(tmp_path / "jobs.duckdb"))

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        submit = await client.post("/jobs/index", json={"namespace": "local_fs"})
        assert submit.status_code == 200
        job_id = submit.json()["job_id"]
        assert job_id

        status_payload: dict[str, object] = {}
        deadline = asyncio.get_running_loop().time() + 5.0
        while asyncio.get_running_loop().time() < deadline:
            status = await client.get(f"/jobs/{job_id}")
            assert status.status_code == 200
            status_payload = status.json()
            if status_payload["status"] in {"completed", "failed", "cancelled"}:
                break
            await asyncio.sleep(0.02)

        assert status_payload["status"] == "completed"
        result = status_payload.get("result")
        assert isinstance(result, dict)
        assert result["indexed_files"] == 1
        assert result["skipped_files"] == 0
        assert result["removed_files"] == 0
        assert isinstance(result["elapsed_seconds"], float)
