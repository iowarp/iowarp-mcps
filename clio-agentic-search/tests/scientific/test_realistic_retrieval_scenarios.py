from __future__ import annotations

from pathlib import Path

from clio_agentic_search.connectors.filesystem import FilesystemConnector
from clio_agentic_search.connectors.object_store import (
    InMemoryS3Client,
    S3ObjectStoreConnector,
)
from clio_agentic_search.indexing.scientific import decode_measurements
from clio_agentic_search.retrieval.coordinator import RetrievalCoordinator
from clio_agentic_search.retrieval.scientific import (
    NumericRangeOperator,
    ScientificQueryOperators,
)
from clio_agentic_search.storage import DuckDBStorage


def _write_mixed_corpus(root: Path) -> None:
    root.mkdir(exist_ok=True)
    (root / "reactor_day1.md").write_text(
        "\n".join(
            [
                "# Reactor Day 1",
                "Figure 1: Pressure and velocity profile.",
                "| Time (min) | Pressure (kPa) | Temperature (C) | Velocity (km/h) |",
                "| --- | --- | --- | --- |",
                "| 1 | 120 | 90 | 36 |",
                "| 2 | 150 | 92 | 54 |",
                "Derived relation uses $P = F / A$ for pressure.",
            ]
        ),
        encoding="utf-8",
    )
    (root / "maintenance_log.txt").write_text(
        "Maintenance notes: pressure valve calibration at 60 kPa baseline.",
        encoding="utf-8",
    )
    (root / "team_policy.txt").write_text(
        "Team policy includes incident reporting, shift handoff, and document retention.",
        encoding="utf-8",
    )


def _build_filesystem_connector(tmp_path: Path) -> FilesystemConnector:
    docs_dir = tmp_path / "docs"
    _write_mixed_corpus(docs_dir)
    connector = FilesystemConnector(
        namespace="local_science",
        root=docs_dir,
        storage=DuckDBStorage(tmp_path / "realistic-fs.duckdb"),
    )
    connector.connect()
    connector.index(full_rebuild=True)
    return connector


def _build_object_connector(tmp_path: Path) -> S3ObjectStoreConnector:
    docs_dir = tmp_path / "object-source"
    _write_mixed_corpus(docs_dir)

    client = InMemoryS3Client()
    for file_path in sorted(docs_dir.iterdir()):
        client.put_object(
            bucket="science",
            key=f"papers/{file_path.name}",
            body=file_path.read_bytes(),
        )

    connector = S3ObjectStoreConnector(
        namespace="object_science",
        bucket="science",
        prefix="papers",
        storage=DuckDBStorage(tmp_path / "realistic-s3.duckdb"),
        client=client,
    )
    connector.connect()
    connector.index(full_rebuild=True)
    return connector


def test_mixed_corpus_generic_and_numeric_queries_are_grounded(tmp_path: Path) -> None:
    connector = _build_filesystem_connector(tmp_path)
    coordinator = RetrievalCoordinator()

    try:
        generic = coordinator.query(
            connector=connector,
            query="velocity 54 km/h reactor",
            top_k=5,
        )
        assert any("row=2&column=4" in citation.uri for citation in generic.citations)

        constrained = coordinator.query(
            connector=connector,
            query="pressure investigation",
            top_k=4,
            scientific_operators=ScientificQueryOperators(
                numeric_range=NumericRangeOperator(unit="kPa", minimum=140.0, maximum=155.0)
            ),
        )
        assert constrained.citations

        for citation in constrained.citations:
            metadata = connector.storage.get_chunk_metadata("local_science", citation.chunk_id)
            measurements = decode_measurements(metadata.get("scientific.measurements", ""))
            assert any(
                measurement.canonical_unit == "pa"
                and 140000.0 <= measurement.canonical_value <= 155000.0
                for measurement in measurements
            )
    finally:
        connector.teardown()


def test_formula_targeting_and_negative_controls_reduce_false_positives(tmp_path: Path) -> None:
    connector = _build_filesystem_connector(tmp_path)
    coordinator = RetrievalCoordinator()

    try:
        formula_query = coordinator.query(
            connector=connector,
            query="formula lookup",
            top_k=2,
            scientific_operators=ScientificQueryOperators(formula="p=f/a"),
        )
        assert formula_query.citations
        assert any(
            connector.storage.get_chunk_metadata("local_science", citation.chunk_id).get(
                "structure.kind"
            )
            == "equation"
            for citation in formula_query.citations
        )

        no_match = coordinator.query(
            connector=connector,
            query="pressure",
            top_k=3,
            scientific_operators=ScientificQueryOperators(
                numeric_range=NumericRangeOperator(unit="kPa", minimum=900.0, maximum=1100.0)
            ),
        )
        assert no_match.citations == []
    finally:
        connector.teardown()


def test_object_store_scientific_path_supports_table_cell_citations(tmp_path: Path) -> None:
    connector = _build_object_connector(tmp_path)
    coordinator = RetrievalCoordinator()

    try:
        result = coordinator.query(
            connector=connector,
            query="pressure 150",
            top_k=3,
            scientific_operators=ScientificQueryOperators(
                numeric_range=NumericRangeOperator(unit="kPa", minimum=145.0, maximum=155.0)
            ),
        )
        assert result.citations
        assert any(
            citation.uri.endswith("papers/reactor_day1.md#table=1&row=2&column=2")
            for citation in result.citations
        )
    finally:
        connector.teardown()
