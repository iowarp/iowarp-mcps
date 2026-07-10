"""Unit tests for metadata schema inference and field alignment."""

from __future__ import annotations

from clio_agentic_search.retrieval.metadata_schema import (
    FieldInfo,
    _normalise_field_name,
    align_field,
    build_metadata_schema,
    describe_schema,
)

# ---------------------------------------------------------------------------
# Field name normalisation
# ---------------------------------------------------------------------------


def test_normalise_strips_unit_suffix() -> None:
    assert _normalise_field_name("Air Temp (C)") == "air_temp"
    assert _normalise_field_name("Vap Pres (kPa)") == "vap_pres"
    assert _normalise_field_name("Wind Speed (m/s)") == "wind_speed"


def test_normalise_lowercases() -> None:
    assert _normalise_field_name("TEMPERATURE") == "temperature"
    assert _normalise_field_name("RelHum") == "relhum"


def test_normalise_handles_empty() -> None:
    assert _normalise_field_name("") == ""
    assert _normalise_field_name("   ") == ""


def test_normalise_collapses_whitespace_and_punct() -> None:
    assert _normalise_field_name("Air.Temperature") == "air_temperature"
    assert _normalise_field_name("wind-speed-avg") == "wind_speed_avg"


# ---------------------------------------------------------------------------
# Field alignment to canonical concepts
# ---------------------------------------------------------------------------


def test_align_temperature_variants() -> None:
    assert align_field("temperature") == "temperature"
    assert align_field("temp") == "temperature"
    assert align_field("Air Temp (C)") == "temperature"
    assert align_field("T_air") == "temperature"
    assert align_field("air_temp") == "temperature"
    assert align_field("T2M") == "temperature"


def test_align_temperature_excludes_sensor_and_id() -> None:
    assert align_field("temperature_sensor_id") is None
    assert align_field("temp_station") is None


def test_align_pressure_variants() -> None:
    assert align_field("pressure") == "pressure"
    assert align_field("press") == "pressure"
    assert align_field("barometric pressure") == "pressure"
    assert align_field("Vap Pres (kPa)") == "pressure"
    assert align_field("MSLP") == "pressure"


def test_align_humidity_variants() -> None:
    assert align_field("humidity") == "humidity"
    assert align_field("Rel Hum (%)") == "humidity"
    assert align_field("RH") == "humidity"
    assert align_field("relative_humidity") == "humidity"
    assert align_field("dew_point") == "humidity"


def test_align_wind_speed_variants() -> None:
    assert align_field("wind_speed") == "wind_speed"
    assert align_field("WS") == "wind_speed"
    assert align_field("Wind Speed (m/s)") == "wind_speed"
    assert align_field("wnd_spd") == "wind_speed"


def test_align_wind_direction_not_speed() -> None:
    assert align_field("wind_direction") == "wind_direction"
    assert align_field("WD") == "wind_direction"


def test_align_location_fields() -> None:
    assert align_field("latitude") == "latitude"
    assert align_field("lat") == "latitude"
    assert align_field("longitude") == "longitude"
    assert align_field("lon") == "longitude"
    assert align_field("lng") == "longitude"
    assert align_field("elevation") == "elevation"
    assert align_field("altitude") == "elevation"


def test_align_quality_field() -> None:
    assert align_field("qc") == "measurement_quality"
    assert align_field("quality") == "measurement_quality"
    assert align_field("qflag") == "measurement_quality"


def test_align_unknown_field_returns_none() -> None:
    assert align_field("random_gibberish_column") is None
    assert align_field("foo") is None


def test_align_empty_returns_none() -> None:
    assert align_field("") is None
    assert align_field("   ") is None


def test_align_station_id_distinct_from_temperature() -> None:
    # "station" alone should not match any concept (no "station" concept),
    # and "station_id" should match station_id concept.
    assert align_field("station") is None
    assert align_field("stn_id") == "station_id"
    assert align_field("station_id") == "station_id"


# ---------------------------------------------------------------------------
# build_metadata_schema
# ---------------------------------------------------------------------------


def test_build_metadata_schema_empty() -> None:
    schema = build_metadata_schema(
        namespace="empty",
        metadata_rows=[],
        total_documents=0,
        total_chunks=0,
    )
    assert schema.namespace == "empty"
    assert len(schema.fields) == 0
    assert len(schema.concepts) == 0
    assert schema.richness_score == 0.0


