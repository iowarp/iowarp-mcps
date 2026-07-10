"""Phase 3.5 hardening tests: quality gate, noisy corpora, ambiguity, reproducibility."""

from __future__ import annotations

from pathlib import Path

from clio_agentic_search.connectors.filesystem import FilesystemConnector
from clio_agentic_search.connectors.object_store import InMemoryS3Client, S3ObjectStoreConnector
from clio_agentic_search.evals.quality_gate import GateThresholds, run_quality_gate
from clio_agentic_search.evals.scientific import numeric_exactness, precision_at_k, unit_consistency
from clio_agentic_search.indexing.scientific import Measurement, decode_measurements
from clio_agentic_search.retrieval.coordinator import RetrievalCoordinator
from clio_agentic_search.retrieval.scientific import (
    NumericRangeOperator,
    ScientificQueryOperators,
    UnitMatchOperator,
)
from clio_agentic_search.storage import DuckDBStorage

# ---------------------------------------------------------------------------
# Corpus fixtures: realistic, noisy, multi-file
# ---------------------------------------------------------------------------

_NOISY_CORPUS: dict[str, str] = {
    "experiment_alpha.md": (
        "# Experiment Alpha\n"
        "## Setup\n"
        "Chamber volume 2.5 m and inlet diameter 30 mm.\n"
        "Table 1: Run conditions.\n"
        "| Run | Pressure (kPa) | Flow Rate (m/s) | Duration (min) |\n"
        "| --- | --- | --- | --- |\n"
        "| A1 | 101 | 3.5 | 60 |\n"
        "| A2 | 250 | 7.0 | 120 |\n"
        "| A3 | 400 | 10.5 | 30 |\n"
        "Figure 1: Pressure ramp profile.\n"
        "Governing relation: $P V = n R T$.\n"
        "Secondary check: $$\\Delta P = \\rho g h$$\n"
    ),
    "experiment_beta.md": (
        "# Experiment Beta\n"
        "Replicate of Alpha with modified flow.\n"
        "Table 1: Run conditions.\n"
        "| Run | Pressure (kPa) | Velocity (km/h) | Mass (g) |\n"
        "| --- | --- | --- | --- |\n"
        "| B1 | 102 | 36 | 500 |\n"
        "| B2 | 305 | 72 | 750 |\n"
        "Observations align with $F = m a$.\n"
    ),
    "unrelated_policy.txt": (
        "Safety policy revision 4.2.\n"
        "All personnel must wear PPE in Zone A.\n"
        "Incident reports filed within 24 hours.\n"
        "No numeric measurements here.\n"
    ),
    "misleading_numbers.md": (
        "# Budget Report\n"
        "Project allocated 350 kPa budget (note: this is a typo, should be $350k).\n"
        "Team size: 12 members. Sprint velocity: 42 points.\n"
        "The word pressure appears in a non-scientific context.\n"
    ),
    "sparse_science.md": (
        "# Sparse Observations\n"
        "Temperature was approximately 20 C.\n"
        "A single measurement of 88 kPa was recorded at hour 3.\n"
    ),
}


def _write_noisy_corpus(root: Path) -> None:
    root.mkdir(exist_ok=True)
    for filename, content in _NOISY_CORPUS.items():
        (root / filename).write_text(content, encoding="utf-8")


def _build_fs_connector(tmp_path: Path, ns: str = "test_ns") -> FilesystemConnector:
    docs = tmp_path / "docs"
    _write_noisy_corpus(docs)
    connector = FilesystemConnector(
        namespace=ns,
        root=docs,
        storage=DuckDBStorage(tmp_path / f"{ns}.duckdb"),
    )
    connector.connect()
    connector.index(full_rebuild=True)
    return connector


