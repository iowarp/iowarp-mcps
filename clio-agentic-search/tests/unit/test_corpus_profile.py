"""Tests for corpus profiling."""

from __future__ import annotations

from clio_agentic_search.retrieval.corpus_profile import CorpusProfile, build_corpus_profile


class _FakeStorage:
    """Minimal stub that lacks corpus_profile_stats."""

    pass


class _FakeStorageWithProfile:
    """Stub that implements corpus_profile_stats."""

    def corpus_profile_stats(self, namespace: str) -> CorpusProfile:
        return CorpusProfile(
            namespace=namespace,
            document_count=10,
            chunk_count=50,
            measurement_count=20,
            formula_count=5,
            distinct_units=("kg", "m"),
            distinct_formulas=("f=ma",),
            metadata_density=0.6,
            embedding_count=50,
            lexical_posting_count=500,
        )


def test_corpus_profile_properties() -> None:
    p = CorpusProfile(
        namespace="ns",
        document_count=5,
        chunk_count=10,
        measurement_count=3,
        formula_count=0,
        distinct_units=("pa",),
        distinct_formulas=(),
        metadata_density=0.3,
        embedding_count=10,
        lexical_posting_count=100,
    )
    assert p.has_measurements is True
    assert p.has_formulas is False
    assert p.has_embeddings is True
    assert p.has_lexical is True


def test_corpus_profile_zero_counts() -> None:
    p = CorpusProfile(
        namespace="empty",
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
    assert p.has_measurements is False
    assert p.has_formulas is False
    assert p.has_embeddings is False
    assert p.has_lexical is False


def test_build_corpus_profile_no_stats_method() -> None:
    """When storage has no corpus_profile_stats, return zeroed profile."""
    profile = build_corpus_profile(_FakeStorage(), "test")  # type: ignore[arg-type]
    assert profile.namespace == "test"
    assert profile.document_count == 0
    assert profile.measurement_count == 0


def test_build_corpus_profile_with_stats() -> None:
    """When storage has corpus_profile_stats, delegate to it."""
    profile = build_corpus_profile(_FakeStorageWithProfile(), "myns")  # type: ignore[arg-type]
    assert profile.namespace == "myns"
    assert profile.document_count == 10
    assert profile.measurement_count == 20
    assert profile.has_formulas is True
