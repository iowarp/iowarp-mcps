"""Lightweight corpus profiling for intelligent branch selection.

A :class:`CorpusProfile` is what the agent looks at *before* deciding
which retrieval branches to activate and what filters to apply. It
summarises three things:

1. **Capability** — what kinds of search the corpus actually supports
   (lexical postings? vector embeddings? scientific measurements?
   formulas?).
2. **Metadata schema** — what structured metadata fields exist and what
   canonical scientific concepts they cover (temperature, pressure,
   station_id, etc.). See :mod:`metadata_schema`.
3. **Quality** — distribution of data-quality flags over the indexed
   measurements. See :mod:`indexing.quality`.

The profile is cheap to compute (a handful of GROUP BY queries on the
DuckDB index), so it's called per query. That's the whole point:
the agent can afford to look before it searches.
"""

from __future__ import annotations

from dataclasses import dataclass

from clio_agentic_search.indexing.quality import QualityFlag, QualitySummary
from clio_agentic_search.retrieval.metadata_schema import MetadataSchema
from clio_agentic_search.retrieval.sample_schema import SampledSchema
from clio_agentic_search.storage.contracts import StorageAdapter


@dataclass(frozen=True, slots=True)
class CorpusProfile:
    """Statistical summary of what is indexed in a namespace.

    The ``metadata_density`` field is the narrow scientific-metadata ratio
    (fraction of chunks with scientific.measurements or scientific.formulas).
    For a broader notion of "how rich is this metadata", see
    ``metadata_schema.richness_score``.
    """

    namespace: str
    document_count: int
    chunk_count: int
    measurement_count: int
    formula_count: int
    distinct_units: tuple[str, ...]
    distinct_formulas: tuple[str, ...]
    metadata_density: float  # fraction of chunks with scientific metadata
    embedding_count: int
    lexical_posting_count: int

    # Optional schema + quality (populated when the storage adapter
    # exposes the corresponding query methods).
    metadata_schema: MetadataSchema | None = None
    quality_summary: QualitySummary | None = None
    # Optional sampled-schema fallback: populated when metadata_density is
    # low but ``enable_sampling=True`` was passed to build_corpus_profile.
    # Captures concepts/measurements found by reading a small sample of
    # chunks, even if structured extraction missed them at index time.
    sampled_schema: SampledSchema | None = None

    @property
    def has_measurements(self) -> bool:
        """True if the primary index contains measurements or if a
        sampling pass discovered recoverable ones."""
        if self.measurement_count > 0:
            return True
        if self.sampled_schema is not None and self.sampled_schema.measurement_count > 0:
            return True
        return False

    @property
    def has_formulas(self) -> bool:
        return self.formula_count > 0

    @property
    def has_embeddings(self) -> bool:
        return self.embedding_count > 0

    @property
    def has_lexical(self) -> bool:
        return self.lexical_posting_count > 0

    @property
    def has_metadata_schema(self) -> bool:
        return self.metadata_schema is not None and len(self.metadata_schema.fields) > 0

    @property
    def has_sampled_schema(self) -> bool:
        return self.sampled_schema is not None and self.sampled_schema.has_recoverable_structure

    @property
    def has_quality_info(self) -> bool:
        return self.quality_summary is not None and self.quality_summary.total > 0

    @property
    def richness_score(self) -> float:
        """Broader metadata richness (schema-based, 0-1).

        Order of preference:
          1. Primary MetadataSchema richness (strongest signal).
          2. Sampled-schema inferred density (fallback when primary is empty).
          3. Raw metadata_density (narrowest signal).
        """
        if self.metadata_schema is not None and self.metadata_schema.richness_score > 0:
            return self.metadata_schema.richness_score
        if self.sampled_schema is not None and self.sampled_schema.inferred_density > 0:
            return self.sampled_schema.inferred_density
        return self.metadata_density

    @property
    def recovered_concepts(self) -> frozenset[str]:
        """Union of concepts from the primary schema and sampled schema."""
        primary = self.metadata_schema.concepts if self.metadata_schema else frozenset()
        sampled = self.sampled_schema.concepts_found if self.sampled_schema else frozenset()
        return primary | sampled

    @property
    def average_quality_score(self) -> float:
        """Mean data-quality score across all measurements, or 1.0 if unknown."""
        if self.quality_summary is None or self.quality_summary.total == 0:
            return 1.0
        return self.quality_summary.average_score


