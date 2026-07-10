"""Tests for QualityFilterOperator integration in retrieval scoring."""

from __future__ import annotations

from clio_agentic_search.indexing.quality import QualityFlag
from clio_agentic_search.indexing.scientific import Measurement, encode_measurements
from clio_agentic_search.retrieval.scientific import (
    NumericRangeOperator,
    QualityFilterOperator,
    ScientificQueryOperators,
    score_scientific_metadata,
)


def _metadata_from_measurements(measurements: list[Measurement]) -> dict[str, str]:
    return {"scientific.measurements": encode_measurements(measurements)}


def test_quality_filter_operator_accepts_defaults() -> None:
    op = QualityFilterOperator()
    assert op.accepts("good") is True
    assert op.accepts("estimated") is True
    assert op.accepts("bad") is False
    assert op.accepts("questionable") is False
    assert op.accepts("missing") is False
    assert op.accepts("unknown") is False


def test_quality_filter_operator_minimum_score() -> None:
    # Custom: accept GOOD only, and require >= 0.9 score
    op = QualityFilterOperator(
        acceptable=(QualityFlag.GOOD,),
        minimum_score=0.9,
    )
    assert op.accepts("good") is True
    assert op.accepts("estimated") is False  # not in whitelist


def test_quality_filter_operator_accept_all_flags() -> None:
    # Custom: accept every flag including MISSING (for debugging/audit)
    op = QualityFilterOperator(
        acceptable=tuple(QualityFlag),
    )
    for flag in QualityFlag:
        assert op.accepts(flag.value) is True


def test_quality_filter_operator_handles_raw_string() -> None:
    op = QualityFilterOperator()
    # Accepts both enum and string forms
    assert op.accepts(QualityFlag.GOOD) is True
    assert op.accepts("good") is True


def test_quality_filter_operator_acceptable_strings() -> None:
    op = QualityFilterOperator(
        acceptable=(QualityFlag.GOOD, QualityFlag.ESTIMATED, QualityFlag.UNKNOWN),
    )
    result = op.acceptable_strings()
    assert set(result) == {"good", "estimated", "unknown"}


# ---------------------------------------------------------------------------
# Integration: score_scientific_metadata with quality filter
# ---------------------------------------------------------------------------


def test_scoring_with_quality_filter_drops_bad_rows() -> None:
    # Chunk has one GOOD temperature (35°C) and one BAD temperature (38°C)
    measurements = [
        Measurement(
            raw_value=35.0,
            raw_unit="degc",
            canonical_value=308.15,
            canonical_unit="0,0,0,0,1,0,0",
            quality="good",
        ),
        Measurement(
            raw_value=38.0,
            raw_unit="degc",
            canonical_value=311.15,
            canonical_unit="0,0,0,0,1,0,0",
            quality="bad",
        ),
    ]
    metadata = _metadata_from_measurements(measurements)

    ops = ScientificQueryOperators(
        numeric_range=NumericRangeOperator(unit="degc", minimum=34.0, maximum=40.0),
        quality_filter=QualityFilterOperator(),  # defaults: GOOD/ESTIMATED only
    )
    # Should still match because the GOOD row survives the filter
    # and falls in [34, 40] degC
    score = score_scientific_metadata(metadata, ops)
    assert score > 0.0


def test_scoring_with_quality_filter_rejects_all_bad() -> None:
    # All measurements are BAD — quality filter removes everything
    measurements = [
        Measurement(
            raw_value=35.0,
            raw_unit="degc",
            canonical_value=308.15,
            canonical_unit="0,0,0,0,1,0,0",
            quality="bad",
        ),
        Measurement(
            raw_value=38.0,
            raw_unit="degc",
            canonical_value=311.15,
            canonical_unit="0,0,0,0,1,0,0",
            quality="bad",
        ),
    ]
    metadata = _metadata_from_measurements(measurements)

    ops = ScientificQueryOperators(
        numeric_range=NumericRangeOperator(unit="degc", minimum=34.0, maximum=40.0),
        quality_filter=QualityFilterOperator(),
    )
    score = score_scientific_metadata(metadata, ops)
    assert score == 0.0


def test_scoring_without_quality_filter_matches_legacy_behavior() -> None:
    # No quality filter → pre-existing behavior unchanged
    measurements = [
        Measurement(
            raw_value=35.0,
            raw_unit="degc",
            canonical_value=308.15,
            canonical_unit="0,0,0,0,1,0,0",
            quality="bad",  # even though bad, no filter → matches
        ),
    ]
    metadata = _metadata_from_measurements(measurements)

    ops = ScientificQueryOperators(
        numeric_range=NumericRangeOperator(unit="degc", minimum=34.0, maximum=40.0),
    )
    score = score_scientific_metadata(metadata, ops)
    assert score > 0.0


def test_scoring_quality_boost_rewards_good_data() -> None:
    # Two chunks, one all-GOOD, one mixed. All-GOOD should score higher.
    good_only = [
        Measurement(
            raw_value=35.0,
            raw_unit="degc",
            canonical_value=308.15,
            canonical_unit="0,0,0,0,1,0,0",
            quality="good",
        ),
    ]
    mixed = [
        Measurement(
            raw_value=35.0,
            raw_unit="degc",
            canonical_value=308.15,
            canonical_unit="0,0,0,0,1,0,0",
            quality="estimated",  # acceptable but lower score
        ),
    ]

    ops = ScientificQueryOperators(
        numeric_range=NumericRangeOperator(unit="degc", minimum=34.0, maximum=40.0),
        quality_filter=QualityFilterOperator(),
    )
    score_good = score_scientific_metadata(_metadata_from_measurements(good_only), ops)
    score_mixed = score_scientific_metadata(_metadata_from_measurements(mixed), ops)

    assert score_good > score_mixed > 0.0


def test_is_active_with_only_quality_filter() -> None:
    ops = ScientificQueryOperators(quality_filter=QualityFilterOperator())
    assert ops.is_active() is True


def test_is_active_empty() -> None:
    ops = ScientificQueryOperators()
    assert ops.is_active() is False
