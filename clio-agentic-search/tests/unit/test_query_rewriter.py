"""Tests for query rewriting."""

from __future__ import annotations

from clio_agentic_search.retrieval.query_rewriter import (
    FallbackQueryRewriter,
    RewriteResult,
    _expand_unit_variants,
    _parse_llm_response,
)

# ---------------------------------------------------------------------------
# _expand_unit_variants
# ---------------------------------------------------------------------------


def test_expand_unit_variants_pressure() -> None:
    """A query containing 'kPa' should expand to include 'pa' and 'mpa'."""
    variants = _expand_unit_variants("pressure 200 kPa")
    assert variants  # non-empty
    lower_variants = {v.lower() for v in variants}
    assert "pa" in lower_variants
    assert "mpa" in lower_variants
    # The original unit itself should NOT appear as an expansion.
    assert "kpa" not in lower_variants


def test_expand_unit_variants_distance() -> None:
    """A query containing 'km' should expand to include 'm', 'cm', 'mm'."""
    variants = _expand_unit_variants("distance 5 km")
    lower_variants = {v.lower() for v in variants}
    assert "m" in lower_variants
    assert "cm" in lower_variants
    assert "mm" in lower_variants
    assert "km" not in lower_variants


def test_expand_unit_variants_no_units() -> None:
    """A query with no recognized units should return an empty list."""
    variants = _expand_unit_variants("no units here")
    assert variants == []


# ---------------------------------------------------------------------------
# FallbackQueryRewriter.rewrite
# ---------------------------------------------------------------------------


def test_fallback_rewriter_with_units() -> None:
    """When the query contains units, strategy should be 'expand'."""
    rewriter = FallbackQueryRewriter()
    result = rewriter.rewrite(
        query="pressure 200 kPa",
        retrieved_snippets=["some snippet"],
        hop_number=1,
        max_hops=3,
    )
    assert isinstance(result, RewriteResult)
    assert result.strategy == "expand"
    assert result.original_query == "pressure 200 kPa"
    # The rewritten query should contain additional unit variants.
    assert len(result.rewritten_query) > len(result.original_query)
    assert "pa" in result.rewritten_query.lower()


def test_fallback_rewriter_without_units() -> None:
    """When the query has no units, strategy should be 'done'."""
    rewriter = FallbackQueryRewriter()
    result = rewriter.rewrite(
        query="generic search terms",
        retrieved_snippets=[],
        hop_number=1,
        max_hops=3,
    )
    assert result.strategy == "done"
    assert result.rewritten_query == "generic search terms"


# ---------------------------------------------------------------------------
# _parse_llm_response
# ---------------------------------------------------------------------------


def test_parse_llm_response_valid_json() -> None:
    """Valid JSON should produce the correct RewriteResult."""
    raw = '{"strategy": "expand", "rewritten_query": "refined query", "reasoning": "added terms"}'
    result = _parse_llm_response(raw, original_query="original")
    assert result.strategy == "expand"
    assert result.rewritten_query == "refined query"
    assert result.reasoning == "added terms"
    assert result.original_query == "original"


def test_parse_llm_response_markdown_fences() -> None:
    """JSON wrapped in markdown code fences should be parsed correctly."""
    raw = (
        "```json\n"
        '{"strategy": "narrow", "rewritten_query": "focused query", "reasoning": "too broad"}\n'
        "```"
    )
    result = _parse_llm_response(raw, original_query="original")
    assert result.strategy == "narrow"
    assert result.rewritten_query == "focused query"
    assert result.reasoning == "too broad"


def test_parse_llm_response_invalid_json() -> None:
    """Unparseable text should return 'done' strategy with original query."""
    raw = "This is not JSON at all."
    result = _parse_llm_response(raw, original_query="my query")
    assert result.strategy == "done"
    assert result.rewritten_query == "my query"
    assert "unparseable" in result.reasoning.lower()


def test_parse_llm_response_missing_fields() -> None:
    """JSON with missing fields should fill in defaults."""
    raw = '{"strategy": "pivot"}'
    result = _parse_llm_response(raw, original_query="fallback query")
    assert result.strategy == "pivot"
    # Missing rewritten_query should fall back to original.
    assert result.rewritten_query == "fallback query"
    # Missing reasoning should default to empty string.
    assert result.reasoning == ""


def test_parse_llm_response_invalid_strategy() -> None:
    """An unrecognized strategy should be replaced with 'done'."""
    raw = '{"strategy": "invalid_strategy", "rewritten_query": "q", "reasoning": "r"}'
    result = _parse_llm_response(raw, original_query="q")
    assert result.strategy == "done"


def test_parse_llm_response_empty_rewritten_query() -> None:
    """An empty rewritten_query should fall back to the original query."""
    raw = '{"strategy": "expand", "rewritten_query": "", "reasoning": "empty"}'
    result = _parse_llm_response(raw, original_query="original")
    assert result.rewritten_query == "original"