def build_corpus_profile(
    storage: StorageAdapter,
    namespace: str,
    *,
    enable_sampling: bool = False,
    sample_size: int = 20,
    sample_density_threshold: float = 0.1,
    sample_seed: int = 42,
) -> CorpusProfile:
    """Build a corpus profile by querying the storage adapter.

    The storage adapter is expected to implement ``corpus_profile_stats``
    (the base profile), and optionally ``query_metadata_schema_rows`` and
    ``query_quality_summary`` (the richer fields). Missing optional
    methods degrade gracefully.

    Args:
        enable_sampling: When True, if the primary metadata_density is
            below ``sample_density_threshold`` and the namespace has chunks,
            read ``sample_size`` random chunks and run extractors on them
            to recover any structure that wasn't captured at index time.
            This is the "reason when metadata is absent" fallback — it
            costs one extra query to the chunks table, bounded in size.
        sample_size: How many chunks to sample.
        sample_density_threshold: Only sample if the primary density is
            below this (to avoid paying the sampling cost when we already
            know the corpus is rich).
        sample_seed: Deterministic seed for the sampling, so repeated
            calls on the same namespace produce the same results.
    """
    stats_fn = getattr(storage, "corpus_profile_stats", None)
    if stats_fn is None:
        return CorpusProfile(
            namespace=namespace,
            document_count=0,
            chunk_count=0,
            measurement_count=0,
            formula_count=0,
            distinct_units=(),
            distinct_formulas=(),
            metadata_density=0.0,
            embedding_count=0,
            lexical_posting_count=0,
        )

    base = stats_fn(namespace)

    # Optional: metadata schema
    schema = None
    schema_fn = getattr(storage, "query_metadata_schema_rows", None)
    if schema_fn is not None:
        from clio_agentic_search.retrieval.metadata_schema import (
            build_metadata_schema,
        )

        rows = schema_fn(namespace)
        if rows:
            schema = build_metadata_schema(
                namespace=namespace,
                metadata_rows=rows,
                total_documents=base.document_count,
                total_chunks=base.chunk_count,
            )

    # Optional: quality summary
    quality = None
    quality_fn = getattr(storage, "query_quality_summary", None)
    if quality_fn is not None:
        counts = quality_fn(namespace)
        if counts:
            total = sum(counts.values())
            quality = QualitySummary(
                total=total,
                good=counts.get(QualityFlag.GOOD.value, 0),
                questionable=counts.get(QualityFlag.QUESTIONABLE.value, 0),
                bad=counts.get(QualityFlag.BAD.value, 0),
                missing=counts.get(QualityFlag.MISSING.value, 0),
                estimated=counts.get(QualityFlag.ESTIMATED.value, 0),
                unknown=counts.get(QualityFlag.UNKNOWN.value, 0),
            )

    # Optional: sampled schema fallback. Trigger only when the primary
    # density is low but the namespace actually has chunks we could inspect.
    sampled = None
    if (
        enable_sampling
        and base.chunk_count > 0
        and base.metadata_density < sample_density_threshold
    ):
        from clio_agentic_search.retrieval.sample_schema import sample_and_infer_schema

        sampled = sample_and_infer_schema(
            storage,
            namespace,
            sample_size=sample_size,
            seed=sample_seed,
        )
        # If sampling didn't find anything useful, discard it so the
        # profile doesn't pretend there's structure.
        if not sampled.has_recoverable_structure:
            sampled = None

    # Rebuild the dataclass with the enrichments attached. We can't mutate
    # a frozen dataclass, so construct a new one.
    return CorpusProfile(
        namespace=base.namespace,
        document_count=base.document_count,
        chunk_count=base.chunk_count,
        measurement_count=base.measurement_count,
        formula_count=base.formula_count,
        distinct_units=base.distinct_units,
        distinct_formulas=base.distinct_formulas,
        metadata_density=base.metadata_density,
        embedding_count=base.embedding_count,
        lexical_posting_count=base.lexical_posting_count,
        metadata_schema=schema,
        quality_summary=quality,
        sampled_schema=sampled,
    )
