"""Neo4j-like graph store connector."""

from __future__ import annotations

import collections
import time
from dataclasses import dataclass, field

from clio_agentic_search.core.connectors import (
    IndexReport,
    NamespaceAuthConfig,
    NamespaceRuntimeConfig,
)
from clio_agentic_search.indexing.text_features import tokenize
from clio_agentic_search.models.contracts import CitationRecord, NamespaceDescriptor
from clio_agentic_search.retrieval.capabilities import ScoredChunk


@dataclass(frozen=True, slots=True)
class GraphNode:
    node_id: str
    document_id: str
    uri: str
    text: str
    metadata: dict[str, str] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class GraphEdge:
    source_id: str
    target_id: str


class Neo4jLikeClient:
    def upsert_nodes(self, database: str, nodes: list[GraphNode]) -> None:
        raise NotImplementedError

    def upsert_edges(self, database: str, edges: list[GraphEdge]) -> None:
        raise NotImplementedError

    def list_nodes(self, database: str) -> list[GraphNode]:
        raise NotImplementedError

    def neighbors(self, database: str, node_id: str) -> list[str]:
        raise NotImplementedError


@dataclass(slots=True)
class InMemoryNeo4jClient(Neo4jLikeClient):
    _nodes: dict[str, dict[str, GraphNode]] = field(default_factory=dict)
    _edges: dict[str, dict[str, set[str]]] = field(default_factory=dict)

    def upsert_nodes(self, database: str, nodes: list[GraphNode]) -> None:
        records = self._nodes.setdefault(database, {})
        for node in nodes:
            records[node.node_id] = node

    def upsert_edges(self, database: str, edges: list[GraphEdge]) -> None:
        adjacency = self._edges.setdefault(database, {})
        for edge in edges:
            adjacency.setdefault(edge.source_id, set()).add(edge.target_id)
            adjacency.setdefault(edge.target_id, set()).add(edge.source_id)

    def list_nodes(self, database: str) -> list[GraphNode]:
        return sorted(self._nodes.get(database, {}).values(), key=lambda node: node.node_id)

    def neighbors(self, database: str, node_id: str) -> list[str]:
        adjacency = self._edges.get(database, {})
        return sorted(adjacency.get(node_id, set()))


