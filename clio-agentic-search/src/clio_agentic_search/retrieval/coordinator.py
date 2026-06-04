"""Hybrid retrieval coordinator with capability negotiation and trace capture."""

from __future__ import annotations

import time
from dataclasses import dataclass, field

from clio_agentic_search.core.connectors import NamespaceConnector
from clio_agentic_search.models.contracts import CitationRecord, TraceEvent
from clio_agentic_search.retrieval.capabilities import (
    CorpusProfileCapable,
    GraphSearchCapable,
    LexicalSearchCapable,
    MetadataFilterCapable,
    ScientificSearchCapable,
    ScoredChunk,
    StreamingLogCapable,
    VectorSearchCapable,
)
from clio_agentic_search.retrieval.rerank import DefaultHeuristicReranker, Reranker
from clio_agentic_search.retrieval.scientific import (
    QualityFilterOperator,
    ScientificQueryOperators,
)
from clio_agentic_search.retrieval.strategy import select_branches
from clio_agentic_search.telemetry import Tracer, get_tracer


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
    tracer: Tracer = field(default_factory=get_tracer)

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

        self._append_trace(
            trace=trace,
            stage="multi_query_started",
            message="multi-namespace query started",
            attributes={"query": query, "namespace_count": str(len(connectors))},
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
        self._append_trace(
            trace=trace,
            stage="multi_query_completed",
            message="multi-namespace query completed",
            attributes={"citations": str(len(selected))},
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
        self._append_trace(
            trace=trace,
            stage="query_started",
            message=f"namespace={namespace}",
            attributes={"query": query},
        )

        # --- Intelligent branch selection via corpus profiling ---
        profile = None
        if isinstance(connector, CorpusProfileCapable):
            profile = connector.corpus_profile()

        plan = select_branches(
            query=query,
            operators=scientific_operators,
            profile=profile,
            connector_has_lexical=isinstance(connector, LexicalSearchCapable),
            connector_has_vector=isinstance(connector, VectorSearchCapable),
            connector_has_graph=isinstance(connector, GraphSearchCapable),
            connector_has_scientific=isinstance(connector, ScientificSearchCapable),
        )
        # If the plan says to apply the quality filter and the user didn't
        # specify one explicitly, inject the default QualityFilterOperator so
        # the scientific branch drops bad/missing rows automatically.
        if plan.apply_quality_filter and scientific_operators.quality_filter is None:
            scientific_operators = ScientificQueryOperators(
                numeric_range=scientific_operators.numeric_range,
                unit_match=scientific_operators.unit_match,
                formula=scientific_operators.formula,
                quality_filter=QualityFilterOperator(),
            )

        self._append_trace(
            trace=trace,
            stage="branch_plan_selected",
            message=f"branch plan: {plan.reasoning}",
            attributes={
                "namespace": namespace,
                "use_lexical": str(plan.use_lexical),
                "use_vector": str(plan.use_vector),
                "use_graph": str(plan.use_graph),
                "use_scientific": str(plan.use_scientific),
                "apply_quality_filter": str(plan.apply_quality_filter),
                "targeted_concepts": ",".join(plan.targeted_concepts),
                "schema_richness": f"{plan.schema_richness:.3f}",
                "average_quality": f"{plan.average_quality:.3f}",
                "has_profile": str(profile is not None),
            },
        )

        lexical: list[ScoredChunk] = []
        if plan.use_lexical and isinstance(connector, LexicalSearchCapable):
            lexical = connector.search_lexical(query, top_k=top_k * 4)
        self._append_trace(
            trace=trace,
            stage="lexical_completed",
            message="lexical branch finished",
            attributes={"namespace": namespace, "candidates": str(len(lexical))},
        )

        vector: list[ScoredChunk] = []
        if plan.use_vector and isinstance(connector, VectorSearchCapable):
            vector = connector.search_vector(query, top_k=top_k * 4)
        self._append_trace(
            trace=trace,
            stage="vector_completed",
            message="vector branch finished",
            attributes={"namespace": namespace, "candidates": str(len(vector))},
        )

        graph: list[ScoredChunk] = []
        if plan.use_graph and isinstance(connector, GraphSearchCapable):
            graph = connector.search_graph(query, top_k=top_k * 2)
        self._append_trace(
            trace=trace,
            stage="graph_completed",
            message="graph branch finished",
            attributes={"namespace": namespace, "candidates": str(len(graph))},
        )

        scientific: list[ScoredChunk] = []
        if plan.use_scientific and isinstance(connector, ScientificSearchCapable):
            scientific = connector.search_scientific(
                query=query,
                top_k=top_k * 4,
                operators=scientific_operators,
            )
            self._append_trace(
                trace=trace,
                stage="scientific_completed",
                message="scientific branch finished",
                attributes={"namespace": namespace, "candidates": str(len(scientific))},
            )

        merged = self._merge_candidates(
            lexical=lexical,
            vector=vector,
            graph=graph,
            scientific=scientific,
        )
        if plan.use_scientific and isinstance(connector, ScientificSearchCapable):
            matched_scientific_ids = {candidate.chunk_id for candidate in scientific}
            merged = [
                candidate for candidate in merged if candidate.chunk_id in matched_scientific_ids
            ]
            self._append_trace(
                trace=trace,
                stage="scientific_filter_completed",
                message="scientific operator filtering finished",
                attributes={"namespace": namespace, "candidates": str(len(merged))},
            )
        self._append_trace(
            trace=trace,
            stage="merge_completed",
            message="hybrid merge finished",
            attributes={"namespace": namespace, "candidates": str(len(merged))},
        )

        filtered = merged
        if isinstance(connector, MetadataFilterCapable):
            filtered = connector.filter_metadata(merged, required=metadata_filters)
        self._append_trace(
            trace=trace,
            stage="metadata_completed",
            message="metadata filtering finished",
            attributes={
                "namespace": namespace,
                "candidates": str(len(filtered)),
                "filters": str(len(metadata_filters)),
            },
        )

        if isinstance(connector, StreamingLogCapable):
            log_messages = connector.stream_logs(namespace=namespace, limit=10)
            self._append_trace(
                trace=trace,
                stage="log_stream_completed",
                message="log stream consumed",
                attributes={"namespace": namespace, "messages": str(len(log_messages))},
            )

        reranked = self.reranker.rerank(query=query, candidates=filtered)
        self._append_trace(
            trace=trace,
            stage="rerank_completed",
            message="reranking finished",
            attributes={"namespace": namespace, "candidates": str(len(reranked))},
        )

        selected = reranked[:top_k]
        citations = [connector.build_citation(chunk) for chunk in selected]
        self._append_trace(
            trace=trace,
            stage="query_completed",
            message="query finished",
            attributes={"namespace": namespace, "citations": str(len(citations))},
        )
        return citations

    def _append_trace(
        self,
        *,
        trace: list[TraceEvent],
        stage: str,
        message: str,
        attributes: dict[str, str],
    ) -> None:
        event = _make_trace(stage, message, attributes)
        trace.append(event)
        with self.tracer.start_span(f"retrieval.{stage}") as span:
            span.set_attribute("retrieval.stage", stage)
            span.set_attribute("retrieval.message", message)
            span.set_attribute("retrieval.timestamp_ns", event.timestamp_ns)
            for key, value in attributes.items():
                span.set_attribute(f"retrieval.attr.{key}", value)

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
