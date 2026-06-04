"""HDF5 namespace connector with incremental indexing."""

from __future__ import annotations

import hashlib
import os
import threading
import time
from concurrent.futures import Future, ThreadPoolExecutor
from dataclasses import dataclass, field
from pathlib import Path

from clio_agentic_search.core.connectors import (
    IndexReport,
    NamespaceAuthConfig,
    NamespaceRuntimeConfig,
)
from clio_agentic_search.indexing.lexical import (
    DEFAULT_STOPWORDS,
    LexicalIngestionConfig,
    LexicalPostingsIngestor,
)
from clio_agentic_search.indexing.scientific import (
    ScientificChunkPlan,
    build_structure_aware_chunk_plan,
    canonicalize_measurement,
    normalize_formula,
)
from clio_agentic_search.indexing.text_features import (
    Embedder,
    HashEmbedder,
    tokenize,
)
from clio_agentic_search.models.contracts import (
    ChunkRecord,
    CitationRecord,
    DocumentRecord,
    EmbeddingRecord,
    MetadataRecord,
    NamespaceDescriptor,
)
from clio_agentic_search.retrieval.ann import ANNAdapter, AnnResult, build_ann_adapter
from clio_agentic_search.retrieval.capabilities import ScoredChunk
from clio_agentic_search.retrieval.scientific import (
    ScientificQueryOperators,
    score_scientific_metadata,
)
from clio_agentic_search.storage.contracts import DocumentBundle, FileIndexState, StorageAdapter

try:
    import h5py

    HAS_H5PY = True
except ImportError:
    HAS_H5PY = False

HDF5_SUFFIXES: frozenset[str] = frozenset({".h5", ".hdf5", ".hdf", ".he5", ".nc"})


def _extract_hdf5_text(file_path: Path) -> str:
    """Walk an HDF5 file and produce a text representation of its structure.

    For each group and dataset the output includes the path, shape, dtype,
    and any HDF5 attributes (especially ``units``, ``long_name``, and
    ``description``).
    """
    sections: list[str] = []

    def _visitor(name: str, obj: h5py.Dataset | h5py.Group) -> None:
        lines: list[str] = []
        if isinstance(obj, h5py.Dataset):
            lines.append(f"Dataset: /{name}")
            lines.append(f"Shape: {obj.shape}")
            lines.append(f"Dtype: {obj.dtype}")
        else:
            lines.append(f"Group: /{name}")

        if obj.attrs:
            lines.append("Attributes:")
            for attr_name in sorted(obj.attrs):
                attr_value = obj.attrs[attr_name]
                # Decode bytes-like attribute values when possible.
                if isinstance(attr_value, bytes):
                    attr_value = attr_value.decode("utf-8", errors="replace")
                lines.append(f"  {attr_name}: {attr_value}")
        sections.append("\n".join(lines))

    with h5py.File(file_path, "r") as f:
        # Emit root-level attributes first.
        if f.attrs:
            root_lines = ["Group: /", "Attributes:"]
            for attr_name in sorted(f.attrs):
                attr_value = f.attrs[attr_name]
                if isinstance(attr_value, bytes):
                    attr_value = attr_value.decode("utf-8", errors="replace")
                root_lines.append(f"  {attr_name}: {attr_value}")
            sections.append("\n".join(root_lines))
        f.visititems(_visitor)

    return "\n\n".join(sections)


