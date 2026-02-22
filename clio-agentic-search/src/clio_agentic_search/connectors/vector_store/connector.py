"""Qdrant-like vector store connector."""

from __future__ import annotations

import math
import time
from dataclasses import dataclass, field

from clio_agentic_search.core.connectors import (
    IndexReport,
    NamespaceAuthConfig,
    NamespaceRuntimeConfig,
)
from clio_agentic_search.indexing.text_features import Embedder, HashEmbedder, tokenize
from clio_agentic_search.models.contracts import CitationRecord, NamespaceDescriptor
from clio_agentic_search.retrieval.capabilities import ScoredChunk


@dataclass(frozen=True, slots=True)
class VectorPoint:
    chunk_id: str
    document_id: str
    uri: str
    text: str
    vector: tuple[float, ...]
    metadata: dict[str, str] = field(default_factory=dict)


class QdrantLikeClient:
    def upsert_points(self, collection: str, points: list[VectorPoint]) -> None:
        raise NotImplementedError

    def list_points(self, collection: str) -> list[VectorPoint]:
        raise NotImplementedError

    def search(
        self, collection: str, query_vector: tuple[float, ...], top_k: int
    ) -> list[tuple[VectorPoint, float]]:
        raise NotImplementedError


@dataclass(slots=True)
class InMemoryQdrantClient(QdrantLikeClient):
    _collections: dict[str, dict[str, VectorPoint]] = field(default_factory=dict)

    def upsert_points(self, collection: str, points: list[VectorPoint]) -> None:
        records = self._collections.setdefault(collection, {})
        for point in points:
            records[point.chunk_id] = point

    def list_points(self, collection: str) -> list[VectorPoint]:
        return sorted(
            self._collections.get(collection, {}).values(), key=lambda point: point.chunk_id
        )

    def search(
        self,
        collection: str,
        query_vector: tuple[float, ...],
        top_k: int,
    ) -> list[tuple[VectorPoint, float]]:
        scored: list[tuple[VectorPoint, float]] = []
        for point in self._collections.get(collection, {}).values():
            score = _cosine_similarity(query_vector, point.vector)
            if score > 0:
                scored.append((point, score))
        scored.sort(key=lambda pair: (-pair[1], pair[0].chunk_id))
        return scored[:top_k]


@dataclass(slots=True)
class QdrantVectorConnector:
    namespace: str
    collection: str
    client: QdrantLikeClient
    embedder: Embedder = field(default_factory=HashEmbedder)
    _runtime_config: NamespaceRuntimeConfig = field(
        default_factory=lambda: NamespaceRuntimeConfig(options={})
    )
    _auth_config: NamespaceAuthConfig | None = None
    _connected: bool = False
    _points_by_chunk: dict[str, VectorPoint] = field(default_factory=dict)

    def configure(
        self,
        *,
        runtime_config: NamespaceRuntimeConfig,
        auth_config: NamespaceAuthConfig | None,
    ) -> None:
        self._runtime_config = runtime_config
        self._auth_config = auth_config
        self.collection = runtime_config.options.get("collection", self.collection)

    def descriptor(self) -> NamespaceDescriptor:
        base_url = self._runtime_config.options.get("url", "http://localhost:6333")
        return NamespaceDescriptor(
            name=self.namespace,
            connector_type="vector_store",
            root_uri=f"{base_url.rstrip('/')}/collections/{self.collection}",
        )

    def connect(self) -> None:
        self._connected = True

    def teardown(self) -> None:
        self._connected = False

    def index(self, *, full_rebuild: bool = False) -> IndexReport:
        del full_rebuild
        self._ensure_connected()
        start = time.perf_counter()
        points = self.client.list_points(self.collection)
        self._points_by_chunk = {point.chunk_id: point for point in points}
        return IndexReport(
            scanned_files=len(points),
            indexed_files=0,
            skipped_files=len(points),
            removed_files=0,
            elapsed_seconds=time.perf_counter() - start,
        )

    def search_vector(self, query: str, top_k: int) -> list[ScoredChunk]:
        self._ensure_connected()
        query_vector = self.embedder.embed(query)
        points = self.client.search(self.collection, query_vector, top_k=top_k)
        self._points_by_chunk.update({point.chunk_id: point for point, _ in points})
        return [
            ScoredChunk(
                chunk_id=point.chunk_id,
                document_id=point.document_id,
                text=point.text,
                vector_score=score,
            )
            for point, score in points
        ]

    def filter_metadata(
        self, candidates: list[ScoredChunk], required: dict[str, str]
    ) -> list[ScoredChunk]:
        self._ensure_connected()
        if not required:
            return candidates
        filtered: list[ScoredChunk] = []
        for candidate in candidates:
            point = self._points_by_chunk.get(candidate.chunk_id)
            if point is None:
                continue
            if all(point.metadata.get(key) == value for key, value in required.items()):
                filtered.append(
                    ScoredChunk(
                        chunk_id=candidate.chunk_id,
                        document_id=candidate.document_id,
                        text=candidate.text,
                        lexical_score=candidate.lexical_score,
                        vector_score=candidate.vector_score,
                        metadata_score=1.0,
                    )
                )
        return filtered

    def build_citation(self, chunk: ScoredChunk) -> CitationRecord:
        point = self._points_by_chunk.get(chunk.chunk_id)
        if point is None:
            point = next(
                item
                for item in self.client.list_points(self.collection)
                if item.chunk_id == chunk.chunk_id
            )
            self._points_by_chunk[chunk.chunk_id] = point
        return CitationRecord(
            namespace=self.namespace,
            document_id=point.document_id,
            chunk_id=point.chunk_id,
            uri=point.uri,
            snippet=point.text[:160],
            score=round(chunk.combined_score, 6),
        )

    def seed_points(self, points: list[VectorPoint]) -> None:
        self.client.upsert_points(self.collection, points)

    def search_lexical(self, query: str, top_k: int) -> list[ScoredChunk]:
        self._ensure_connected()
        query_terms = set(tokenize(query))
        if not query_terms:
            return []
        points = self.client.list_points(self.collection)
        scored: list[ScoredChunk] = []
        for point in points:
            overlap = len(query_terms.intersection(tokenize(point.text)))
            if overlap <= 0:
                continue
            self._points_by_chunk[point.chunk_id] = point
            scored.append(
                ScoredChunk(
                    chunk_id=point.chunk_id,
                    document_id=point.document_id,
                    text=point.text,
                    lexical_score=overlap / len(query_terms),
                )
            )
        scored.sort(key=lambda candidate: (-candidate.lexical_score, candidate.chunk_id))
        return scored[:top_k]

    def _ensure_connected(self) -> None:
        if not self._connected:
            raise RuntimeError("Connector is not connected")


def _cosine_similarity(left: tuple[float, ...], right: tuple[float, ...]) -> float:
    if len(left) != len(right):
        return 0.0
    left_norm = math.sqrt(sum(component * component for component in left))
    right_norm = math.sqrt(sum(component * component for component in right))
    if left_norm == 0.0 or right_norm == 0.0:
        return 0.0
    dot = sum(left[index] * right[index] for index in range(len(left)))
    return dot / (left_norm * right_norm)
