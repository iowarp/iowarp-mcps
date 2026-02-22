from __future__ import annotations

from pathlib import Path

from clio_agentic_search.connectors.filesystem import FilesystemConnector
from clio_agentic_search.evals import numeric_exactness, precision_at_k, unit_consistency
from clio_agentic_search.indexing.scientific import Measurement, decode_measurements
from clio_agentic_search.retrieval.coordinator import RetrievalCoordinator
from clio_agentic_search.retrieval.scientific import (
    NumericRangeOperator,
    ScientificQueryOperators,
    UnitMatchOperator,
)
from clio_agentic_search.storage import DuckDBStorage


def _build_scientific_connector(tmp_path: Path, filename: str, content: str) -> FilesystemConnector:
    docs_dir = tmp_path / "docs"
    docs_dir.mkdir(exist_ok=True)
    (docs_dir / filename).write_text(content, encoding="utf-8")

    connector = FilesystemConnector(
        namespace="local_science",
        root=docs_dir,
        storage=DuckDBStorage(tmp_path / "scientific.duckdb"),
    )
    connector.connect()
    connector.index(full_rebuild=True)
    return connector


def test_structure_aware_chunking_indexes_sections_tables_equations_and_captions(
    tmp_path: Path,
) -> None:
    connector = _build_scientific_connector(
        tmp_path,
        "paper.md",
        (
            "# Reactor Run A\n"
            "Table 1: Pressure and velocity readings.\n"
            "| Time (min) | Pressure (kPa) | Velocity (km/h) |\n"
            "| --- | --- | --- |\n"
            "| 1 | 120 | 36 |\n"
            "| 2 | 150 | 54 |\n"
            "Figure 1: Trend remains stable.\n"
            "Energy relation: $E = m c^2$.\n"
            "$$F = m a$$\n"
            "Sample mass was 500 g and tube length was 2 km.\n"
        ),
    )

    try:
        chunks = connector.storage.list_chunks("local_science")
        metadata_by_chunk = {
            chunk.chunk_id: connector.storage.get_chunk_metadata("local_science", chunk.chunk_id)
            for chunk in chunks
        }

        kinds = {metadata.get("structure.kind", "") for metadata in metadata_by_chunk.values()}
        assert {"section", "caption", "equation", "table", "table_cell"}.issubset(kinds)

        table_cells = [
            metadata
            for metadata in metadata_by_chunk.values()
            if metadata.get("structure.kind") == "table_cell"
        ]
        assert any(
            metadata.get("table.row") == "2" and metadata.get("table.column") == "2"
            for metadata in table_cells
        )
        assert all("citation.fragment" in metadata for metadata in table_cells)

        all_measurements: list[Measurement] = []
        for metadata in metadata_by_chunk.values():
            all_measurements.extend(
                decode_measurements(metadata.get("scientific.measurements", ""))
            )

        assert any(
            measurement.canonical_unit == "pa" and measurement.canonical_value == 120000.0
            for measurement in all_measurements
        )
        assert any(
            measurement.canonical_unit == "m/s" and measurement.canonical_value == 10.0
            for measurement in all_measurements
        )
        assert any(
            measurement.canonical_unit == "kg" and measurement.canonical_value == 0.5
            for measurement in all_measurements
        )
        assert any(
            metadata.get("scientific.formulas", "").find("c^2m=e") >= 0
            for metadata in metadata_by_chunk.values()
        )
    finally:
        connector.teardown()


def test_scientific_query_operators_support_numeric_unit_and_formula_targeting(
    tmp_path: Path,
) -> None:
    connector = _build_scientific_connector(
        tmp_path,
        "query.md",
        (
            "# Scientific Index\n"
            "| Time (min) | Pressure (kPa) | Velocity (km/h) |\n"
            "| --- | --- | --- |\n"
            "| 1 | 120 | 36 |\n"
            "| 2 | 150 | 54 |\n"
            "Derivation uses $E = m c^2$.\n"
        ),
    )
    coordinator = RetrievalCoordinator()

    try:
        numeric_result = coordinator.query(
            connector=connector,
            query="reactor pressure",
            top_k=3,
            scientific_operators=ScientificQueryOperators(
                numeric_range=NumericRangeOperator(unit="kPa", minimum=130.0, maximum=160.0)
            ),
        )
        assert numeric_result.citations
        assert any("row=2&column=2" in citation.uri for citation in numeric_result.citations)

        unit_result = coordinator.query(
            connector=connector,
            query="velocity",
            top_k=3,
            scientific_operators=ScientificQueryOperators(
                unit_match=UnitMatchOperator(unit="m/s", value=15.0, tolerance=1e-9)
            ),
        )
        assert unit_result.citations
        assert any("row=2&column=3" in citation.uri for citation in unit_result.citations)

        formula_result = coordinator.query(
            connector=connector,
            query="unrelated lookup",
            top_k=2,
            scientific_operators=ScientificQueryOperators(formula="E = m c^2"),
        )
        assert formula_result.citations
        assert "scientific_completed" in [event.stage for event in formula_result.trace]
        assert any(
            connector.storage.get_chunk_metadata("local_science", citation.chunk_id).get(
                "structure.kind"
            )
            == "equation"
            for citation in formula_result.citations
        )
    finally:
        connector.teardown()


def test_scientific_benchmark_metrics_are_reproducible_on_same_corpus(tmp_path: Path) -> None:
    connector = _build_scientific_connector(
        tmp_path,
        "benchmark.md",
        ("# Benchmark\n| Time (min) | Pressure (kPa) |\n| --- | --- |\n| 1 | 120 |\n| 2 | 150 |\n"),
    )
    coordinator = RetrievalCoordinator()
    operators = ScientificQueryOperators(
        numeric_range=NumericRangeOperator(unit="kPa", minimum=100.0, maximum=160.0)
    )

    try:
        first = coordinator.query(
            connector=connector,
            query="pressure benchmark",
            top_k=2,
            scientific_operators=operators,
        )
        second = coordinator.query(
            connector=connector,
            query="pressure benchmark",
            top_k=2,
            scientific_operators=operators,
        )

        first_uris = [citation.uri for citation in first.citations]
        second_uris = [citation.uri for citation in second.citations]
        assert first_uris == second_uris

        relevant = {
            "benchmark.md#table=1&row=1&column=2",
            "benchmark.md#table=1&row=2&column=2",
        }
        assert precision_at_k(first_uris, relevant, k=2) == 1.0

        retrieved_measurements: list[Measurement] = []
        for citation in first.citations:
            metadata = connector.storage.get_chunk_metadata("local_science", citation.chunk_id)
            retrieved_measurements.extend(
                decode_measurements(metadata.get("scientific.measurements", ""))
            )

        assert (
            numeric_exactness(
                retrieved_measurements,
                expected=[(120000.0, "pa"), (150000.0, "pa")],
                tolerance=1e-9,
            )
            == 1.0
        )
        assert unit_consistency(retrieved_measurements) == 1.0
    finally:
        connector.teardown()
