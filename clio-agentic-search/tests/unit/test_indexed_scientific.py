"""Tests for R5: indexed scientific queries via DuckDB tables."""

from __future__ import annotations

import hashlib
from pathlib import Path

from clio_agentic_search.indexing.scientific import (
    build_structure_aware_chunk_plan,
    normalize_formula,
)
from clio_agentic_search.models.contracts import (
    DocumentRecord,
    EmbeddingRecord,
    MetadataRecord,
)
from clio_agentic_search.storage import DuckDBStorage
from clio_agentic_search.storage.contracts import FileIndexState

_SCIENCE_TEXT = (
    "# Experiment\n"
    "| Time (min) | Pressure (kPa) |\n"
    "| --- | --- |\n"
    "| 1 | 120 |\n"
    "| 2 | 250 |\n"
    "Governing relation: $P V = n R T$.\n"
)

_PLAIN_FORMULA_TEXT = "# Kinetics\nThe rate follows k = A e^{-E_a/RT}, where A is a constant.\n"


def _index_document(storage: DuckDBStorage, namespace: str, text: str) -> None:
    doc_id = hashlib.sha1(f"{namespace}:test.md".encode()).hexdigest()
    plan = build_structure_aware_chunk_plan(
        namespace=namespace, document_id=doc_id, text=text, chunk_size=400
    )
    doc = DocumentRecord(
        namespace=namespace,
        document_id=doc_id,
        uri="test.md",
        checksum="abc",
        modified_at_ns=0,
    )
    embeddings = [
        EmbeddingRecord(
            namespace=namespace,
            chunk_id=c.chunk_id,
            model="hash16-v1",
            vector=(0.5,) * 16,
        )
        for c in plan.chunks
    ]
    metadata: list[MetadataRecord] = []
    for chunk in plan.chunks:
        for key, value in sorted(plan.metadata_by_chunk_id.get(chunk.chunk_id, {}).items()):
            metadata.append(
                MetadataRecord(
                    namespace=namespace,
                    record_id=chunk.chunk_id,
                    scope="chunk",
                    key=key,
                    value=value,
                )
            )
    file_state = FileIndexState(
        namespace=namespace, path="test.md", document_id=doc_id, mtime_ns=0, content_hash="abc"
    )
    storage.upsert_document_bundle(
        document=doc,
        chunks=plan.chunks,
        embeddings=embeddings,
        metadata=metadata,
        file_state=file_state,
    )


def test_measurement_range_query_returns_correct_chunks(tmp_path: Path) -> None:
    storage = DuckDBStorage(tmp_path / "test.duckdb")
    storage.connect()
    try:
        _index_document(storage, "ns", _SCIENCE_TEXT)
        # 120 kPa = 120000 Pa, 250 kPa = 250000 Pa
        results = storage.query_chunks_by_measurement_range("ns", "pa", 200000.0, 260000.0)
        assert results
        # Should contain the chunk with 250 kPa but not 120 kPa
        texts = " ".join(c.text for c in results)
        assert "250" in texts
    finally:
        storage.teardown()


def test_formula_query_returns_correct_chunks(tmp_path: Path) -> None:
    storage = DuckDBStorage(tmp_path / "test.duckdb")
    storage.connect()
    try:
        _index_document(storage, "ns", _SCIENCE_TEXT)
        sig = normalize_formula("P V = n R T")
        results = storage.query_chunks_by_formula("ns", sig)
        assert results
    finally:
        storage.teardown()


def test_indexed_search_matches_old_full_scan(tmp_path: Path) -> None:
    """Indexed search produces same results as the old full-scan approach."""
    from clio_agentic_search.connectors.filesystem import FilesystemConnector
    from clio_agentic_search.retrieval.scientific import (
        NumericRangeOperator,
        ScientificQueryOperators,
        score_scientific_metadata,
    )

    docs = tmp_path / "docs"
    docs.mkdir()
    (docs / "test.md").write_text(_SCIENCE_TEXT)
    storage = DuckDBStorage(tmp_path / "test.duckdb")
    connector = FilesystemConnector(namespace="ns", root=docs, storage=storage)
    connector.connect()
    connector.index(full_rebuild=True)
    try:
        operators = ScientificQueryOperators(
            numeric_range=NumericRangeOperator(unit="kPa", minimum=100.0, maximum=260.0)
        )
        # Indexed path (via connector)
        indexed_results = connector.search_scientific("pressure", top_k=10, operators=operators)
        indexed_ids = {r.chunk_id for r in indexed_results}

        # Old full-scan path
        full_scan_ids: set[str] = set()
        for chunk in storage.list_chunks("ns"):
            metadata = storage.get_chunk_metadata("ns", chunk.chunk_id)
            score = score_scientific_metadata(metadata, operators)
            if score > 0:
                full_scan_ids.add(chunk.chunk_id)

        assert indexed_ids == full_scan_ids
    finally:
        connector.teardown()


def test_plain_text_formula_indexed_and_queryable(tmp_path: Path) -> None:
    """Plain-text equations (no $ delimiters) are stored in scientific_formulas."""
    storage = DuckDBStorage(tmp_path / "test.duckdb")
    storage.connect()
    try:
        _index_document(storage, "ns", _PLAIN_FORMULA_TEXT)
        sig = normalize_formula("k = A e^{-E_a/RT}")
        results = storage.query_chunks_by_formula("ns", sig)
        assert results, "Plain-text Arrhenius formula should be indexed and queryable"
    finally:
        storage.teardown()


def test_delete_cleans_scientific_tables(tmp_path: Path) -> None:
    storage = DuckDBStorage(tmp_path / "test.duckdb")
    storage.connect()
    try:
        _index_document(storage, "ns", _SCIENCE_TEXT)
        # Verify data exists
        assert storage.query_chunks_by_measurement_range("ns", "pa", None, None)
        sig = normalize_formula("P V = n R T")
        assert storage.query_chunks_by_formula("ns", sig)

        # Clear and verify empty
        storage.clear_namespace("ns")
        assert not storage.query_chunks_by_measurement_range("ns", "pa", None, None)
        assert not storage.query_chunks_by_formula("ns", sig)
    finally:
        storage.teardown()
