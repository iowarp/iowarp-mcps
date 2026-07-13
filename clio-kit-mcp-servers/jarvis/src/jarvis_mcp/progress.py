"""MCP progress forwarding from JARVIS-owned execution snapshots.

JARVIS-CD owns package interpretation, execution identity, and durable progress
sidecars.  This module only polls the public execution API and forwards changed
snapshots through the standard MCP progress channel.
"""

from __future__ import annotations

import asyncio
import json
import math
from collections.abc import Awaitable, Callable, Mapping
from typing import Any, TypeVar, cast


ProgressReporter = Callable[[float, float | None, str], Awaitable[None]]

PROGRESS_SNAPSHOT_SCHEMA = "jarvis.execution.progress.v1"
PROGRESS_EVENT_SCHEMA = "jarvis.progress.v1"
PROGRESS_POLL_SECONDS = 0.05
PROGRESS_MAX_NOTIFICATION_BYTES = 64 * 1024
PROGRESS_MAX_NOTIFICATIONS = 10_000
PROGRESS_MAX_TOTAL_BYTES = 4 * 1024 * 1024
PROGRESS_MAX_SNAPSHOT_BYTES = 4 * 1024 * 1024
PROGRESS_MAX_PACKAGES = 4096
EXECUTION_STATES = {
    "preparing",
    "scripted",
    "submitting",
    "submitted",
    "running",
    "completed",
    "failed",
    "canceled",
    "unknown",
}

_ResultT = TypeVar("_ResultT")


class NativeProgressExecution:
    """Run one synchronous JARVIS operation while polling its durable progress."""

    def __init__(self, pipeline: Any, *, execution_id: str, pipeline_id: str) -> None:
        """Bind the poller to one exact JARVIS execution identity."""
        if not isinstance(execution_id, str) or not execution_id:
            raise ValueError("execution_id must be a non-empty string")
        if not isinstance(pipeline_id, str) or not pipeline_id:
            raise ValueError("pipeline_id must be a non-empty string")
        self.pipeline = pipeline
        self.execution_id = execution_id
        self.pipeline_id = pipeline_id
        self._last_snapshot: str | None = None
        self._notification_count = 0
        self._notification_bytes = 0

    async def run(
        self,
        operation: Callable[[], _ResultT],
        reporter: ProgressReporter,
    ) -> _ResultT:
        """Run ``operation`` in a worker and report each changed JARVIS snapshot.

        A progress transport or validation failure never abandons the owned
        operation.  The worker is always awaited before the progress error is
        propagated.
        """
        task = asyncio.create_task(asyncio.to_thread(operation))
        operation_error: BaseException | None = None
        progress_error: BaseException | None = None
        result: _ResultT | None = None

        while not task.done():
            if progress_error is None:
                try:
                    await self._poll(reporter, allow_missing=True)
                except BaseException as exc:
                    progress_error = exc
            try:
                await asyncio.sleep(PROGRESS_POLL_SECONDS)
            except BaseException as exc:
                if progress_error is None:
                    progress_error = exc

        try:
            result = await asyncio.shield(task)
        except BaseException as exc:
            operation_error = exc

        if progress_error is None:
            try:
                await self._poll(
                    reporter,
                    allow_missing=operation_error is not None,
                )
            except BaseException as exc:
                progress_error = exc

        if progress_error is not None:
            if operation_error is not None:
                raise progress_error from operation_error
            raise progress_error
        if operation_error is not None:
            raise operation_error
        return cast(_ResultT, result)

    async def _poll(
        self,
        reporter: ProgressReporter,
        *,
        allow_missing: bool,
    ) -> None:
        try:
            snapshot = self.pipeline.get_execution_progress(self.execution_id)
        except FileNotFoundError:
            if allow_missing:
                return
            raise
        document = progress_snapshot_document(
            snapshot,
            expected_execution_id=self.execution_id,
            expected_pipeline_id=self.pipeline_id,
        )
        snapshot_json = json.dumps(
            document,
            allow_nan=False,
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        )
        if snapshot_json == self._last_snapshot:
            return
        notification_sequence = self._notification_count + 1
        encoded_size = len(snapshot_json.encode("utf-8"))
        if encoded_size > PROGRESS_MAX_NOTIFICATION_BYTES:
            raise RuntimeError("JARVIS progress snapshot exceeded the MCP byte limit")
        if notification_sequence > PROGRESS_MAX_NOTIFICATIONS:
            raise RuntimeError("JARVIS progress exceeded the MCP notification limit")
        self._notification_count = notification_sequence
        self._notification_bytes += encoded_size
        if self._notification_bytes > PROGRESS_MAX_TOTAL_BYTES:
            raise RuntimeError("JARVIS progress exceeded the MCP total byte limit")
        await reporter(float(notification_sequence), None, snapshot_json)
        self._last_snapshot = snapshot_json