@dataclass(slots=True)
class HDF5Connector:
    """Connector that indexes HDF5 files with hybrid search capabilities.

    Walks a directory tree for HDF5 files, extracts group/dataset hierarchy,
    shapes, dtypes, and attributes, then indexes the resulting text through
    the scientific chunk pipeline.
    """

    namespace: str
    root: Path
    storage: StorageAdapter
    embedder: Embedder = field(default_factory=HashEmbedder)
    embedding_model: str = "hash16-v1"
    chunk_size: int = 400
    reindex_delay_seconds: float = 0.0
    _runtime_config: NamespaceRuntimeConfig = field(
        default_factory=lambda: NamespaceRuntimeConfig(options={})
    )
    _auth_config: NamespaceAuthConfig | None = None
    ann_backend: str = "exact"
    cache_shards: int = 16
    warmup_async: bool = True
    document_batch_size: int = 32
    lexical_batch_size: int = 50_000
    lexical_df_prune_threshold: float = 0.98
    lexical_df_prune_min_chunks: int = 200
    lexical_max_tokens_per_chunk: int = 96
    lexical_prune_stopwords: bool = True
    stopwords: frozenset[str] = DEFAULT_STOPWORDS
    lexical_postings_compression: str = "none"
    _connected: bool = False
    _ann_index: ANNAdapter | None = field(default=None, init=False, repr=False)
    _warmup_executor: ThreadPoolExecutor | None = field(default=None, init=False, repr=False)
    _warmup_future: Future[None] | None = field(default=None, init=False, repr=False)
    _runtime_lock: threading.RLock = field(default_factory=threading.RLock, init=False, repr=False)

    # ------------------------------------------------------------------
    # Configuration
    # ------------------------------------------------------------------

    def configure(
        self,
        *,
        runtime_config: NamespaceRuntimeConfig,
        auth_config: NamespaceAuthConfig | None,
    ) -> None:
        self._runtime_config = runtime_config
        self._auth_config = auth_config
        if "root" in runtime_config.options:
            self.root = Path(runtime_config.options["root"])
        ann_backend = runtime_config.options.get("ann_backend")
        if ann_backend:
            self.ann_backend = ann_backend
        cache_shards = runtime_config.options.get("cache_shards")
        if cache_shards:
            self.cache_shards = max(1, int(cache_shards))
        warmup_async = runtime_config.options.get("warmup_async")
        if warmup_async:
            self.warmup_async = _parse_bool(warmup_async)
        document_batch_size = runtime_config.options.get("document_batch_size")
        if document_batch_size:
            self.document_batch_size = max(1, int(document_batch_size))
        if os.environ.get("CLIO_ANN_BACKEND"):
            self.ann_backend = os.environ["CLIO_ANN_BACKEND"]
        if os.environ.get("CLIO_CACHE_SHARDS"):
            self.cache_shards = max(1, int(os.environ["CLIO_CACHE_SHARDS"]))
        if os.environ.get("CLIO_VECTOR_WARMUP_ASYNC"):
            self.warmup_async = _parse_bool(os.environ["CLIO_VECTOR_WARMUP_ASYNC"])
        if os.environ.get("CLIO_INDEX_DOCUMENT_BATCH_SIZE"):
            self.document_batch_size = max(1, int(os.environ["CLIO_INDEX_DOCUMENT_BATCH_SIZE"]))
        if os.environ.get("CLIO_LEXICAL_BATCH_SIZE"):
            self.lexical_batch_size = max(1, int(os.environ["CLIO_LEXICAL_BATCH_SIZE"]))
        if os.environ.get("CLIO_LEXICAL_DF_PRUNE_THRESHOLD"):
            self.lexical_df_prune_threshold = float(os.environ["CLIO_LEXICAL_DF_PRUNE_THRESHOLD"])
        if os.environ.get("CLIO_LEXICAL_DF_PRUNE_MIN_CHUNKS"):
            self.lexical_df_prune_min_chunks = max(
                1,
                int(os.environ["CLIO_LEXICAL_DF_PRUNE_MIN_CHUNKS"]),
            )
        if os.environ.get("CLIO_LEXICAL_MAX_TOKENS_PER_CHUNK"):
            self.lexical_max_tokens_per_chunk = max(
                0,
                int(os.environ["CLIO_LEXICAL_MAX_TOKENS_PER_CHUNK"]),
            )
        if os.environ.get("CLIO_LEXICAL_PRUNE_STOPWORDS"):
            self.lexical_prune_stopwords = _parse_bool(os.environ["CLIO_LEXICAL_PRUNE_STOPWORDS"])
        postings_compression = runtime_config.options.get("lexical_postings_compression")
        if postings_compression:
            self.lexical_postings_compression = _parse_postings_compression(postings_compression)
        if os.environ.get("CLIO_LEXICAL_POSTINGS_COMPRESSION"):
            self.lexical_postings_compression = _parse_postings_compression(
                os.environ["CLIO_LEXICAL_POSTINGS_COMPRESSION"]
            )

    # ------------------------------------------------------------------
    # NamespaceConnector protocol
    # ------------------------------------------------------------------

    def descriptor(self) -> NamespaceDescriptor:
        return NamespaceDescriptor(
            name=self.namespace,
            connector_type="hdf5",
            root_uri=str(self.root.resolve()),
        )

    def connect(self) -> None:
        if not HAS_H5PY:
            raise RuntimeError(
                "h5py is required for HDF5Connector but is not installed. "
                "Install it with: pip install h5py"
            )
        self.storage.connect()
        self._connected = True
        self._schedule_warmup()

    def teardown(self) -> None:
        self._connected = False
        self._stop_warmup_worker()
        self.storage.teardown()
        with self._runtime_lock:
            self._ann_index = None

    def index(self, *, full_rebuild: bool = False) -> IndexReport:
        self._ensure_connected()
        start = time.perf_counter()

        if full_rebuild:
            self.storage.clear_namespace(self.namespace)

        scanned_files = 0
        indexed_files = 0
        skipped_files = 0
        existing_paths: set[str] = set()
        pending_bundles: list[DocumentBundle] = []
        lexical_ingestor = LexicalPostingsIngestor(
            LexicalIngestionConfig(
                batch_size=self.lexical_batch_size,
                df_prune_threshold=self.lexical_df_prune_threshold,
                df_prune_min_chunks=self.lexical_df_prune_min_chunks,
                max_tokens_per_chunk=self.lexical_max_tokens_per_chunk,
                prune_stopwords=self.lexical_prune_stopwords,
                stopwords=self.stopwords,
                postings_compression=self.lexical_postings_compression,
            )
        )

        try:
            for file_path in sorted(
                path
                for path in self.root.rglob("*")
                if path.is_file() and path.suffix.lower() in HDF5_SUFFIXES
            ):
                relative_path = file_path.relative_to(self.root).as_posix()
                existing_paths.add(relative_path)
                scanned_files += 1

                content_bytes = file_path.read_bytes()
                content_hash = hashlib.sha256(content_bytes).hexdigest()
                mtime_ns = file_path.stat().st_mtime_ns

                if not full_rebuild:
                    previous = self.storage.get_file_state(self.namespace, relative_path)
                    if (
                        previous is not None
                        and previous.mtime_ns == mtime_ns
                        and previous.content_hash == content_hash
                    ):
                        skipped_files += 1
                        continue

                if self.reindex_delay_seconds > 0:
                    time.sleep(self.reindex_delay_seconds)

                document_id = hashlib.sha1(f"{self.namespace}:{relative_path}".encode()).hexdigest()

                text = _extract_hdf5_text(file_path)
                if not text.strip():
                    skipped_files += 1
                    continue

                document = DocumentRecord(
                    namespace=self.namespace,
                    document_id=document_id,
                    uri=relative_path,
                    checksum=content_hash,
                    modified_at_ns=mtime_ns,
                )
                chunk_plan = self._build_chunks(document_id=document_id, text=text)
                chunks = chunk_plan.chunks
                embeddings = [
                    EmbeddingRecord(
                        namespace=self.namespace,
                        chunk_id=chunk.chunk_id,
                        model=self.embedding_model,
                        vector=self.embedder.embed(chunk.text),
                    )
                    for chunk in chunks
                ]
                metadata = self._build_metadata(
                    relative_path=relative_path,
                    document_id=document_id,
                    chunks=chunks,
                    chunk_metadata=chunk_plan.metadata_by_chunk_id,
                )
                file_state = FileIndexState(
                    namespace=self.namespace,
                    path=relative_path,
                    document_id=document_id,
                    mtime_ns=mtime_ns,
                    content_hash=content_hash,
                )

                pending_bundles.append(
                    DocumentBundle(
                        document=document,
                        chunks=chunks,
                        embeddings=embeddings,
                        metadata=metadata,
                        file_state=file_state,
                    )
                )
                if len(pending_bundles) >= self.document_batch_size:
                    self.storage.upsert_document_bundles(
                        pending_bundles,
                        include_lexical_postings=False,
                        skip_prior_delete=full_rebuild,
                    )
                    pending_bundles = []
                lexical_ingestor.add_chunks(chunks)
                indexed_files += 1

            if pending_bundles:
                self.storage.upsert_document_bundles(
                    pending_bundles,
                    include_lexical_postings=False,
                    skip_prior_delete=full_rebuild,
                )
            removed_files = (
                0
                if full_rebuild
                else self.storage.remove_missing_paths(self.namespace, existing_paths)
            )
            lexical_ingestor.flush(namespace=self.namespace, storage=self.storage)
        finally:
            lexical_ingestor.close()

        if full_rebuild or indexed_files > 0 or removed_files > 0:
            self._refresh_vector_index()
        elif self._ann_index is None:
            self._schedule_warmup()

        elapsed_seconds = time.perf_counter() - start
        return IndexReport(
            scanned_files=scanned_files,
            indexed_files=indexed_files,
            skipped_files=skipped_files,
            removed_files=removed_files,
            elapsed_seconds=elapsed_seconds,
        )

    # ------------------------------------------------------------------
    # LexicalSearchCapable
    # ------------------------------------------------------------------

    def search_lexical(self, query: str, top_k: int) -> list[ScoredChunk]:
        self._ensure_connected()
        query_tokens = tuple(sorted(set(tokenize(query))))
        if not query_tokens:
            return []

        matches = self.storage.query_chunks_lexical(
            namespace=self.namespace,
            query_tokens=query_tokens,
            limit=top_k,
        )
        return [
            ScoredChunk(
                chunk_id=match.chunk.chunk_id,
                document_id=match.chunk.document_id,
                text=match.chunk.text,
                lexical_score=match.bm25_score,
            )
            for match in matches
        ]

    # ------------------------------------------------------------------
    # VectorSearchCapable
    # ------------------------------------------------------------------

    def search_vector(self, query: str, top_k: int) -> list[ScoredChunk]:
        self._ensure_connected()
        self._ensure_vector_index_ready()
        with self._runtime_lock:
            ann_index = self._ann_index
        if ann_index is None:
            return []
        query_vector = self.embedder.embed(query)

        candidate_ids: set[str] | None = None
        if isinstance(self.embedder, HashEmbedder):
            query_tokens = tuple(sorted(set(tokenize(query))))
            if query_tokens:
                prefilter_limit = max(top_k * 40, 512)
                candidate_ids = {
                    match.chunk.chunk_id
                    for match in self.storage.query_chunks_lexical(
                        namespace=self.namespace,
                        query_tokens=query_tokens,
                        limit=prefilter_limit,
                    )
                }
                if not candidate_ids:
                    candidate_ids = None
        neighbors = ann_index.query(
            query_vector=query_vector,
            top_k=top_k,
            candidate_ids=candidate_ids,
        )
        return self._neighbors_to_scored_chunks(neighbors)

    # ------------------------------------------------------------------
    # MetadataFilterCapable
    # ------------------------------------------------------------------

    def filter_metadata(
        self,
        candidates: list[ScoredChunk],
        required: dict[str, str],
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

    # ------------------------------------------------------------------
    # ScientificSearchCapable
    # ------------------------------------------------------------------

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

        candidate_ids: set[str] | None = None

        if operators.numeric_range is not None:
            try:
                canonical_min = None
                canonical_max = None
                canonical_unit = canonicalize_measurement(0.0, operators.numeric_range.unit)[1]
                if operators.numeric_range.minimum is not None:
                    canonical_min = canonicalize_measurement(
                        operators.numeric_range.minimum,
                        operators.numeric_range.unit,
                    )[0]
                if operators.numeric_range.maximum is not None:
                    canonical_max = canonicalize_measurement(
                        operators.numeric_range.maximum,
                        operators.numeric_range.unit,
                    )[0]
            except ValueError:
                return []
            range_chunks = self.storage.query_chunks_by_measurement_range(
                self.namespace, canonical_unit, canonical_min, canonical_max
            )
            range_ids = {c.chunk_id for c in range_chunks}
            candidate_ids = range_ids if candidate_ids is None else candidate_ids & range_ids

        if operators.formula:
            sig = normalize_formula(operators.formula)
            formula_chunks = self.storage.query_chunks_by_formula(self.namespace, sig)
            formula_ids = {c.chunk_id for c in formula_chunks}
            candidate_ids = formula_ids if candidate_ids is None else candidate_ids & formula_ids

        if candidate_ids is not None:
            chunks = [self.storage.get_chunk(self.namespace, cid) for cid in sorted(candidate_ids)]
        else:
            chunks = self.storage.list_chunks(self.namespace)

        scored: list[ScoredChunk] = []
        for chunk in chunks:
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

    # ------------------------------------------------------------------
    # Citation
    # ------------------------------------------------------------------

    def build_citation(self, chunk: ScoredChunk) -> CitationRecord:
        stored_chunk = self.storage.get_chunk(self.namespace, chunk.chunk_id)
        metadata = self.storage.get_chunk_metadata(self.namespace, stored_chunk.chunk_id)
        uri = self.storage.get_document_uri(self.namespace, stored_chunk.document_id)
        fragment = metadata.get("citation.fragment", "")
        if fragment:
            uri = f"{uri}#{fragment}"
        snippet = stored_chunk.text.strip()[:160]
        return CitationRecord(
            namespace=self.namespace,
            document_id=stored_chunk.document_id,
            chunk_id=stored_chunk.chunk_id,
            uri=uri,
            snippet=snippet,
            score=round(chunk.combined_score, 6),
        )

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _build_chunks(self, *, document_id: str, text: str) -> ScientificChunkPlan:
        return build_structure_aware_chunk_plan(
            namespace=self.namespace,
            document_id=document_id,
            text=text,
            chunk_size=self.chunk_size,
        )

    def _build_metadata(
        self,
        *,
        relative_path: str,
        document_id: str,
        chunks: list[ChunkRecord],
        chunk_metadata: dict[str, dict[str, str]],
    ) -> list[MetadataRecord]:
        suffix = Path(relative_path).suffix.lower()
        records: list[MetadataRecord] = [
            MetadataRecord(
                namespace=self.namespace,
                record_id=document_id,
                scope="document",
                key="path",
                value=relative_path,
            ),
            MetadataRecord(
                namespace=self.namespace,
                record_id=document_id,
                scope="document",
                key="suffix",
                value=suffix,
            ),
            MetadataRecord(
                namespace=self.namespace,
                record_id=document_id,
                scope="document",
                key="format",
                value="hdf5",
            ),
        ]

        for chunk in chunks:
            records.append(
                MetadataRecord(
                    namespace=self.namespace,
                    record_id=chunk.chunk_id,
                    scope="chunk",
                    key="path",
                    value=relative_path,
                )
            )
            records.append(
                MetadataRecord(
                    namespace=self.namespace,
                    record_id=chunk.chunk_id,
                    scope="chunk",
                    key="suffix",
                    value=suffix,
                )
            )
            records.append(
                MetadataRecord(
                    namespace=self.namespace,
                    record_id=chunk.chunk_id,
                    scope="chunk",
                    key="format",
                    value="hdf5",
                )
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

    def _refresh_vector_index(self) -> None:
        if not self._connected:
            return
        embeddings = self.storage.list_embeddings(self.namespace, self.embedding_model)
        ann_index = build_ann_adapter(
            backend=self.ann_backend,
            dimensions=self.embedder.dimensions,
            shard_count=max(1, self.cache_shards),
        )
        ann_index.build(embeddings)
        with self._runtime_lock:
            if not self._connected:
                return
            self._ann_index = ann_index

    def _schedule_warmup(self) -> None:
        if not self.warmup_async:
            self._refresh_vector_index()
            return
        with self._runtime_lock:
            if self._warmup_future is not None and not self._warmup_future.done():
                return
            if self._warmup_executor is None:
                self._warmup_executor = ThreadPoolExecutor(
                    max_workers=1,
                    thread_name_prefix=f"clio-warmup-{self.namespace}",
                )
            self._warmup_future = self._warmup_executor.submit(self._refresh_vector_index)

    def _ensure_vector_index_ready(self) -> None:
        with self._runtime_lock:
            ann_index = self._ann_index
            warmup_future = self._warmup_future
        if ann_index is not None:
            return
        if warmup_future is not None:
            warmup_future.result()
            with self._runtime_lock:
                if self._ann_index is not None:
                    return
        self._refresh_vector_index()

    def _stop_warmup_worker(self) -> None:
        with self._runtime_lock:
            executor = self._warmup_executor
            self._warmup_executor = None
            self._warmup_future = None
        if executor is not None:
            executor.shutdown(wait=True, cancel_futures=True)

    def _neighbors_to_scored_chunks(self, neighbors: list[AnnResult]) -> list[ScoredChunk]:
        scored: list[ScoredChunk] = []
        for neighbor in neighbors:
            chunk = self.storage.get_chunk(self.namespace, neighbor.chunk_id)
            scored.append(
                ScoredChunk(
                    chunk_id=neighbor.chunk_id,
                    document_id=chunk.document_id,
                    text=chunk.text,
                    vector_score=neighbor.score,
                )
            )
        return scored


def _parse_bool(value: str) -> bool:
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _parse_postings_compression(value: str) -> str:
    normalized = value.strip().lower()
    if normalized in {"", "none"}:
        return "none"
    if normalized in {"gzip", "gz"}:
        return "gzip"
    raise ValueError("Unsupported lexical postings compression; expected one of: none, gzip")