def _build_s3_connector(tmp_path: Path, ns: str = "s3_ns") -> S3ObjectStoreConnector:
    docs = tmp_path / "s3source"
    _write_noisy_corpus(docs)
    client = InMemoryS3Client()
    for f in sorted(docs.iterdir()):
        client.put_object(bucket="test", key=f"data/{f.name}", body=f.read_bytes())
    connector = S3ObjectStoreConnector(
        namespace=ns,
        bucket="test",
        prefix="data",
        storage=DuckDBStorage(tmp_path / f"{ns}.duckdb"),
        client=client,
    )
    connector.connect()
    connector.index(full_rebuild=True)
    return connector


# ---------------------------------------------------------------------------
# Deliverable 1: Quality gate harness integration
# ---------------------------------------------------------------------------


def test_quality_gate_passes_default_thresholds() -> None:
    """The built-in quality gate corpus and scenarios must pass default thresholds."""
    results = run_quality_gate(GateThresholds())
    failures = [r for r in results if not r.passed]
    assert not failures, f"Quality gate failures: {failures}"


def test_quality_gate_detects_unreachable_thresholds() -> None:
    """Raising thresholds above achievable values must produce failures."""
    impossible = GateThresholds(precision_at_k=1.5)
    results = run_quality_gate(impossible)
    assert any(not r.passed for r in results)


# ---------------------------------------------------------------------------
# Deliverable 2: Expanded noisy corpus scenarios
# ---------------------------------------------------------------------------


def test_numeric_range_filters_noisy_corpus_correctly(tmp_path: Path) -> None:
    """Numeric range 200-310 kPa should hit experiment_alpha row A2 and beta row B2,
    but NOT the misleading '350 kPa budget' line or unrelated docs."""
    connector = _build_fs_connector(tmp_path)
    coordinator = RetrievalCoordinator()
    try:
        result = coordinator.query(
            connector=connector,
            query="pressure readings",
            top_k=10,
            scientific_operators=ScientificQueryOperators(
                numeric_range=NumericRangeOperator(unit="kPa", minimum=200.0, maximum=310.0)
            ),
        )
        # Must have citations
        assert result.citations, "Expected citations for 200-310 kPa range"

        # Every returned citation must actually contain a measurement in range
        for citation in result.citations:
            metadata = connector.storage.get_chunk_metadata("test_ns", citation.chunk_id)
            measurements = decode_measurements(metadata.get("scientific.measurements", ""))
            in_range = any(
                m.canonical_unit == "1,-1,-2,0,0,0,0" and 200000.0 <= m.canonical_value <= 310000.0
                for m in measurements
            )
            assert in_range, (
                f"Citation {citation.uri} does not contain a measurement in [200,310] kPa: "
                f"{measurements}"
            )

        # Must NOT include unrelated_policy or team_roster
        uris = [c.uri for c in result.citations]
        assert not any("unrelated_policy" in u for u in uris)
    finally:
        connector.teardown()


def test_misleading_pressure_mention_excluded_by_tight_range(tmp_path: Path) -> None:
    """The misleading '350 kPa budget' line should be found by range 340-360,
    but experiment_alpha's 400 kPa row should NOT appear in this range."""
    connector = _build_fs_connector(tmp_path)
    coordinator = RetrievalCoordinator()
    try:
        result = coordinator.query(
            connector=connector,
            query="pressure",
            top_k=10,
            scientific_operators=ScientificQueryOperators(
                numeric_range=NumericRangeOperator(unit="kPa", minimum=340.0, maximum=360.0)
            ),
        )
        for citation in result.citations:
            metadata = connector.storage.get_chunk_metadata("test_ns", citation.chunk_id)
            measurements = decode_measurements(metadata.get("scientific.measurements", ""))
            in_range = any(
                m.canonical_unit == "1,-1,-2,0,0,0,0" and 340000.0 <= m.canonical_value <= 360000.0
                for m in measurements
            )
            assert in_range, f"Citation {citation.uri} outside [340,360] kPa"
    finally:
        connector.teardown()