def progress_snapshot_document(
    snapshot: object,
    *,
    expected_execution_id: str,
    expected_pipeline_id: str,
) -> dict[str, Any]:
    """Return and minimally cross-check one JARVIS progress snapshot document."""
    if isinstance(snapshot, Mapping):
        value = dict(snapshot)
    else:
        to_dict = getattr(snapshot, "to_dict", None)
        if not callable(to_dict):
            raise RuntimeError("JARVIS progress snapshot is not serializable")
        rendered = to_dict()
        if not isinstance(rendered, dict):
            raise RuntimeError("JARVIS progress snapshot is not an object")
        value = rendered
    required = {
        "schema_version",
        "execution_id",
        "pipeline_id",
        "execution_state",
        "terminal",
        "packages",
    }
    if set(value) != required or value.get("schema_version") != (
        PROGRESS_SNAPSHOT_SCHEMA
    ):
        raise RuntimeError("JARVIS progress snapshot schema is unsupported")
    if value.get("execution_id") != expected_execution_id:
        raise RuntimeError("JARVIS progress execution identity did not match")
    if value.get("pipeline_id") != expected_pipeline_id:
        raise RuntimeError("JARVIS progress pipeline identity did not match")
    if (
        not isinstance(value.get("execution_state"), str)
        or not value["execution_state"]
    ):
        raise RuntimeError("JARVIS progress execution state is invalid")
    if value["execution_state"] not in EXECUTION_STATES:
        raise RuntimeError("JARVIS progress execution state is unsupported")
    if not isinstance(value.get("terminal"), bool):
        raise RuntimeError("JARVIS progress terminal flag is invalid")
    packages = value.get("packages")
    if not isinstance(packages, list):
        raise RuntimeError("JARVIS progress packages must be a list")
    if len(packages) > PROGRESS_MAX_PACKAGES:
        raise RuntimeError("JARVIS progress snapshot contains too many packages")
    seen_packages: set[str] = set()
    for package in packages:
        _validate_package_snapshot(
            package,
            execution_id=expected_execution_id,
            seen_packages=seen_packages,
        )
    try:
        encoded = json.dumps(
            value,
            allow_nan=False,
            separators=(",", ":"),
            sort_keys=True,
        ).encode("utf-8")
    except (TypeError, ValueError, OverflowError, RecursionError) as exc:
        raise RuntimeError("JARVIS progress snapshot is not bounded JSON") from exc
    if len(encoded) > PROGRESS_MAX_SNAPSHOT_BYTES:
        raise RuntimeError("JARVIS progress snapshot exceeded its byte limit")
    return cast(dict[str, Any], value)


