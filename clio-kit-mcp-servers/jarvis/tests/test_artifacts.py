"""Production invariants for exposing JARVIS-owned artifact snapshots."""

from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path
from typing import Any

import pytest
from jarvis_mcp.artifacts import (
    ArtifactQueryError,
    ArtifactSnapshotError,
    artifact_query_page,
    artifact_snapshot_document,
    execution_output_artifact_events,
)


def _artifact(
    identifier: str = "A",
    *,
    package_id: str = "simulation",
    role: str = "output",
    state: str = "finalized",
) -> dict[str, Any]:
    return {
        "schema_version": "jarvis.artifact.v1",
        "package_name": "builtin.gray_scott",
        "package_id": package_id,
        "execution_id": "execution-a",
        "artifact_id": f"art_{identifier * 22}",
        "logical_name": f"simulation-output-{identifier}",
        "kind": "scientific-dataset",
        "role": role,
        "structure": "collection",
        "ownership": "execution",
        "state": state,
        "location": {
            "kind": "execution_path",
            "value": "shared/simulation.bp",
        },
        "media_type": "application/x-adios2-bp",
        "format": "adios2-bp",
        "size_bytes": 4096,
        "checksum": "sha256:0123456789abcdef",
        "revision": 2,
        "sequence": 4,
        "observed_at_epoch": 1783900000.0,
        "metadata": {"steps": 10},
    }


def _snapshot() -> dict[str, Any]:
    return {
        "schema_version": "jarvis.execution.artifacts.v1",
        "execution_id": "execution-a",
        "pipeline_id": "pipeline-a",
        "execution_state": "completed",
        "terminal": True,
        "artifacts": [_artifact()],
    }


class _NativeSnapshot:
    def to_dict(self) -> dict[str, Any]:
        return _snapshot()


def test_artifact_snapshot_accepts_native_document_without_rewriting_it() -> None:
    expected = _snapshot()

    observed = artifact_snapshot_document(
        _NativeSnapshot(),
        expected_execution_id="execution-a",
        expected_pipeline_id="pipeline-a",
    )

    assert observed == expected