def test_formula_search_across_noisy_corpus(tmp_path: Path) -> None:
    """Formula targeting 'PV=nRT' should return equation chunks from experiment_alpha,
    not from beta (F=ma) or unrelated docs."""
    connector = _build_fs_connector(tmp_path)
    coordinator = RetrievalCoordinator()
    try:
        result = coordinator.query(
            connector=connector,
            query="gas law",
            top_k=5,
            scientific_operators=ScientificQueryOperators(formula="P V = n R T"),
        )
        assert result.citations, "Expected formula match for PV=nRT"
        for citation in result.citations:
            metadata = connector.storage.get_chunk_metadata("test_ns", citation.chunk_id)
            formulas = metadata.get("scientific.formulas", "")
            assert "nrt=pv" in formulas, f"Citation {citation.uri} missing PV=nRT formula"
    finally:
        connector.teardown()


def test_negative_control_nonexistent_formula_returns_empty(tmp_path: Path) -> None:
    """Formula that exists nowhere must return zero results."""
    connector = _build_fs_connector(tmp_path)
    coordinator = RetrievalCoordinator()
    try:
        result = coordinator.query(
            connector=connector,
            query="quantum entanglement",
            top_k=5,
            scientific_operators=ScientificQueryOperators(formula="H psi = E psi"),
        )
        assert result.citations == []
    finally:
        connector.teardown()


def test_negative_control_out_of_range_returns_empty(tmp_path: Path) -> None:
    """Pressure range far above any corpus value must return zero results."""
    connector = _build_fs_connector(tmp_path)
    coordinator = RetrievalCoordinator()
    try:
        result = coordinator.query(
            connector=connector,
            query="pressure",
            top_k=5,
            scientific_operators=ScientificQueryOperators(
                numeric_range=NumericRangeOperator(unit="kPa", minimum=50000.0, maximum=60000.0)
            ),
        )
        assert result.citations == []
    finally:
        connector.teardown()


# ---------------------------------------------------------------------------
# Deliverable 2b: Object store scientific path with noisy corpus
# ---------------------------------------------------------------------------


def test_object_store_noisy_corpus_numeric_precision(tmp_path: Path) -> None:
    """S3 connector with noisy corpus: numeric range 95-105 kPa should find
    alpha A1 (101) and beta B1 (102)."""
    connector = _build_s3_connector(tmp_path)
    coordinator = RetrievalCoordinator()
    try:
        result = coordinator.query(
            connector=connector,
            query="low pressure",
            top_k=10,
            scientific_operators=ScientificQueryOperators(
                numeric_range=NumericRangeOperator(unit="kPa", minimum=95.0, maximum=105.0)
            ),
        )
        assert result.citations
        retrieved_measurements: list[Measurement] = []
        for citation in result.citations:
            metadata = connector.storage.get_chunk_metadata("s3_ns", citation.chunk_id)
            retrieved_measurements.extend(
                decode_measurements(metadata.get("scientific.measurements", ""))
            )
        # At least 101000 and 102000 Pa should be present
        exactness = numeric_exactness(
            retrieved_measurements,
            expected=[(101000.0, "1,-1,-2,0,0,0,0"), (102000.0, "1,-1,-2,0,0,0,0")],
            tolerance=1.0,
        )
        assert exactness >= 1.0
    finally:
        connector.teardown()


# ---------------------------------------------------------------------------
# Deliverable 3: Reproducibility and determinism
# ---------------------------------------------------------------------------


def test_repeated_queries_produce_identical_results(tmp_path: Path) -> None:
    """Three identical queries on the same index must return bit-identical citation lists."""
    connector = _build_fs_connector(tmp_path)
    coordinator = RetrievalCoordinator()
    operators = ScientificQueryOperators(
        numeric_range=NumericRangeOperator(unit="kPa", minimum=90.0, maximum=420.0)
    )
    try:
        runs = []
        for _ in range(3):
            result = coordinator.query(
                connector=connector,
                query="pressure measurement",
                top_k=5,
                scientific_operators=operators,
            )
            runs.append([(c.uri, c.score) for c in result.citations])

        assert runs[0] == runs[1] == runs[2], "Non-deterministic retrieval detected"
    finally:
        connector.teardown()


