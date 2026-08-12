"""Production invariants for exposing JARVIS-owned artifact snapshots."""

from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path
from typing import Any

import pytest

from jarvis_mcp.artifact_content import ArtifactContentError, read_artifact_tail, resolve_artifact_path
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


def _log_snapshot(
    *,
    execution_id: str = "execution-a",
    location: dict[str, str],
    state: str = "finalized",
) -> dict[str, Any]:
    artifact = _artifact(
        "L", package_id="lammps-cu-elastic", role="log", state=state
    )
    artifact["execution_id"] = execution_id
    artifact["location"] = location
    return {
        "schema_version": "jarvis.execution.artifacts.v1",
        "execution_id": execution_id,
        "pipeline_id": "pipeline-a",
        "execution_state": "failed",
        "terminal": True,
        "artifacts": [artifact],
    }


def _validated_log_snapshot(**kwargs: Any) -> dict[str, Any]:
    return artifact_snapshot_document(
        _log_snapshot(**kwargs),
        expected_execution_id=kwargs.get("execution_id", "execution-a"),
        expected_pipeline_id="pipeline-a",
    )


class TestArtifactContentMaxBytes:
    """FAILING-FIRST (gating fix): the LAMMPS demo's compute expert reached a
    real terminal failure with no curated way to read the actual stdout/
    stderr text -- jarvis_get_execution's artifact manifest was content-free
    by design. ``content_max_bytes`` adds a narrow, bounded tail read scoped
    to ``role="log"`` artifacts only."""

    def test_reads_the_tail_of_an_execution_scoped_log_file(self, tmp_path: Path) -> None:
        execution_root = tmp_path / "jarvis_c658476089200e8ee78951f11054b737"
        execution_root.mkdir()
        (execution_root / "stdout.log").write_bytes(
            b"line-1\nline-2\nline-3\nLAMMPS failed with exit status 1\n"
        )
        snapshot = _validated_log_snapshot(
            location={"kind": "execution_path", "value": "stdout.log"}
        )

        page = artifact_query_page(
            snapshot, role="log", content_max_bytes=4096, execution_root=execution_root
        )

        artifact = page["artifacts"][0]
        assert artifact["content"] == (
            "line-1\nline-2\nline-3\nLAMMPS failed with exit status 1\n"
        )
        assert artifact["content_truncated"] is False
        assert artifact["content_bytes_read"] == len(artifact["content"])
        assert artifact["content_error"] is None

    def test_reads_only_the_tail_when_the_file_exceeds_the_bound(self, tmp_path: Path) -> None:
        execution_root = tmp_path / "exec"
        execution_root.mkdir()
        body = "".join(f"step {i}\n" for i in range(1000))
        (execution_root / "stdout.log").write_bytes(body.encode("utf-8"))
        snapshot = _validated_log_snapshot(
            location={"kind": "execution_path", "value": "stdout.log"}
        )

        page = artifact_query_page(
            snapshot, role="log", content_max_bytes=64, execution_root=execution_root
        )

        artifact = page["artifacts"][0]
        assert artifact["content_truncated"] is True
        assert artifact["content_bytes_read"] == 64
        assert artifact["content"] == body.encode("utf-8")[-64:].decode(
            "utf-8", errors="replace"
        )
        # The tail carries the LAST lines -- nearest a crash -- not the head.
        assert artifact["content"].endswith("step 999\n")

    def test_resolves_a_cluster_path_location_directly_without_an_execution_root(
        self, tmp_path: Path
    ) -> None:
        """Unit-level (bypassing the POSIX-only cluster-path string validation
        exercised elsewhere in this file): ``cluster_path`` locations are
        already-absolute paths on the SAME host jarvis_mcp runs on (it is
        co-located with the execution it reports on), so resolution is a
        direct ``Path(value)`` -- no ``execution_root`` join, unlike
        ``execution_path``. This is exactly the ``log.lammps`` case."""
        log_file = tmp_path / "log.lammps"
        log_file.write_bytes(b"LAMMPS (2 Aug2026)\n")

        resolved = resolve_artifact_path(
            {"kind": "cluster_path", "value": str(log_file)}, execution_root=None
        )
        content, truncated, bytes_read = read_artifact_tail(resolved, max_bytes=4096)

        assert resolved == log_file
        assert content == "LAMMPS (2 Aug2026)\n"
        assert truncated is False
        assert bytes_read == len(b"LAMMPS (2 Aug2026)\n")

    def test_execution_path_location_requires_an_execution_root(self) -> None:
        with pytest.raises(ArtifactContentError, match="root directory could not be resolved"):
            resolve_artifact_path(
                {"kind": "execution_path", "value": "stdout.log"}, execution_root=None
            )

    def test_types_a_reason_for_non_log_roles_instead_of_silently_omitting(self) -> None:
        snapshot = artifact_snapshot_document(
            _snapshot(),  # default artifact role="output"
            expected_execution_id="execution-a",
            expected_pipeline_id="pipeline-a",
        )

        page = artifact_query_page(snapshot, content_max_bytes=4096)

        artifact = page["artifacts"][0]
        assert artifact["content"] is None
        assert artifact["content_truncated"] is False
        assert artifact["content_bytes_read"] == 0
        assert artifact["content_error"] is not None
        assert "log" in artifact["content_error"]

    def test_types_a_reason_when_execution_root_cannot_be_resolved(self) -> None:
        snapshot = _validated_log_snapshot(
            location={"kind": "execution_path", "value": "stdout.log"}
        )

        page = artifact_query_page(
            snapshot, role="log", content_max_bytes=4096, execution_root=None
        )

        artifact = page["artifacts"][0]
        assert artifact["content"] is None
        assert artifact["content_error"] is not None
        assert "root" in artifact["content_error"]

    def test_types_a_reason_for_an_unreadable_file_without_failing_the_page(
        self, tmp_path: Path
    ) -> None:
        execution_root = tmp_path / "exec"
        execution_root.mkdir()
        # stdout.log deliberately not created -- exercises the missing-file path.
        snapshot = _validated_log_snapshot(
            location={"kind": "execution_path", "value": "stdout.log"}
        )

        page = artifact_query_page(
            snapshot, role="log", content_max_bytes=4096, execution_root=execution_root
        )

        artifact = page["artifacts"][0]
        assert artifact["content"] is None
        assert artifact["content_error"] is not None
        assert page["returned_artifact_count"] == 1  # the page itself still succeeds

    def test_omits_content_fields_entirely_when_not_requested(self) -> None:
        """Regression: the default (content_max_bytes=None) path must be
        byte-identical to pre-fix behavior -- no new keys, no schema drift
        for every existing caller that never asks for content."""
        snapshot = _validated_log_snapshot(
            location={"kind": "execution_path", "value": "stdout.log"}
        )

        page = artifact_query_page(snapshot, role="log")

        artifact = page["artifacts"][0]
        assert "content" not in artifact
        assert "content_truncated" not in artifact
        assert "content_bytes_read" not in artifact
        assert "content_error" not in artifact

    @pytest.mark.parametrize("content_max_bytes", [0, 65537, True, "10"])
    def test_rejects_invalid_content_max_bytes(self, content_max_bytes: object) -> None:
        snapshot = _validated_log_snapshot(
            location={"kind": "execution_path", "value": "stdout.log"}
        )
        with pytest.raises(ArtifactQueryError, match="content_max_bytes must be between"):
            artifact_query_page(
                snapshot,
                role="log",
                content_max_bytes=content_max_bytes,  # type: ignore[arg-type]
            )
