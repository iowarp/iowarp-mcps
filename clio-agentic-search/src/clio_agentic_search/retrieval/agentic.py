"""Multi-hop agentic retrieval with iterative query refinement."""

from __future__ import annotations

import time
from dataclasses import dataclass, field

from clio_agentic_search.core.connectors import NamespaceConnector
from clio_agentic_search.models.contracts import CitationRecord, TraceEvent
from clio_agentic_search.retrieval.capabilities import CorpusProfileCapable
from clio_agentic_search.retrieval.coordinator import RetrievalCoordinator
from clio_agentic_search.retrieval.corpus_profile import CorpusProfile
from clio_agentic_search.retrieval.query_rewriter import (
    FallbackQueryRewriter,
    QueryRewriter,
    RewriteResult,
)
from clio_agentic_search.retrieval.scientific import ScientificQueryOperators


@dataclass(frozen=True, slots=True)
class HopRecord:
    hop_number: int
    query: str
    strategy: str
    reasoning: str
    citations_found: int
    new_citations: int


@dataclass(frozen=True, slots=True)
class TokenUsage:
    """Cumulative LLM token usage across all hops."""

    total_input_tokens: int = 0
    total_output_tokens: int = 0
    llm_calls: int = 0


@dataclass(frozen=True, slots=True)
class AgenticQueryResult:
    namespace: str
    original_query: str
    final_query: str
    citations: list[CitationRecord]
    hops: list[HopRecord]
    trace: list[TraceEvent]
    total_hops: int
    strategy_used: str = "default"
    token_usage: TokenUsage = field(default_factory=TokenUsage)