def test_reindex_same_corpus_produces_identical_results(tmp_path: Path) -> None:
    """Full re-index of unchanged corpus must produce identical query output."""
    connector = _build_fs_connector(tmp_path)
    coordinator = RetrievalCoordinator()
    operators = ScientificQueryOperators(
        numeric_range=NumericRangeOperator(unit="kPa", minimum=90.0, maximum=420.0)
    )
    try:
        first = coordinator.query(
            connector=connector,
            query="pressure",
            top_k=5,
            scientific_operators=operators,
        )
        first_uris = [c.uri for c in first.citations]

        connector.index(full_rebuild=True)

        second = coordinator.query(
            connector=connector,
            query="pressure",
            top_k=5,
            scientific_operators=operators,
        )
        second_uris = [c.uri for c in second.citations]

        assert first_uris == second_uris
    finally:
        connector.teardown()


# ---------------------------------------------------------------------------
# Deliverable 3b: Unit consistency under ambiguity
# ---------------------------------------------------------------------------


def test_unit_consistency_across_mixed_unit_corpus(tmp_path: Path) -> None:
    """All retrieved measurements must have canonical units assigned."""
    connector = _build_fs_connector(tmp_path)
    coordinator = RetrievalCoordinator()
    try:
        result = coordinator.query(
            connector=connector,
            query="measurement values",
            top_k=20,
        )
        all_measurements: list[Measurement] = []
        for citation in result.citations:
            metadata = connector.storage.get_chunk_metadata("test_ns", citation.chunk_id)
            all_measurements.extend(
                decode_measurements(metadata.get("scientific.measurements", ""))
            )

        if all_measurements:
            consistency = unit_consistency(all_measurements)
            assert consistency == 1.0, f"Unit consistency {consistency} < 1.0"
    finally:
        connector.teardown()


def test_sparse_document_single_measurement_found(tmp_path: Path) -> None:
    """sparse_science.md has exactly one kPa measurement (88 kPa).
    A tight range should find it."""
    connector = _build_fs_connector(tmp_path)
    coordinator = RetrievalCoordinator()
    try:
        result = coordinator.query(
            connector=connector,
            query="observation",
            top_k=5,
            scientific_operators=ScientificQueryOperators(
                numeric_range=NumericRangeOperator(unit="kPa", minimum=85.0, maximum=90.0)
            ),
        )
        assert result.citations, "Expected to find 88 kPa measurement"
        uris = [c.uri for c in result.citations]
        assert any("sparse_science" in u for u in uris)
    finally:
        connector.teardown()


# ---------------------------------------------------------------------------
# Deliverable 3c: precision@k with mixed relevant/irrelevant
# ---------------------------------------------------------------------------


def test_precision_at_k_with_partial_relevance(tmp_path: Path) -> None:
    """Query for velocity in km/h — only experiment_beta has km/h velocity column.
    experiment_alpha uses m/s for flow rate. Verify precision is reasonable."""
    connector = _build_fs_connector(tmp_path)
    coordinator = RetrievalCoordinator()
    try:
        result = coordinator.query(
            connector=connector,
            query="velocity",
            top_k=5,
            scientific_operators=ScientificQueryOperators(
                unit_match=UnitMatchOperator(unit="km/h")
            ),
        )
        velocity_uris = [c.uri for c in result.citations]
        # Beta has 2 km/h rows
        relevant = {
            "experiment_beta.md#table=1&row=1&column=3",
            "experiment_beta.md#table=1&row=2&column=3",
        }
        p = precision_at_k(velocity_uris, relevant, k=len(velocity_uris))
        # At least some relevant results should be found
        assert p > 0.0, "Expected at least one relevant velocity citation"
    finally:
        connector.teardown()
