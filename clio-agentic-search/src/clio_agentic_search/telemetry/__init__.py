"""Telemetry: tracing and metrics with graceful fallback when optional deps missing."""

from __future__ import annotations

import os
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass, field
from typing import Any

# ---------- Tracer abstraction ----------


class SpanContext:
    """Minimal span interface used by application code."""

    def set_attribute(self, key: str, value: object) -> None:
        pass

    def __enter__(self) -> SpanContext:
        return self

    def __exit__(self, *args: object) -> None:
        pass


class NoopTracer:
    """Tracer used when OpenTelemetry is not installed."""

    @contextmanager
    def start_span(self, name: str) -> Iterator[SpanContext]:
        yield SpanContext()


class OTelTracer:
    """Thin wrapper over opentelemetry-api Tracer."""

    def __init__(self) -> None:
        from opentelemetry import trace
        from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
        from opentelemetry.sdk.trace import TracerProvider
        from opentelemetry.sdk.trace.export import BatchSpanProcessor

        endpoint = os.environ.get("OTEL_EXPORTER_OTLP_ENDPOINT", "http://localhost:4317")
        provider = TracerProvider()
        exporter = OTLPSpanExporter(endpoint=endpoint, insecure=True)
        provider.add_span_processor(BatchSpanProcessor(exporter))
        trace.set_tracer_provider(provider)
        self._tracer = trace.get_tracer("clio-agentic-search")

    @contextmanager
    def start_span(self, name: str) -> Iterator[SpanContext]:
        span = self._tracer.start_span(name)
        wrapper = _OTelSpanContext(span)
        try:
            yield wrapper
        finally:
            span.end()


class _OTelSpanContext(SpanContext):
    def __init__(self, span: Any) -> None:
        self._span = span

    def set_attribute(self, key: str, value: object) -> None:
        self._span.set_attribute(key, value)


Tracer = NoopTracer | OTelTracer

_tracer_instance: Tracer | None = None


def get_tracer() -> Tracer:
    global _tracer_instance  # noqa: PLW0603
    if _tracer_instance is not None:
        return _tracer_instance
    if os.environ.get("CLIO_OTEL_ENABLED", "").lower() in ("1", "true", "yes"):
        try:
            _tracer_instance = OTelTracer()
            return _tracer_instance
        except ImportError:
            pass
    _tracer_instance = NoopTracer()
    return _tracer_instance


# ---------- Metrics abstraction ----------


@dataclass
class Metrics:
    """In-process Prometheus-style metrics with plain-text export."""

    _query_count: int = 0
    _query_latency_sum: float = 0.0
    _query_latency_buckets: dict[float, int] = field(default_factory=dict)
    _index_duration_sum: float = 0.0
    _index_duration_buckets: dict[float, int] = field(default_factory=dict)

    # Histogram bucket boundaries (seconds)
    _QUERY_BUCKETS: tuple[float, ...] = (0.01, 0.025, 0.05, 0.1, 0.2, 0.5, 1.0, 5.0, float("inf"))
    _INDEX_BUCKETS: tuple[float, ...] = (0.1, 0.5, 1.0, 5.0, 10.0, 30.0, 60.0, float("inf"))

    def __post_init__(self) -> None:
        for b in self._QUERY_BUCKETS:
            self._query_latency_buckets[b] = 0
        for b in self._INDEX_BUCKETS:
            self._index_duration_buckets[b] = 0

    def inc_query_count(self) -> None:
        self._query_count += 1

    def observe_query_latency(self, seconds: float) -> None:
        self._query_latency_sum += seconds
        for b in self._QUERY_BUCKETS:
            if seconds <= b:
                self._query_latency_buckets[b] = self._query_latency_buckets.get(b, 0) + 1
                break

    def observe_index_duration(self, seconds: float) -> None:
        self._index_duration_sum += seconds
        for b in self._INDEX_BUCKETS:
            if seconds <= b:
                self._index_duration_buckets[b] = self._index_duration_buckets.get(b, 0) + 1
                break

    def export(self) -> str:
        lines: list[str] = []
        lines.append("# HELP query_count Total number of queries served.")
        lines.append("# TYPE query_count counter")
        lines.append(f"query_count {self._query_count}")
        lines.append("")
        lines.append("# HELP query_latency_seconds Query latency histogram.")
        lines.append("# TYPE query_latency_seconds histogram")
        cumulative = 0
        for b in self._QUERY_BUCKETS:
            cumulative += self._query_latency_buckets[b]
            le = "+Inf" if b == float("inf") else f"{b}"
            lines.append(f'query_latency_seconds_bucket{{le="{le}"}} {cumulative}')
        lines.append(f"query_latency_seconds_sum {self._query_latency_sum:.6f}")
        lines.append(f"query_latency_seconds_count {self._query_count}")
        lines.append("")
        lines.append("# HELP index_duration_seconds Index duration histogram.")
        lines.append("# TYPE index_duration_seconds histogram")
        cumulative = 0
        total_index = 0
        for b in self._INDEX_BUCKETS:
            cumulative += self._index_duration_buckets[b]
            total_index = cumulative
            le = "+Inf" if b == float("inf") else f"{b}"
            lines.append(f'index_duration_seconds_bucket{{le="{le}"}} {cumulative}')
        lines.append(f"index_duration_seconds_sum {self._index_duration_sum:.6f}")
        lines.append(f"index_duration_seconds_count {total_index}")
        lines.append("")
        return "\n".join(lines)


_metrics_instance: Metrics | None = None


def get_metrics() -> Metrics:
    global _metrics_instance  # noqa: PLW0603
    if _metrics_instance is None:
        _metrics_instance = Metrics()
    return _metrics_instance


__all__ = [
    "Metrics",
    "NoopTracer",
    "OTelTracer",
    "SpanContext",
    "Tracer",
    "get_metrics",
    "get_tracer",
]
