"""Tests for the science-aware CSV parser (indexing.csv_parser)."""

from __future__ import annotations

import textwrap

from clio_agentic_search.indexing.csv_parser import (
    _find_qc_column_index,
    _parse_header_unit,
    analyse_header,
    filter_rows_by_concept,
    parse_scientific_csv,
)
from clio_agentic_search.indexing.quality import QualityFlag

# ---------------------------------------------------------------------------
# Header parsing
# ---------------------------------------------------------------------------


def test_parse_header_unit_parentheses() -> None:
    assert _parse_header_unit("Air Temp (C)") == ("Air Temp", "C")


def test_parse_header_unit_square_brackets() -> None:
    assert _parse_header_unit("Pressure [kPa]") == ("Pressure", "kPa")


def test_parse_header_unit_no_unit() -> None:
    assert _parse_header_unit("Station Name") == ("Station Name", None)


def test_parse_header_unit_compound_unit() -> None:
    assert _parse_header_unit("Wind Speed (m/s)") == ("Wind Speed", "m/s")


# ---------------------------------------------------------------------------
# QC column detection
# ---------------------------------------------------------------------------


def test_find_qc_column_cimis_convention() -> None:
    # CIMIS format: each measurement followed by a "qc" column
    headers = ["Date", "Air Temp (C)", "qc", "Rel Hum (%)", "qc"]
    assert _find_qc_column_index(headers, 1) == 2  # Air Temp's qc
    assert _find_qc_column_index(headers, 3) == 4  # Rel Hum's qc


def test_find_qc_column_suffix_convention() -> None:
    headers = ["Date", "temp", "temp_qflag", "pressure", "pressure_q"]
    assert _find_qc_column_index(headers, 1) == 2
    assert _find_qc_column_index(headers, 3) == 4


def test_find_qc_column_none_when_no_qc() -> None:
    headers = ["Date", "temperature", "pressure"]
    assert _find_qc_column_index(headers, 1) is None
    assert _find_qc_column_index(headers, 2) is None


# ---------------------------------------------------------------------------
# analyse_header
# ---------------------------------------------------------------------------


def test_analyse_header_cimis() -> None:
    headers = [
        "Stn Id",
        "Stn Name",
        "Date",
        "Hour (PST)",
        "Air Temp (C)",
        "qc",
        "Rel Hum (%)",
        "qc",
        "Wind Speed (m/s)",
        "qc",
    ]
    schema = analyse_header(headers)
    # Air Temp, Wind Speed are parseable measurements
    # (Rel Hum has % which isn't in the registry)
    measurement_cols = schema.measurement_columns
    display_names = [c.display_name for c in measurement_cols]
    assert "Air Temp" in display_names
    assert "Wind Speed" in display_names

    # Air Temp should have an adjacent qc column detected
    air_temp = next(c for c in schema.columns if c.display_name == "Air Temp")
    assert air_temp.qc_column_index == 5

    # Air Temp should be aligned to the "temperature" concept
    assert air_temp.canonical_concept == "temperature"


def test_analyse_header_ignores_percent() -> None:
    # "%" is dimensionless and not in the registry — not a measurement column.
    headers = ["Humidity (%)"]
    schema = analyse_header(headers)
    assert len(schema.measurement_columns) == 0


# ---------------------------------------------------------------------------
# End-to-end parsing with CIMIS-like fixture
# ---------------------------------------------------------------------------


_CIMIS_FIXTURE = textwrap.dedent("""\
    Stn Id,Stn Name,Date,Hour (PST),Air Temp (C),qc,Wind Speed (m/s),qc
    105,Westlands,2024-06-01,0100,20.6,,2.1,
    105,Westlands,2024-06-01,1400,35.2,,3.4,
    105,Westlands,2024-06-01,1500,36.1,Y,3.5,
    105,Westlands,2024-06-01,1600,999,M,4.2,
    105,Westlands,2024-06-01,1700,32.0,,100.0,R
""").strip()


def test_parse_cimis_fixture_shape() -> None:
    parsed = parse_scientific_csv(_CIMIS_FIXTURE)
    # 5 data rows (all non-empty)
    assert len(parsed.rows) == 5
    # 2 measurement columns
    assert len(parsed.schema.measurement_columns) == 2


def test_parse_cimis_fixture_air_temp_values() -> None:
    parsed = parse_scientific_csv(_CIMIS_FIXTURE)
    # Extract just the temperature measurements across rows.
    # Measurements are emitted in the same order as schema.measurement_columns;
    # air temp is first (after wind speed in header order — but our schema
    # walks header order, so air temp is first).
    temp_measurements = []
    for row in parsed.rows:
        for col, m in zip(parsed.schema.measurement_columns, row.measurements, strict=False):
            if col.canonical_concept == "temperature":
                temp_measurements.append(m)
    assert len(temp_measurements) == 5

    raw_values = [m.raw_value for m in temp_measurements]
    assert raw_values == [20.6, 35.2, 36.1, 999.0, 32.0]


