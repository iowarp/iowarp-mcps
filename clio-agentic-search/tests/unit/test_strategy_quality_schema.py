"""Tests for BranchPlan fields added by the quality + metadata schema layers."""

from __future__ import annotations

from clio_agentic_search.indexing.quality import QualitySummary
from clio_agentic_search.retrieval.corpus_profile import CorpusProfile
from clio_agentic_search.retrieval.metadata_schema import build_metadata_schema
from clio_agentic_search.retrieval.scientific import (
    NumericRangeOperator,
    ScientificQueryOperators,
)
from clio_agentic_search.retrieval.strategy import select_branches


def _make_profile_with_schema_and_quality(
    *,
    concepts_in_schema: list[str] | None = None,
    quality_acceptable_ratio: float = 1.0,
    total_quality_rows: int = 1000,
) -> CorpusProfile:
    # Build a schema matching the supplied concepts
    if concepts_in_schema is None:
        concepts_in_schema = ["temperature", "humidity"]
    rows = [(concept, "chunk", "x", 100) for concept in concepts_in_schema]
    schema = build_metadata_schema(
        namespace="test",
        metadata_rows=rows,
        total_documents=10,
        total_chunks=1000,
    )

    # Build a quality summary with the target acceptable ratio
    good = int(total_quality_rows * quality_acceptable_ratio)
    bad = total_quality_rows - good
    quality = QualitySummary(
        total=total_quality_rows,
        good=good,
        questionable=0,
        bad=bad,
        missing=0,
        estimated=0,
        unknown=0,
    )

    return CorpusProfile(
        namespace="test",
        document_count=10,
        chunk_count=1000,
        measurement_count=total_quality_rows,
        formula_count=0,
        distinct_units=("0,0,0,0,1,0,0",),
        distinct_formulas=(),
        metadata_density=0.8,
        embedding_count=1000,
        lexical_posting_count=5000,
        metadata_schema=schema,
        quality_summary=quality,
    )


def test_quality_filter_enabled_when_corpus_has_non_good_rows() -> None:
    """If the profile shows the corpus has some bad/missing rows, the
    quality filter should auto-activate so users get clean results by default."""
    profile = _make_profile_with_schema_and_quality(
        quality_acceptable_ratio=0.9,  # 10% non-acceptable
    )
    plan = select_branches(
        query="temperature above 30 celsius",
        operators=ScientificQueryOperators(
            numeric_range=NumericRangeOperator(unit="degC", minimum=30.0),
        ),
        profile=profile,
        connector_has_lexical=True,
        connector_has_vector=True,
        connector_has_graph=False,
        connector_has_scientific=True,
    )
    assert plan.use_scientific is True
    assert plan.apply_quality_filter is True
    assert "quality filter enabled" in plan.reasoning
    assert 0.0 <= plan.average_quality <= 1.0


def test_quality_filter_not_enabled_when_corpus_all_good() -> None:
    """If every row is GOOD, no filter needed."""
    profile = _make_profile_with_schema_and_quality(
        quality_acceptable_ratio=1.0,
    )
    plan = select_branches(
        query="temperature above 30 celsius",
        operators=ScientificQueryOperators(
            numeric_range=NumericRangeOperator(unit="degC", minimum=30.0),
        ),
        profile=profile,
        connector_has_lexical=True,
        connector_has_vector=True,
        connector_has_graph=False,
        connector_has_scientific=True,
    )
    assert plan.apply_quality_filter is False


def test_targeted_concepts_picked_from_query() -> None:
    """When the query mentions a known concept and the schema has it, it's targeted."""
    profile = _make_profile_with_schema_and_quality(
        concepts_in_schema=["temperature", "pressure", "humidity"],
    )
    plan = select_branches(
        query="Find temperature above 30 degrees celsius",
        operators=ScientificQueryOperators(
            numeric_range=NumericRangeOperator(unit="degC", minimum=30.0),
        ),
        profile=profile,
        connector_has_lexical=True,
        connector_has_vector=True,
        connector_has_graph=False,
        connector_has_scientific=True,
    )
    assert "temperature" in plan.targeted_concepts
    # Other concepts not mentioned in the query should not be targeted
    assert "humidity" not in plan.targeted_concepts
    assert "pressure" not in plan.targeted_concepts


def test_targeted_concepts_requires_concept_in_schema() -> None:
    """If the query mentions a concept but the schema doesn't have it, not targeted."""
    profile = _make_profile_with_schema_and_quality(
        concepts_in_schema=["humidity"],  # no temperature
    )
    plan = select_branches(
        query="Find temperature above 30 celsius",
        operators=ScientificQueryOperators(
            numeric_range=NumericRangeOperator(unit="degC", minimum=30.0),
        ),
        profile=profile,
        connector_has_lexical=True,
        connector_has_vector=True,
        connector_has_graph=False,
        connector_has_scientific=True,
    )
    assert "temperature" not in plan.targeted_concepts


def test_schema_richness_propagated_to_plan() -> None:
    profile = _make_profile_with_schema_and_quality(
        concepts_in_schema=["temperature", "pressure", "humidity", "wind_speed", "solar_radiation"],
    )
    plan = select_branches(
        query="anything",
        operators=ScientificQueryOperators(),
        profile=profile,
        connector_has_lexical=True,
        connector_has_vector=True,
        connector_has_graph=False,
        connector_has_scientific=True,
    )
    # richness_score should be > 0 when the schema has recognised concepts
    assert plan.schema_richness > 0.3


def test_quality_filter_not_enabled_without_scientific_branch() -> None:
    """If the scientific branch won't run, the quality filter isn't needed either."""
    profile = _make_profile_with_schema_and_quality(
        quality_acceptable_ratio=0.5,
    )
    plan = select_branches(
        query="free text query with no operators",
        operators=ScientificQueryOperators(),  # nothing active
        profile=profile,
        connector_has_lexical=True,
        connector_has_vector=True,
        connector_has_graph=False,
        connector_has_scientific=True,
    )
    assert plan.use_scientific is False
    assert plan.apply_quality_filter is False


def test_profile_none_yields_default_fields() -> None:
    plan = select_branches(
        query="x",
        operators=ScientificQueryOperators(
            numeric_range=NumericRangeOperator(unit="degC", minimum=0),
        ),
        profile=None,
        connector_has_lexical=True,
        connector_has_vector=True,
        connector_has_scientific=True,
    )
    # Defaults when profile is missing
    assert plan.apply_quality_filter is False
    assert plan.targeted_concepts == ()
    assert plan.schema_richness == 0.0
    assert plan.average_quality == 1.0