def _validate_package_snapshot(
    value: object,
    *,
    execution_id: str,
    seen_packages: set[str],
) -> None:
    if not isinstance(value, dict) or set(value) != {
        "package_id",
        "package_name",
        "event_count",
        "latest",
    }:
        raise RuntimeError("JARVIS package progress snapshot is invalid")
    package_id = value.get("package_id")
    package_name = value.get("package_name")
    event_count = value.get("event_count")
    if (
        not isinstance(package_id, str)
        or not package_id
        or len(package_id) > 256
        or package_id in seen_packages
    ):
        raise RuntimeError("JARVIS package progress identity is invalid")
    seen_packages.add(package_id)
    if not isinstance(package_name, str) or not package_name or len(package_name) > 256:
        raise RuntimeError("JARVIS package progress name is invalid")
    if (
        isinstance(event_count, bool)
        or not isinstance(event_count, int)
        or event_count < 0
    ):
        raise RuntimeError("JARVIS package progress event count is invalid")
    latest = value.get("latest")
    if latest is None:
        if event_count != 0:
            raise RuntimeError("JARVIS package progress omitted its latest event")
        return
    if not isinstance(latest, dict):
        raise RuntimeError("JARVIS package progress latest event is invalid")
    required_event_fields = {
        "schema_version",
        "package_name",
        "package_id",
        "execution_id",
        "label",
        "state",
        "sequence",
        "observed_at_epoch",
        "determinate",
        "metadata",
    }
    optional_event_fields = {"current", "total", "unit", "message"}
    if not required_event_fields.issubset(latest) or not set(latest).issubset(
        required_event_fields | optional_event_fields
    ):
        raise RuntimeError("JARVIS package progress event fields are invalid")
    if (
        latest.get("schema_version") != PROGRESS_EVENT_SCHEMA
        or latest.get("execution_id") != execution_id
        or latest.get("package_id") != package_id
        or latest.get("package_name") != package_name
    ):
        raise RuntimeError("JARVIS package progress event identity did not match")
    sequence = latest.get("sequence")
    if isinstance(sequence, bool) or not isinstance(sequence, int) or sequence < 0:
        raise RuntimeError("JARVIS package progress sequence is invalid")
    for field_name in ("label", "state"):
        field_value = latest.get(field_name)
        if not isinstance(field_value, str) or not field_value:
            raise RuntimeError(f"JARVIS package progress {field_name} is invalid")
        if len(field_value) > 256:
            raise RuntimeError(f"JARVIS package progress {field_name} is too long")
    if latest["state"] not in {
        "pending",
        "starting",
        "running",
        "ready",
        "completed",
        "failed",
        "canceled",
    }:
        raise RuntimeError("JARVIS package progress state is unsupported")
    for field_name in ("unit", "message"):
        field_value = latest.get(field_name)
        maximum = 256 if field_name == "unit" else 4096
        if field_value is not None and (
            not isinstance(field_value, str)
            or not field_value
            or len(field_value) > maximum
        ):
            raise RuntimeError(f"JARVIS package progress {field_name} is invalid")
    observed_at = latest.get("observed_at_epoch")
    if not _finite_number(observed_at):
        raise RuntimeError("JARVIS package progress observation time is invalid")
    if not isinstance(latest.get("metadata"), dict):
        raise RuntimeError("JARVIS package progress metadata is invalid")
    determinate = latest.get("determinate")
    if not isinstance(determinate, bool):
        raise RuntimeError("JARVIS package progress determination flag is invalid")
    current = latest.get("current")
    total = latest.get("total")
    if current is not None and not _finite_number(current):
        raise RuntimeError("JARVIS package progress current value is invalid")
    if total is not None and (not _finite_number(total) or float(total) <= 0):
        raise RuntimeError("JARVIS package progress total value is invalid")
    if total is not None and (current is None or float(current) > float(total)):
        raise RuntimeError("JARVIS package progress total did not cover current")
    if determinate is not (current is not None and total is not None):
        raise RuntimeError("JARVIS package progress determination did not match values")
    if event_count == 0:
        raise RuntimeError(
            "JARVIS package progress event count omitted its latest event"
        )


def _finite_number(value: object) -> bool:
    return (
        not isinstance(value, bool)
        and isinstance(value, (int, float))
        and math.isfinite(float(value))
        and float(value) >= 0
    )
