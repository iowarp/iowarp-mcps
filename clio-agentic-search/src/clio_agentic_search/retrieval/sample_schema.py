"""Active schema inference via sampling.

When a namespace was indexed without structured metadata extraction — for
example, a CSV ingested as raw text or an HDF5 file whose attribute
extractor was disabled — ``CorpusProfile.metadata_density`` comes out near
zero. The basic branch planner then skips the scientific branch because
it believes there are no measurements.

But the measurements might actually be *there*, sitting in chunk text
that nobody extracted. :func:`sample_and_infer_schema` recovers from this
by reading a small deterministic sample of chunks, running the regex
extractors and field aligners on them, and reporting what it finds. The
caller can then re-enable the scientific branch based on the inferred
schema — without having to re-index the entire corpus.

This is the "reason when metadata is absent" half of the agentic search
motivation: the agent does a cheap bounded inspection rather than either
scanning everything or giving up.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from clio_agentic_search.indexing.scientific import extract_measurements
from clio_agentic_search.retrieval.metadata_schema import align_field
from clio_agentic_search.storage.contracts import StorageAdapter

# Separators that typically appear between CSV/TSV/pipe-delimited fields in
# text chunks that came from tabular sources. Used to split each line of
# a sampled chunk into candidate field names for the aligner.
_FIELD_SEPARATOR_RE = re.compile(r"[,\t|;]")


@dataclass(frozen=True, slots=True)
class SampledSchema:
    """Schema discovered by reading a random sample of chunks.

    Attributes:
        namespace: The namespace that was sampled.
        sample_size: How many chunks were actually inspected (may be less
            than the requested size if the namespace is small).
        total_chunks: Total chunks in the namespace (for reference).
        concepts_found: Canonical scientific concepts discovered
            (via :func:`metadata_schema.align_field` on line-split text).
        measurement_units_found: Distinct raw unit strings extracted from
            the sampled text (via :func:`extract_measurements`).
        measurement_count: Total extractable measurements found in the
            sample, summed across all chunks.
        chunks_with_signal: Number of sampled chunks that yielded at least
            one concept or measurement.
        inferred_density: ``chunks_with_signal / sample_size``. If this is
            high, the namespace has recoverable structure even though the
            primary metadata_density may have been low.
        sample_chunk_ids: The chunk IDs actually read (for reproducibility).
    """

    namespace: str
    sample_size: int
    total_chunks: int
    concepts_found: frozenset[str]
    measurement_units_found: frozenset[str]
    measurement_count: int
    chunks_with_signal: int
    inferred_density: float
    sample_chunk_ids: tuple[str, ...]

    @property
    def has_recoverable_structure(self) -> bool:
        """True if sampling found concepts or measurements that weren't
        captured by the primary index."""
        return bool(self.concepts_found) or self.measurement_count > 0


def sample_and_infer_schema(
    storage: StorageAdapter,
    namespace: str,
    *,
    sample_size: int = 20,
    seed: int = 42,
) -> SampledSchema:
    """Sample chunks from a namespace and infer what's inside.

    The function:
      1. Asks storage for ``sample_size`` deterministically-random chunks.
      2. Runs :func:`extract_measurements` on each chunk's text.
      3. Scans each line for candidate field names separated by commas,
         tabs, or pipes, and aligns each to a canonical concept.
      4. Aggregates the findings into a :class:`SampledSchema`.

    Args:
        storage: Any :class:`StorageAdapter` implementing ``sample_chunks``
            (currently :class:`DuckDBStorage`).
        namespace: The namespace to sample.
        sample_size: Maximum number of chunks to inspect.
        seed: Deterministic seed for sampling.

    Returns:
        :class:`SampledSchema`. Fields are zero / empty if the namespace
        has no chunks or the storage adapter doesn't support sampling.
    """
    # Gracefully degrade if the adapter doesn't support sampling yet.
    sample_fn = getattr(storage, "sample_chunks", None)
    if sample_fn is None:
        return SampledSchema(
            namespace=namespace,
            sample_size=0,
            total_chunks=0,
            concepts_found=frozenset(),
            measurement_units_found=frozenset(),
            measurement_count=0,
            chunks_with_signal=0,
            inferred_density=0.0,
            sample_chunk_ids=(),
        )

    # Total chunk count (for the ratio) — use corpus_profile_stats if present
    total_chunks = 0
    stats_fn = getattr(storage, "corpus_profile_stats", None)
    if stats_fn is not None:
        total_chunks = stats_fn(namespace).chunk_count

    sampled = sample_fn(namespace, sample_size=sample_size, seed=seed)
    if not sampled:
        return SampledSchema(
            namespace=namespace,
            sample_size=0,
            total_chunks=total_chunks,
            concepts_found=frozenset(),
            measurement_units_found=frozenset(),
            measurement_count=0,
            chunks_with_signal=0,
            inferred_density=0.0,
            sample_chunk_ids=(),
        )

    concepts: set[str] = set()
    units: set[str] = set()
    total_measurements = 0
    chunks_with_signal = 0

    for chunk in sampled:
        chunk_signal = False

        # 1. Regex measurement extraction on the full text
        measurements = extract_measurements(chunk.text)
        if measurements:
            chunk_signal = True
            total_measurements += len(measurements)
            for m in measurements:
                units.add(m.raw_unit)

        # 2. Line-oriented field-name alignment: treat each line as
        # possibly a CSV row and each comma/tab/pipe-separated cell as a
        # candidate field name. Tabular data ingested as plain text shows
        # up here even if its headers weren't captured as structured metadata.
        for line in chunk.text.splitlines():
            line = line.strip()
            if not line or len(line) > 500:
                # Skip very long lines (prose paragraphs, not CSV rows).
                continue
            for cell in _FIELD_SEPARATOR_RE.split(line):
                cell = cell.strip()
                if not cell or len(cell) > 60:
                    continue
                concept = align_field(cell)
                if concept:
                    concepts.add(concept)
                    chunk_signal = True

        if chunk_signal:
            chunks_with_signal += 1

    inferred_density = chunks_with_signal / len(sampled)

    return SampledSchema(
        namespace=namespace,
        sample_size=len(sampled),
        total_chunks=total_chunks,
        concepts_found=frozenset(concepts),
        measurement_units_found=frozenset(units),
        measurement_count=total_measurements,
        chunks_with_signal=chunks_with_signal,
        inferred_density=round(inferred_density, 4),
        sample_chunk_ids=tuple(c.chunk_id for c in sampled),
    )
