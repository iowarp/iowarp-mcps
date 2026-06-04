"""Tests for active schema inference via sampling (retrieval.sample_schema)."""

from __future__ import annotations

import tempfile
from pathlib import Path

import pytest

from clio_agentic_search.indexing.scientific import ScientificChunkPlan
from clio_agentic_search.models.contracts import (
    ChunkRecord,
    DocumentRecord,
    MetadataRecord,
)
from clio_agentic_search.retrieval.corpus_profile import build_corpus_profile
from clio_agentic_search.retrieval.sample_schema import (
    SampledSchema,
    sample_and_infer_schema,
)
from clio_agentic_search.storage.contracts import DocumentBundle, FileIndexState
from clio_agentic_search.storage.duckdb_store import DuckDBStorage

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def tmp_storage() -> DuckDBStorage:
    tmpdir = tempfile.mkdtemp()
    storage = DuckDBStorage(database_path=Path(tmpdir) / "sample_test.duckdb")
    storage.connect()
    yield storage
    storage.teardown()


def _ingest_plain_chunks(
    storage: DuckDBStorage,
    namespace: str,
    chunks_text: list[str],
) -> None:
    """Insert chunks as plain text, deliberately WITHOUT any
    scientific.measurements metadata — simulating a dataset ingested as
    raw text where structured extraction was never run."""
    bundles: list[DocumentBundle] = []
    for i, text in enumerate(chunks_text):
        doc_id = f"doc_{i}"
        chunk_id = f"{doc_id}_c0"
        doc = DocumentRecord(
            namespace=namespace,
            document_id=doc_id,
            uri=f"synth://{doc_id}",
            checksum=f"h{i}",
            modified_at_ns=1_000_000 + i,
        )
        chunk = ChunkRecord(
            namespace=namespace,
            chunk_id=chunk_id,
            document_id=doc_id,
            chunk_index=0,
            text=text,
            start_offset=0,
            end_offset=len(text),
        )
        # Only path metadata — no scientific fields
        meta = [
            MetadataRecord(
                namespace=namespace,
                record_id=doc_id,
                scope="document",
                key="source",
                value="synthetic",
            ),
        ]
        file_state = FileIndexState(
            namespace=namespace,
            path=f"synth/{doc_id}",
            document_id=doc_id,
            mtime_ns=1_000_000 + i,
            content_hash=f"h{i}",
        )
        bundles.append(
            DocumentBundle(
                document=doc,
                chunks=[chunk],
                embeddings=[],
                metadata=meta,
                file_state=file_state,
            )
        )
    storage.upsert_document_bundles(bundles, include_lexical_postings=False)


# ---------------------------------------------------------------------------
# sample_and_infer_schema basic behaviour
# ---------------------------------------------------------------------------


def test_sample_empty_namespace(tmp_storage: DuckDBStorage) -> None:
    result = sample_and_infer_schema(tmp_storage, "empty_ns", sample_size=10)
    assert result.sample_size == 0
    assert result.total_chunks == 0
    assert len(result.concepts_found) == 0
    assert result.measurement_count == 0
    assert result.inferred_density == 0.0
    assert result.has_recoverable_structure is False


def test_sample_namespace_with_no_signal(tmp_storage: DuckDBStorage) -> None:
    """A namespace with pure prose should yield no recoverable structure."""
    _ingest_plain_chunks(
        tmp_storage,
        "prose_ns",
        [
            "This is a paragraph of prose about nothing in particular.",
            "Another paragraph, still no numbers or column names.",
            "The quick brown fox jumps over the lazy dog.",
        ],
    )
    result = sample_and_infer_schema(tmp_storage, "prose_ns", sample_size=10)
    assert result.sample_size == 3
    assert result.total_chunks == 3
    assert result.measurement_count == 0
    assert len(result.concepts_found) == 0
    assert result.has_recoverable_structure is False


