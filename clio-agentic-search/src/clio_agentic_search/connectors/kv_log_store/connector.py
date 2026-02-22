"""Redis-stream-like KV/log connector."""

from __future__ import annotations

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
class StreamLogEntry:
    entry_id: str
    message: str
    metadata: dict[str, str] = field(default_factory=dict)


class RedisStreamLikeClient:
    def append(self, stream: str, entry: StreamLogEntry) -> None:
        raise NotImplementedError

    def tail(self, stream: str, limit: int) -> list[StreamLogEntry]:
        raise NotImplementedError


@dataclass(slots=True)
class InMemoryRedisStreamClient(RedisStreamLikeClient):
    _streams: dict[str, list[StreamLogEntry]] = field(default_factory=dict)

    def append(self, stream: str, entry: StreamLogEntry) -> None:
        self._streams.setdefault(stream, []).append(entry)

    def tail(self, stream: str, limit: int) -> list[StreamLogEntry]:
        records = self._streams.get(stream, [])
        if limit <= 0:
            return []
        return list(records[-limit:])


@dataclass(slots=True)
class RedisLogConnector:
    namespace: str
    stream: str
    client: RedisStreamLikeClient
    _runtime_config: NamespaceRuntimeConfig = field(
        default_factory=lambda: NamespaceRuntimeConfig(options={})
    )
    _auth_config: NamespaceAuthConfig | None = None
    _connected: bool = False
    _cached: dict[str, StreamLogEntry] = field(default_factory=dict)

    def configure(
        self,
        *,
        runtime_config: NamespaceRuntimeConfig,
        auth_config: NamespaceAuthConfig | None,
    ) -> None:
        self._runtime_config = runtime_config
        self._auth_config = auth_config
        self.stream = runtime_config.options.get("stream", self.stream)

    def descriptor(self) -> NamespaceDescriptor:
        url = self._runtime_config.options.get("url", "redis://localhost:6379/0")
        return NamespaceDescriptor(
            name=self.namespace,
            connector_type="kv_log_store",
            root_uri=f"{url.rstrip('/')}/streams/{self.stream}",
        )

    def connect(self) -> None:
        self._connected = True

    def teardown(self) -> None:
        self._connected = False

    def index(self, *, full_rebuild: bool = False) -> IndexReport:
        del full_rebuild
        self._ensure_connected()
        start = time.perf_counter()
        entries = self.client.tail(self.stream, limit=5000)
        self._cached = {entry.entry_id: entry for entry in entries}
        return IndexReport(
            scanned_files=len(entries),
            indexed_files=0,
            skipped_files=len(entries),
            removed_files=0,
            elapsed_seconds=time.perf_counter() - start,
        )

    def stream_logs(self, namespace: str, limit: int) -> list[str]:
        self._ensure_connected()
        if namespace != self.namespace:
            return []
        entries = self.client.tail(self.stream, limit=limit)
        for entry in entries:
            self._cached[entry.entry_id] = entry
        return [entry.message for entry in entries]

    def search_lexical(self, query: str, top_k: int) -> list[ScoredChunk]:
        self._ensure_connected()
        query_terms = set(tokenize(query))
        if not query_terms:
            return []
        entries = self.client.tail(self.stream, limit=max(100, top_k * 20))
        scored: list[ScoredChunk] = []
        for entry in entries:
            self._cached[entry.entry_id] = entry
            overlap = len(query_terms.intersection(tokenize(entry.message)))
            if overlap <= 0:
                continue
            scored.append(
                ScoredChunk(
                    chunk_id=entry.entry_id,
                    document_id=self.stream,
                    text=entry.message,
                    lexical_score=overlap / len(query_terms),
                )
            )
        scored.sort(key=lambda candidate: (-candidate.lexical_score, candidate.chunk_id))
        return scored[:top_k]

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
            entry = self._cached.get(candidate.chunk_id)
            if entry is None:
                continue
            if all(entry.metadata.get(key) == value for key, value in required.items()):
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
        entry = self._cached.get(chunk.chunk_id)
        if entry is None:
            raise KeyError(f"Missing log entry '{chunk.chunk_id}'")
        return CitationRecord(
            namespace=self.namespace,
            document_id=self.stream,
            chunk_id=entry.entry_id,
            uri=f"redis://{self.stream}/{entry.entry_id}",
            snippet=entry.message[:160],
            score=round(chunk.combined_score, 6),
        )

    def append_log(self, message: str, *, metadata: dict[str, str] | None = None) -> str:
        entry_id = f"{int(time.time() * 1000)}-{len(self._cached)}"
        entry = StreamLogEntry(entry_id=entry_id, message=message, metadata=dict(metadata or {}))
        self.client.append(self.stream, entry)
        self._cached[entry_id] = entry
        return entry_id

    def _ensure_connected(self) -> None:
        if not self._connected:
            raise RuntimeError("Connector is not connected")
