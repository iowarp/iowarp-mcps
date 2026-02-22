"""Tests for R6: DuckDB write lock."""

from __future__ import annotations

import threading
from pathlib import Path

from clio_agentic_search.models.contracts import (
    ChunkRecord,
    DocumentRecord,
    EmbeddingRecord,
    MetadataRecord,
)
from clio_agentic_search.storage import DuckDBStorage
from clio_agentic_search.storage.contracts import FileIndexState


def _make_bundle(
    namespace: str, doc_id: str
) -> tuple[
    DocumentRecord,
    list[ChunkRecord],
    list[EmbeddingRecord],
    list[MetadataRecord],
    FileIndexState,
]:
    document = DocumentRecord(
        namespace=namespace,
        document_id=doc_id,
        uri=f"test://{doc_id}",
        checksum="abc",
        modified_at_ns=0,
    )
    chunks = [
        ChunkRecord(
            namespace=namespace,
            chunk_id=f"{doc_id}-c1",
            document_id=doc_id,
            chunk_index=0,
            text="chunk text",
            start_offset=0,
            end_offset=10,
        )
    ]
    embeddings = [
        EmbeddingRecord(
            namespace=namespace,
            chunk_id=f"{doc_id}-c1",
            model="hash16-v1",
            vector=(0.5,) * 16,
        )
    ]
    metadata: list[MetadataRecord] = []
    file_state = FileIndexState(
        namespace=namespace,
        path=f"{doc_id}.txt",
        document_id=doc_id,
        mtime_ns=0,
        content_hash="abc",
    )
    return document, chunks, embeddings, metadata, file_state


def test_lock_file_created_on_write(tmp_path: Path) -> None:
    db_path = tmp_path / "test.duckdb"
    storage = DuckDBStorage(db_path)
    storage.connect()
    try:
        bundle = _make_bundle("ns", "doc1")
        storage.upsert_document_bundle(*bundle)
        lock_path = db_path.with_suffix(".lock")
        assert lock_path.exists()
    finally:
        storage.teardown()


def test_concurrent_threads_serialize_correctly(tmp_path: Path) -> None:
    db_path = tmp_path / "concurrent.duckdb"
    storage = DuckDBStorage(db_path)
    storage.connect()
    errors: list[Exception] = []

    def writer(doc_id: str) -> None:
        try:
            bundle = _make_bundle("ns", doc_id)
            storage.upsert_document_bundle(*bundle)
        except Exception as exc:
            errors.append(exc)

    try:
        threads = [threading.Thread(target=writer, args=(f"doc{i}",)) for i in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert not errors, f"Concurrent write errors: {errors}"
        chunks = storage.list_chunks("ns")
        chunk_ids = {c.chunk_id for c in chunks}
        for i in range(5):
            assert f"doc{i}-c1" in chunk_ids
    finally:
        storage.teardown()