@dataclass(slots=True)
class Neo4jGraphConnector:
    namespace: str
    database: str
    client: Neo4jLikeClient
    _runtime_config: NamespaceRuntimeConfig = field(
        default_factory=lambda: NamespaceRuntimeConfig(options={})
    )
    _auth_config: NamespaceAuthConfig | None = None
    _connected: bool = False
    _nodes_by_id: dict[str, GraphNode] = field(default_factory=dict)

    def configure(
        self,
        *,
        runtime_config: NamespaceRuntimeConfig,
        auth_config: NamespaceAuthConfig | None,
    ) -> None:
        self._runtime_config = runtime_config
        self._auth_config = auth_config
        self.database = runtime_config.options.get("database", self.database)

    def descriptor(self) -> NamespaceDescriptor:
        uri = self._runtime_config.options.get("uri", "bolt://localhost:7687")
        return NamespaceDescriptor(
            name=self.namespace,
            connector_type="graph_store",
            root_uri=f"{uri.rstrip('/')}/{self.database}",
        )

    def connect(self) -> None:
        self._connected = True

    def teardown(self) -> None:
        self._connected = False

    def index(self, *, full_rebuild: bool = False) -> IndexReport:
        del full_rebuild
        self._ensure_connected()
        start = time.perf_counter()
        nodes = self.client.list_nodes(self.database)
        self._nodes_by_id = {node.node_id: node for node in nodes}
        return IndexReport(
            scanned_files=len(nodes),
            indexed_files=0,
            skipped_files=len(nodes),
            removed_files=0,
            elapsed_seconds=time.perf_counter() - start,
        )

    def search_lexical(self, query: str, top_k: int) -> list[ScoredChunk]:
        self._ensure_connected()
        query_terms = set(tokenize(query))
        if not query_terms:
            return []
        scored: list[ScoredChunk] = []
        for node in self.client.list_nodes(self.database):
            overlap = len(query_terms.intersection(tokenize(node.text)))
            if overlap <= 0:
                continue
            self._nodes_by_id[node.node_id] = node
            scored.append(
                ScoredChunk(
                    chunk_id=node.node_id,
                    document_id=node.document_id,
                    text=node.text,
                    lexical_score=overlap / len(query_terms),
                )
            )
        scored.sort(key=lambda candidate: (-candidate.lexical_score, candidate.chunk_id))
        return scored[:top_k]

    def search_graph(self, query: str, top_k: int) -> list[ScoredChunk]:
        self._ensure_connected()
        seeds = self.search_lexical(query, top_k=max(top_k, 1))
        if not seeds:
            return []
        seen_ids = {seed.chunk_id for seed in seeds}
        traversal_scores: dict[str, float] = {}
        for seed in seeds:
            neighborhood = self.traverse_graph(seed.chunk_id, depth=1)
            for node_id in neighborhood:
                if node_id in seen_ids:
                    continue
                traversal_scores[node_id] = max(traversal_scores.get(node_id, 0.0), 0.5)
                seen_ids.add(node_id)

        scored: list[ScoredChunk] = []
        for node_id, score in traversal_scores.items():
            node = self._nodes_by_id.get(node_id)
            if node is None:
                nodes = self.client.list_nodes(self.database)
                node_lookup = {item.node_id: item for item in nodes}
                node = node_lookup.get(node_id)
                if node is None:
                    continue
                self._nodes_by_id[node_id] = node
            scored.append(
                ScoredChunk(
                    chunk_id=node.node_id,
                    document_id=node.document_id,
                    text=node.text,
                    metadata_score=score,
                )
            )
        scored.sort(key=lambda candidate: (-candidate.metadata_score, candidate.chunk_id))
        return scored[:top_k]

    def traverse_graph(self, seed: str, depth: int) -> list[str]:
        self._ensure_connected()
        if depth <= 0:
            return []
        visited: set[str] = {seed}
        queue: collections.deque[tuple[str, int]] = collections.deque([(seed, 0)])
        results: list[str] = []
        while queue:
            node_id, current_depth = queue.popleft()
            if current_depth >= depth:
                continue
            for neighbor in self.client.neighbors(self.database, node_id):
                if neighbor in visited:
                    continue
                visited.add(neighbor)
                results.append(neighbor)
                queue.append((neighbor, current_depth + 1))
        return results

    def search_vector(self, query: str, top_k: int) -> list[ScoredChunk]:
        del query, top_k
        return []

    def filter_metadata(
        self, candidates: list[ScoredChunk], required: dict[str, str]
    ) -> list[ScoredChunk]:
        self._ensure_connected()
        if not required:
            return candidates
        filtered: list[ScoredChunk] = []
        for candidate in candidates:
            node = self._nodes_by_id.get(candidate.chunk_id)
            if node is None:
                continue
            if all(node.metadata.get(key) == value for key, value in required.items()):
                filtered.append(
                    ScoredChunk(
                        chunk_id=candidate.chunk_id,
                        document_id=candidate.document_id,
                        text=candidate.text,
                        lexical_score=candidate.lexical_score,
                        vector_score=candidate.vector_score,
                        metadata_score=candidate.metadata_score + 1.0,
                    )
                )
        return filtered

    def build_citation(self, chunk: ScoredChunk) -> CitationRecord:
        node = self._nodes_by_id.get(chunk.chunk_id)
        if node is None:
            raise KeyError(f"Unknown graph node '{chunk.chunk_id}'")
        return CitationRecord(
            namespace=self.namespace,
            document_id=node.document_id,
            chunk_id=node.node_id,
            uri=node.uri,
            snippet=node.text[:160],
            score=round(chunk.combined_score, 6),
        )

    def seed_graph(self, *, nodes: list[GraphNode], edges: list[GraphEdge]) -> None:
        self.client.upsert_nodes(self.database, nodes)
        self.client.upsert_edges(self.database, edges)

    def _ensure_connected(self) -> None:
        if not self._connected:
            raise RuntimeError("Connector is not connected")
