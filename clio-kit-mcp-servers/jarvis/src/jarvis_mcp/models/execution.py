"""Execution handle/record/run-result documents and the execution intent request model.

Bundles ``ExecutionIntent`` with its validation/conversion helpers
(``_validated_execution_intent``, ``_execution_intent_to_pipeline_config``,
``_detect_scheduler_name``) as one concern: the request-side execution intent
and the response-side execution documents it drives. The tool functions that
call these helpers (``jarvis_run_tool``, ``jarvis_create_pipeline_tool``) stay
in ``server.py``; only the pure validation/conversion logic lives here.
"""

from __future__ import annotations

import os
import re
from typing import Any, Literal

from typing_extensions import TypedDict

from fastmcp.exceptions import ToolError
from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    ValidationError,
    field_validator,
    model_validator,
)

from .artifact_documents import JarvisExecutionArtifactPageDocument
from .progress import JarvisProgressSnapshotDocument
from .service_runtime import JarvisServiceRuntimeSnapshotDocument


class JarvisExecutionHandleDocument(TypedDict):
    """Stable JARVIS-CD execution-handle document."""

    schema_version: Literal["jarvis.execution.handle.v1"]
    execution_id: str
    pipeline_id: str
    mode: Literal["direct", "scheduler"]
    scheduler_provider: str | None
    scheduler_native_id: str | None
    cluster: str | None


class JarvisExecutionRecordDocument(TypedDict):
    """Stable JARVIS-CD durable execution-record document."""

    schema_version: Literal["jarvis.execution.record.v1"]
    execution_id: str
    pipeline_id: str
    pipeline_name: str
    mode: Literal["direct", "scheduler"]
    scheduler_provider: str | None
    scheduler_native_id: str | None
    cluster: str | None
    state: Literal[
        "preparing",
        "scripted",
        "submitting",
        "submitted",
        "running",
        "completed",
        "failed",
        "canceled",
        "unknown",
    ]
    submitted: bool
    terminal: bool
    created_at: str
    updated_at: str
    return_code: int | None
    error: str | None
    metadata: dict[str, Any]


class JarvisRunResult(TypedDict):
    """Frozen top-level result envelope for ``jarvis_run``."""

    schema_version: Literal["clio-kit.jarvis-run.v1"]
    pipeline_id: str
    execution_id: str
    status: Literal[
        "preparing",
        "scripted",
        "submitting",
        "submitted",
        "running",
        "completed",
        "failed",
        "canceled",
        "unknown",
    ]
    mode: Literal["direct", "scheduler"]
    scheduler: dict[str, Any] | None
    script_path: str | None
    wait: bool
    execution_handle: JarvisExecutionHandleDocument
    execution_record: JarvisExecutionRecordDocument
    progress: JarvisProgressSnapshotDocument
    runtime_metadata: dict[str, Any]


class JarvisExecutionResult(BaseModel):
    """Frozen top-level result envelope for a selectable execution query."""

    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
        hide_input_in_errors=True,
    )

    schema_version: Literal["clio-kit.jarvis-execution.v2"]
    pipeline_id: str
    execution_id: str
    execution_handle: JarvisExecutionHandleDocument
    execution_record: JarvisExecutionRecordDocument
    runtime_metadata: dict[str, Any]
    progress: JarvisProgressSnapshotDocument | None
    artifact_page: JarvisExecutionArtifactPageDocument | None
    service_runtimes: JarvisServiceRuntimeSnapshotDocument | None


_EXECUTION_MODES = {
    "auto",
    "local",
    "direct",
    "cluster",
    "scheduler",
    "hostfile",
}
_SCHEDULER_EXECUTION_FIELDS = {
    "job_name",
    "nodes",
    "tasks",
    "tasks_per_node",
    "cpus_per_task",
    "walltime",
    "partition",
    "account",
    "qos",
    "output",
    "error",
    "exclusive",
    "gpus",
    "gpus_per_node",
}
_SCHEDULER_TOKEN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:@%+,-]{0,255}$")
_HOST_ENTRY = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,252}$")


def _bounded_single_line(value: str, *, field: str, limit: int = 4096) -> str:
    """Reject control characters and unbounded scheduler/path text."""
    if not value or len(value.encode("utf-8")) > limit:
        raise ValueError(f"execution.{field} must be a non-empty bounded string")
    if any(ord(character) < 32 or ord(character) == 127 for character in value):
        raise ValueError(f"execution.{field} cannot contain control characters")
    return value


