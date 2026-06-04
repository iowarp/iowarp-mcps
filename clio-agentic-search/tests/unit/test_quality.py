"""Unit tests for the data-quality layer (indexing.quality)."""

from __future__ import annotations

from clio_agentic_search.indexing.quality import (
    QualityFlag,
    derive_flag_from_value,
    is_physically_plausible,
    parse_qc_token,
    summarise_quality,
)
from clio_agentic_search.indexing.scientific import (
    Measurement,
    decode_measurements,
    encode_measurements,
)

# ---------------------------------------------------------------------------
# QualityFlag enum + string round-trips
# ---------------------------------------------------------------------------


def test_quality_flag_from_string_known_values() -> None:
    assert QualityFlag.from_string("good") is QualityFlag.GOOD
    assert QualityFlag.from_string("bad") is QualityFlag.BAD
    assert QualityFlag.from_string("missing") is QualityFlag.MISSING
    assert QualityFlag.from_string("questionable") is QualityFlag.QUESTIONABLE
    assert QualityFlag.from_string("estimated") is QualityFlag.ESTIMATED


def test_quality_flag_from_string_unknown_or_none() -> None:
    assert QualityFlag.from_string(None) is QualityFlag.UNKNOWN
    assert QualityFlag.from_string("") is QualityFlag.UNKNOWN
    assert QualityFlag.from_string("complete gibberish") is QualityFlag.UNKNOWN


def test_quality_flag_case_insensitive() -> None:
    assert QualityFlag.from_string("GOOD") is QualityFlag.GOOD
    assert QualityFlag.from_string("  Bad  ") is QualityFlag.BAD


def test_quality_flag_is_acceptable() -> None:
    assert QualityFlag.GOOD.is_acceptable is True
    assert QualityFlag.ESTIMATED.is_acceptable is True
    assert QualityFlag.QUESTIONABLE.is_acceptable is False
    assert QualityFlag.BAD.is_acceptable is False
    assert QualityFlag.MISSING.is_acceptable is False
    assert QualityFlag.UNKNOWN.is_acceptable is False


def test_quality_flag_numeric_score_ordering() -> None:
    # GOOD > ESTIMATED > UNKNOWN > QUESTIONABLE > BAD = MISSING
    assert QualityFlag.GOOD.numeric_score > QualityFlag.ESTIMATED.numeric_score
    assert QualityFlag.ESTIMATED.numeric_score > QualityFlag.UNKNOWN.numeric_score
    assert QualityFlag.UNKNOWN.numeric_score > QualityFlag.QUESTIONABLE.numeric_score
    assert QualityFlag.QUESTIONABLE.numeric_score > QualityFlag.BAD.numeric_score
    assert QualityFlag.BAD.numeric_score == QualityFlag.MISSING.numeric_score == 0.0
    assert QualityFlag.GOOD.numeric_score == 1.0


# ---------------------------------------------------------------------------
# parse_qc_token — covers CIMIS, NOAA, and common conventions
# ---------------------------------------------------------------------------


def test_parse_qc_token_cimis_conventions() -> None:
    # CIMIS: blank/nothing = good, Y = questionable, R = rejected/bad, M = missing
    assert parse_qc_token("") is QualityFlag.GOOD
    assert parse_qc_token(" ") is QualityFlag.GOOD
    assert parse_qc_token("Y") is QualityFlag.QUESTIONABLE
    assert parse_qc_token("R") is QualityFlag.BAD
    assert parse_qc_token("M") is QualityFlag.MISSING


def test_parse_qc_token_noaa_conventions() -> None:
    assert parse_qc_token("M") is QualityFlag.MISSING
    # Generic good cases used by multiple NOAA feeds
    assert parse_qc_token("0") is QualityFlag.GOOD
    assert parse_qc_token("good") is QualityFlag.GOOD


def test_parse_qc_token_missing_sentinels() -> None:
    assert parse_qc_token("NA") is QualityFlag.MISSING
    assert parse_qc_token("N/A") is QualityFlag.MISSING
    assert parse_qc_token("null") is QualityFlag.MISSING
    assert parse_qc_token("NaN") is QualityFlag.MISSING
    assert parse_qc_token("-9999") is QualityFlag.MISSING


def test_parse_qc_token_none_returns_unknown() -> None:
    assert parse_qc_token(None) is QualityFlag.UNKNOWN


def test_parse_qc_token_unknown_flag_returns_unknown() -> None:
    assert parse_qc_token("XYZ") is QualityFlag.UNKNOWN
    assert parse_qc_token("123") is QualityFlag.UNKNOWN


# ---------------------------------------------------------------------------
# QualitySummary aggregation
# ---------------------------------------------------------------------------


def test_summarise_quality_empty() -> None:
    summary = summarise_quality([])
    assert summary.total == 0
    assert summary.acceptable_count == 0
    assert summary.acceptable_ratio == 0.0
    assert summary.average_score == 0.0


