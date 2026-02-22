"""Storage contracts for backend-independent persistence."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from clio_agentic_search.models.contracts import (
    ChunkRecord,
    DocumentRecord,
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
    ) -> None:
        """Store a full document with associated chunk, embedding, and metadata records."""

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
