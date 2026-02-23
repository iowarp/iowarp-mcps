from __future__ import annotations

from pathlib import Path

import pytest
from pytest import CaptureFixture

from clio_agentic_search.cli.main import main


def test_query_command_prints_response(
    capsys: CaptureFixture[str],
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    docs_dir = tmp_path / "docs"
    docs_dir.mkdir()
    (docs_dir / "example.txt").write_text("phase one retrieval document", encoding="utf-8")
    monkeypatch.setenv("CLIO_LOCAL_ROOT", str(docs_dir))
    monkeypatch.setenv("CLIO_STORAGE_PATH", str(tmp_path / "cli.duckdb"))

    exit_code = main(["query", "--q", "phase one", "--namespace", "local_fs"])
    captured = capsys.readouterr()

    assert exit_code == 0
    assert "query=phase one,namespaces=local_fs" in captured.out
    assert "trace_events=" in captured.out


def test_query_unknown_namespace_returns_non_zero(capsys: CaptureFixture[str]) -> None:
    exit_code = main(["query", "--q", "phase-0", "--namespace", "missing"])
    captured = capsys.readouterr()

    assert exit_code == 2
    assert "Unknown namespace 'missing'" in captured.err


def test_seed_command_reports_seeded_namespaces(
    capsys: CaptureFixture[str],
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    local_root = tmp_path / "local"
    object_root = tmp_path / "object"
    local_root.mkdir()
    object_root.mkdir()
    monkeypatch.setenv("CLIO_LOCAL_ROOT", str(local_root))
    monkeypatch.setenv("CLIO_OBJECT_STORE_ROOT", str(object_root))
    monkeypatch.setenv("CLIO_STORAGE_PATH", str(tmp_path / "seed.duckdb"))

    exit_code = main(["seed", "--namespaces", "local_fs,object_s3,vector_qdrant"])
    captured = capsys.readouterr()

    assert exit_code == 0
    assert "seeded namespace=local_fs,records=1" in captured.out
    assert "seeded namespace=object_s3,records=1" in captured.out
    assert "seeded namespace=vector_qdrant,records=1" in captured.out


def test_query_plain_text_formula_retrieval(
    capsys: CaptureFixture[str],
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Plain-text equations (no $ delimiters) are indexed and found via --formula."""
    docs_dir = tmp_path / "docs"
    docs_dir.mkdir()
    (docs_dir / "kinetics.md").write_text(
        "# Kinetics\nThe rate follows k = A e^{-E_a/RT}, where A is a constant.\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("CLIO_LOCAL_ROOT", str(docs_dir))
    monkeypatch.setenv("CLIO_STORAGE_PATH", str(tmp_path / "formula.duckdb"))

    exit_code = main(["query", "--q", "rate constant", "--formula", "k = A e^{-E_a/RT}"])
    captured = capsys.readouterr()

    assert exit_code == 0
    assert "citation=" in captured.out
    assert "kinetics.md" in captured.out


def test_query_supports_scientific_operator_flags(
    capsys: CaptureFixture[str],
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    docs_dir = tmp_path / "docs"
    docs_dir.mkdir()
    (docs_dir / "science.md").write_text(
        "\n".join(
            [
                "# Benchmark",
                "| Time (min) | Pressure (kPa) |",
                "| --- | --- |",
                "| 1 | 120 |",
                "| 2 | 150 |",
            ]
        ),
        encoding="utf-8",
    )
    monkeypatch.setenv("CLIO_LOCAL_ROOT", str(docs_dir))
    monkeypatch.setenv("CLIO_STORAGE_PATH", str(tmp_path / "cli-science.duckdb"))

    exit_code = main(
        [
            "query",
            "--q",
            "pressure",
            "--namespace",
            "local_fs",
            "--numeric-range",
            "130:160:kPa",
        ]
    )
    captured = capsys.readouterr()

    assert exit_code == 0
    assert "citation=local_fs:science.md#table=1&row=2&column=2" in captured.out
