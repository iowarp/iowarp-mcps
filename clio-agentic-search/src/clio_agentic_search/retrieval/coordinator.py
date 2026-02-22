"""Hybrid retrieval coordinator with capability negotiation and trace capture."""

from __future__ import annotations

import time
from dataclasses import dataclass

from clio_agentic_search.core.connectors import NamespaceConnector
from clio_agentic_search.models.contracts import CitationRecord, TraceEvent
from clio_agentic_search.retrieval.capabilities import (
    GraphSearchCapable,
    LexicalSearchCapable,
    MetadataFilterCapable,
    ScientificSearchCapable,
    ScoredChunk,
    StreamingLogCapable,
    VectorSearchCapable,
)
from clio_agentic_search.retrieval.rerank import DefaultHeuristicReranker, Reranker
from clio_agentic_search.retrieval.scientific import ScientificQueryOperators


@dataclass(frozen=True, slots=True)
class QueryResult:
    namespace: str
    query: str
    citations: list[CitationRecord]
    trace: list[TraceEvent]


@dataclass(frozen=True, slots=True)
class MultiNamespaceQueryResult:
    namespaces: tuple[str, ...]
    query: str
    citations: list[CitationRecord]
    trace: list[TraceEvent]


@dataclass(slots=True)
class RetrievalCoordinator:
    reranker: Reranker = DefaultHeuristicReranker()

    def query(
        self,
        *,
        connector: NamespaceConnector,
        query: str,
        top_k: int = 5,
        metadata_filters: dict[str, str] | None = None,
        scientific_operators: ScientificQueryOperators | None = None,
    ) -> QueryResult:
        namespace = connector.descriptor().name
        trace: list[TraceEvent] = []
        citations = self._query_single_connector(
            connector=connector,
            query=query,
            top_k=top_k,
            metadata_filters=metadata_filters or {},
            scientific_operators=scientific_operators or ScientificQueryOperators(),
            trace=trace,
        )
        return QueryResult(namespace=namespace, query=query, citations=citations, trace=trace)

    def query_namespaces(
        self,
        *,
        connectors: list[NamespaceConnector],
        query: str,
        top_k: int = 5,
        metadata_filters: dict[str, str] | None = None,
        scientific_operators: ScientificQueryOperators | None = None,
    ) -> MultiNamespaceQueryResult:
        trace: list[TraceEvent] = []
        filters = metadata_filters or {}
        operators = scientific_operators or ScientificQueryOperators()
        all_citations: list[CitationRecord] = []
        namespaces: list[str] = []

        trace.append(
            _make_trace(
                "multi_query_started",
                "multi-namespace query started",
                {"query": query, "namespace_count": str(len(connectors))},
            )
        )
        for connector in connectors:
            namespace = connector.descriptor().name
            namespaces.append(namespace)
            citations = self._query_single_connector(
                connector=connector,
                query=query,
                top_k=top_k,
                metadata_filters=filters,
                scientific_operators=operators,
                trace=trace,
            )
            all_citations.extend(citations)

        all_citations.sort(
            key=lambda citation: (
                -citation.score,
                citation.namespace,
                citation.document_id,
                citation.chunk_id,
            )
        )
        selected = all_citations[:top_k]
        trace.append(
            _make_trace(
                "multi_query_completed",
                "multi-namespace query completed",
                {"citations": str(len(selected))},
            )
        )
        return MultiNamespaceQueryResult(
            namespaces=tuple(namespaces),
            query=query,
            citations=selected,
            trace=trace,
        )

    def _query_single_connector(
        self,
        *,
        connector: NamespaceConnector,
        query: str,
        top_k: int,
        metadata_filters: dict[str, str],
        scientific_operators: ScientificQueryOperators,
        trace: list[TraceEvent],
    ) -> list[CitationRecord]:
        namespace = connector.descriptor().name
        trace.append(_make_trace("query_started", f"namespace={namespace}", {"query": query}))

        lexical: list[ScoredChunk] = []
        if isinstance(connector, LexicalSearchCapable):
            lexical = connector.search_lexical(query, top_k=top_k * 4)
        trace.append(
            _make_trace(
                "lexical_completed",
                "lexical branch finished",
                {"namespace": namespace, "candidates": str(len(lexical))},
            )
        )

        vector: list[ScoredChunk] = []
        if isinstance(connector, VectorSearchCapable):
            vector = connector.search_vector(query, top_k=top_k * 4)
        trace.append(
            _make_trace(
                "vector_completed",
                "vector branch finished",
                {"namespace": namespace, "candidates": str(len(vector))},
            )
        )

        graph: list[ScoredChunk] = []
        if isinstance(connector, GraphSearchCapable):
            graph = connector.search_graph(query, top_k=top_k * 2)
        trace.append(
            _make_trace(
                "graph_completed",
                "graph branch finished",
                {"namespace": namespace, "candidates": str(len(graph))},
            )
        )

        scientific: list[ScoredChunk] = []
        if scientific_operators.is_active() and isinstance(connector, ScientificSearchCapable):
            scientific = connector.search_scientific(
                query=query,
                top_k=top_k * 4,
                operators=scientific_operators,
            )
            trace.append(
                _make_trace(
                    "scientific_completed",
                    "scientific branch finished",
                    {"namespace": namespace, "candidates": str(len(scientific))},
                )
            )

        merged = self._merge_candidates(
            lexical=lexical,
            vector=vector,
            graph=graph,
            scientific=scientific,
        )
        if scientific_operators.is_active() and isinstance(connector, ScientificSearchCapable):
            matched_scientific_ids = {candidate.chunk_id for candidate in scientific}
            merged = [
                candidate for candidate in merged if candidate.chunk_id in matched_scientific_ids
            ]
            trace.append(
                _make_trace(
                    "scientific_filter_completed",
                    "scientific operator filtering finished",
                    {"namespace": namespace, "candidates": str(len(merged))},
                )
            )
        trace.append(
            _make_trace(
                "merge_completed",
                "hybrid merge finished",
                {"namespace": namespace, "candidates": str(len(merged))},
            )
        )

        filtered = merged
        if isinstance(connector, MetadataFilterCapable):
            filtered = connector.filter_metadata(merged, required=metadata_filters)
        trace.append(
            _make_trace(
                "metadata_completed",
                "metadata filtering finished",
                {
                    "namespace": namespace,
                    "candidates": str(len(filtered)),
                    "filters": str(len(metadata_filters)),
                },
            )
        )

        if isinstance(connector, StreamingLogCapable):
            log_messages = connector.stream_logs(namespace=namespace, limit=10)
            trace.append(
                _make_trace(
                    "log_stream_completed",
                    "log stream consumed",
                    {"namespace": namespace, "messages": str(len(log_messages))},
                )
            )

        reranked = self.reranker.rerank(query=query, candidates=filtered)
        trace.append(
            _make_trace(
                "rerank_completed",
                "reranking finished",
                {"namespace": namespace, "candidates": str(len(reranked))},
            )
        )

        selected = reranked[:top_k]
        citations = [connector.build_citation(chunk) for chunk in selected]
        trace.append(
            _make_trace(
                "query_completed",
                "query finished",
                {"namespace": namespace, "citations": str(len(citations))},
            )
        )
        return citations

    @staticmethod
    def _merge_candidates(
        *,
        lexical: list[ScoredChunk],
        vector: list[ScoredChunk],
        graph: list[ScoredChunk],
        scientific: list[ScoredChunk],
    ) -> list[ScoredChunk]:
        merged_by_chunk: dict[str, ScoredChunk] = {}
        for candidate in lexical:
            merged_by_chunk[candidate.chunk_id] = candidate

        for candidate in vector:
            existing = merged_by_chunk.get(candidate.chunk_id)
            if existing is None:
                merged_by_chunk[candidate.chunk_id] = candidate
                continue
            merged_by_chunk[candidate.chunk_id] = ScoredChunk(
                chunk_id=existing.chunk_id,
                document_id=existing.document_id,
                text=existing.text,
                lexical_score=existing.lexical_score,
                vector_score=max(existing.vector_score, candidate.vector_score),
                metadata_score=existing.metadata_score,
            )

        for candidate in graph:
            existing = merged_by_chunk.get(candidate.chunk_id)
            if existing is None:
                merged_by_chunk[candidate.chunk_id] = candidate
                continue
            merged_by_chunk[candidate.chunk_id] = ScoredChunk(
                chunk_id=existing.chunk_id,
                document_id=existing.document_id,
                text=existing.text,
                lexical_score=existing.lexical_score,
                vector_score=existing.vector_score,
                metadata_score=max(existing.metadata_score, candidate.metadata_score),
            )

        for candidate in scientific:
            existing = merged_by_chunk.get(candidate.chunk_id)
            if existing is None:
                merged_by_chunk[candidate.chunk_id] = candidate
                continue
            merged_by_chunk[candidate.chunk_id] = ScoredChunk(
                chunk_id=existing.chunk_id,
                document_id=existing.document_id,
                text=existing.text,
                lexical_score=existing.lexical_score,
                vector_score=existing.vector_score,
                metadata_score=max(existing.metadata_score, candidate.metadata_score),
            )

        return list(merged_by_chunk.values())


def _make_trace(stage: str, message: str, attributes: dict[str, str]) -> TraceEvent:
    return TraceEvent(
        stage=stage,
        message=message,
        timestamp_ns=time.time_ns(),
        attributes=attributes,
    )
