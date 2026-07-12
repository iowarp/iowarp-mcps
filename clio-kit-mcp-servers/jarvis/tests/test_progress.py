"""Production invariants for forwarding JARVIS-owned progress snapshots."""

from __future__ import annotations

import json
import threading
import time
from copy import deepcopy
from typing import Any

import pytest

from jarvis_mcp.progress import NativeProgressExecution, progress_snapshot_document


def _snapshot(*, latest: dict[str, Any] | None = None) -> dict[str, Any]:
    event_count = 0 if latest is None else int(latest["sequence"]) + 1
    return {
        "schema_version": "jarvis.execution.progress.v1",
        "execution_id": "execution-a",
        "pipeline_id": "pipeline-a",
        "execution_state": "running",
        "terminal": False,
        "packages": [
            {
                "package_id": "render",
                "package_name": "builtin.paraview",
                "event_count": event_count,
                "latest": latest,
            }
        ],
    }


def _event(
    *,
    sequence: int,
    current: float | None = None,
    total: float | None = None,
) -> dict[str, Any]:
    event: dict[str, Any] = {
        "schema_version": "jarvis.progress.v1",
        "package_name": "builtin.paraview",
        "package_id": "render",
        "execution_id": "execution-a",
        "label": "frame",
        "state": "running",
        "message": "rendered a real frame",
        "sequence": sequence,
        "observed_at_epoch": time.time(),
        "determinate": current is not None and total is not None,
        "metadata": {"output": "frame.png"},
    }
    if current is not None:
        event["current"] = current
    if total is not None:
        event["total"] = total
    return event


class _Pipeline:
    def __init__(self, document: dict[str, Any] | None) -> None:
        self.document = document
        self.lock = threading.Lock()

    def get_execution_progress(self, execution_id: str) -> dict[str, Any]:
        assert execution_id == "execution-a"
        with self.lock:
            if self.document is None:
                raise FileNotFoundError(execution_id)
            return deepcopy(self.document)

    def replace(self, document: dict[str, Any]) -> None:
        with self.lock:
            self.document = document


@pytest.mark.asyncio
async def test_native_progress_polls_durable_snapshots_before_completion() -> None:
    pipeline = _Pipeline(_snapshot())
    finished = threading.Event()
    reports: list[tuple[float, float | None, dict[str, Any], bool]] = []

    def operation() -> str:
        time.sleep(0.08)
        pipeline.replace(_snapshot(latest=_event(sequence=0, current=1, total=3)))
        time.sleep(0.1)
        finished.set()
        return "complete"

    async def reporter(current: float, total: float | None, message: str) -> None:
        reports.append((current, total, json.loads(message), finished.is_set()))

    result = await NativeProgressExecution(
        pipeline,
        execution_id="execution-a",
        pipeline_id="pipeline-a",
    ).run(operation, reporter)

    assert result == "complete"
    assert any(not was_finished for _, _, _, was_finished in reports)
    assert all(
        message["schema_version"] == "jarvis.execution.progress.v1"
        and message["execution_id"] == "execution-a"
        for _, _, message, _ in reports
    )
    assert all(
        set(message)
        == {
            "schema_version",
            "execution_id",
            "pipeline_id",
            "execution_state",
            "terminal",
            "packages",
        }
        for _, _, message, _ in reports
    )
    assert [current for current, _, _, _ in reports] == list(
        map(float, range(1, len(reports) + 1))
    )
    assert all(total is None for _, total, _, _ in reports)
    assert any(
        package["latest"] is not None
        and package["latest"].get("current") == 1
        and package["latest"].get("total") == 3
        for _, _, message, _ in reports
        for package in message["packages"]
    )


@pytest.mark.asyncio
async def test_reporter_failure_waits_for_owned_operation() -> None:
    pipeline = _Pipeline(_snapshot())
    finished = threading.Event()

    def operation() -> None:
        time.sleep(0.2)
        finished.set()

    async def reporter(_current: float, _total: float | None, _message: str) -> None:
        raise RuntimeError("notification transport failed")

    started = time.monotonic()
    with pytest.raises(RuntimeError, match="notification transport failed"):
        await NativeProgressExecution(
            pipeline,
            execution_id="execution-a",
            pipeline_id="pipeline-a",
        ).run(operation, reporter)

    assert finished.is_set()
    assert time.monotonic() - started >= 0.18


@pytest.mark.asyncio
async def test_transport_sequence_is_independent_of_workload_progress() -> None:
    pipeline = _Pipeline(_snapshot(latest=_event(sequence=7)))
    reports: list[tuple[float, float | None]] = []

    async def reporter(current: float, total: float | None, _message: str) -> None:
        reports.append((current, total))

    await NativeProgressExecution(
        pipeline,
        execution_id="execution-a",
        pipeline_id="pipeline-a",
    ).run(lambda: None, reporter)

    assert reports == [(1.0, None)]


def test_progress_snapshot_rejects_cross_execution_and_duplicate_packages() -> None:
    wrong = _snapshot(latest=_event(sequence=0))
    wrong["packages"].append(deepcopy(wrong["packages"][0]))
    with pytest.raises(RuntimeError, match="identity is invalid"):
        progress_snapshot_document(
            wrong,
            expected_execution_id="execution-a",
            expected_pipeline_id="pipeline-a",
        )

    wrong = _snapshot(latest=_event(sequence=0))
    wrong["packages"][0]["latest"]["execution_id"] = "execution-forged"
    with pytest.raises(RuntimeError, match="event identity did not match"):
        progress_snapshot_document(
            wrong,
            expected_execution_id="execution-a",
            expected_pipeline_id="pipeline-a",
        )


def test_progress_snapshot_rejects_fabricated_determinate_flag() -> None:
    wrong = _snapshot(latest=_event(sequence=0, current=1, total=2))
    wrong["packages"][0]["latest"]["determinate"] = False
    with pytest.raises(RuntimeError, match="determination did not match"):
        progress_snapshot_document(
            wrong,
            expected_execution_id="execution-a",
            expected_pipeline_id="pipeline-a",
        )


def test_progress_snapshot_rejects_extended_event_schema() -> None:
    """Unknown provider fields cannot silently extend the frozen JARVIS event."""
    wrong = _snapshot(latest=_event(sequence=0))
    wrong["packages"][0]["latest"]["untrusted"] = True
    with pytest.raises(RuntimeError, match="event fields are invalid"):
        progress_snapshot_document(
            wrong,
            expected_execution_id="execution-a",
            expected_pipeline_id="pipeline-a",
        )