@dataclass(slots=True)
class AgenticRetriever:
    coordinator: RetrievalCoordinator = field(default_factory=RetrievalCoordinator)
    rewriter: QueryRewriter | FallbackQueryRewriter = field(default_factory=FallbackQueryRewriter)
    max_hops: int = 3
    min_score_threshold: float = 0.5
    convergence_threshold: int = 0  # stop if no new citations found

    def query(
        self,
        *,
        connector: NamespaceConnector,
        query: str,
        top_k: int = 5,
        metadata_filters: dict[str, str] | None = None,
        scientific_operators: ScientificQueryOperators | None = None,
    ) -> AgenticQueryResult:
        """Run multi-hop agentic retrieval against a single namespace."""
        namespace = connector.descriptor().name
        trace: list[TraceEvent] = []
        hops: list[HopRecord] = []
        all_citations: dict[str, CitationRecord] = {}  # chunk_id -> best citation
        current_query = query

        # --- Metadata-adaptive strategy selection ---
        strategy_used = "default"
        profile: CorpusProfile | None = None
        if isinstance(connector, CorpusProfileCapable):
            profile = connector.corpus_profile()
            if profile.metadata_density > 0.5:
                strategy_used = "metadata_rich"
            elif profile.metadata_density < 0.1:
                strategy_used = "metadata_sparse"

        self._append_trace(
            trace=trace,
            stage="agentic_started",
            message="agentic retrieval loop started",
            attributes={
                "query": query,
                "namespace": namespace,
                "max_hops": str(self.max_hops),
                "strategy": strategy_used,
                "metadata_density": f"{profile.metadata_density:.2f}" if profile else "n/a",
            },
        )

        for hop_number in range(1, self.max_hops + 1):
            self._append_trace(
                trace=trace,
                stage="hop_started",
                message=f"hop {hop_number} started",
                attributes={
                    "hop": str(hop_number),
                    "query": current_query,
                },
            )

            result = self.coordinator.query(
                connector=connector,
                query=current_query,
                top_k=top_k,
                metadata_filters=metadata_filters,
                scientific_operators=scientific_operators,
            )
            trace.extend(result.trace)

            # Merge citations — keep highest score per chunk_id.
            new_count = 0
            for citation in result.citations:
                existing = all_citations.get(citation.chunk_id)
                if existing is None:
                    all_citations[citation.chunk_id] = citation
                    new_count += 1
                elif citation.score > existing.score:
                    all_citations[citation.chunk_id] = citation

            hop_record = HopRecord(
                hop_number=hop_number,
                query=current_query,
                strategy="initial" if hop_number == 1 else "rewrite",
                reasoning="",
                citations_found=len(result.citations),
                new_citations=new_count,
            )

            self._append_trace(
                trace=trace,
                stage="hop_completed",
                message=f"hop {hop_number} completed",
                attributes={
                    "citations_found": str(len(result.citations)),
                    "new_citations": str(new_count),
                    "total_accumulated": str(len(all_citations)),
                },
            )

            # Check if best results meet score threshold.
            max_score = max((c.score for c in result.citations), default=0.0)
            results_sufficient = max_score >= self.min_score_threshold and len(result.citations) > 0

            # Decide whether to continue.
            if hop_number >= self.max_hops:
                hops.append(hop_record)
                break

            # Convergence: no new citations.
            if new_count <= self.convergence_threshold and hop_number > 1:
                hops.append(
                    HopRecord(
                        hop_number=hop_record.hop_number,
                        query=hop_record.query,
                        strategy="converged",
                        reasoning="No new citations found; stopping.",
                        citations_found=hop_record.citations_found,
                        new_citations=hop_record.new_citations,
                    )
                )
                self._append_trace(
                    trace=trace,
                    stage="convergence_reached",
                    message="no new citations; stopping",
                    attributes={"hop": str(hop_number)},
                )
                break

            # Ask the rewriter whether/how to refine.
            snippets = [c.snippet for c in result.citations if c.snippet]
            rewrite_result: RewriteResult = self.rewriter.rewrite(
                query=current_query,
                retrieved_snippets=snippets,
                hop_number=hop_number,
                max_hops=self.max_hops,
            )

            hop_record = HopRecord(
                hop_number=hop_record.hop_number,
                query=hop_record.query,
                strategy=rewrite_result.strategy,
                reasoning=rewrite_result.reasoning,
                citations_found=hop_record.citations_found,
                new_citations=hop_record.new_citations,
            )
            hops.append(hop_record)

            self._append_trace(
                trace=trace,
                stage="rewrite_completed",
                message=f"rewriter chose strategy={rewrite_result.strategy}",
                attributes={
                    "hop": str(hop_number),
                    "strategy": rewrite_result.strategy,
                    "rewritten_query": rewrite_result.rewritten_query,
                    "reasoning": rewrite_result.reasoning,
                },
            )

            if rewrite_result.strategy == "done":
                break
            if results_sufficient and rewrite_result.strategy == "done":
                break

            current_query = rewrite_result.rewritten_query
            continue

        # Final citation list sorted by score descending, capped at top_k.
        final_citations = sorted(
            all_citations.values(),
            key=lambda c: (-c.score, c.namespace, c.document_id, c.chunk_id),
        )[:top_k]

        self._append_trace(
            trace=trace,
            stage="agentic_completed",
            message="agentic retrieval loop completed",
            attributes={
                "total_hops": str(len(hops)),
                "final_citations": str(len(final_citations)),
                "final_query": current_query,
            },
        )

        # Aggregate token usage from rewrite results.
        total_input = sum(getattr(h, "_input_tokens", 0) for h in hops)
        total_output = sum(getattr(h, "_output_tokens", 0) for h in hops)
        llm_calls = sum(1 for h in hops if h.strategy not in ("initial", "converged"))

        return AgenticQueryResult(
            namespace=namespace,
            original_query=query,
            final_query=current_query,
            citations=final_citations,
            hops=hops,
            trace=trace,
            total_hops=len(hops),
            strategy_used=strategy_used,
            token_usage=TokenUsage(
                total_input_tokens=total_input,
                total_output_tokens=total_output,
                llm_calls=llm_calls,
            ),
        )

    def query_namespaces(
        self,
        *,
        connectors: list[NamespaceConnector],
        query: str,
        top_k: int = 5,
        metadata_filters: dict[str, str] | None = None,
        scientific_operators: ScientificQueryOperators | None = None,
    ) -> AgenticQueryResult:
        """Run multi-hop agentic retrieval across multiple namespaces."""
        trace: list[TraceEvent] = []
        hops: list[HopRecord] = []
        all_citations: dict[str, CitationRecord] = {}
        current_query = query
        namespaces = [c.descriptor().name for c in connectors]

        # --- Namespace routing: score and rank connectors ---
        ops = scientific_operators or ScientificQueryOperators()
        scored_connectors: list[tuple[float, NamespaceConnector]] = []
        for conn in connectors:
            score = 0.5  # base score for any non-empty namespace
            if isinstance(conn, CorpusProfileCapable):
                p = conn.corpus_profile()
                if p.document_count > 0:
                    score += 0.5
                if ops.is_active() and p.has_measurements:
                    score += 2.0
                if ops.formula is not None and p.has_formulas:
                    score += 1.5
                if p.metadata_density > 0.3:
                    score += 1.0
            scored_connectors.append((score, conn))

        # Sort descending by score; on first hop query only top-ranked.
        scored_connectors.sort(key=lambda sc: -sc[0])
        ranked_connectors = [conn for _, conn in scored_connectors]
        routing_order = [conn.descriptor().name for conn in ranked_connectors]

        self._append_trace(
            trace=trace,
            stage="agentic_multi_started",
            message="agentic multi-namespace retrieval started",
            attributes={
                "query": query,
                "namespaces": ",".join(namespaces),
                "routing_order": ",".join(routing_order),
                "max_hops": str(self.max_hops),
            },
        )

        for hop_number in range(1, self.max_hops + 1):
            # On hop 1, query only the top-ranked namespace(s);
            # on subsequent hops, widen to all namespaces.
            if hop_number == 1 and len(ranked_connectors) > 1:
                active_connectors = ranked_connectors[:1]
            else:
                active_connectors = ranked_connectors

            self._append_trace(
                trace=trace,
                stage="hop_started",
                message=f"hop {hop_number} started (multi-namespace)",
                attributes={
                    "hop": str(hop_number),
                    "query": current_query,
                    "active_namespaces": ",".join(c.descriptor().name for c in active_connectors),
                },
            )

            result = self.coordinator.query_namespaces(
                connectors=active_connectors,
                query=current_query,
                top_k=top_k,
                metadata_filters=metadata_filters,
                scientific_operators=scientific_operators,
            )
            trace.extend(result.trace)

            new_count = 0
            for citation in result.citations:
                existing = all_citations.get(citation.chunk_id)
                if existing is None:
                    all_citations[citation.chunk_id] = citation
                    new_count += 1
                elif citation.score > existing.score:
                    all_citations[citation.chunk_id] = citation

            hop_record = HopRecord(
                hop_number=hop_number,
                query=current_query,
                strategy="initial" if hop_number == 1 else "rewrite",
                reasoning="",
                citations_found=len(result.citations),
                new_citations=new_count,
            )

            self._append_trace(
                trace=trace,
                stage="hop_completed",
                message=f"hop {hop_number} completed (multi-namespace)",
                attributes={
                    "citations_found": str(len(result.citations)),
                    "new_citations": str(new_count),
                    "total_accumulated": str(len(all_citations)),
                },
            )

            if hop_number >= self.max_hops:
                hops.append(hop_record)
                break

            if new_count <= self.convergence_threshold and hop_number > 1:
                hops.append(
                    HopRecord(
                        hop_number=hop_record.hop_number,
                        query=hop_record.query,
                        strategy="converged",
                        reasoning="No new citations found; stopping.",
                        citations_found=hop_record.citations_found,
                        new_citations=hop_record.new_citations,
                    )
                )
                self._append_trace(
                    trace=trace,
                    stage="convergence_reached",
                    message="no new citations; stopping (multi-namespace)",
                    attributes={"hop": str(hop_number)},
                )
                break

            snippets = [c.snippet for c in result.citations if c.snippet]
            rewrite_result: RewriteResult = self.rewriter.rewrite(
                query=current_query,
                retrieved_snippets=snippets,
                hop_number=hop_number,
                max_hops=self.max_hops,
            )

            hop_record = HopRecord(
                hop_number=hop_record.hop_number,
                query=hop_record.query,
                strategy=rewrite_result.strategy,
                reasoning=rewrite_result.reasoning,
                citations_found=hop_record.citations_found,
                new_citations=hop_record.new_citations,
            )
            hops.append(hop_record)

            self._append_trace(
                trace=trace,
                stage="rewrite_completed",
                message=f"rewriter chose strategy={rewrite_result.strategy}",
                attributes={
                    "hop": str(hop_number),
                    "strategy": rewrite_result.strategy,
                    "rewritten_query": rewrite_result.rewritten_query,
                    "reasoning": rewrite_result.reasoning,
                },
            )

            if rewrite_result.strategy == "done":
                break

            current_query = rewrite_result.rewritten_query
            continue

        final_citations = sorted(
            all_citations.values(),
            key=lambda c: (-c.score, c.namespace, c.document_id, c.chunk_id),
        )[:top_k]

        self._append_trace(
            trace=trace,
            stage="agentic_multi_completed",
            message="agentic multi-namespace retrieval completed",
            attributes={
                "total_hops": str(len(hops)),
                "final_citations": str(len(final_citations)),
                "final_query": current_query,
            },
        )

        llm_calls = sum(1 for h in hops if h.strategy not in ("initial", "converged"))

        return AgenticQueryResult(
            namespace=",".join(namespaces),
            original_query=query,
            final_query=current_query,
            citations=final_citations,
            hops=hops,
            trace=trace,
            total_hops=len(hops),
            strategy_used="routed",
            token_usage=TokenUsage(
                total_input_tokens=0,
                total_output_tokens=0,
                llm_calls=llm_calls,
            ),
        )

    @staticmethod
    def _append_trace(
        *,
        trace: list[TraceEvent],
        stage: str,
        message: str,
        attributes: dict[str, str],
    ) -> None:
        trace.append(
            TraceEvent(
                stage=stage,
                message=message,
                timestamp_ns=time.time_ns(),
                attributes=attributes,
            )
        )
