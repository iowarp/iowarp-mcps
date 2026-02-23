"""Approximate nearest-neighbor adapters for connector vector search."""

from __future__ import annotations

import hashlib
import heapq
import importlib
from dataclasses import dataclass, field
from typing import Any, Protocol

from clio_agentic_search.indexing.text_features import cosine_similarity


@dataclass(frozen=True, slots=True)
class AnnResult:
    chunk_id: str
    score: float


class ANNAdapter(Protocol):
    def build(self, embeddings: dict[str, tuple[float, ...]]) -> None:
        """Build index state from embeddings keyed by chunk id."""

    def query(
        self,
        *,
        query_vector: tuple[float, ...],
        top_k: int,
        candidate_ids: set[str] | None = None,
    ) -> list[AnnResult]:
        """Query nearest neighbors, optionally constrained to candidates."""


def _stable_shard_id(chunk_id: str, shard_count: int) -> int:
    digest = hashlib.sha1(chunk_id.encode("utf-8")).hexdigest()
    return int(digest[:8], 16) % shard_count


@dataclass(slots=True)
class ExactANNAdapter:
    """Exact cosine similarity scorer with sharded embedding state."""

    shard_count: int = 16
    _shards: tuple[dict[str, tuple[float, ...]], ...] = field(default_factory=tuple, init=False)

    def build(self, embeddings: dict[str, tuple[float, ...]]) -> None:
        shards = [dict[str, tuple[float, ...]]() for _ in range(max(1, self.shard_count))]
        for chunk_id, vector in embeddings.items():
            shard_id = _stable_shard_id(chunk_id, len(shards))
            shards[shard_id][chunk_id] = vector
        self._shards = tuple(shards)

    def query(
        self,
        *,
        query_vector: tuple[float, ...],
        top_k: int,
        candidate_ids: set[str] | None = None,
    ) -> list[AnnResult]:
        if top_k <= 0:
            return []
        if not self._shards:
            return []
        best: list[tuple[float, str]] = []
        if candidate_ids is None:
            for shard in self._shards:
                for chunk_id, vector in shard.items():
                    _push_best(best, top_k, chunk_id, query_vector, vector)
        else:
            for chunk_id in candidate_ids:
                shard = self._shards[_stable_shard_id(chunk_id, len(self._shards))]
                vector_candidate = shard.get(chunk_id)
                if vector_candidate is None:
                    continue
                _push_best(best, top_k, chunk_id, query_vector, vector_candidate)
        return [
            AnnResult(chunk_id=chunk_id, score=score)
            for score, chunk_id in sorted(best, key=lambda item: (-item[0], item[1]))
        ]


def _push_best(
    best: list[tuple[float, str]],
    top_k: int,
    chunk_id: str,
    query_vector: tuple[float, ...],
    vector: tuple[float, ...],
) -> None:
    similarity = cosine_similarity(query_vector, vector)
    if similarity <= 0.0:
        return
    if len(best) < top_k:
        heapq.heappush(best, (similarity, chunk_id))
        return
    if similarity > best[0][0]:
        heapq.heapreplace(best, (similarity, chunk_id))


@dataclass(slots=True)
class HnswANNAdapter:
    """Optional HNSW adapter backed by hnswlib when installed."""

    dimensions: int
    shard_count: int = 16
    _index: Any = None
    _chunk_by_label: dict[int, str] = field(default_factory=dict, init=False)
    _fallback: ExactANNAdapter = field(init=False)

    def __post_init__(self) -> None:
        self._fallback = ExactANNAdapter(shard_count=self.shard_count)

    def build(self, embeddings: dict[str, tuple[float, ...]]) -> None:
        if not embeddings:
            self._index = None
            self._chunk_by_label = {}
            self._fallback.build({})
            return
        self._fallback.build(embeddings)
        try:
            hnswlib = importlib.import_module("hnswlib")
            np = importlib.import_module("numpy")
        except ImportError:
            self._index = None
            self._chunk_by_label = {}
            return

        chunk_ids = sorted(embeddings)
        vectors = np.array([embeddings[cid] for cid in chunk_ids], dtype=np.float32)
        labels = np.arange(len(chunk_ids), dtype=np.int32)

        index = hnswlib.Index(space="cosine", dim=self.dimensions)
        index.init_index(
            max_elements=len(chunk_ids),
            ef_construction=max(100, min(800, len(chunk_ids) // 2)),
            M=16,
        )
        index.add_items(vectors, labels)
        index.set_ef(max(64, min(256, len(chunk_ids))))

        self._index = index
        self._chunk_by_label = {
            int(label): chunk_id for label, chunk_id in zip(labels, chunk_ids, strict=True)
        }

    def query(
        self,
        *,
        query_vector: tuple[float, ...],
        top_k: int,
        candidate_ids: set[str] | None = None,
    ) -> list[AnnResult]:
        if top_k <= 0:
            return []
        if candidate_ids is not None or self._index is None:
            return self._fallback.query(
                query_vector=query_vector,
                top_k=top_k,
                candidate_ids=candidate_ids,
            )
        try:
            np = importlib.import_module("numpy")
        except ImportError:
            return self._fallback.query(
                query_vector=query_vector,
                top_k=top_k,
                candidate_ids=candidate_ids,
            )

        labels, distances = self._index.knn_query(
            np.array([query_vector], dtype=np.float32),
            k=top_k,
        )
        results: list[AnnResult] = []
        for label, distance in zip(labels[0], distances[0], strict=True):
            chunk_id = self._chunk_by_label.get(int(label))
            if chunk_id is None:
                continue
            score = 1.0 - float(distance)
            if score <= 0.0:
                continue
            results.append(AnnResult(chunk_id=chunk_id, score=score))
        return results


def build_ann_adapter(
    *,
    backend: str,
    dimensions: int,
    shard_count: int,
) -> ANNAdapter:
    normalized = backend.strip().lower()
    if normalized == "hnsw":
        return HnswANNAdapter(dimensions=dimensions, shard_count=shard_count)
    return ExactANNAdapter(shard_count=shard_count)
