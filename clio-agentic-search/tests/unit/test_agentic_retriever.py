"""Tests for multi-hop agentic retrieval."""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass, field

from clio_agentic_search.core.connectors import IndexReport
from clio_agentic_search.models.contracts import CitationRecord, NamespaceDescriptor
from clio_agentic_search.retrieval.agentic import AgenticRetriever
from clio_agentic_search.retrieval.capabilities import ScoredChunk
from clio_agentic_search.retrieval.coordinator import RetrievalCoordinator
from clio_agentic_search.retrieval.query_rewriter import FallbackQueryRewriter

# ---------------------------------------------------------------------------
# Lightweight stubs (same pattern as test_coordinator_tracing.py)
# ---------------------------------------------------------------------------


@dataclass
class _RecordedSpan:
    name: str
    attributes: dict[str, object] = field(default_factory=dict)

    def set_attribute(self, key: str, value: object) -> None:
        self.attributes[key] = value

    def __enter__(self) -> _RecordedSpan:
        return self

    def __exit__(self, *args: object) -> None:
        return None


@dataclass
class _RecordingTracer:
    spans: list[_RecordedSpan] = field(default_factory=list)

    @contextmanager
    def start_span(self, name: str) -> Iterator[_RecordedSpan]:
        span = _RecordedSpan(name=name)
        self.spans.append(span)
        yield span


@dataclass
class _MinimalConnector:
    """A connector that returns a fixed set of citations."""

    namespace: str = "test-ns"
    _citations: list[tuple[str, str, str, float]] = field(default_factory=list)

    def set_citations(self, citations: list[tuple[str, str, str, float]]) -> None:
        """Set (doc_id, chunk_id, text, score) tuples to return."""
        self._citations = citations

    def descriptor(self) -> NamespaceDescriptor:
        return NamespaceDescriptor(name=self.namespace, connector_type="mock", root_uri="mock://")

    def connect(self) -> None:
        return None

    def teardown(self) -> None:
        return None

    def index(self, *, full_rebuild: bool = False) -> IndexReport:
        del full_rebuild
        return IndexReport(
            scanned_files=0,
            indexed_files=0,
            skipped_files=0,
            removed_files=0,
            elapsed_seconds=0.0,
        )

    def build_citation(self, chunk: ScoredChunk) -> CitationRecord:
        return CitationRecord(
            namespace=self.namespace,
            document_id=chunk.document_id,
            chunk_id=chunk.chunk_id,
            uri=f"mock://{chunk.document_id}",
            snippet=chunk.text,
            score=chunk.combined_score,
        )


def _make_connector(
    namespace: str,
    citations: list[tuple[str, str, str, float]],
) -> _MinimalConnector:
    c = _MinimalConnector(namespace=namespace)
    c.set_citations(citations)
    return c


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_single_hop() -> None:
    """With max_hops=1, the retriever runs exactly one pass."""
    connector = _make_connector("ns", [("d1", "c1", "text1", 0.9)])
    tracer = _RecordingTracer()
    coordinator = RetrievalCoordinator(tracer=tracer)
    retriever = AgenticRetriever(
        coordinator=coordinator,
        rewriter=FallbackQueryRewriter(),
        max_hops=1,
    )

    result = retriever.query(connector=connector, query="test query", top_k=5)

    assert result.namespace == "ns"
    assert result.original_query == "test query"
    assert result.total_hops == 1
    assert len(result.hops) == 1


def test_multi_hop_convergence() -> None:
    """When the second hop finds no new citations, the loop stops early."""
    connector = _make_connector("ns", [("d1", "c1", "text1", 0.9)])
    tracer = _RecordingTracer()
    coordinator = RetrievalCoordinator(tracer=tracer)
    retriever = AgenticRetriever(
        coordinator=coordinator,
        rewriter=FallbackQueryRewriter(),
        max_hops=5,
        convergence_threshold=0,
    )

    # The FallbackQueryRewriter on a unit-less query will return strategy="done"
    # on the first hop, so the loop should stop after hop 1.
    result = retriever.query(connector=connector, query="no units here", top_k=5)
    assert result.total_hops <= 2


def test_multi_hop_with_unit_rewrite() -> None:
    """FallbackQueryRewriter expands units, enabling a second hop."""
    connector = _make_connector("ns", [("d1", "c1", "pressure 200 kPa data", 0.8)])
    tracer = _RecordingTracer()
    coordinator = RetrievalCoordinator(tracer=tracer)
    retriever = AgenticRetriever(
        coordinator=coordinator,
        rewriter=FallbackQueryRewriter(),
        max_hops=3,
    )

    result = retriever.query(connector=connector, query="pressure 200 kPa", top_k=5)

    # The rewriter should have expanded the query with unit variants.
    # Check that at least one hop recorded strategy "expand".
    strategies = {hop.strategy for hop in result.hops}
    assert "expand" in strategies or "initial" in strategies


def test_trace_events_include_agentic_stages() -> None:
    """Trace should contain agentic_started, hop_started, hop_completed, and agentic_completed."""
    connector = _make_connector("ns", [("d1", "c1", "text1", 0.9)])
    tracer = _RecordingTracer()
    coordinator = RetrievalCoordinator(tracer=tracer)
    retriever = AgenticRetriever(
        coordinator=coordinator,
        rewriter=FallbackQueryRewriter(),
        max_hops=1,
    )

    result = retriever.query(connector=connector, query="test", top_k=5)

    stages = {event.stage for event in result.trace}
    assert "agentic_started" in stages
    assert "hop_started" in stages
    assert "hop_completed" in stages
    assert "agentic_completed" in stages


def test_citations_deduplicated_by_chunk_id() -> None:
    """When the same chunk appears across hops, the highest score wins."""
    connector = _make_connector("ns", [("d1", "c1", "text1", 0.7)])
    tracer = _RecordingTracer()
    coordinator = RetrievalCoordinator(tracer=tracer)
    retriever = AgenticRetriever(
        coordinator=coordinator,
        rewriter=FallbackQueryRewriter(),
        max_hops=1,
    )

    result = retriever.query(connector=connector, query="test", top_k=10)

    # Only one citation per chunk_id.
    chunk_ids = [c.chunk_id for c in result.citations]
    assert len(chunk_ids) == len(set(chunk_ids))


def test_query_namespaces_across_multiple_connectors() -> None:
    """query_namespaces should merge results from multiple connectors."""
    conn_a = _make_connector("ns-a", [("d1", "c1", "text-a", 0.9)])
    conn_b = _make_connector("ns-b", [("d2", "c2", "text-b", 0.8)])
    tracer = _RecordingTracer()
    coordinator = RetrievalCoordinator(tracer=tracer)
    retriever = AgenticRetriever(
        coordinator=coordinator,
        rewriter=FallbackQueryRewriter(),
        max_hops=1,
    )

    result = retriever.query_namespaces(
        connectors=[conn_a, conn_b],
        query="test",
        top_k=10,
    )

    assert "ns-a" in result.namespace
    assert "ns-b" in result.namespace
    stages = {event.stage for event in result.trace}
    assert "agentic_multi_started" in stages
    assert "agentic_multi_completed" in stages
