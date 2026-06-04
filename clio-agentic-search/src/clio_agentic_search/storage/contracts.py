"""Storage contracts for backend-independent persistence."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from typing import Protocol

from clio_agentic_search.models.contracts import (
    ChunkRecord,
    DocumentRecord,
    DocumentSummary,
    EmbeddingRecord,
    MetadataRecord,
)


@dataclass(frozen=True, slots=True)
class FileIndexState:
    namespace: str
    path: str
    document_id: str
    mtime_ns: int
    content_hash: str


@dataclass(frozen=True, slots=True)
class LexicalChunkMatch:
    chunk: ChunkRecord
    overlap_count: int
    bm25_score: float = 0.0


@dataclass(frozen=True, slots=True)
class DocumentBundle:
    document: DocumentRecord
    chunks: list[ChunkRecord]
    embeddings: list[EmbeddingRecord]
    metadata: list[MetadataRecord]
    file_state: FileIndexState


class StorageAdapter(Protocol):
    def connect(self) -> None:
        """Initialize storage resources."""

    def teardown(self) -> None:
        """Close storage resources."""

    def clear_namespace(self, namespace: str) -> None:
        """Delete all records associated with a namespace."""

    def upsert_document_bundle(
        self,
        document: DocumentRecord,
        chunks: list[ChunkRecord],
        embeddings: list[EmbeddingRecord],
        metadata: list[MetadataRecord],
        file_state: FileIndexState,
        *,
        include_lexical_postings: bool = True,
    ) -> None:
        """Store a full document with associated chunk, embedding, and metadata records."""

    def upsert_document_bundles(
        self,
        bundles: list[DocumentBundle],
        *,
        include_lexical_postings: bool = True,
        skip_prior_delete: bool = False,
    ) -> None:
        """Store many document bundles in one write session."""

    def upsert_lexical_postings_batch(
        self,
        namespace: str,
        postings: list[tuple[str, str, int]],
    ) -> None:
        """Store lexical postings in batch as (chunk_id, token, term_freq) rows."""

    def upsert_lexical_postings_stream(
        self,
        namespace: str,
        postings: Iterable[tuple[str, str, int]],
        *,
        batch_size: int = 50_000,
    ) -> None:
        """Store lexical postings from an iterator using bounded batched writes."""

    def get_file_state(self, namespace: str, path: str) -> FileIndexState | None:
        """Fetch existing file indexing state."""

    def remove_missing_paths(self, namespace: str, existing_paths: set[str]) -> int:
        """Remove indexed records for paths that no longer exist."""

    def list_chunks(self, namespace: str) -> list[ChunkRecord]:
        """List all chunks for a namespace."""

    def list_embeddings(self, namespace: str, model: str) -> dict[str, tuple[float, ...]]:
        """List embeddings keyed by chunk id."""

    def get_chunk(self, namespace: str, chunk_id: str) -> ChunkRecord:
        """Fetch a chunk by id."""

    def get_chunk_metadata(self, namespace: str, chunk_id: str) -> dict[str, str]:
        """Fetch metadata for a chunk."""

    def get_document_uri(self, namespace: str, document_id: str) -> str:
        """Resolve a document URI by id."""

    def query_chunks_by_measurement_range(
        self,
        namespace: str,
        canonical_unit: str,
        minimum: float | None,
        maximum: float | None,
    ) -> list[ChunkRecord]:
        """Query chunks by canonical measurement range."""

    def query_chunks_by_formula(self, namespace: str, formula_signature: str) -> list[ChunkRecord]:
        """Query chunks by normalized formula signature."""

    def list_documents(self, namespace: str) -> list[DocumentSummary]:
        """List documents with chunk counts for a namespace."""

    def query_chunks_lexical(
        self,
        namespace: str,
        query_tokens: tuple[str, ...],
        limit: int,
    ) -> list[LexicalChunkMatch]:
        """Query top lexical chunk matches from persisted token postings."""
