"""Load benchmarks: index time, query latency, concurrent throughput.

Run with: uv run pytest tests/benchmarks/ -v --benchmark-enable
Benchmarks are skipped by default in normal test runs.
"""

from __future__ import annotations

import os
import statistics
import time
from pathlib import Path
from typing import Any

import pytest

from clio_agentic_search.connectors.filesystem import FilesystemConnector
from clio_agentic_search.indexing.text_features import HashEmbedder
from clio_agentic_search.retrieval.coordinator import RetrievalCoordinator
from clio_agentic_search.storage import DuckDBStorage

# SLO thresholds
QUERY_P95_SLO_SECONDS = 0.200  # p95 < 200ms for 10k chunks
INDEX_SLO_CHUNKS_PER_SECOND = 50  # minimum throughput
ENFORCE_LARGE_CORPUS_SLO = os.environ.get("CLIO_ENFORCE_LARGE_SLO", "").lower() in (
    "1",
    "true",
    "yes",
)


def _generate_corpus(root: Path, num_files: int, chunk_size: int = 400) -> None:
    """Generate synthetic text files that produce approximately num_files * 1 chunk each."""
    for i in range(num_files):
        content = f"Document {i}. " + f"word{i % 100} " * (chunk_size // 8)
        (root / f"doc_{i:05d}.txt").write_text(content)


@pytest.fixture(params=[100, 1000, 10000], ids=["100_chunks", "1000_chunks", "10000_chunks"])
def corpus_size(request: Any) -> int:
    return request.param  # type: ignore[no-any-return]


@pytest.fixture
def indexed_connector(corpus_size: int, tmp_path: Path) -> FilesystemConnector:
    corpus_dir = tmp_path / "corpus"
    corpus_dir.mkdir()
    _generate_corpus(corpus_dir, corpus_size)

    db_path = tmp_path / "bench.duckdb"
    storage = DuckDBStorage(database_path=db_path)
    connector = FilesystemConnector(
        namespace="bench",
        root=corpus_dir,
        storage=storage,
        embedder=HashEmbedder(),
        embedding_model="hash16-v1",
    )
    connector.connect()
    connector.index(full_rebuild=True)
    return connector


def test_index_throughput(corpus_size: int, tmp_path: Path, benchmark: Any) -> None:
    """Measure indexing speed (files/second)."""
    corpus_dir = tmp_path / "corpus_idx"
    corpus_dir.mkdir()
    _generate_corpus(corpus_dir, corpus_size)

    db_path = tmp_path / "idx_bench.duckdb"
    storage = DuckDBStorage(database_path=db_path)
    connector = FilesystemConnector(
        namespace="bench_idx",
        root=corpus_dir,
        storage=storage,
        embedder=HashEmbedder(),
        embedding_model="hash16-v1",
    )
    connector.connect()

    def _index() -> None:
        storage.clear_namespace("bench_idx")
        connector.index(full_rebuild=True)

    benchmark(_index)


def test_query_latency(indexed_connector: FilesystemConnector, benchmark: Any) -> None:
    """Measure single query latency."""
    coordinator = RetrievalCoordinator()

    def _query() -> None:
        coordinator.query(
            connector=indexed_connector,
            query="word42 document information",
            top_k=5,
        )

    benchmark(_query)


def test_query_latency_p95(indexed_connector: FilesystemConnector, corpus_size: int) -> None:
    """Assert p95 query latency SLO."""
    coordinator = RetrievalCoordinator()
    latencies: list[float] = []
    iterations = 50

    for _ in range(iterations):
        start = time.perf_counter()
        coordinator.query(
            connector=indexed_connector,
            query="word42 document information",
            top_k=5,
        )
        latencies.append(time.perf_counter() - start)

    p50 = statistics.median(latencies)
    p95 = sorted(latencies)[int(0.95 * len(latencies))]
    p99 = sorted(latencies)[int(0.99 * len(latencies))]

    print(f"\n[{corpus_size} chunks] p50={p50:.4f}s p95={p95:.4f}s p99={p99:.4f}s")

    if corpus_size < 10000:
        assert p95 < QUERY_P95_SLO_SECONDS, (
            f"p95 latency {p95:.4f}s exceeds SLO {QUERY_P95_SLO_SECONDS}s for {corpus_size} chunks"
        )
    elif ENFORCE_LARGE_CORPUS_SLO:
        assert p95 < QUERY_P95_SLO_SECONDS, (
            f"p95 latency {p95:.4f}s exceeds SLO {QUERY_P95_SLO_SECONDS}s for {corpus_size} chunks"
        )
    else:
        pytest.skip(
            "10k-chunk p95 SLO is hardware dependent; set CLIO_ENFORCE_LARGE_SLO=1 to enforce"
        )


def test_concurrent_query_throughput(indexed_connector: FilesystemConnector) -> None:
    """Measure throughput under serialized rapid-fire load.

    DuckDB connections are not thread-safe for concurrent reads,
    so we measure rapid sequential throughput instead.
    """
    coordinator = RetrievalCoordinator()
    queries = ["word42", "document information", "word99 data", "word1 content"]
    total_queries = 40

    latencies: list[float] = []
    start = time.perf_counter()
    for i in range(total_queries):
        q_start = time.perf_counter()
        coordinator.query(
            connector=indexed_connector,
            query=queries[i % len(queries)],
            top_k=5,
        )
        latencies.append(time.perf_counter() - q_start)
    wall_time = time.perf_counter() - start

    throughput = total_queries / wall_time
    print(f"\nThroughput: {throughput:.1f} queries/s ({total_queries} queries in {wall_time:.2f}s)")
    assert throughput > 1.0, f"Throughput {throughput:.1f} q/s is unexpectedly low"
