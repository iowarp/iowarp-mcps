"""Canonical data contracts shared across connectors and retrieval."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True, slots=True)
class NamespaceDescriptor:
    name: str
    connector_type: str
    root_uri: str


@dataclass(frozen=True, slots=True)
class DocumentRecord:
    namespace: str
    document_id: str
    uri: str
    checksum: str
    modified_at_ns: int


@dataclass(frozen=True, slots=True)
class ChunkRecord:
    namespace: str
    chunk_id: str
    document_id: str
    chunk_index: int
    text: str
    start_offset: int
    end_offset: int


@dataclass(frozen=True, slots=True)
class EmbeddingRecord:
    namespace: str
    chunk_id: str
    model: str
    vector: tuple[float, ...]


@dataclass(frozen=True, slots=True)
class MetadataRecord:
    namespace: str
    record_id: str
    scope: str
    key: str
    value: str


@dataclass(frozen=True, slots=True)
class CitationRecord:
    namespace: str
    document_id: str
    chunk_id: str
    uri: str
    snippet: str
    score: float


@dataclass(frozen=True, slots=True)
class TraceEvent:
    stage: str
    message: str
    timestamp_ns: int
    attributes: dict[str, str] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class DocumentSummary:
    namespace: str
    document_id: str
    uri: str
    chunk_count: int
    modified_at_ns: int
