"""Protocol-style retrieval capabilities."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Protocol, runtime_checkable

from clio_agentic_search.retrieval.scientific import ScientificQueryOperators

if TYPE_CHECKING:
    from clio_agentic_search.retrieval.corpus_profile import CorpusProfile


@dataclass(frozen=True, slots=True)
class ScoredChunk:
    chunk_id: str
    document_id: str
    text: str
    lexical_score: float = 0.0
    vector_score: float = 0.0
    metadata_score: float = 0.0

    @property
    def combined_score(self) -> float:
        return self.lexical_score + self.vector_score + self.metadata_score


@runtime_checkable
class LexicalSearchCapable(Protocol):
    def search_lexical(self, query: str, top_k: int) -> list[ScoredChunk]:
        """Search by lexical overlap."""


@runtime_checkable
class VectorSearchCapable(Protocol):
    def search_vector(self, query: str, top_k: int) -> list[ScoredChunk]:
        """Search by embedding similarity."""


@runtime_checkable
class MetadataFilterCapable(Protocol):
    def filter_metadata(
        self,
        candidates: list[ScoredChunk],
        required: dict[str, str],
    ) -> list[ScoredChunk]:
        """Filter candidate chunks by metadata constraints."""


@runtime_checkable
class GraphTraversalCapable(Protocol):
    def traverse_graph(self, seed: str, depth: int) -> list[str]:
        """Traverse graph-shaped neighborhood around a seed node."""


@runtime_checkable
class GraphSearchCapable(Protocol):
    def search_graph(self, query: str, top_k: int) -> list[ScoredChunk]:
        """Search via graph traversal signals."""


@runtime_checkable
class StreamingLogCapable(Protocol):
    def stream_logs(self, namespace: str, limit: int) -> list[str]:
        """Read streaming log records."""


@runtime_checkable
class ScientificSearchCapable(Protocol):
    def search_scientific(
        self,
        query: str,
        top_k: int,
        operators: ScientificQueryOperators,
    ) -> list[ScoredChunk]:
        """Search by scientific operators on structured/indexed scientific metadata."""


@runtime_checkable
class CorpusProfileCapable(Protocol):
    def corpus_profile(self) -> CorpusProfile:
        """Return a lightweight statistical profile of indexed content."""