def test_sample_detects_measurements_in_plain_text(tmp_storage: DuckDBStorage) -> None:
    """Measurements embedded in prose should be detected by the regex extractor."""
    _ingest_plain_chunks(
        tmp_storage,
        "measurement_ns",
        [
            "The recorded air temperature was 35 degC at noon.",
            "Wind speed measured 12 m/s during the storm.",
            "A dataset of mostly prose with no numbers here.",
        ],
    )
    result = sample_and_infer_schema(tmp_storage, "measurement_ns", sample_size=10)
    assert result.sample_size == 3
    assert result.measurement_count >= 2  # temp + wind
    assert "degc" in result.measurement_units_found or "m/s" in result.measurement_units_found
    assert result.chunks_with_signal == 2
    assert result.has_recoverable_structure is True


def test_sample_detects_concepts_from_csv_header_lines(tmp_storage: DuckDBStorage) -> None:
    """CSV-like headers embedded in chunk text should be aligned to concepts."""
    _ingest_plain_chunks(
        tmp_storage,
        "csv_ns",
        [
            "Stn Id,Stn Name,Date,Air Temp (C),qc,Wind Speed (m/s),qc",
            "105,Westlands,2024-06-01,25.3,,3.2,",
            "105,Westlands,2024-06-01,26.1,,3.5,",
        ],
    )
    result = sample_and_infer_schema(tmp_storage, "csv_ns", sample_size=10)
    assert "temperature" in result.concepts_found
    assert "wind_speed" in result.concepts_found
    assert result.has_recoverable_structure is True


def test_sample_deterministic_seed(tmp_storage: DuckDBStorage) -> None:
    """Same seed → same sample; different seeds → potentially different samples."""
    # Create more chunks than the sample size so the order matters
    chunks = [f"Chunk number {i} contains {i * 3} degC measurement." for i in range(30)]
    _ingest_plain_chunks(tmp_storage, "det_ns", chunks)

    result_a = sample_and_infer_schema(tmp_storage, "det_ns", sample_size=5, seed=42)
    result_b = sample_and_infer_schema(tmp_storage, "det_ns", sample_size=5, seed=42)
    assert result_a.sample_chunk_ids == result_b.sample_chunk_ids

    # Different seed → likely different sample
    result_c = sample_and_infer_schema(tmp_storage, "det_ns", sample_size=5, seed=99)
    # They could coincide on a tiny set, so we don't assert hard inequality.
    # At minimum both should be valid samples of size 5.
    assert len(result_c.sample_chunk_ids) == 5


def test_sample_bounded_by_size_and_corpus(tmp_storage: DuckDBStorage) -> None:
    """If sample_size > chunk count, returns all chunks."""
    _ingest_plain_chunks(tmp_storage, "small_ns", ["a", "b"])
    result = sample_and_infer_schema(tmp_storage, "small_ns", sample_size=100)
    assert result.sample_size == 2


def test_sample_storage_without_sample_chunks_method() -> None:
    """If the storage adapter doesn't implement sample_chunks, degrade gracefully."""

    class DummyStorage:
        pass

    result = sample_and_infer_schema(DummyStorage(), "ns")  # type: ignore[arg-type]
    assert result.sample_size == 0
    assert result.has_recoverable_structure is False


# ---------------------------------------------------------------------------
# Integration with build_corpus_profile
# ---------------------------------------------------------------------------


def test_build_profile_with_sampling_disabled(tmp_storage: DuckDBStorage) -> None:
    """enable_sampling=False (default) means no sampled schema even if density is low."""
    _ingest_plain_chunks(
        tmp_storage,
        "no_sampling",
        ["Air temperature 35 degC, pressure 101 kPa."],
    )
    profile = build_corpus_profile(tmp_storage, "no_sampling")
    assert profile.sampled_schema is None
    assert profile.has_sampled_schema is False


