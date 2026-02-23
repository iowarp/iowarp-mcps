"""Tests for telemetry: metrics export and tracer fallback."""

from __future__ import annotations

from clio_agentic_search.telemetry import Metrics, NoopTracer


class TestMetrics:
    def test_initial_query_count_zero(self) -> None:
        m = Metrics()
        assert "query_count 0" in m.export()

    def test_inc_query_count(self) -> None:
        m = Metrics()
        m.inc_query_count()
        m.inc_query_count()
        assert "query_count 2" in m.export()

    def test_observe_query_latency(self) -> None:
        m = Metrics()
        m.observe_query_latency(0.05)
        output = m.export()
        assert "query_latency_seconds_sum" in output
        assert "query_latency_seconds_count 0" in output  # count tracks via inc_query_count

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
        # le=0.01 bucket should have 1 (only the 0.005)
        assert 'query_latency_seconds_bucket{le="0.01"} 1' in output
        # le=0.05 should be cumulative: 2
        assert 'query_latency_seconds_bucket{le="0.05"} 2' in output

    def test_export_format_prometheus_compatible(self) -> None:
        m = Metrics()
        output = m.export()
        assert "# HELP query_count" in output
        assert "# TYPE query_count counter" in output
        assert "# TYPE query_latency_seconds histogram" in output
        assert "# TYPE index_duration_seconds histogram" in output


class TestNoopTracer:
    def test_start_span_returns_context_manager(self) -> None:
        tracer = NoopTracer()
        with tracer.start_span("test") as span:
            span.set_attribute("key", "value")  # should not raise
