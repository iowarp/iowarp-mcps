"""Tests for branch selection strategy."""

from __future__ import annotations

from clio_agentic_search.retrieval.corpus_profile import CorpusProfile
from clio_agentic_search.retrieval.scientific import (
    NumericRangeOperator,
    ScientificQueryOperators,
)
from clio_agentic_search.retrieval.strategy import select_branches


def _make_profile(
    *,
    has_meas: bool = True,
    has_form: bool = True,
    has_emb: bool = True,
    has_lex: bool = True,
) -> CorpusProfile:
    return CorpusProfile(
        namespace="test",
        document_count=10,
        chunk_count=50,
        measurement_count=5 if has_meas else 0,
        formula_count=3 if has_form else 0,
        distinct_units=("pa",) if has_meas else (),
        distinct_formulas=("f=ma",) if has_form else (),
        metadata_density=0.5,
        embedding_count=50 if has_emb else 0,
        lexical_posting_count=100 if has_lex else 0,
    )


def test_no_profile_uses_all_branches() -> None:
    """When profile is None, all declared branches are used."""
    plan = select_branches(
        query="pressure 200 kPa",
        operators=ScientificQueryOperators(
            numeric_range=NumericRangeOperator(minimum=200, maximum=400, unit="kPa"),
        ),
        profile=None,
        connector_has_lexical=True,
        connector_has_vector=True,
        connector_has_graph=True,
        connector_has_scientific=True,
    )
    assert plan.use_lexical is True
    assert plan.use_vector is True
    assert plan.use_graph is True
    assert plan.use_scientific is True
    assert "no corpus profile" in plan.reasoning


def test_skip_scientific_when_no_measurements() -> None:
    """Scientific branch skipped when corpus has no measurements."""
    profile = _make_profile(has_meas=False)
    plan = select_branches(
        query="pressure 200 kPa",
        operators=ScientificQueryOperators(
            numeric_range=NumericRangeOperator(minimum=200, maximum=400, unit="kPa"),
        ),
        profile=profile,
        connector_has_lexical=True,
        connector_has_vector=True,
        connector_has_graph=False,
        connector_has_scientific=True,
    )
    assert plan.use_scientific is False
    assert "scientific skipped" in plan.reasoning


def test_skip_vector_when_no_embeddings() -> None:
    """Vector branch skipped when no embeddings indexed."""
    profile = _make_profile(has_emb=False)
    plan = select_branches(
        query="temperature data",
        operators=ScientificQueryOperators(),
        profile=profile,
        connector_has_lexical=True,
        connector_has_vector=True,
        connector_has_graph=False,
        connector_has_scientific=True,
    )
    assert plan.use_vector is False
    assert "vector skipped" in plan.reasoning


def test_all_branches_when_profile_has_everything() -> None:
    """All branches activated when corpus has all data types."""
    profile = _make_profile()
    plan = select_branches(
        query="pressure 200 kPa",
        operators=ScientificQueryOperators(
            numeric_range=NumericRangeOperator(minimum=200, maximum=400, unit="kPa"),
        ),
        profile=profile,
        connector_has_lexical=True,
        connector_has_vector=True,
        connector_has_graph=True,
        connector_has_scientific=True,
    )
    assert plan.use_lexical is True
    assert plan.use_vector is True
    assert plan.use_graph is True
    assert plan.use_scientific is True


def test_no_operators_skips_scientific() -> None:
    """Scientific branch skipped when no operators in query."""
    profile = _make_profile()
    plan = select_branches(
        query="general search",
        operators=ScientificQueryOperators(),
        profile=profile,
        connector_has_lexical=True,
        connector_has_vector=True,
        connector_has_graph=False,
        connector_has_scientific=True,
    )
    assert plan.use_scientific is False
    assert "no operators" in plan.reasoning


def test_formula_operator_uses_scientific_when_formulas_exist() -> None:
    """Scientific branch activated for formula queries when corpus has formulas."""
    profile = _make_profile(has_meas=False, has_form=True)
    plan = select_branches(
        query="F=ma",
        operators=ScientificQueryOperators(formula="F=ma"),
        profile=profile,
        connector_has_lexical=True,
        connector_has_vector=True,
        connector_has_graph=False,
        connector_has_scientific=True,
    )
    assert plan.use_scientific is True