class ExecutionIntent(BaseModel):
    """Validated, backend-neutral execution request for a JARVIS pipeline."""

    model_config = ConfigDict(extra="forbid", strict=True)

    mode: Literal["auto", "local", "direct", "cluster", "scheduler", "hostfile"] = (
        "auto"
    )
    hostfile: str | None = None
    hosts: list[str] | None = Field(default=None, min_length=1)
    job_name: str | None = None
    nodes: int | None = Field(default=None, gt=0)
    tasks: int | None = Field(default=None, gt=0)
    tasks_per_node: int | None = Field(default=None, gt=0)
    cpus_per_task: int | None = Field(default=None, gt=0)
    walltime: str | None = None
    partition: str | None = None
    account: str | None = None
    qos: str | None = None
    output: str | None = None
    error: str | None = None
    exclusive: bool | None = None
    gpus: int | None = Field(default=None, gt=0)
    gpus_per_node: int | None = Field(default=None, gt=0)

    @field_validator("mode", mode="before")
    @classmethod
    def normalize_mode(cls, value: object) -> object:
        """Normalize a textual mode while preserving strict rejection of other types."""
        if isinstance(value, str):
            return value.strip().lower()
        return value

    @field_validator("hostfile", mode="after")
    @classmethod
    def validate_hostfile(cls, value: str | None) -> str | None:
        """Validate a hostfile path without forbidding platform separators."""
        if value is None:
            return None
        return _bounded_single_line(value, field="hostfile")

    @field_validator("output", "error", mode="after")
    @classmethod
    def validate_scheduler_path(cls, value: str | None, info: Any) -> str | None:
        """Require a single printable directive path token."""
        if value is None:
            return None
        rendered = _bounded_single_line(value, field=info.field_name)
        if any(character.isspace() for character in rendered) or "#" in rendered:
            raise ValueError(
                f"execution.{info.field_name} must be one printable path token"
            )
        return rendered

    @field_validator(
        "job_name",
        "walltime",
        "partition",
        "account",
        "qos",
        mode="after",
    )
    @classmethod
    def validate_scheduler_token(cls, value: str | None, info: Any) -> str | None:
        """Reject whitespace/control injection in scheduler directive values."""
        if value is None:
            return None
        rendered = _bounded_single_line(value, field=info.field_name, limit=256)
        if _SCHEDULER_TOKEN.fullmatch(rendered) is None:
            raise ValueError(
                f"execution.{info.field_name} is not a valid scheduler token"
            )
        return rendered

    @field_validator("hosts", mode="after")
    @classmethod
    def validate_hosts(cls, value: list[str] | None) -> list[str] | None:
        """Validate semantic host names before writing a scheduler hostfile."""
        if value is None:
            return None
        if len(value) > 4096:
            raise ValueError("execution.hosts cannot contain more than 4096 entries")
        if any(_HOST_ENTRY.fullmatch(host) is None for host in value):
            raise ValueError("execution.hosts contains an invalid host name")
        return value

    @model_validator(mode="after")
    def validate_mode_fields(self) -> "ExecutionIntent":
        """Reject fields that cannot be represented by the selected execution mode."""
        populated = self.model_fields_set
        scheduler_fields = sorted(populated & _SCHEDULER_EXECUTION_FIELDS)
        host_fields = sorted(populated & {"hostfile", "hosts"})

        if self.mode in {"local", "direct"} and (scheduler_fields or host_fields):
            incompatible = ", ".join(scheduler_fields + host_fields)
            raise ValueError(
                f"execution.mode='{self.mode}' does not accept fields: {incompatible}"
            )
        if self.mode == "hostfile":
            if scheduler_fields:
                raise ValueError(
                    "execution.mode='hostfile' does not accept scheduler fields: "
                    + ", ".join(scheduler_fields)
                )
            if (self.hostfile is None) == (self.hosts is None):
                raise ValueError(
                    "execution.hostfile requires exactly one of hostfile or hosts "
                    "when execution.mode='hostfile'"
                )
        elif host_fields:
            raise ValueError(
                f"execution.mode='{self.mode}' does not accept fields: "
                + ", ".join(host_fields)
            )
        return self


def _validated_execution_intent(
    execution: ExecutionIntent | dict[str, Any],
) -> ExecutionIntent:
    if isinstance(execution, ExecutionIntent):
        return execution
    raw_mode = execution.get("mode", "auto")
    if (
        not isinstance(raw_mode, str)
        or raw_mode.strip().lower() not in _EXECUTION_MODES
    ):
        raise ToolError(
            "execution.mode must be one of: auto, local, direct, cluster, scheduler, hostfile"
        )
    try:
        return ExecutionIntent.model_validate(execution)
    except ValidationError as error:
        details = []
        for item in error.errors(include_url=False, include_context=False):
            location = ".".join(str(part) for part in item["loc"])
            prefix = f"{location}: " if location else ""
            details.append(f"{prefix}{item['msg']}")
        raise ToolError("invalid execution intent: " + "; ".join(details)) from error


def _execution_intent_to_pipeline_config(
    execution: ExecutionIntent | dict[str, Any],
) -> dict[str, Any]:
    intent = _validated_execution_intent(execution)
    values = intent.model_dump(exclude_none=True)
    mode = intent.mode
    if mode in {"local", "direct"}:
        return {"scheduler": None, "hostfile": None}
    if mode == "hostfile":
        if intent.hostfile is not None:
            return {"scheduler": None, "hostfile": intent.hostfile}
        if intent.hosts is not None:
            return {
                "scheduler": None,
                "hostfile_entries": intent.hosts,
            }
        raise AssertionError("validated hostfile intent has no target")
    if mode in {"cluster", "scheduler", "auto"}:
        scheduler_name = _detect_scheduler_name()
        if scheduler_name is None:
            if mode == "auto" and set(values) <= {"mode"}:
                return {}
            raise ToolError("no supported cluster scheduler detected on this machine")
        if mode == "auto" and set(values) <= {"mode"}:
            return {}
        scheduler: dict[str, Any] = {"name": scheduler_name}
        mapping = {
            "job_name": "job_name",
            "nodes": "nodes",
            "tasks": "ntasks",
            "tasks_per_node": "ntasks_per_node",
            "cpus_per_task": "cpus_per_task",
            "walltime": "time",
            "partition": "partition",
            "account": "account",
            "qos": "qos",
            "output": "output",
            "error": "error",
            "exclusive": "exclusive",
            "gpus": "gpus",
            "gpus_per_node": "gpus_per_node",
        }
        for public_key, scheduler_key in mapping.items():
            if public_key in values:
                scheduler[scheduler_key] = values[public_key]
        return {"scheduler": scheduler}
    raise AssertionError(f"validated execution intent has unsupported mode: {mode}")


def _detect_scheduler_name() -> str | None:
    configured = os.getenv("JARVIS_MCP_SCHEDULER") or os.getenv("JARVIS_SCHEDULER")
    if configured:
        return configured.strip().lower()
    from shutil import which

    if which("sbatch") is not None:
        return "slurm"
    return None
