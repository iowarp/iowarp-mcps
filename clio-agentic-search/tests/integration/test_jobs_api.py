"""Integration tests for job API validation endpoints and /metrics."""

from __future__ import annotations

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
