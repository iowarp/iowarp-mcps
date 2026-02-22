"""Reranking hooks for retrieval results."""

from __future__ import annotations

from typing import Protocol

from clio_agentic_search.retrieval.capabilities import ScoredChunk


class Reranker(Protocol):
    def rerank(self, query: str, candidates: list[ScoredChunk]) -> list[ScoredChunk]:
        """Reorder or adjust candidates for the final ranking."""


class DefaultHeuristicReranker:
    """Simple deterministic reranker for early-phase retrieval."""

    def rerank(self, query: str, candidates: list[ScoredChunk]) -> list[ScoredChunk]:
        del query
        return sorted(
            candidates,
            key=lambda chunk: (-chunk.combined_score, chunk.document_id, chunk.chunk_id),
        )
