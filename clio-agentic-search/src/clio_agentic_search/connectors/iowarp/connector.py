"""IOWarp CTE namespace connector.

Bridges CLIO's retrieval pipeline to IOWarp's Context Transfer Engine.
Blobs live in CTE (managed by the Chimaera runtime); this connector:

  1. Enumerates blobs via ``BlobQuery`` / ``TagQuery``
  2. Reads blob content via ``Tag.GetBlob``
  3. Indexes text + scientific metadata into CLIO's DuckDB store
  4. Searches using CLIO's standard lexical, vector, and scientific branches

This lets CLIO's science-aware operators (SI unit conversion, formula
normalization, corpus profiling) run on data that physically resides in
IOWarp's tiered blob storage — the integration point the paper needs.
"""

from __future__ import annotations

import csv as _csv
import hashlib
import io as _io
import json as _json
import time
from dataclasses import dataclass, field

try:
    from iowarp_core import wrp_cte_core_ext as cte

    HAS_IOWARP = True
except ImportError:
    HAS_IOWARP = False
    cte = None  # type: ignore[assignment]

from clio_agentic_search.core.connectors import IndexReport
from clio_agentic_search.indexing.lexical import (
    DEFAULT_STOPWORDS,
    LexicalIngestionConfig,
    LexicalPostingsIngestor,
)
from clio_agentic_search.indexing.scientific import (
    build_structure_aware_chunk_plan,
    canonicalize_measurement,
    normalize_formula,
)
from clio_agentic_search.indexing.text_features import Embedder, HashEmbedder, tokenize
from clio_agentic_search.models.contracts import (
    CitationRecord,
    EmbeddingRecord,
    MetadataRecord,
    NamespaceDescriptor,
)
from clio_agentic_search.retrieval.ann import ANNAdapter, build_ann_adapter
from clio_agentic_search.retrieval.capabilities import ScoredChunk
from clio_agentic_search.retrieval.corpus_profile import CorpusProfile, build_corpus_profile
from clio_agentic_search.retrieval.scientific import (
    ScientificQueryOperators,
    score_scientific_metadata,
)
from clio_agentic_search.storage.contracts import DocumentBundle, FileIndexState, StorageAdapter