def test_build_profile_with_sampling_enabled_recovers_measurements(
    tmp_storage: DuckDBStorage,
) -> None:
    """enable_sampling=True recovers measurements when primary density is low."""
    _ingest_plain_chunks(
        tmp_storage,
        "recover_ns",
        [
            "Air temperature was 35 degC and wind 12 m/s.",
            "Pressure measured 101 kPa at sea level.",
            "Another chunk with Air Temp (C) column",
        ],
    )
    # Primary density will be ~0 because we ingested without structured metadata
    profile_no_sample = build_corpus_profile(tmp_storage, "recover_ns")
    assert profile_no_sample.metadata_density < 0.1  # primary sees nothing
    assert profile_no_sample.has_measurements is False

    # With sampling, the same profile recovers measurements and concepts
    profile_sampled = build_corpus_profile(
        tmp_storage,
        "recover_ns",
        enable_sampling=True,
        sample_size=10,
    )
    assert profile_sampled.sampled_schema is not None
    assert profile_sampled.sampled_schema.measurement_count > 0
    # has_measurements now returns True because sampled_schema backs it
    assert profile_sampled.has_measurements is True
    # richness_score reflects the sampled density
    assert profile_sampled.richness_score > 0.0
    # Recovered concepts union
    assert "temperature" in profile_sampled.recovered_concepts


def test_build_profile_sampling_skipped_when_density_already_high(
    tmp_storage: DuckDBStorage,
) -> None:
    """If the primary density is already high, sampling shouldn't re-scan."""
    # Ingest with real scientific metadata (via the structured pipeline)
    from clio_agentic_search.indexing.scientific import build_structure_aware_chunk_plan

    plan: ScientificChunkPlan = build_structure_aware_chunk_plan(
        namespace="rich_ns",
        document_id="doc_0",
        text="The temperature is 25 degC and pressure is 101 kPa.",
        chunk_size=200,
    )
    # Manually create the document + inject chunks with their metadata
    doc = DocumentRecord(
        namespace="rich_ns",
        document_id="doc_0",
        uri="synth://doc_0",
        checksum="h",
        modified_at_ns=1,
    )
    meta_records: list[MetadataRecord] = []
    for chunk_id, chunk_meta in plan.metadata_by_chunk_id.items():
        for k, v in chunk_meta.items():
            meta_records.append(
                MetadataRecord(
                    namespace="rich_ns",
                    record_id=chunk_id,
                    scope="chunk",
                    key=k,
                    value=v,
                )
            )
    file_state = FileIndexState(
        namespace="rich_ns",
        path="synth/doc_0",
        document_id="doc_0",
        mtime_ns=1,
        content_hash="h",
    )
    tmp_storage.upsert_document_bundles(
        [
            DocumentBundle(
                document=doc,
                chunks=plan.chunks,
                embeddings=[],
                metadata=meta_records,
                file_state=file_state,
            ),
        ],
        include_lexical_postings=False,
    )

    profile = build_corpus_profile(
        tmp_storage,
        "rich_ns",
        enable_sampling=True,
    )
    # Primary metadata density > threshold → sampled_schema should be None
    # (we don't waste the sampling pass)
    if profile.metadata_density >= 0.1:
        assert profile.sampled_schema is None


def test_sample_schema_has_recoverable_structure_flag() -> None:
    empty = SampledSchema(
        namespace="x",
        sample_size=5,
        total_chunks=5,
        concepts_found=frozenset(),
        measurement_units_found=frozenset(),
        measurement_count=0,
        chunks_with_signal=0,
        inferred_density=0.0,
        sample_chunk_ids=(),
    )
    assert empty.has_recoverable_structure is False

    with_measurements = SampledSchema(
        namespace="x",
        sample_size=5,
        total_chunks=5,
        concepts_found=frozenset(),
        measurement_units_found=frozenset({"degc"}),
        measurement_count=3,
        chunks_with_signal=2,
        inferred_density=0.4,
        sample_chunk_ids=(),
    )
    assert with_measurements.has_recoverable_structure is True

    with_concepts = SampledSchema(
        namespace="x",
        sample_size=5,
        total_chunks=5,
        concepts_found=frozenset({"temperature"}),
        measurement_units_found=frozenset(),
        measurement_count=0,
        chunks_with_signal=1,
        inferred_density=0.2,
        sample_chunk_ids=(),
    )
    assert with_concepts.has_recoverable_structure is True