def test_summarise_quality_mixed() -> None:
    flags = [
        QualityFlag.GOOD,
        QualityFlag.GOOD,
        QualityFlag.GOOD,
        QualityFlag.QUESTIONABLE,
        QualityFlag.MISSING,
    ]
    summary = summarise_quality(flags)
    assert summary.total == 5
    assert summary.good == 3
    assert summary.questionable == 1
    assert summary.missing == 1
    assert summary.acceptable_count == 3  # only GOOD + ESTIMATED
    assert summary.acceptable_ratio == 0.6
    # (3*1.0 + 1*0.25 + 1*0.0) / 5 = 0.65
    assert abs(summary.average_score - 0.65) < 1e-9


def test_summarise_quality_all_good() -> None:
    flags = [QualityFlag.GOOD] * 10
    summary = summarise_quality(flags)
    assert summary.acceptable_ratio == 1.0
    assert summary.average_score == 1.0


# ---------------------------------------------------------------------------
# Physical plausibility
# ---------------------------------------------------------------------------


def test_is_physically_plausible_temperature() -> None:
    # Ordinary room temp = 293 K → OK
    assert is_physically_plausible("0,0,0,0,1,0,0", 293.15) is True
    # Cryo = 77 K (liquid nitrogen) → OK
    assert is_physically_plausible("0,0,0,0,1,0,0", 77.0) is True
    # Near absolute zero → rejected
    assert is_physically_plausible("0,0,0,0,1,0,0", 0.5) is False
    # Sun surface-ish → rejected
    assert is_physically_plausible("0,0,0,0,1,0,0", 1e6) is False


def test_is_physically_plausible_pressure() -> None:
    # 1 atm = 101325 Pa → OK
    assert is_physically_plausible("1,-1,-2,0,0,0,0", 101325.0) is True
    # Deep lab vacuum = 0.001 Pa → rejected by our sanity lower bound
    assert is_physically_plausible("1,-1,-2,0,0,0,0", 0.001) is False
    # 10 GPa → at the upper edge, OK
    assert is_physically_plausible("1,-1,-2,0,0,0,0", 1e9) is True
    # 100 GPa → out of range
    assert is_physically_plausible("1,-1,-2,0,0,0,0", 1e11) is False


def test_is_physically_plausible_unknown_dimension() -> None:
    # Dimensions not in the table always pass (we don't constrain them)
    assert is_physically_plausible("unknown_dim", 1e20) is True


def test_derive_flag_downgrades_out_of_range() -> None:
    # Out-of-range value with a GOOD source flag → QUESTIONABLE
    assert (
        derive_flag_from_value("0,0,0,0,1,0,0", 1e6, QualityFlag.GOOD) is QualityFlag.QUESTIONABLE
    )


def test_derive_flag_preserves_bad() -> None:
    # BAD stays BAD even if the value happens to be in range
    assert derive_flag_from_value("0,0,0,0,1,0,0", 293.0, QualityFlag.BAD) is QualityFlag.BAD


def test_derive_flag_preserves_good_in_range() -> None:
    # In-range with GOOD source → stays GOOD
    assert derive_flag_from_value("0,0,0,0,1,0,0", 293.0, QualityFlag.GOOD) is QualityFlag.GOOD


# ---------------------------------------------------------------------------
# Measurement encode / decode with quality — backward compatibility
# ---------------------------------------------------------------------------


def test_measurement_encode_decode_roundtrip_with_quality() -> None:
    original = [
        Measurement(
            raw_value=30.0,
            raw_unit="degc",
            canonical_value=303.15,
            canonical_unit="0,0,0,0,1,0,0",
            quality="good",
        ),
        Measurement(
            raw_value=120.0,
            raw_unit="degc",
            canonical_value=393.15,
            canonical_unit="0,0,0,0,1,0,0",
            quality="questionable",
        ),
    ]
    encoded = encode_measurements(original)
    decoded = decode_measurements(encoded)
    assert len(decoded) == 2
    assert decoded[0].quality == "good"
    assert decoded[1].quality == "questionable"
    assert decoded[0].canonical_value == 303.15
    assert decoded[1].canonical_value == 393.15


def test_measurement_decode_legacy_4field_format_defaults_unknown() -> None:
    # Legacy rows without quality field should parse as "unknown"
    legacy_encoded = "0,0,0,0,1,0,0|303.15|degc|30"
    decoded = decode_measurements(legacy_encoded)
    assert len(decoded) == 1
    assert decoded[0].quality == "unknown"
    assert decoded[0].canonical_value == 303.15


def test_measurement_default_quality_is_unknown() -> None:
    # Constructing a Measurement without quality → "unknown"
    m = Measurement(
        raw_value=1.0,
        raw_unit="m",
        canonical_value=1.0,
        canonical_unit="0,1,0,0,0,0,0",
    )
    assert m.quality == "unknown"


def test_encode_measurements_empty() -> None:
    assert encode_measurements([]) == ""


def test_decode_measurements_empty() -> None:
    assert decode_measurements("") == []


def test_decode_measurements_skips_malformed() -> None:
    # Mix of valid and malformed entries
    encoded = "0,0,0,0,1,0,0|303.15|degc|30|good;junk;0,1,0,0,0,0,0|5|m|5|bad"
    decoded = decode_measurements(encoded)
    assert len(decoded) == 2  # "junk" dropped
    assert decoded[0].quality == "good"
    assert decoded[1].quality == "bad"
