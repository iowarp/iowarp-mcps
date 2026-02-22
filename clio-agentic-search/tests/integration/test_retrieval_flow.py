from __future__ import annotations

from pathlib import Path

from clio_agentic_search.connectors.filesystem import FilesystemConnector
from clio_agentic_search.core.namespace_registry import NamespaceRegistry
from clio_agentic_search.retrieval.coordinator import RetrievalCoordinator
from clio_agentic_search.storage import DuckDBStorage


def _build_registry(root: Path, database_path: Path) -> NamespaceRegistry:
    connector = FilesystemConnector(
        namespace="local_docs",
        root=root,
        storage=DuckDBStorage(database_path),
    )
    registry = NamespaceRegistry()
    registry.register("local_docs", connector)
    return registry


def test_query_returns_deterministic_citations_and_trace(tmp_path: Path) -> None:
    docs_dir = tmp_path / "docs"
    docs_dir.mkdir()
    (docs_dir / "alpha.txt").write_text(
        "orbital mechanics phase one trajectory update",
        encoding="utf-8",
    )
    (docs_dir / "beta.txt").write_text(
        "phase one risk register and mitigation plan",
        encoding="utf-8",
    )
    registry = _build_registry(root=docs_dir, database_path=tmp_path / "query.duckdb")
    connector = registry.connect("local_docs")
    connector.index(full_rebuild=True)
    coordinator = RetrievalCoordinator()

    first = coordinator.query(connector=connector, query="phase one plan", top_k=3)
    second = coordinator.query(connector=connector, query="phase one plan", top_k=3)

    assert [citation.chunk_id for citation in first.citations] == [
        citation.chunk_id for citation in second.citations
    ]
    assert [citation.uri for citation in first.citations] == [
        citation.uri for citation in second.citations
    ]
    assert first.trace and second.trace
    assert [event.stage for event in first.trace] == [
        "query_started",
        "lexical_completed",
        "vector_completed",
        "graph_completed",
        "merge_completed",
        "metadata_completed",
        "rerank_completed",
        "query_completed",
    ]
    registry.teardown()


def test_incremental_reindex_is_faster_for_unchanged_corpus(tmp_path: Path) -> None:
    docs_dir = tmp_path / "docs"
    docs_dir.mkdir()
    for index in range(30):
        (docs_dir / f"doc-{index}.txt").write_text(
            f"phase one document {index} with repeated retrieval terms",
            encoding="utf-8",
        )

    connector = FilesystemConnector(
        namespace="local_docs",
        root=docs_dir,
        storage=DuckDBStorage(tmp_path / "incremental.duckdb"),
        reindex_delay_seconds=0.004,
    )
    connector.connect()
    full = connector.index(full_rebuild=True)
    incremental = connector.index(full_rebuild=False)
    connector.teardown()

    assert full.indexed_files == 30
    assert incremental.indexed_files == 0
    assert incremental.skipped_files == full.scanned_files
    assert incremental.elapsed_seconds < full.elapsed_seconds
