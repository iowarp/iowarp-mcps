from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from clio_agentic_search import __version__
from clio_agentic_search.api.app import _registry, app


def test_health_endpoint() -> None:
    client = TestClient(app)
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_version_endpoint() -> None:
    client = TestClient(app)
    response = client.get("/version")

    assert response.status_code == 200
    assert response.json() == {"version": __version__}


def test_query_endpoint_returns_citations_and_trace(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    docs_dir = tmp_path / "docs"
    docs_dir.mkdir()
    (docs_dir / "query.txt").write_text("phase one api coverage document", encoding="utf-8")
    monkeypatch.setenv("CLIO_LOCAL_ROOT", str(docs_dir))
    monkeypatch.setenv("CLIO_STORAGE_PATH", str(tmp_path / "api.duckdb"))
    _registry.cache_clear()

    client = TestClient(app)
    response = client.post(
        "/query",
        json={
            "namespace": "local_fs",
            "query": "phase one api",
            "top_k": 3,
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["citations"]
    assert payload["trace"]
    assert payload["namespaces"] == ["local_fs"]
    assert payload["trace"][-1]["stage"] == "query_completed"

    _registry().teardown()
    _registry.cache_clear()