def test_execution_output_artifacts_declare_direct_files_and_typed_truncation(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Terminal output discovery is bounded, typed, and execution-root scoped."""
    (tmp_path / "stdout.log").write_bytes(b"thermo: 42\n")
    (tmp_path / "log.lammps").write_bytes(b"LAMMPS log\n")
    (tmp_path / "dump.dcd").write_bytes(b"frame-bytes")
    (tmp_path / "z-output.dat").write_bytes(b"application output")
    nested = tmp_path / "dumps"
    nested.mkdir()
    (nested / "frame.0002").write_bytes(b"nested-frame")
    (tmp_path / "submit.slurm").write_bytes(b"#!/bin/sh\n")
    monkeypatch.setattr("jarvis_mcp.artifacts.MAX_EXECUTION_OUTPUT_FILES", 3)

    events, truncation = execution_output_artifact_events(
        tmp_path,
        execution_id="execution-a",
        observed_at_epoch=1783900000.0,
    )

    file_events = [event for event in events if "location" in event]
    assert [event["location"]["value"] for event in file_events] == [
        "dump.dcd",
        "log.lammps",
        "stdout.log",
    ]
    assert [event["role"] for event in file_events] == ["frame", "output", "log"]
    assert file_events[2]["size_bytes"] == len(b"thermo: 42\n")
    assert file_events[2]["checksum"].startswith("sha256:")
    assert truncation == {
        "schema_version": "jarvis.execution-output-truncation.v1",
        "limit": 3,
        "observed_count": 4,
        "omitted_count": 1,
    }
    assert all("dumps" not in str(event) for event in events)


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("execution_id", "execution-forged", "execution identity did not match"),
        ("pipeline_id", "pipeline-forged", "pipeline identity did not match"),
        ("schema_version", "jarvis.execution.artifacts.v2", "schema is unsupported"),
    ],
)
def test_artifact_snapshot_rejects_forged_identity_or_schema(
    field: str,
    value: str,
    message: str,
) -> None:
    snapshot = _snapshot()
    snapshot[field] = value

    with pytest.raises(RuntimeError, match=message):
        artifact_snapshot_document(
            snapshot,
            expected_execution_id="execution-a",
            expected_pipeline_id="pipeline-a",
        )


def test_artifact_snapshot_rejects_duplicate_and_cross_execution_artifacts() -> None:
    duplicate = _snapshot()
    duplicate["artifacts"].append(deepcopy(duplicate["artifacts"][0]))
    with pytest.raises(RuntimeError, match="artifact identity is invalid"):
        artifact_snapshot_document(
            duplicate,
            expected_execution_id="execution-a",
            expected_pipeline_id="pipeline-a",
        )

    forged = _snapshot()
    forged["artifacts"][0]["execution_id"] = "execution-forged"
    with pytest.raises(RuntimeError, match="event identity did not match"):
        artifact_snapshot_document(
            forged,
            expected_execution_id="execution-a",
            expected_pipeline_id="pipeline-a",
        )


def test_artifact_snapshot_rejects_extended_or_inconsistent_events() -> None:
    extended = _snapshot()
    extended["artifacts"][0]["download_url"] = "file:///not-authorized"
    with pytest.raises(RuntimeError, match="event fields are invalid"):
        artifact_snapshot_document(
            extended,
            expected_execution_id="execution-a",
            expected_pipeline_id="pipeline-a",
        )

    inconsistent = _snapshot()
    inconsistent["artifacts"][0]["ownership"] = "shared"
    with pytest.raises(RuntimeError, match="location ownership is invalid"):
        artifact_snapshot_document(
            inconsistent,
            expected_execution_id="execution-a",
            expected_pipeline_id="pipeline-a",
        )


def test_artifact_snapshot_rejects_unbounded_metadata() -> None:
    snapshot = _snapshot()
    snapshot["artifacts"][0]["metadata"] = {"value": "x" * (64 * 1024)}

    with pytest.raises(RuntimeError, match="metadata exceeded its byte limit"):
        artifact_snapshot_document(
            snapshot,
            expected_execution_id="execution-a",
            expected_pipeline_id="pipeline-a",
        )


def test_artifact_snapshot_enforces_the_native_per_event_byte_limit() -> None:
    snapshot = _snapshot()
    snapshot["artifacts"][0]["metadata"] = {"padding": "x" * (60 * 1024)}
    snapshot["artifacts"][0]["message"] = "y" * 4096

    with pytest.raises(ArtifactSnapshotError, match="event exceeded") as exc_info:
        artifact_snapshot_document(
            snapshot,
            expected_execution_id="execution-a",
            expected_pipeline_id="pipeline-a",
        )

    assert exc_info.value.code == "jarvis_artifact_snapshot_invalid"


@pytest.mark.parametrize(
    ("kind", "location", "ownership", "message"),
    [
        ("execution_path", "../escape", "execution", "execution artifact path"),
        ("cluster_path", "relative/output.bp", "shared", "cluster artifact path"),
        ("external_uri", "file:///tmp/output.bp", "external", "external artifact URI"),
    ],
)
def test_artifact_snapshot_rejects_unsafe_locations(
    kind: str,
    location: str,
    ownership: str,
    message: str,
) -> None:
    snapshot = _snapshot()
    snapshot["artifacts"][0]["location"] = {"kind": kind, "value": location}
    snapshot["artifacts"][0]["ownership"] = ownership

    with pytest.raises(RuntimeError, match=message):
        artifact_snapshot_document(
            snapshot,
            expected_execution_id="execution-a",
            expected_pipeline_id="pipeline-a",
        )


def test_artifact_query_pages_with_snapshot_bound_opaque_cursor() -> None:
    snapshot = _snapshot()
    snapshot["artifacts"] = [_artifact("A"), _artifact("B"), _artifact("C")]
    validated = artifact_snapshot_document(
        snapshot,
        expected_execution_id="execution-a",
        expected_pipeline_id="pipeline-a",
    )

    first = artifact_query_page(validated, page_size=2)
    cursor = first["next_cursor"]
    assert first == {
        "producer_schema_version": "jarvis.execution.artifacts.v1",
        "pipeline_id": "pipeline-a",
        "execution_id": "execution-a",
        "execution_state": "completed",
        "terminal": True,
        "artifacts": [_artifact("A"), _artifact("B")],
        "matching_artifact_count": 3,
        "returned_artifact_count": 2,
        "next_cursor": cursor,
    }
    assert isinstance(cursor, str) and cursor
    assert "art_" not in cursor

    second = artifact_query_page(validated, page_size=2, cursor=cursor)
    assert second["artifacts"] == [_artifact("C")]
    assert second["returned_artifact_count"] == 1
    assert second["next_cursor"] is None


def test_artifact_query_default_page_is_fifty_items() -> None:
    snapshot = _snapshot()
    snapshot["artifacts"] = [_artifact(f"{index:02d}") for index in range(60)]
    validated = artifact_snapshot_document(
        snapshot,
        expected_execution_id="execution-a",
        expected_pipeline_id="pipeline-a",
    )

    page = artifact_query_page(validated)

    assert page["matching_artifact_count"] == 60
    assert page["returned_artifact_count"] == 50
    assert len(page["artifacts"]) == 50
    assert isinstance(page["next_cursor"], str)


def test_artifact_query_pages_a_manifest_beyond_old_aggregate_limits() -> None:
    snapshot = _snapshot()
    artifacts: list[dict[str, Any]] = []
    for index in range(4100):
        artifact = _artifact()
        artifact["artifact_id"] = f"art_{index:022d}"
        artifact["logical_name"] = f"simulation-output-{index}"
        artifact["metadata"] = {"padding": "x" * 1024}
        artifacts.append(artifact)
    snapshot["artifacts"] = artifacts
    assert len(json.dumps(snapshot, separators=(",", ":")).encode("utf-8")) > (
        4 * 1024 * 1024
    )
    validated = artifact_snapshot_document(
        snapshot,
        expected_execution_id="execution-a",
        expected_pipeline_id="pipeline-a",
    )

    exact = artifact_query_page(
        validated,
        artifact_id="art_0000000000000000004099",
        page_size=1,
    )
    first = artifact_query_page(validated, page_size=1)
    cursor = first["next_cursor"]
    assert isinstance(cursor, str)
    second = artifact_query_page(validated, page_size=1, cursor=cursor)

    assert exact["matching_artifact_count"] == 1
    assert exact["returned_artifact_count"] == 1
    assert exact["artifacts"][0]["artifact_id"] == "art_0000000000000000004099"
    assert first["matching_artifact_count"] == 4100
    assert first["returned_artifact_count"] == 1
    assert second["artifacts"][0]["artifact_id"] == "art_0000000000000000000001"


def test_artifact_query_byte_boundary_never_skips_a_large_artifact() -> None:
    snapshot = _snapshot()
    artifacts: list[dict[str, Any]] = []
    for index in range(12):
        artifact = _artifact()
        artifact["artifact_id"] = f"art_{index:022d}"
        artifact["logical_name"] = f"simulation-output-{index}"
        if index < 11:
            artifact["metadata"] = {"padding": "x" * (48 * 1024)}
        artifacts.append(artifact)
    snapshot["artifacts"] = artifacts
    validated = artifact_snapshot_document(
        snapshot,
        expected_execution_id="execution-a",
        expected_pipeline_id="pipeline-a",
    )

    first = artifact_query_page(validated, page_size=100)
    cursor = first["next_cursor"]
    assert isinstance(cursor, str)
    second = artifact_query_page(validated, page_size=100, cursor=cursor)

    first_ids = [item["artifact_id"] for item in first["artifacts"]]
    second_ids = [item["artifact_id"] for item in second["artifacts"]]
    assert first_ids == [f"art_{index:022d}" for index in range(10)]
    assert second_ids == [f"art_{index:022d}" for index in range(10, 12)]
    assert first_ids + second_ids == [f"art_{index:022d}" for index in range(12)]


def test_artifact_query_filters_before_paging_and_binds_cursor_to_filters() -> None:
    snapshot = _snapshot()
    snapshot["artifacts"] = [
        _artifact("A", package_id="core", role="log"),
        _artifact("B", package_id="core", role="provenance"),
        _artifact("C", package_id="application", role="output"),
    ]
    validated = artifact_snapshot_document(
        snapshot,
        expected_execution_id="execution-a",
        expected_pipeline_id="pipeline-a",
    )

    first = artifact_query_page(validated, package_id="core", page_size=1)
    assert first["matching_artifact_count"] == 2
    assert [item["package_id"] for item in first["artifacts"]] == ["core"]
    cursor = first["next_cursor"]
    assert isinstance(cursor, str)
    with pytest.raises(
        ArtifactQueryError,
        match="does not match the requested filters",
    ) as exc_info:
        artifact_query_page(
            validated,
            package_id="application",
            page_size=1,
            cursor=cursor,
        )
    assert exc_info.value.code == "jarvis_artifact_cursor_filter_mismatch"
    assert exc_info.value.retryable is False


def test_artifact_query_cursor_rejects_changed_filtered_snapshot() -> None:
    snapshot = _snapshot()
    snapshot["artifacts"] = [_artifact("A"), _artifact("B")]
    validated = artifact_snapshot_document(
        snapshot,
        expected_execution_id="execution-a",
        expected_pipeline_id="pipeline-a",
    )
    first = artifact_query_page(validated, page_size=1)
    cursor = first["next_cursor"]
    assert isinstance(cursor, str)

    changed = deepcopy(validated)
    changed["artifacts"][1]["metadata"] = {"steps": 11}
    with pytest.raises(
        ArtifactQueryError,
        match="filtered snapshot changed",
    ) as exc_info:
        artifact_query_page(changed, page_size=1, cursor=cursor)
    assert exc_info.value.code == "jarvis_artifact_cursor_stale"
    assert exc_info.value.retryable is True


@pytest.mark.parametrize("page_size", [0, 101, True])
def test_artifact_query_rejects_invalid_page_size(page_size: object) -> None:
    validated = artifact_snapshot_document(
        _snapshot(),
        expected_execution_id="execution-a",
        expected_pipeline_id="pipeline-a",
    )
    with pytest.raises(RuntimeError, match="page_size must be between 1 and 100"):
        artifact_query_page(validated, page_size=page_size)  # type: ignore[arg-type]


@pytest.mark.parametrize("cursor", ["not+urlsafe", "A" * 1025])
def test_artifact_query_rejects_invalid_or_oversized_cursor(cursor: str) -> None:
    validated = artifact_snapshot_document(
        _snapshot(),
        expected_execution_id="execution-a",
        expected_pipeline_id="pipeline-a",
    )
    with pytest.raises(RuntimeError, match="cursor is invalid"):
        artifact_query_page(validated, cursor=cursor)
