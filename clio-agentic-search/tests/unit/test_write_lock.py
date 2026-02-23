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
from clio_agentic_search.storage.contracts import DocumentBundle, FileIndexState


def _make_bundle(
    namespace: str,
    doc_id: str,
    *,
    text: str = "chunk text",
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
            text=text,
            start_offset=0,
            end_offset=max(len(text), 10),
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


def test_lexical_postings_query_orders_by_overlap(tmp_path: Path) -> None:
    db_path = tmp_path / "lexical.duckdb"
    storage = DuckDBStorage(db_path)
    storage.connect()
    try:
        storage.upsert_document_bundle(*_make_bundle("ns", "doc1", text="alpha beta beta"))
        storage.upsert_document_bundle(*_make_bundle("ns", "doc2", text="alpha gamma"))
        matches = storage.query_chunks_lexical(
            namespace="ns",
            query_tokens=("alpha", "beta"),
            limit=10,
        )
        assert [match.chunk.chunk_id for match in matches] == ["doc1-c1", "doc2-c1"]
        assert matches[0].overlap_count == 3
        assert matches[1].overlap_count == 1
    finally:
        storage.teardown()


def test_lexical_postings_replaced_on_document_upsert(tmp_path: Path) -> None:
    db_path = tmp_path / "lexical-replace.duckdb"
    storage = DuckDBStorage(db_path)
    storage.connect()
    try:
        storage.upsert_document_bundle(*_make_bundle("ns", "doc1", text="alpha beta"))
        storage.upsert_document_bundle(*_make_bundle("ns", "doc1", text="delta epsilon"))
        stale = storage.query_chunks_lexical(
            namespace="ns",
            query_tokens=("alpha",),
            limit=10,
        )
        fresh = storage.query_chunks_lexical(
            namespace="ns",
            query_tokens=("delta",),
            limit=10,
        )
        assert stale == []
        assert [match.chunk.chunk_id for match in fresh] == ["doc1-c1"]
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


def test_concurrent_read_write_access_is_safe(tmp_path: Path) -> None:
    db_path = tmp_path / "readwrite.duckdb"
    storage = DuckDBStorage(db_path)
    storage.connect()
    errors: list[Exception] = []
    stop = threading.Event()

    def writer() -> None:
        try:
            for i in range(20):
                bundle = _make_bundle("ns", f"doc{i}")
                storage.upsert_document_bundle(*bundle)
        except Exception as exc:
            errors.append(exc)
        finally:
            stop.set()

    def reader() -> None:
        try:
            while not stop.is_set():
                storage.list_chunks("ns")
                storage.list_documents("ns")
        except Exception as exc:
            errors.append(exc)

    try:
        writer_thread = threading.Thread(target=writer)
        reader_thread = threading.Thread(target=reader)
        writer_thread.start()
        reader_thread.start()
        writer_thread.join()
        reader_thread.join()
        assert not errors, f"Concurrent read/write errors: {errors}"
    finally:
        storage.teardown()


def test_upsert_document_bundles_replaces_documents_atomically(tmp_path: Path) -> None:
    db_path = tmp_path / "bundle.duckdb"
    storage = DuckDBStorage(db_path)
    storage.connect()
    try:
        bundle1 = _make_bundle("ns", "doc1", text="alpha beta")
        bundle2 = _make_bundle("ns", "doc2", text="gamma delta")
        storage.upsert_document_bundles(
            [
                DocumentBundle(
                    document=bundle1[0],
                    chunks=bundle1[1],
                    embeddings=bundle1[2],
                    metadata=bundle1[3],
                    file_state=bundle1[4],
                ),
                DocumentBundle(
                    document=bundle2[0],
                    chunks=bundle2[1],
                    embeddings=bundle2[2],
                    metadata=bundle2[3],
                    file_state=bundle2[4],
                ),
            ],
            include_lexical_postings=False,
        )
        storage.upsert_lexical_postings_stream(
            "ns",
            [
                ("doc1-c1", "alpha", 1),
                ("doc2-c1", "gamma", 1),
            ],
            batch_size=1,
        )

        alpha_hits = storage.query_chunks_lexical("ns", ("alpha",), limit=10)
        gamma_hits = storage.query_chunks_lexical("ns", ("gamma",), limit=10)
        assert [hit.chunk.chunk_id for hit in alpha_hits] == ["doc1-c1"]
        assert [hit.chunk.chunk_id for hit in gamma_hits] == ["doc2-c1"]
    finally:
        storage.teardown()


def test_skip_prior_delete_inserts_without_cascade(tmp_path: Path) -> None:
    db_path = tmp_path / "skip-delete.duckdb"
    storage = DuckDBStorage(db_path)
    storage.connect()
    try:
        bundle1 = _make_bundle("ns", "doc1", text="alpha beta")
        storage.upsert_document_bundles(
            [
                DocumentBundle(
                    document=bundle1[0],
                    chunks=bundle1[1],
                    embeddings=bundle1[2],
                    metadata=bundle1[3],
                    file_state=bundle1[4],
                ),
            ],
            skip_prior_delete=True,
        )
        chunks = storage.list_chunks("ns")
        assert len(chunks) == 1
        assert chunks[0].chunk_id == "doc1-c1"
    finally:
        storage.teardown()
