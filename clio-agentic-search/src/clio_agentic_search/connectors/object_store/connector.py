"""S3-compatible object store connector."""

from __future__ import annotations

import hashlib
import time
from dataclasses import dataclass, field

from clio_agentic_search.core.connectors import (
    IndexReport,
    NamespaceAuthConfig,
    NamespaceRuntimeConfig,
)
from clio_agentic_search.indexing.scientific import (
    ScientificChunkPlan,
    build_structure_aware_chunk_plan,
)
from clio_agentic_search.indexing.text_features import cosine_similarity, embed_text, tokenize
from clio_agentic_search.models.contracts import (
    ChunkRecord,
    CitationRecord,
    DocumentRecord,
    EmbeddingRecord,
    MetadataRecord,
    NamespaceDescriptor,
)
from clio_agentic_search.retrieval.capabilities import ScoredChunk
from clio_agentic_search.retrieval.scientific import (
    ScientificQueryOperators,
    score_scientific_metadata,
)
from clio_agentic_search.storage import FileIndexState, StorageAdapter


@dataclass(frozen=True, slots=True)
class S3Object:
    key: str
    body: bytes
    last_modified_ns: int
    metadata: dict[str, str] = field(default_factory=dict)


class S3CompatibleClient:
    def list_objects(self, bucket: str, prefix: str) -> list[S3Object]:
        raise NotImplementedError


@dataclass(slots=True)
class InMemoryS3Client(S3CompatibleClient):
    _buckets: dict[str, dict[str, S3Object]] = field(default_factory=dict)

    def put_object(
        self, *, bucket: str, key: str, body: bytes, metadata: dict[str, str] | None = None
    ) -> None:
        bucket_records = self._buckets.setdefault(bucket, {})
        object_record = S3Object(
            key=key,
            body=body,
            last_modified_ns=time.time_ns(),
            metadata=dict(metadata or {}),
        )
        bucket_records[key] = object_record

    def list_objects(self, bucket: str, prefix: str) -> list[S3Object]:
        records = self._buckets.get(bucket, {})
        return sorted(
            [record for key, record in records.items() if key.startswith(prefix)],
            key=lambda record: record.key,
        )