@dataclass(slots=True)
class IOWarpConnector:
    """CLIO connector for IOWarp CTE blob storage.

    Parameters
    ----------
    namespace:
        Logical namespace name used in CLIO's index.
    tag_pattern:
        Regex pattern for CTE tags to include (default ``".*"`` = all).
    blob_pattern:
        Regex pattern for blob names to include (default ``".*"`` = all).
    storage:
        A CLIO ``StorageAdapter`` (typically DuckDB) for the local index.
    max_blobs_per_query:
        Upper limit passed to ``BlobQuery`` during enumeration.
    """

    namespace: str
    storage: StorageAdapter
    tag_pattern: str = ".*"
    blob_pattern: str = ".*"
    max_blobs_per_query: int = 2_000_000
    embedder: Embedder = field(default_factory=HashEmbedder)
    embedding_model: str = "hash16-v1"
    chunk_size: int = 400
    ann_backend: str = "exact"
    cache_shards: int = 16
    _connected: bool = False
    _cte_client: object | None = field(default=None, init=False, repr=False)
    _ann_index: ANNAdapter | None = field(default=None, init=False, repr=False)
    _tag_cache: dict[str, object] = field(default_factory=dict, init=False, repr=False)

    def descriptor(self) -> NamespaceDescriptor:
        return NamespaceDescriptor(
            name=self.namespace,
            connector_type="iowarp",
            root_uri=f"cte://{self.tag_pattern}",
        )

    def connect(self) -> None:
        if not HAS_IOWARP:
            raise RuntimeError(
                "iowarp_core is not installed. Install the wheel: pip install iowarp_core-*.whl"
            )
        self._cte_client = cte.get_cte_client()
        self.storage.connect()
        self._connected = True

    def teardown(self) -> None:
        self._connected = False
        self._ann_index = None
        self._tag_cache.clear()
        self.storage.teardown()

    def index(
        self,
        *,
        full_rebuild: bool = False,
        known_tag_names: list[str] | None = None,
    ) -> IndexReport:
        """Enumerate blobs from CTE, extract scientific metadata, build index.

        Parameters
        ----------
        full_rebuild:
            Clear the namespace before indexing.
        known_tag_names:
            Optional explicit list of tag names to enumerate.  When provided,
            uses ``Tag.GetContainedBlobs()`` on each tag — avoiding
            ``BlobQuery`` (which hangs in iowarp_core 0.6.4 due to a
            Broadcast-dispatch bug on aarch64 64KB-page systems like DeltaAI
            GH200).  When *not* provided, falls back to ``BlobQuery`` (works
            on x86 and iowarp_core 1.0.3+).
        """
        self._ensure_connected()
        start = time.perf_counter()

        if full_rebuild:
            self.storage.clear_namespace(self.namespace)

        # Discover blobs.
        # known_tag_names fast path: use Tag.GetContainedBlobs() per tag.
        # This avoids BlobQuery which hangs on iowarp_core 0.6.4 aarch64
        # (Broadcast dispatch deadlock).
        if known_tag_names is not None:
            raw_results: list[tuple[str, str]] = []
            import re as _re

            blob_re = _re.compile(self.blob_pattern)
            for tag_name in known_tag_names:
                tag_obj = self._get_or_create_tag(tag_name)
                for blob_name in tag_obj.GetContainedBlobs():
                    if blob_re.fullmatch(blob_name):
                        raw_results.append((tag_name, blob_name))
        else:
            # BlobQuery path (iowarp_core 1.0.3+ / x86).
            # Support both iowarp_core 0.6.4+ (requires MemContext as first
            # arg) and 1.0.3 (no MemContext).
            if hasattr(cte, "MemContext"):
                _mctx = cte.MemContext()
                raw_results = list(
                    self._cte_client.BlobQuery(  # type: ignore[union-attr]
                        _mctx,
                        self.tag_pattern,
                        self.blob_pattern,
                        self.max_blobs_per_query,
                        cte.PoolQuery.Dynamic(),
                    )
                )
            else:
                raw_results = list(
                    self._cte_client.BlobQuery(  # type: ignore[union-attr]
                        self.tag_pattern,
                        self.blob_pattern,
                        self.max_blobs_per_query,
                        cte.PoolQuery.Dynamic(),
                    )
                )

        scanned = len(raw_results)
        indexed = 0
        skipped = 0
        pending_bundles: list[DocumentBundle] = []
        lexical_ingestor = LexicalPostingsIngestor(
            LexicalIngestionConfig(
                batch_size=50_000,
                df_prune_threshold=0.98,
                df_prune_min_chunks=200,
                max_tokens_per_chunk=96,
                prune_stopwords=True,
                stopwords=DEFAULT_STOPWORDS,
                postings_compression="none",
            )
        )

        try:
            for item in raw_results:
                # Each item is (tag_name, blob_name) or similar tuple
                if isinstance(item, (list, tuple)) and len(item) >= 2:
                    tag_name, blob_name = str(item[0]), str(item[1])
                else:
                    tag_name, blob_name = str(item), str(item)

                # Read blob content from CTE
                tag_obj = self._get_or_create_tag(tag_name)
                try:
                    blob_size = tag_obj.GetBlobSize(blob_name)
                    if blob_size <= 0:
                        skipped += 1
                        continue
                    content_bytes = tag_obj.GetBlob(blob_name, blob_size, 0)
                except Exception:
                    skipped += 1
                    continue

                raw = (
                    content_bytes
                    if isinstance(content_bytes, bytes)
                    else str(content_bytes).encode()
                )
                text = self._parse_blob_content(raw)
                if not text.strip():
                    skipped += 1
                    continue

                # Build CLIO document from blob
                blob_uri = f"cte://{tag_name}/{blob_name}"
                content_hash = hashlib.sha256(raw).hexdigest()
                document_id = hashlib.sha1(f"{self.namespace}:{blob_uri}".encode()).hexdigest()

                from clio_agentic_search.models.contracts import DocumentRecord

                document = DocumentRecord(
                    namespace=self.namespace,
                    document_id=document_id,
                    uri=blob_uri,
                    checksum=content_hash,
                    modified_at_ns=int(time.time_ns()),
                )

                chunk_plan = build_structure_aware_chunk_plan(
                    namespace=self.namespace,
                    document_id=document_id,
                    text=text,
                    chunk_size=self.chunk_size,
                )
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
                    blob_uri=blob_uri,
                    tag_name=tag_name,
                    blob_name=blob_name,
                    document_id=document_id,
                    chunks=chunks,
                    chunk_metadata=chunk_plan.metadata_by_chunk_id,
                )
                file_state = FileIndexState(
                    namespace=self.namespace,
                    path=blob_uri,
                    document_id=document_id,
                    mtime_ns=int(time.time_ns()),
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
                if len(pending_bundles) >= 32:
                    self.storage.upsert_document_bundles(
                        pending_bundles,
                        include_lexical_postings=False,
                        skip_prior_delete=full_rebuild,
                    )
                    pending_bundles = []
                lexical_ingestor.add_chunks(chunks)
                indexed += 1

            if pending_bundles:
                self.storage.upsert_document_bundles(
                    pending_bundles,
                    include_lexical_postings=False,
                    skip_prior_delete=full_rebuild,
                )
            lexical_ingestor.flush(namespace=self.namespace, storage=self.storage)
        finally:
            lexical_ingestor.close()

        # Build vector index
        self._refresh_vector_index()

        elapsed = time.perf_counter() - start
        return IndexReport(
            scanned_files=scanned,
            indexed_files=indexed,
            skipped_files=skipped,
            removed_files=0,
            elapsed_seconds=elapsed,
        )

    def index_from_texts(
        self, blob_texts: dict[str, str], *, full_rebuild: bool = False
    ) -> IndexReport:
        """Index blobs from pre-loaded text content.

        This avoids per-blob CTE reads during indexing — suitable when blobs
        are ingested and indexed in the same pipeline (the production path).
        ``blob_texts`` maps ``cte://tag/blob`` URIs to their text content.
        """
        self._ensure_connected()
        start = time.perf_counter()

        if full_rebuild:
            self.storage.clear_namespace(self.namespace)

        indexed = 0
        skipped = 0
        pending_bundles: list[DocumentBundle] = []
        lexical_ingestor = LexicalPostingsIngestor(
            LexicalIngestionConfig(
                batch_size=50_000,
                df_prune_threshold=0.98,
                df_prune_min_chunks=200,
                max_tokens_per_chunk=96,
                prune_stopwords=True,
                stopwords=DEFAULT_STOPWORDS,
                postings_compression="none",
            )
        )

        try:
            for blob_uri, text in blob_texts.items():
                if not text.strip():
                    skipped += 1
                    continue

                # Parse tag/blob from URI: cte://tag_name/blob_name
                parts = blob_uri.replace("cte://", "").split("/", 1)
                tag_name = parts[0] if len(parts) > 0 else "unknown"
                blob_name = parts[1] if len(parts) > 1 else "unknown"

                content_hash = hashlib.sha256(text.encode()).hexdigest()
                document_id = hashlib.sha1(f"{self.namespace}:{blob_uri}".encode()).hexdigest()

                from clio_agentic_search.models.contracts import DocumentRecord

                document = DocumentRecord(
                    namespace=self.namespace,
                    document_id=document_id,
                    uri=blob_uri,
                    checksum=content_hash,
                    modified_at_ns=int(time.time_ns()),
                )

                chunk_plan = build_structure_aware_chunk_plan(
                    namespace=self.namespace,
                    document_id=document_id,
                    text=text,
                    chunk_size=self.chunk_size,
                )
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
                    blob_uri=blob_uri,
                    tag_name=tag_name,
                    blob_name=blob_name,
                    document_id=document_id,
                    chunks=chunks,
                    chunk_metadata=chunk_plan.metadata_by_chunk_id,
                )
                file_state = FileIndexState(
                    namespace=self.namespace,
                    path=blob_uri,
                    document_id=document_id,
                    mtime_ns=int(time.time_ns()),
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
                if len(pending_bundles) >= 500:
                    self.storage.upsert_document_bundles(
                        pending_bundles,
                        include_lexical_postings=False,
                        skip_prior_delete=full_rebuild,
                    )
                    pending_bundles = []
                lexical_ingestor.add_chunks(chunks)
                indexed += 1

            if pending_bundles:
                self.storage.upsert_document_bundles(
                    pending_bundles,
                    include_lexical_postings=False,
                    skip_prior_delete=full_rebuild,
                )
            lexical_ingestor.flush(namespace=self.namespace, storage=self.storage)
        finally:
            lexical_ingestor.close()

        self._refresh_vector_index()

        elapsed = time.perf_counter() - start
        return IndexReport(
            scanned_files=len(blob_texts),
            indexed_files=indexed,
            skipped_files=skipped,
            removed_files=0,
            elapsed_seconds=elapsed,
        )

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

    def search_vector(self, query: str, top_k: int) -> list[ScoredChunk]:
        self._ensure_connected()
        if self._ann_index is None:
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
        neighbors = self._ann_index.query(
            query_vector=query_vector,
            top_k=top_k,
            candidate_ids=candidate_ids,
        )
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
                canonical_unit = canonicalize_measurement(0.0, operators.numeric_range.unit)[1]
                canonical_min = (
                    canonicalize_measurement(
                        operators.numeric_range.minimum, operators.numeric_range.unit
                    )[0]
                    if operators.numeric_range.minimum is not None
                    else None
                )
                canonical_max = (
                    canonicalize_measurement(
                        operators.numeric_range.maximum, operators.numeric_range.unit
                    )[0]
                    if operators.numeric_range.maximum is not None
                    else None
                )
            except ValueError:
                return []
            range_chunks = self.storage.query_chunks_by_measurement_range(
                self.namespace,
                canonical_unit,
                canonical_min,
                canonical_max,
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

        scored.sort(key=lambda c: (-c.metadata_score, c.chunk_id))
        return scored[:top_k]

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

    def build_citation(self, chunk: ScoredChunk) -> CitationRecord:
        stored_chunk = self.storage.get_chunk(self.namespace, chunk.chunk_id)
        uri = self.storage.get_document_uri(self.namespace, stored_chunk.document_id)
        snippet = stored_chunk.text.strip()[:160]
        return CitationRecord(
            namespace=self.namespace,
            document_id=stored_chunk.document_id,
            chunk_id=stored_chunk.chunk_id,
            uri=uri,
            snippet=snippet,
            score=round(chunk.combined_score, 6),
        )

    def corpus_profile(self) -> CorpusProfile:
        self._ensure_connected()
        return build_corpus_profile(self.storage, self.namespace)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _get_or_create_tag(self, tag_name: str) -> object:
        if tag_name not in self._tag_cache:
            self._tag_cache[tag_name] = cte.Tag(tag_name)
        return self._tag_cache[tag_name]

    def _build_metadata(
        self,
        *,
        blob_uri: str,
        tag_name: str,
        blob_name: str,
        document_id: str,
        chunks: list,
        chunk_metadata: dict[str, dict[str, str]],
    ) -> list[MetadataRecord]:
        records: list[MetadataRecord] = [
            MetadataRecord(
                namespace=self.namespace,
                record_id=document_id,
                scope="document",
                key="path",
                value=blob_uri,
            ),
            MetadataRecord(
                namespace=self.namespace,
                record_id=document_id,
                scope="document",
                key="cte_tag",
                value=tag_name,
            ),
            MetadataRecord(
                namespace=self.namespace,
                record_id=document_id,
                scope="document",
                key="cte_blob",
                value=blob_name,
            ),
        ]
        for chunk in chunks:
            records.append(
                MetadataRecord(
                    namespace=self.namespace,
                    record_id=chunk.chunk_id,
                    scope="chunk",
                    key="path",
                    value=blob_uri,
                )
            )
            records.append(
                MetadataRecord(
                    namespace=self.namespace,
                    record_id=chunk.chunk_id,
                    scope="chunk",
                    key="cte_tag",
                    value=tag_name,
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
        self._ann_index = ann_index

    def _parse_blob_content(self, content_bytes: bytes) -> str:
        """Parse blob bytes into indexable text regardless of format.

        Tries formats in order: JSON → CSV → UTF-8 text → binary summary.
        Synthesizes measurement-friendly text so CLIO's SI unit extraction
        works even when blobs carry no external metadata — CLIO reads what
        is *inside* the blob to build the index.
        """
        # --- Try JSON ---
        try:
            data = _json.loads(content_bytes)
            return self._json_to_measurement_text(data)
        except (_json.JSONDecodeError, UnicodeDecodeError, ValueError):
            pass

        # --- Try CSV ---
        try:
            text = content_bytes.decode("utf-8")
            lines = text.splitlines()
            if len(lines) >= 2 and "," in lines[0]:
                return self._csv_to_measurement_text(text)
        except UnicodeDecodeError:
            pass

        # --- Try plain UTF-8 text ---
        try:
            return content_bytes.decode("utf-8")
        except UnicodeDecodeError:
            pass

        # --- Binary fallback ---
        return f"binary blob {len(content_bytes)} bytes"

    def _json_to_measurement_text(self, data: object) -> str:
        """Flatten JSON to measurement-friendly text.

        Concatenates all string values and numeric values so that patterns
        like ``"23.15 degC"`` appear adjacent in the output and can be
        picked up by CLIO's measurement extraction regex.
        """
        if not isinstance(data, dict):
            return str(data)
        parts: list[str] = []
        for value in data.values():
            if isinstance(value, str):
                parts.append(value)
            elif isinstance(value, (int, float)):
                parts.append(str(value))
            elif isinstance(value, (list, dict)):
                parts.append(self._json_to_measurement_text(value))
        return " ".join(parts)

    def _csv_to_measurement_text(self, text: str) -> str:
        """Parse CSV, synthesize measurement text from header + all data rows."""
        reader = _csv.DictReader(_io.StringIO(text))
        parts: list[str] = []
        for row in reader:
            parts.extend(f"{k} {v}" for k, v in row.items() if v.strip())
        return " | ".join(parts)

    def _ensure_connected(self) -> None:
        if not self._connected:
            raise RuntimeError("IOWarpConnector is not connected — call connect() first")