def test_parse_cimis_fixture_qc_flags() -> None:
    parsed = parse_scientific_csv(_CIMIS_FIXTURE)
    temp_measurements = []
    for row in parsed.rows:
        for col, m in zip(parsed.schema.measurement_columns, row.measurements, strict=False):
            if col.canonical_concept == "temperature":
                temp_measurements.append(m)

    # Row 1: blank qc → good
    assert temp_measurements[0].quality == "good"
    # Row 2: blank qc → good
    assert temp_measurements[1].quality == "good"
    # Row 3: Y qc → questionable
    assert temp_measurements[2].quality == "questionable"
    # Row 4: M qc → missing (but value is 999, physically implausible too)
    assert temp_measurements[3].quality == "missing"
    # Row 5: blank qc → good
    assert temp_measurements[4].quality == "good"


def test_parse_cimis_fixture_wind_quality_and_range() -> None:
    parsed = parse_scientific_csv(_CIMIS_FIXTURE)
    wind_measurements = []
    for row in parsed.rows:
        for col, m in zip(parsed.schema.measurement_columns, row.measurements, strict=False):
            if col.canonical_concept == "wind_speed":
                wind_measurements.append(m)
    # Row 5 has wind=100 m/s with qc=R (rejected). Source flag is BAD, kept.
    assert wind_measurements[4].quality == "bad"


def test_parse_cimis_fixture_filter_by_concept_default_quality() -> None:
    parsed = parse_scientific_csv(_CIMIS_FIXTURE)
    # Filter: temperature >= 30°C = 303.15 K, default quality (good/estimated)
    results = filter_rows_by_concept(
        parsed,
        concept="temperature",
        min_value_canonical=303.15,
    )
    # Row 2 (35.2 → 308.35, good), row 3 (36.1, questionable - dropped),
    # row 4 (999, missing - dropped), row 5 (32.0 → 305.15, good).
    # So 2 results expected.
    assert len(results) == 2
    raw_values = sorted(r["raw_value"] for r in results)
    assert raw_values == [32.0, 35.2]


def test_parse_cimis_fixture_filter_relaxed_quality_includes_questionable() -> None:
    parsed = parse_scientific_csv(_CIMIS_FIXTURE)
    # Allow questionable through too
    results = filter_rows_by_concept(
        parsed,
        concept="temperature",
        min_value_canonical=303.15,
        acceptable_quality=frozenset(
            {
                QualityFlag.GOOD,
                QualityFlag.ESTIMATED,
                QualityFlag.QUESTIONABLE,
            }
        ),
    )
    # Adds row 3 (36.1) and row 4 (999°C → physically implausible → questionable)
    raw_values = sorted(r["raw_value"] for r in results)
    # Note: 999 C → 1272.15 K, exceeds physical plausibility → questionable
    # (source was MISSING though, so still excluded). That's important to
    # verify: derive_flag preserves MISSING.
    # So we expect: 32.0, 35.2, 36.1
    assert raw_values == [32.0, 35.2, 36.1]


def test_parse_cimis_fixture_context_preserved() -> None:
    parsed = parse_scientific_csv(_CIMIS_FIXTURE)
    # Station and date should be captured in each row's context
    for row in parsed.rows:
        assert row.context  # non-empty
        # Either "Stn Name" or "Date" should be captured
        context_keys_lower = [k.lower() for k in row.context]
        assert any("station" in k or "stn" in k or "date" in k for k in context_keys_lower)


def test_parse_empty_csv() -> None:
    parsed = parse_scientific_csv("")
    assert parsed.rows == ()
    assert parsed.schema.columns == ()


def test_parse_csv_header_only() -> None:
    parsed = parse_scientific_csv("col1,col2\n")
    assert parsed.rows == ()
    assert len(parsed.schema.columns) == 2


def test_parse_csv_respects_max_rows() -> None:
    parsed = parse_scientific_csv(_CIMIS_FIXTURE, max_rows=2)
    assert len(parsed.rows) == 2


def test_parse_csv_counts_parse_errors() -> None:
    csv = "Air Temp (C),qc\n20.5,\nnot_a_number,\n30.1,"
    parsed = parse_scientific_csv(csv)
    # 3 rows total, 1 has a bad numeric value
    assert parsed.parse_errors == 1
