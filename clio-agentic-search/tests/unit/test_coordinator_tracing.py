from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass, field

from clio_agentic_search.core.connectors import IndexReport
from clio_agentic_search.models.contracts import CitationRecord, NamespaceDescriptor
from clio_agentic_search.retrieval.capabilities import ScoredChunk
from clio_agentic_search.retrieval.coordinator import RetrievalCoordinator


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
    namespace: str = "ns"

    def descriptor(self) -> NamespaceDescriptor:
        return NamespaceDescriptor(name=self.namespace, connector_type="dummy", root_uri="dummy://")

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
            uri="dummy://citation",
            snippet=chunk.text,
            score=chunk.combined_score,
        )


def test_trace_events_emit_child_spans() -> None:
    tracer = _RecordingTracer()
    connector = _MinimalConnector()
    coordinator = RetrievalCoordinator(tracer=tracer)

    result = coordinator.query(connector=connector, query="test query", top_k=3)

    assert result.trace
    assert len(tracer.spans) == len(result.trace)
    assert all(span.name.startswith("retrieval.") for span in tracer.spans)
    assert all("retrieval.stage" in span.attributes for span in tracer.spans)
