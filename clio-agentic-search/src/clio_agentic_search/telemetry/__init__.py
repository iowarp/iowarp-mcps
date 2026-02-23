"""Telemetry: tracing and metrics with graceful fallback when optional deps missing."""

from __future__ import annotations

import os
import threading
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass, field
from typing import Any, Protocol, cast

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
    """In-process metrics with Prometheus exposition output."""

    # Histogram bucket boundaries (seconds)
    _QUERY_BUCKETS: tuple[float, ...] = (0.01, 0.025, 0.05, 0.1, 0.2, 0.5, 1.0, 5.0, float("inf"))
    _INDEX_BUCKETS: tuple[float, ...] = (0.1, 0.5, 1.0, 5.0, 10.0, 30.0, 60.0, float("inf"))
    _backend: _MetricsBackend = field(init=False)
    _lock: threading.Lock = field(default_factory=threading.Lock, init=False, repr=False)

    def __post_init__(self) -> None:
        self._backend = _build_metrics_backend(
            query_buckets=self._QUERY_BUCKETS,
            index_buckets=self._INDEX_BUCKETS,
        )

    def inc_query_count(self) -> None:
        with self._lock:
            self._backend.inc_query_count()

    def observe_query_latency(self, seconds: float) -> None:
        with self._lock:
            self._backend.observe_query_latency(seconds)

    def observe_index_duration(self, seconds: float) -> None:
        with self._lock:
            self._backend.observe_index_duration(seconds)

    def export(self) -> str:
        with self._lock:
            return self._backend.export()


class _MetricsBackend(Protocol):
    def inc_query_count(self) -> None: ...

    def observe_query_latency(self, seconds: float) -> None: ...

    def observe_index_duration(self, seconds: float) -> None: ...

    def export(self) -> str: ...


@dataclass
class _FallbackMetricsBackend:
    query_buckets: tuple[float, ...]
    index_buckets: tuple[float, ...]
    query_count: int = 0
    query_latency_sum: float = 0.0
    query_latency_count: int = 0
    query_latency_buckets: dict[float, int] = field(default_factory=dict)
    index_duration_sum: float = 0.0
    index_duration_count: int = 0
    index_duration_buckets: dict[float, int] = field(default_factory=dict)

    def __post_init__(self) -> None:
        for boundary in self.query_buckets:
            self.query_latency_buckets[boundary] = 0
        for boundary in self.index_buckets:
            self.index_duration_buckets[boundary] = 0

    def inc_query_count(self) -> None:
        self.query_count += 1

    def observe_query_latency(self, seconds: float) -> None:
        self.query_latency_sum += seconds
        self.query_latency_count += 1
        for boundary in self.query_buckets:
            if seconds <= boundary:
                self.query_latency_buckets[boundary] += 1
                break

    def observe_index_duration(self, seconds: float) -> None:
        self.index_duration_sum += seconds
        self.index_duration_count += 1
        for boundary in self.index_buckets:
            if seconds <= boundary:
                self.index_duration_buckets[boundary] += 1
                break

    def export(self) -> str:
        lines: list[str] = []
        lines.append("# HELP query_count Total number of queries served.")
        lines.append("# TYPE query_count counter")
        lines.append(f"query_count {self.query_count}")
        lines.append("")
        lines.append("# HELP query_latency_seconds Query latency histogram.")
        lines.append("# TYPE query_latency_seconds histogram")
        query_cumulative = 0
        for boundary in self.query_buckets:
            query_cumulative += self.query_latency_buckets[boundary]
            upper = "+Inf" if boundary == float("inf") else f"{boundary}"
            lines.append(f'query_latency_seconds_bucket{{le="{upper}"}} {query_cumulative}')
        lines.append(f"query_latency_seconds_sum {self.query_latency_sum:.6f}")
        lines.append(f"query_latency_seconds_count {self.query_latency_count}")
        lines.append("")
        lines.append("# HELP index_duration_seconds Index duration histogram.")
        lines.append("# TYPE index_duration_seconds histogram")
        index_cumulative = 0
        for boundary in self.index_buckets:
            index_cumulative += self.index_duration_buckets[boundary]
            upper = "+Inf" if boundary == float("inf") else f"{boundary}"
            lines.append(f'index_duration_seconds_bucket{{le="{upper}"}} {index_cumulative}')
        lines.append(f"index_duration_seconds_sum {self.index_duration_sum:.6f}")
        lines.append(f"index_duration_seconds_count {self.index_duration_count}")
        lines.append("")
        return "\n".join(lines)


class _PrometheusClientMetricsBackend:
    def __init__(
        self,
        *,
        query_buckets: tuple[float, ...],
        index_buckets: tuple[float, ...],
    ) -> None:
        from prometheus_client import CollectorRegistry, Counter, Histogram, generate_latest

        finite_query_buckets = tuple(
            boundary for boundary in query_buckets if boundary != float("inf")
        )
        finite_index_buckets = tuple(
            boundary for boundary in index_buckets if boundary != float("inf")
        )
        self._generate_latest = generate_latest
        self._registry = CollectorRegistry()
        self._query_count = Counter(
            "query_count",
            "Total number of queries served.",
            registry=self._registry,
        )
        self._query_latency = Histogram(
            "query_latency_seconds",
            "Query latency histogram.",
            buckets=finite_query_buckets,
            registry=self._registry,
        )
        self._index_duration = Histogram(
            "index_duration_seconds",
            "Index duration histogram.",
            buckets=finite_index_buckets,
            registry=self._registry,
        )

    def inc_query_count(self) -> None:
        self._query_count.inc()

    def observe_query_latency(self, seconds: float) -> None:
        self._query_latency.observe(seconds)

    def observe_index_duration(self, seconds: float) -> None:
        self._index_duration.observe(seconds)

    def export(self) -> str:
        raw = cast(bytes, self._generate_latest(self._registry))
        return raw.decode("utf-8")


def _build_metrics_backend(
    *,
    query_buckets: tuple[float, ...],
    index_buckets: tuple[float, ...],
) -> _MetricsBackend:
    try:
        return _PrometheusClientMetricsBackend(
            query_buckets=query_buckets,
            index_buckets=index_buckets,
        )
    except ImportError:
        return _FallbackMetricsBackend(
            query_buckets=query_buckets,
            index_buckets=index_buckets,
        )


_metrics_instance: Metrics | None = None


def get_metrics() -> Metrics:
    global _metrics_instance  # noqa: PLW0603
    if _metrics_instance is None:
        _metrics_instance = Metrics()
    return _metrics_instance


def reset_telemetry() -> None:
    global _metrics_instance, _tracer_instance  # noqa: PLW0603
    _metrics_instance = None
    _tracer_instance = None


__all__ = [
    "Metrics",
    "NoopTracer",
    "OTelTracer",
    "SpanContext",
    "Tracer",
    "get_metrics",
    "get_tracer",
    "reset_telemetry",
]
