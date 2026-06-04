"""Scientific quality-gate harness with explicit thresholds.

Run via: uv run python -m clio_agentic_search.evals.quality_gate
"""

from __future__ import annotations

import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path

from clio_agentic_search.connectors.filesystem import FilesystemConnector
from clio_agentic_search.evals.scientific import numeric_exactness, precision_at_k, unit_consistency
from clio_agentic_search.indexing.scientific import Measurement, decode_measurements
from clio_agentic_search.retrieval.coordinator import RetrievalCoordinator
from clio_agentic_search.retrieval.scientific import (
    NumericRangeOperator,
    ScientificQueryOperators,
    UnitMatchOperator,
)
from clio_agentic_search.storage import DuckDBStorage


@dataclass(frozen=True, slots=True)
class GateThresholds:
    precision_at_k: float = 0.8
    numeric_exactness: float = 0.9
    unit_consistency: float = 1.0


@dataclass(frozen=True, slots=True)
class GateResult:
    scenario: str
    metric: str
    value: float
    threshold: float

    @property
    def passed(self) -> bool:
        return self.value >= self.threshold


_CORPUS = {
    "reactor_report.md": (
        "# Reactor Experiment Report\n"
        "Table 1: Steady-state measurements.\n"
        "| Time (min) | Pressure (kPa) | Velocity (km/h) |\n"
        "| --- | --- | --- |\n"
        "| 1 | 101 | 36 |\n"
        "| 5 | 200 | 72 |\n"
        "| 10 | 350 | 108 |\n"
        "Key derivation: $P V = n R T$.\n"
        "Sample mass: 250 g.\n"
    ),
    "calibration_notes.md": (
        "# Calibration Notes\n"
        "Sensor baseline offset was 5 kPa. Temperature drift under 0.3 C.\n"
        "No anomalies observed during the calibration window.\n"
    ),
    "team_roster.txt": ("Operations team: Alice, Bob, Carol.\nShift schedule rotates weekly.\n"),
}


def _build_connector(tmp_dir: Path) -> FilesystemConnector:
    docs = tmp_dir / "gate_docs"
    docs.mkdir(exist_ok=True)
    for filename, content in _CORPUS.items():
        (docs / filename).write_text(content, encoding="utf-8")

    connector = FilesystemConnector(
        namespace="gate_ns",
        root=docs,
        storage=DuckDBStorage(tmp_dir / "gate.duckdb"),
    )
    connector.connect()
    connector.index(full_rebuild=True)
    return connector


def _run_precision_scenario(
    connector: FilesystemConnector,
    coordinator: RetrievalCoordinator,
    thresholds: GateThresholds,
) -> list[GateResult]:
    results: list[GateResult] = []

    # Scenario: numeric range should hit rows with pressure 200-350 kPa
    query_result = coordinator.query(
        connector=connector,
        query="reactor pressure",
        top_k=3,
        scientific_operators=ScientificQueryOperators(
            numeric_range=NumericRangeOperator(unit="kPa", minimum=190.0, maximum=360.0)
        ),
    )
    retrieved_uris = [c.uri for c in query_result.citations]
    relevant = {
        "reactor_report.md#table=1&row=2&column=2",
        "reactor_report.md#table=1&row=3&column=2",
    }
    p_at_k = precision_at_k(retrieved_uris, relevant, k=3)
    results.append(
        GateResult(
            scenario="numeric_range_pressure",
            metric="precision@3",
            value=p_at_k,
            threshold=thresholds.precision_at_k,
        )
    )

    # Scenario: unit match for velocity
    unit_result = coordinator.query(
        connector=connector,
        query="velocity measurement",
        top_k=3,
        scientific_operators=ScientificQueryOperators(unit_match=UnitMatchOperator(unit="km/h")),
    )
    velocity_uris = [c.uri for c in unit_result.citations]
    velocity_relevant = {
        "reactor_report.md#table=1&row=1&column=3",
        "reactor_report.md#table=1&row=2&column=3",
        "reactor_report.md#table=1&row=3&column=3",
    }
    p_vel = precision_at_k(velocity_uris, velocity_relevant, k=3)
    results.append(
        GateResult(
            scenario="unit_match_velocity",
            metric="precision@3",
            value=p_vel,
            threshold=thresholds.precision_at_k,
        )
    )

    return results


