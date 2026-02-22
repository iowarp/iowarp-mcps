"""Tests for MVP usability gaps (Gaps 1-8)."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient
from pytest import CaptureFixture

from clio_agentic_search.api.app import _registry, app
from clio_agentic_search.cli.main import build_parser, main
from clio_agentic_search.connectors.filesystem.connector import (
    DEFAULT_EXCLUDE_PATTERNS,
    DEFAULT_EXCLUDE_SUFFIXES,
    FilesystemConnector,
    _should_skip_path,
)
from clio_agentic_search.connectors.object_store.connector import _should_skip_key
from clio_agentic_search.storage.duckdb_store import DuckDBStorage

# --- Gap 1: File filtering ---


class TestFileFiltering:
    def test_git_directory_skipped(self, tmp_path: Path) -> None:
        root = tmp_path / "project"
        root.mkdir()
        git_dir = root / ".git" / "objects"
        git_dir.mkdir(parents=True)
        (git_dir / "abc123").write_bytes(b"\x00packed")
        assert _should_skip_path(
            git_dir / "abc123", root, DEFAULT_EXCLUDE_PATTERNS, DEFAULT_EXCLUDE_SUFFIXES
        )

    def test_duckdb_suffix_skipped(self, tmp_path: Path) -> None:
        root = tmp_path
        f = root / "data.duckdb"
        f.write_text("x")
        assert _should_skip_path(f, root, DEFAULT_EXCLUDE_PATTERNS, DEFAULT_EXCLUDE_SUFFIXES)

    def test_duckdb_wal_suffix_skipped(self, tmp_path: Path) -> None:
        root = tmp_path
        f = root / "data.duckdb.wal"
        f.write_text("x")
        assert _should_skip_path(f, root, DEFAULT_EXCLUDE_PATTERNS, DEFAULT_EXCLUDE_SUFFIXES)

    def test_binary_suffix_skipped(self, tmp_path: Path) -> None:
        root = tmp_path
        for suffix in [".png", ".jpg", ".exe", ".so", ".zip"]:
            f = root / f"file{suffix}"
            f.write_text("x")
            assert _should_skip_path(f, root, DEFAULT_EXCLUDE_PATTERNS, DEFAULT_EXCLUDE_SUFFIXES), (
                f"{suffix} should be skipped"
            )

    def test_pycache_directory_skipped(self, tmp_path: Path) -> None:
        root = tmp_path
        cache = root / "__pycache__"
        cache.mkdir()
        f = cache / "mod.cpython-311.pyc"
        f.write_text("x")
        assert _should_skip_path(f, root, DEFAULT_EXCLUDE_PATTERNS, DEFAULT_EXCLUDE_SUFFIXES)

    def test_text_files_not_skipped(self, tmp_path: Path) -> None:
        root = tmp_path
        for suffix in [".md", ".txt", ".py", ".json", ".csv", ".yaml"]:
            f = root / f"file{suffix}"
            f.write_text("x")
            assert not _should_skip_path(
                f, root, DEFAULT_EXCLUDE_PATTERNS, DEFAULT_EXCLUDE_SUFFIXES
            ), f"{suffix} should NOT be skipped"

    def test_connector_indexes_text_skips_binary(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        root = tmp_path / "docs"
        root.mkdir()
        (root / "readme.md").write_text("hello world", encoding="utf-8")
        (root / "image.png").write_bytes(b"\x89PNG\r\n")
        git_dir = root / ".git"
        git_dir.mkdir()
        (git_dir / "HEAD").write_text("ref: refs/heads/main")

        monkeypatch.setenv("CLIO_STORAGE_PATH", str(tmp_path / "test.duckdb"))
        storage = DuckDBStorage(tmp_path / "test.duckdb")
        connector = FilesystemConnector(namespace="test", root=root, storage=storage)
        connector.connect()
        try:
            report = connector.index()
            assert report.indexed_files == 1
            assert report.scanned_files == 1
        finally:
            connector.teardown()

    def test_s3_key_suffix_filtering(self) -> None:
        assert _should_skip_key("data/file.duckdb", DEFAULT_EXCLUDE_SUFFIXES)
        assert _should_skip_key("imgs/photo.png", DEFAULT_EXCLUDE_SUFFIXES)
        assert not _should_skip_key("docs/readme.md", DEFAULT_EXCLUDE_SUFFIXES)
        assert not _should_skip_key("no_extension", DEFAULT_EXCLUDE_SUFFIXES)


# --- Gap 2: CORS middleware ---


class TestCORSMiddleware:
    def test_cors_headers_present(self) -> None:
        client = TestClient(app)
        response = client.options(
            "/health",
            headers={"Origin": "http://localhost:3000", "Access-Control-Request-Method": "GET"},
        )
        assert "access-control-allow-origin" in response.headers


# --- Gap 3: CLI serve command ---


class TestServeCommand:
    def test_serve_subcommand_parsed(self) -> None:
        parser = build_parser()
        args = parser.parse_args(["serve", "--host", "0.0.0.0", "--port", "9000", "--reload"])
        assert args.command == "serve"
        assert args.host == "0.0.0.0"
        assert args.port == 9000
        assert args.reload is True

    def test_serve_defaults(self) -> None:
        parser = build_parser()
        args = parser.parse_args(["serve"])
        assert args.host == "127.0.0.1"
        assert args.port == 8000
        assert args.reload is False

    def test_serve_calls_uvicorn(self) -> None:
        with patch("uvicorn.run") as mock_run:
            main(["serve", "--port", "9999"])
            mock_run.assert_called_once_with(
                "clio_agentic_search.api.app:app",
                host="127.0.0.1",
                port=9999,
                reload=False,
            )


# --- Gap 4: Empty results diagnostics ---


class TestEmptyResultsDiagnostics:
    def test_empty_directory_prints_warning(
        self,
        capsys: CaptureFixture[str],
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        empty_dir = tmp_path / "empty"
        empty_dir.mkdir()
        monkeypatch.setenv("CLIO_LOCAL_ROOT", str(empty_dir))
        monkeypatch.setenv("CLIO_STORAGE_PATH", str(tmp_path / "empty.duckdb"))

        exit_code = main(["query", "--q", "anything", "--namespace", "local_fs"])
        captured = capsys.readouterr()

        assert exit_code == 0
        assert "Warning: no documents found" in captured.err

    def test_no_results_prints_diagnostic(
        self,
        capsys: CaptureFixture[str],
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        docs_dir = tmp_path / "docs"
        docs_dir.mkdir()
        (docs_dir / "data.txt").write_text("alpha beta gamma", encoding="utf-8")
        monkeypatch.setenv("CLIO_LOCAL_ROOT", str(docs_dir))
        monkeypatch.setenv("CLIO_STORAGE_PATH", str(tmp_path / "diag.duckdb"))

        exit_code = main(["query", "--q", "xyznonexistentquery99999", "--namespace", "local_fs"])
        captured = capsys.readouterr()

        assert exit_code == 0
        assert "No results." in captured.out


# --- Gap 5: DuckDB error wrapping ---


class TestDuckDBErrorWrapping:
    def test_invalid_path_produces_runtime_error(self, tmp_path: Path) -> None:
        bad_path = tmp_path / "nonexistent" / "deep" / "path" / "db.duckdb"
        storage = DuckDBStorage(bad_path)
        # DuckDB can create the parent via mkdir, so test the wrapping by mocking
        with patch("duckdb.connect", side_effect=OSError("permission denied")):
            with pytest.raises(RuntimeError, match="Cannot open database"):
                storage.connect()


# --- Gap 6: CLI help text ---


class TestCLIHelpText:
    def test_main_help_shows_env_vars(self, capsys: CaptureFixture[str]) -> None:
        parser = build_parser()
        help_text = parser.format_help()
        assert "CLIO_LOCAL_ROOT" in help_text
        assert "CLIO_STORAGE_PATH" in help_text
        assert "CLIO_CORS_ORIGINS" in help_text

    def test_query_help_shows_env_vars(self) -> None:
        parser = build_parser()
        # Get the query subparser help
        for action in parser._subparsers._actions:
            if hasattr(action, "_parser_class"):
                for name, subparser in action.choices.items():
                    if name == "query":
                        help_text = subparser.format_help()
                        assert "CLIO_LOCAL_ROOT" in help_text
                        return
        pytest.fail("query subparser not found")


# --- Gap 7: API error handling ---


class TestAPIErrorHandling:
    def test_unknown_namespace_returns_404(self) -> None:
        _registry.cache_clear()
        client = TestClient(app)
        response = client.post(
            "/query",
            json={"namespace": "nonexistent_ns", "query": "test"},
        )
        assert response.status_code == 404
        assert "Unknown namespace" in response.json()["detail"]
        _registry().teardown()
        _registry.cache_clear()

    def test_value_error_returns_400(self) -> None:
        client = TestClient(app, raise_server_exceptions=False)
        with patch(
            "clio_agentic_search.api.app._registry",
            side_effect=ValueError("bad input"),
        ):
            response = client.post("/query", json={"namespace": "x", "query": "q"})
            assert response.status_code == 400
            assert "bad input" in response.json()["error"]

    def test_runtime_error_returns_503(self) -> None:
        client = TestClient(app, raise_server_exceptions=False)
        with patch(
            "clio_agentic_search.api.app._registry",
            side_effect=RuntimeError("db unavailable"),
        ):
            response = client.post("/query", json={"namespace": "x", "query": "q"})
            assert response.status_code == 503
            assert "db unavailable" in response.json()["error"]


# --- Gap 8: clio index command ---


class TestIndexCommand:
    def test_index_subcommand_parsed(self) -> None:
        parser = build_parser()
        args = parser.parse_args(["index", "--namespace", "local_fs", "--full-reindex"])
        assert args.command == "index"
        assert args.namespace == "local_fs"
        assert args.full_reindex is True

    def test_index_command_runs(
        self,
        capsys: CaptureFixture[str],
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        docs_dir = tmp_path / "docs"
        docs_dir.mkdir()
        (docs_dir / "sample.txt").write_text("indexing test content", encoding="utf-8")
        monkeypatch.setenv("CLIO_LOCAL_ROOT", str(docs_dir))
        monkeypatch.setenv("CLIO_STORAGE_PATH", str(tmp_path / "idx.duckdb"))

        exit_code = main(["index", "--namespace", "local_fs"])
        captured = capsys.readouterr()

        assert exit_code == 0
        assert "namespace=local_fs,indexed=1" in captured.out
        assert "elapsed=" in captured.out

    def test_index_unknown_namespace(
        self,
        capsys: CaptureFixture[str],
    ) -> None:
        exit_code = main(["index", "--namespace", "missing"])
        captured = capsys.readouterr()

        assert exit_code == 2
        assert "Unknown namespace 'missing'" in captured.err
