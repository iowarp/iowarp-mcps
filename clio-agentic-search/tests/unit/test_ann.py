from __future__ import annotations

from clio_agentic_search.retrieval.ann import build_ann_adapter


def test_exact_adapter_respects_candidate_filter() -> None:
    adapter = build_ann_adapter(backend="exact", dimensions=3, shard_count=4)
    adapter.build(
        {
            "a": (1.0, 0.0, 0.0),
            "b": (0.9, 0.1, 0.0),
            "c": (0.0, 1.0, 0.0),
        }
    )
    results = adapter.query(
        query_vector=(1.0, 0.0, 0.0),
        top_k=2,
        candidate_ids={"b", "c"},
    )
    assert [item.chunk_id for item in results] == ["b"]


def test_hnsw_backend_falls_back_or_returns_results() -> None:
    adapter = build_ann_adapter(backend="hnsw", dimensions=2, shard_count=8)
    adapter.build({"x": (1.0, 0.0), "y": (0.0, 1.0)})
    results = adapter.query(query_vector=(1.0, 0.0), top_k=1)
    assert results
    assert results[0].chunk_id == "x"