def _run_numeric_exactness_scenario(
    connector: FilesystemConnector,
    coordinator: RetrievalCoordinator,
    thresholds: GateThresholds,
) -> list[GateResult]:
    results: list[GateResult] = []

    query_result = coordinator.query(
        connector=connector,
        query="pressure readings",
        top_k=5,
        scientific_operators=ScientificQueryOperators(
            numeric_range=NumericRangeOperator(unit="kPa", minimum=100.0, maximum=360.0)
        ),
    )
    measurements: list[Measurement] = []
    for citation in query_result.citations:
        metadata = connector.storage.get_chunk_metadata("gate_ns", citation.chunk_id)
        measurements.extend(decode_measurements(metadata.get("scientific.measurements", "")))

    expected = [
        (101000.0, "1,-1,-2,0,0,0,0"),
        (200000.0, "1,-1,-2,0,0,0,0"),
        (350000.0, "1,-1,-2,0,0,0,0"),
    ]
    exactness = numeric_exactness(measurements, expected, tolerance=1e-6)
    results.append(
        GateResult(
            scenario="pressure_exactness",
            metric="numeric_exactness",
            value=exactness,
            threshold=thresholds.numeric_exactness,
        )
    )

    return results


def _run_unit_consistency_scenario(
    connector: FilesystemConnector,
    coordinator: RetrievalCoordinator,
    thresholds: GateThresholds,
) -> list[GateResult]:
    results: list[GateResult] = []

    query_result = coordinator.query(
        connector=connector,
        query="all measurements",
        top_k=10,
        scientific_operators=ScientificQueryOperators(unit_match=UnitMatchOperator(unit="kPa")),
    )
    measurements: list[Measurement] = []
    for citation in query_result.citations:
        metadata = connector.storage.get_chunk_metadata("gate_ns", citation.chunk_id)
        measurements.extend(decode_measurements(metadata.get("scientific.measurements", "")))

    consistency = unit_consistency(measurements)
    results.append(
        GateResult(
            scenario="unit_consistency_pressure",
            metric="unit_consistency",
            value=consistency,
            threshold=thresholds.unit_consistency,
        )
    )

    return results


def _run_negative_control(
    connector: FilesystemConnector,
    coordinator: RetrievalCoordinator,
) -> list[GateResult]:
    results: list[GateResult] = []

    # Out-of-range query must return zero citations
    out_of_range = coordinator.query(
        connector=connector,
        query="pressure",
        top_k=5,
        scientific_operators=ScientificQueryOperators(
            numeric_range=NumericRangeOperator(unit="kPa", minimum=9000.0, maximum=10000.0)
        ),
    )
    results.append(
        GateResult(
            scenario="negative_control_out_of_range",
            metric="precision@5",
            value=1.0 if len(out_of_range.citations) == 0 else 0.0,
            threshold=1.0,
        )
    )

    # Nonexistent formula must return zero citations
    no_formula = coordinator.query(
        connector=connector,
        query="formula check",
        top_k=3,
        scientific_operators=ScientificQueryOperators(formula="Z = Q + W"),
    )
    results.append(
        GateResult(
            scenario="negative_control_nonexistent_formula",
            metric="precision@3",
            value=1.0 if len(no_formula.citations) == 0 else 0.0,
            threshold=1.0,
        )
    )

    return results


def run_quality_gate(thresholds: GateThresholds | None = None) -> list[GateResult]:
    """Execute all quality-gate scenarios and return results."""
    if thresholds is None:
        thresholds = GateThresholds()

    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_path = Path(tmp_dir)
        connector = _build_connector(tmp_path)
        coordinator = RetrievalCoordinator()

        try:
            all_results: list[GateResult] = []
            all_results.extend(_run_precision_scenario(connector, coordinator, thresholds))
            all_results.extend(_run_numeric_exactness_scenario(connector, coordinator, thresholds))
            all_results.extend(_run_unit_consistency_scenario(connector, coordinator, thresholds))
            all_results.extend(_run_negative_control(connector, coordinator))
            return all_results
        finally:
            connector.teardown()


def main() -> None:
    """CLI entry point for quality-gate harness."""
    thresholds = GateThresholds()
    results = run_quality_gate(thresholds)

    failures: list[GateResult] = []
    print("=" * 72)
    print("Scientific Quality Gate Report")
    print("=" * 72)

    for result in results:
        status = "PASS" if result.passed else "FAIL"
        print(
            f"  [{status}] {result.scenario:40s} "
            f"{result.metric}={result.value:.4f} (threshold={result.threshold:.2f})"
        )
        if not result.passed:
            failures.append(result)

    print("-" * 72)
    if failures:
        print(f"GATE FAILED: {len(failures)} check(s) below threshold.")
        sys.exit(1)
    else:
        print(f"GATE PASSED: all {len(results)} checks met thresholds.")
        sys.exit(0)


if __name__ == "__main__":
    main()