def test_build_metadata_schema_with_real_cimis_fields() -> None:
    # Simulate what we'd get from a CIMIS-derived corpus
    rows = [
        ("Air Temp (C)", "chunk", "25.3", 1000),
        ("Rel Hum (%)", "chunk", "40", 1000),
        ("Wind Speed (m/s)", "chunk", "2.1", 1000),
        ("Sol Rad (W/sq.m)", "chunk", "800", 1000),
        ("Stn Id", "document", "105", 10),
        ("Date", "chunk", "2024-06-01", 1000),
        ("random_internal_field", "chunk", "x", 50),
    ]
    schema = build_metadata_schema(
        namespace="cimis",
        metadata_rows=rows,
        total_documents=10,
        total_chunks=1000,
    )
    assert schema.namespace == "cimis"
    assert len(schema.fields) == 7
    # Detected concepts
    assert "temperature" in schema.concepts
    assert "humidity" in schema.concepts
    assert "wind_speed" in schema.concepts
    assert "solar_radiation" in schema.concepts
    assert "time" in schema.concepts
    assert "station_id" in schema.concepts
    # Convenience properties
    assert schema.has_temperature_field is True
    assert schema.has_pressure_field is False  # CIMIS doesn't have it
    assert schema.has_quality_field is False
    # Richness should be high given multiple concepts + 100% chunk coverage
    assert schema.richness_score > 0.5


def test_build_metadata_schema_sparse_corpus() -> None:
    # Corpus with only a single low-frequency random field
    rows = [
        ("internal_id", "document", "xyz", 1),
    ]
    schema = build_metadata_schema(
        namespace="sparse",
        metadata_rows=rows,
        total_documents=100,
        total_chunks=500,
    )
    # Only 1 field, no recognised concept
    assert len(schema.fields) == 1
    assert len(schema.concepts) == 0
    assert schema.richness_score < 0.2


def test_schema_fields_for_concept() -> None:
    rows = [
        ("Air Temp (C)", "chunk", "25", 1000),
        ("temperature", "chunk", "25", 500),  # two aliases for the same thing
        ("humidity", "chunk", "40", 1000),
    ]
    schema = build_metadata_schema(
        namespace="multi",
        metadata_rows=rows,
        total_documents=10,
        total_chunks=1000,
    )
    temp_fields = schema.fields_for_concept("temperature")
    assert len(temp_fields) == 2
    assert {f.key for f in temp_fields} == {"Air Temp (C)", "temperature"}


def test_describe_schema_returns_serialisable_dict() -> None:
    rows = [
        ("Air Temp (C)", "chunk", "25", 1000),
        ("humidity", "chunk", "40", 1000),
    ]
    schema = build_metadata_schema(
        namespace="test",
        metadata_rows=rows,
        total_documents=10,
        total_chunks=1000,
    )
    description = describe_schema(schema)
    assert description["namespace"] == "test"
    assert description["distinct_field_count"] == 2
    assert "temperature" in description["concepts"]
    assert "humidity" in description["concepts"]
    assert len(description["top_fields"]) == 2

    # Must be JSON-serialisable
    import json

    json.dumps(description)  # raises if not


def test_field_info_construction() -> None:
    info = FieldInfo(
        key="temperature",
        scope="chunk",
        occurrences=100,
        canonical_concept="temperature",
    )
    assert info.key == "temperature"
    assert info.canonical_concept == "temperature"


def test_richness_score_bounded_0_1() -> None:
    # Extreme case: lots of fields, perfect coverage
    rows = [(f"field_{i}", "chunk", "x", 1000) for i in range(20)] + [
        ("temperature", "chunk", "25", 1000),
        ("humidity", "chunk", "40", 1000),
        ("pressure", "chunk", "101", 1000),
        ("wind_speed", "chunk", "5", 1000),
        ("solar_radiation", "chunk", "800", 1000),
    ]
    schema = build_metadata_schema(
        namespace="rich",
        metadata_rows=rows,
        total_documents=10,
        total_chunks=1000,
    )
    assert 0.0 <= schema.richness_score <= 1.0
    assert schema.richness_score > 0.9  # all signals maxed