@dataclass(slots=True)
class S3ObjectStoreConnector:
    namespace: str
    bucket: str
    prefix: str
    storage: StorageAdapter
    client: S3CompatibleClient
    embedding_model: str = "hash16-v1"
    _runtime_config: NamespaceRuntimeConfig = field(
        default_factory=lambda: NamespaceRuntimeConfig(options={})
    )
    _auth_config: NamespaceAuthConfig | None = None
    _connected: bool = False

    def configure(
        self,
        *,
        runtime_config: NamespaceRuntimeConfig,
        auth_config: NamespaceAuthConfig | None,
    ) -> None:
        self._runtime_config = runtime_config
        self._auth_config = auth_config
        self.bucket = runtime_config.options.get("bucket", self.bucket)
        self.prefix = runtime_config.options.get("prefix", self.prefix)

    def descriptor(self) -> NamespaceDescriptor:
        endpoint = self._runtime_config.options.get("endpoint_url", "s3://")
        return NamespaceDescriptor(
            name=self.namespace,
            connector_type="object_store",
            root_uri=f"{endpoint.rstrip('/')}/{self.bucket}/{self.prefix}".rstrip("/"),
        )

    def connect(self) -> None:
        self.storage.connect()
        self._connected = True

    def teardown(self) -> None:
        self.storage.teardown()
        self._connected = False

    def index(self, *, full_rebuild: bool = False) -> IndexReport:
        self._ensure_connected()
        start = time.perf_counter()
        if full_rebuild:
            self.storage.clear_namespace(self.namespace)

        scanned_files = 0
        indexed_files = 0
        skipped_files = 0
        existing_paths: set[str] = set()

        for object_record in self.client.list_objects(self.bucket, self.prefix):
            scanned_files += 1
            existing_paths.add(object_record.key)
            content_hash = hashlib.sha256(object_record.body).hexdigest()
            previous = self.storage.get_file_state(self.namespace, object_record.key)
            if (
                not full_rebuild
                and previous is not None
                and previous.mtime_ns == object_record.last_modified_ns
                and previous.content_hash == content_hash
            ):
                skipped_files += 1
                continue

            text = object_record.body.decode("utf-8", errors="ignore")
            document_id = hashlib.sha1(f"{self.namespace}:{object_record.key}".encode()).hexdigest()
            document = DocumentRecord(
                namespace=self.namespace,
                document_id=document_id,
                uri=f"s3://{self.bucket}/{object_record.key}",
                checksum=content_hash,
                modified_at_ns=object_record.last_modified_ns,
            )
            chunk_plan = self._build_chunks(document_id=document_id, text=text)
            chunks = chunk_plan.chunks
            embeddings = [
                EmbeddingRecord(
                    namespace=self.namespace,
                    chunk_id=chunk.chunk_id,
                    model=self.embedding_model,
                    vector=embed_text(chunk.text),
                )
                for chunk in chunks
            ]
            metadata = self._build_metadata(
                object_record=object_record,
                document_id=document_id,
                chunks=chunks,
                chunk_metadata=chunk_plan.metadata_by_chunk_id,
            )
            file_state = FileIndexState(
                namespace=self.namespace,
                path=object_record.key,
                document_id=document_id,
                mtime_ns=object_record.last_modified_ns,
                content_hash=content_hash,
            )
            self.storage.upsert_document_bundle(
                document=document,
                chunks=chunks,
                embeddings=embeddings,
                metadata=metadata,
                file_state=file_state,
            )
            indexed_files += 1

        removed_files = self.storage.remove_missing_paths(self.namespace, existing_paths)
        return IndexReport(
            scanned_files=scanned_files,
            indexed_files=indexed_files,
            skipped_files=skipped_files,
            removed_files=removed_files,
            elapsed_seconds=time.perf_counter() - start,
        )

    def search_lexical(self, query: str, top_k: int) -> list[ScoredChunk]:
        self._ensure_connected()
        query_tokens = set(tokenize(query))
        if not query_tokens:
            return []

        scored: list[ScoredChunk] = []
        for chunk in self.storage.list_chunks(self.namespace):
            chunk_tokens = set(tokenize(chunk.text))
            overlap = len(query_tokens.intersection(chunk_tokens))
            if overlap <= 0:
                continue
            scored.append(
                ScoredChunk(
                    chunk_id=chunk.chunk_id,
                    document_id=chunk.document_id,
                    text=chunk.text,
                    lexical_score=overlap / len(query_tokens),
                )
            )
        scored.sort(key=lambda candidate: (-candidate.lexical_score, candidate.chunk_id))
        return scored[:top_k]

    def search_vector(self, query: str, top_k: int) -> list[ScoredChunk]:
        self._ensure_connected()
        query_vector = embed_text(query)
        embeddings = self.storage.list_embeddings(self.namespace, self.embedding_model)
        chunk_cache = {chunk.chunk_id: chunk for chunk in self.storage.list_chunks(self.namespace)}

        scored: list[ScoredChunk] = []
        for chunk_id, vector in embeddings.items():
            similarity = cosine_similarity(query_vector, vector)
            if similarity <= 0:
                continue
            chunk = chunk_cache.get(chunk_id)
            if chunk is None:
                continue
            scored.append(
                ScoredChunk(
                    chunk_id=chunk.chunk_id,
                    document_id=chunk.document_id,
                    text=chunk.text,
                    vector_score=similarity,
                )
            )
        scored.sort(key=lambda candidate: (-candidate.vector_score, candidate.chunk_id))
        return scored[:top_k]

    def filter_metadata(
        self, candidates: list[ScoredChunk], required: dict[str, str]
    ) -> list[ScoredChunk]:
        self._ensure_connected()
        if not required:
            return candidates

        filtered: list[ScoredChunk] = []
        for candidate in candidates:
            metadata = self.storage.get_chunk_metadata(self.namespace, candidate.chunk_id)
            if all(metadata.get(key) == value for key, value in required.items()):
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

    def search_scientific(
        self,
        query: str,
        top_k: int,
        operators: ScientificQueryOperators,
    ) -> list[ScoredChunk]:
        self._ensure_connected()
        del query
        if not operators.is_active():
            return []

        scored: list[ScoredChunk] = []
        for chunk in self.storage.list_chunks(self.namespace):
            metadata = self.storage.get_chunk_metadata(self.namespace, chunk.chunk_id)
            score = score_scientific_metadata(metadata, operators)
            if score <= 0.0:
                continue
            scored.append(
                ScoredChunk(
                    chunk_id=chunk.chunk_id,
                    document_id=chunk.document_id,
                    text=chunk.text,
                    metadata_score=score,
                )
            )

        scored.sort(key=lambda candidate: (-candidate.metadata_score, candidate.chunk_id))
        return scored[:top_k]

    def build_citation(self, chunk: ScoredChunk) -> CitationRecord:
        stored_chunk = self.storage.get_chunk(self.namespace, chunk.chunk_id)
        metadata = self.storage.get_chunk_metadata(self.namespace, stored_chunk.chunk_id)
        uri = self.storage.get_document_uri(self.namespace, stored_chunk.document_id)
        fragment = metadata.get("citation.fragment", "")
        if fragment:
            uri = f"{uri}#{fragment}"
        return CitationRecord(
            namespace=self.namespace,
            document_id=stored_chunk.document_id,
            chunk_id=stored_chunk.chunk_id,
            uri=uri,
            snippet=stored_chunk.text.strip()[:160],
            score=round(chunk.combined_score, 6),
        )

    def _build_chunks(self, *, document_id: str, text: str) -> ScientificChunkPlan:
        return build_structure_aware_chunk_plan(
            namespace=self.namespace,
            document_id=document_id,
            text=text,
            chunk_size=400,
        )

    def _build_metadata(
        self,
        *,
        object_record: S3Object,
        document_id: str,
        chunks: list[ChunkRecord],
        chunk_metadata: dict[str, dict[str, str]],
    ) -> list[MetadataRecord]:
        suffix = object_record.key.rsplit(".", maxsplit=1)[-1] if "." in object_record.key else ""
        records: list[MetadataRecord] = [
            MetadataRecord(
                namespace=self.namespace,
                record_id=document_id,
                scope="document",
                key="bucket",
                value=self.bucket,
            ),
            MetadataRecord(
                namespace=self.namespace,
                record_id=document_id,
                scope="document",
                key="key",
                value=object_record.key,
            ),
            MetadataRecord(
                namespace=self.namespace,
                record_id=document_id,
                scope="document",
                key="suffix",
                value=suffix.lower(),
            ),
        ]
        for key, value in object_record.metadata.items():
            records.append(
                MetadataRecord(
                    namespace=self.namespace,
                    record_id=document_id,
                    scope="document",
                    key=f"object.{key}",
                    value=value,
                )
            )
        for chunk in chunks:
            records.extend(
                [
                    MetadataRecord(
                        namespace=self.namespace,
                        record_id=chunk.chunk_id,
                        scope="chunk",
                        key="bucket",
                        value=self.bucket,
                    ),
                    MetadataRecord(
                        namespace=self.namespace,
                        record_id=chunk.chunk_id,
                        scope="chunk",
                        key="key",
                        value=object_record.key,
                    ),
                    MetadataRecord(
                        namespace=self.namespace,
                        record_id=chunk.chunk_id,
                        scope="chunk",
                        key="suffix",
                        value=suffix.lower(),
                    ),
                ]
            )
            for key, value in sorted(chunk_metadata.get(chunk.chunk_id, {}).items()):
                records.append(
                    MetadataRecord(
                        namespace=self.namespace,
                        record_id=chunk.chunk_id,
                        scope="chunk",
                        key=key,
                        value=value,
                    )
                )
        return records

    def _ensure_connected(self) -> None:
        if not self._connected:
            raise RuntimeError("Connector is not connected")
