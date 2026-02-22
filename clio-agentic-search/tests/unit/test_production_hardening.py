"""Tests for production hardening: registry cleanup, embedder auto-detect, list, pagination."""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from pytest import CaptureFixture

from clio_agentic_search.api.app import _registry, app
from clio_agentic_search.cli.main import build_parser, main
from clio_agentic_search.core.namespace_registry import _default_embedder, build_default_registry
from clio_agentic_search.indexing.text_features import HashEmbedder


class TestRegistryCleanup:
    def test_default_registry_excludes_graph_and_kv(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.setenv("CLIO_LOCAL_ROOT", str(tmp_path))
        monkeypatch.setenv("CLIO_STORAGE_PATH", str(tmp_path / "reg.duckdb"))
        registry = build_default_registry()
        assert "local_fs" in registry
        assert "object_s3" in registry
        assert "vector_qdrant" in registry
        assert "graph_neo4j" not in registry
        assert "kv_redis" not in registry
        registry.teardown()

    def test_default_registry_has_three_namespaces(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.setenv("CLIO_LOCAL_ROOT", str(tmp_path))
        monkeypatch.setenv("CLIO_STORAGE_PATH", str(tmp_path / "reg2.duckdb"))
        registry = build_default_registry()
        assert len(registry.list_namespaces()) == 3
        registry.teardown()


class TestEmbedderAutoDetect:
    def test_falls_back_to_hash_when_no_sentence_transformers(self) -> None:
        embedder = _default_embedder()
        # In test environment without sentence-transformers installed,
        # should fall back to HashEmbedder
        assert isinstance(embedder, HashEmbedder)


class TestListCommand:
    def test_list_subcommand_parsed(self) -> None:
        parser = build_parser()
        args = parser.parse_args(["list", "--namespace", "local_fs"])
        assert args.command == "list"
        assert args.namespace == "local_fs"

    def test_list_empty_namespace(
        self,
        capsys: CaptureFixture[str],
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        empty_dir = tmp_path / "empty"
        empty_dir.mkdir()
        monkeypatch.setenv("CLIO_LOCAL_ROOT", str(empty_dir))
        monkeypatch.setenv("CLIO_STORAGE_PATH", str(tmp_path / "list.duckdb"))

        # Index first so storage is connected
        main(["index", "--namespace", "local_fs"])
        exit_code = main(["list", "--namespace", "local_fs"])
        captured = capsys.readouterr()

        assert exit_code == 0
        assert "No documents indexed" in captured.out

    def test_list_shows_indexed_documents(
        self,
        capsys: CaptureFixture[str],
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        docs_dir = tmp_path / "docs"
        docs_dir.mkdir()
        (docs_dir / "alpha.txt").write_text("alpha content", encoding="utf-8")
        (docs_dir / "beta.md").write_text("beta content", encoding="utf-8")
        monkeypatch.setenv("CLIO_LOCAL_ROOT", str(docs_dir))
        monkeypatch.setenv("CLIO_STORAGE_PATH", str(tmp_path / "list2.duckdb"))

        main(["index", "--namespace", "local_fs"])
        exit_code = main(["list", "--namespace", "local_fs"])
        captured = capsys.readouterr()

        assert exit_code == 0
        assert "alpha.txt" in captured.out
        assert "beta.md" in captured.out
        assert "Total: 2 documents" in captured.out

    def test_list_unknown_namespace(
        self,
        capsys: CaptureFixture[str],
    ) -> None:
        exit_code = main(["list", "--namespace", "nonexistent"])
        captured = capsys.readouterr()

        assert exit_code == 2
        assert "Unknown namespace" in captured.err


class TestDocumentsEndpoint:
    def test_documents_endpoint_returns_list(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        docs_dir = tmp_path / "docs"
        docs_dir.mkdir()
        (docs_dir / "test.txt").write_text("api document listing test", encoding="utf-8")
        monkeypatch.setenv("CLIO_LOCAL_ROOT", str(docs_dir))
        monkeypatch.setenv("CLIO_STORAGE_PATH", str(tmp_path / "docs-api.duckdb"))
        _registry.cache_clear()

        client = TestClient(app)
        # First index via query
        client.post("/query", json={"namespace": "local_fs", "query": "test"})
        # Then list
        response = client.get("/documents", params={"namespace": "local_fs"})

        assert response.status_code == 200
        payload = response.json()
        assert payload["total_documents"] >= 1
        assert payload["total_chunks"] >= 1
        assert any(d["uri"] == "test.txt" for d in payload["documents"])

        _registry().teardown()
        _registry.cache_clear()

    def test_documents_endpoint_unknown_namespace(self) -> None:
        _registry.cache_clear()
        client = TestClient(app)
        response = client.get("/documents", params={"namespace": "missing_ns"})
        assert response.status_code == 404
        _registry().teardown()
        _registry.cache_clear()


class TestQueryPagination:
    def test_pagination_fields_in_response(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        docs_dir = tmp_path / "docs"
        docs_dir.mkdir()
        (docs_dir / "pag.txt").write_text("pagination test content", encoding="utf-8")
        monkeypatch.setenv("CLIO_LOCAL_ROOT", str(docs_dir))
        monkeypatch.setenv("CLIO_STORAGE_PATH", str(tmp_path / "pag.duckdb"))
        _registry.cache_clear()

        client = TestClient(app)
        response = client.post(
            "/query",
            json={"namespace": "local_fs", "query": "pagination", "offset": 0, "limit": 10},
        )

        assert response.status_code == 200
        payload = response.json()
        assert "total_count" in payload
        assert "offset" in payload
        assert "limit" in payload
        assert payload["offset"] == 0
        assert payload["limit"] == 10

        _registry().teardown()
        _registry.cache_clear()

    def test_pagination_offset_skips_results(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        docs_dir = tmp_path / "docs"
        docs_dir.mkdir()
        (docs_dir / "a.txt").write_text("content for pagination offset test", encoding="utf-8")
        monkeypatch.setenv("CLIO_LOCAL_ROOT", str(docs_dir))
        monkeypatch.setenv("CLIO_STORAGE_PATH", str(tmp_path / "pag2.duckdb"))
        _registry.cache_clear()

        client = TestClient(app)
        # Get all results first
        full = client.post(
            "/query",
            json={"namespace": "local_fs", "query": "content", "offset": 0, "limit": 100},
        ).json()
        # Then with high offset
        offset = client.post(
            "/query",
            json={
                "namespace": "local_fs",
                "query": "content",
                "offset": full["total_count"],
                "limit": 100,
            },
        ).json()

        assert offset["total_count"] == full["total_count"]
        assert len(offset["citations"]) == 0

        _registry().teardown()
        _registry.cache_clear()
