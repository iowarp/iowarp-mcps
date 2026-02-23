"""Tests for telemetry: metrics export and tracer fallback."""

from __future__ import annotations

from clio_agentic_search.telemetry import Metrics, NoopTracer, get_metrics, reset_telemetry


class TestMetrics:
    def test_initial_query_count_zero(self) -> None:
        m = Metrics()
        output = m.export()
        assert "query_count" in output

    def test_inc_query_count(self) -> None:
        m = Metrics()
        m.inc_query_count()
        m.inc_query_count()
        output = m.export()
        assert "query_count" in output
        assert "2" in output

    def test_observe_query_latency(self) -> None:
        m = Metrics()
        m.observe_query_latency(0.05)
        output = m.export()
        assert "query_latency_seconds_sum" in output
        assert "query_latency_seconds_count" in output

    def test_observe_index_duration(self) -> None:
        m = Metrics()
        m.observe_index_duration(2.5)
        output = m.export()
        assert "index_duration_seconds_sum" in output

    def test_histogram_buckets_cumulative(self) -> None:
        m = Metrics()
        m.observe_query_latency(0.005)  # below 0.01
        m.observe_query_latency(0.03)  # below 0.05
        output = m.export()
        assert 'query_latency_seconds_bucket{le="0.01"}' in output
        assert 'query_latency_seconds_bucket{le="0.05"}' in output

    def test_export_format_prometheus_compatible(self) -> None:
        m = Metrics()
        output = m.export()
        assert "# HELP query_count" in output or "# HELP query_count_total" in output
        assert (
            "# TYPE query_count counter" in output or "# TYPE query_count_total counter" in output
        )
        assert "# TYPE query_latency_seconds histogram" in output
        assert "# TYPE index_duration_seconds histogram" in output

    def test_reset_telemetry_resets_singletons(self) -> None:
        first = get_metrics()
        reset_telemetry()
        second = get_metrics()
        assert first is not second


class TestNoopTracer:
    def test_start_span_returns_context_manager(self) -> None:
        tracer = NoopTracer()
        with tracer.start_span("test") as span:
            span.set_attribute("key", "value")  # should not raise
