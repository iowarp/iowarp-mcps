"""Compact, typed agent-facing contract for the Slurm MCP server.

The implementation modules intentionally remain available for the legacy/admin
profile.  This module composes those scheduler operations into a smaller user
surface with stable result envelopes and explicit native-ID semantics.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Annotated, Any, Literal

from fastmcp.exceptions import ToolError
from pydantic import BaseModel, ConfigDict, Field

from .implementation.array_jobs import submit_array_job
from .implementation.cluster_info import get_slurm_info
from .implementation.job_cancellation import cancel_slurm_job
from .implementation.job_details import get_job_details
from .implementation.job_listing import list_slurm_jobs
from .implementation.job_output import get_job_output
from .implementation.job_status import get_job_status
from .implementation.job_submission import submit_slurm_job
from .implementation.node_info import get_node_info
from .implementation.queue_info import get_queue_info

SchedulerNativeJobId = Annotated[
    str,
    Field(
        min_length=1,
        max_length=128,
        description=(
            "Slurm's scheduler-native job identifier, for example '12345', "
            "'12345_7', '12345+1', or '12345.batch'."
        ),
    ),
]
ScriptPath = Annotated[
    str,
    Field(
        min_length=1,
        max_length=4096,
        description="Path to an existing executable or shell job script.",
    ),
]
CoreCount = Annotated[
    int,
    Field(ge=1, le=1_048_576, description="CPU cores requested per task."),
]
MemoryRequest = Annotated[
    str,
    Field(
        min_length=1,
        max_length=64,
        description="Positive Slurm memory request such as 4096M or 16G.",
    ),
]
TimeLimit = Annotated[
    str,
    Field(
        min_length=7,
        max_length=64,
        description="Slurm walltime in [days-]hours:minutes:seconds syntax.",
    ),
]
ResourceToken = Annotated[
    str,
    Field(
        min_length=1,
        max_length=128,
        pattern=r"^[A-Za-z0-9_.-]+$",
        description="A scheduler name or filter containing no shell metacharacters.",
    ),
]
ArraySpec = Annotated[
    str,
    Field(
        min_length=1,
        max_length=256,
        description="Slurm array task expression such as 0-31 or 0-99%8.",
    ),
]
OutputLimit = Annotated[
    int,
    Field(
        ge=1,
        le=1_000_000,
        description="Maximum number of trailing characters returned per output stream.",
    ),
]
RecordLimit = Annotated[
    int,
    Field(
        ge=1,
        le=1_000,
        description="Maximum number of scheduler records returned by this call.",
    ),
]

_NATIVE_JOB_ID = re.compile(
    r"^[1-9][0-9]*(?:_[0-9]+)?(?:\+[0-9]+)?(?:\.(?:batch|extern|[0-9]+))?$"
)
_ARRAY_SPEC = re.compile(
    r"^[0-9]+(?:-[0-9]+(?::[1-9][0-9]*)?)?(?:%[1-9][0-9]*)?"
    r"(?:,[0-9]+(?:-[0-9]+(?::[1-9][0-9]*)?)?(?:%[1-9][0-9]*)?)*$"
)
_SAFE_TOKEN = re.compile(r"^[A-Za-z0-9_.-]+$")
_MEMORY = re.compile(r"^[1-9][0-9]*(?:\.[0-9]+)?(?:[KMGTP](?:i?B)?|B)?$", re.I)
_WALLTIME = re.compile(r"^(?:[0-9]+-)?[0-9]{1,3}:[0-5][0-9]:[0-5][0-9]$")


class ClosedModel(BaseModel):
    """Base for contract documents that reject unknown fields."""

    model_config = ConfigDict(extra="forbid", frozen=True)


class SubmissionResources(ClosedModel):
    """Resources recorded for a submitted Slurm job or array."""

    cores: int = Field(ge=1, le=1_048_576)
    memory: str
    time_limit: str
    partition: str | None
    job_name: str | None


class SlurmSubmission(ClosedModel):
    """Stable result returned by ``slurm_submit``."""

    schema_version: Literal["clio-kit.slurm-submission.v1"] = (
        "clio-kit.slurm-submission.v1"
    )
    scheduler: Literal["slurm"] = "slurm"
    scheduler_native_id: str
    kind: Literal["job", "array"]
    state: Literal["submitted"] = "submitted"
    script_path: str
    array: str | None
    resources: SubmissionResources


class JobListFilter(ClosedModel):
    """Filters applied to a Slurm job-list query."""

    user: str | None
    state: str | None
    partition: str | None


class SlurmJobSummary(ClosedModel):
    """Small scheduler-native job summary suitable for agent selection."""

    scheduler_native_id: str
    state: str
    name: str
    user: str
    elapsed: str
    time_limit: str
    nodes: str
    cpus: str


class SlurmJobList(ClosedModel):
    """Stable result returned by ``slurm_list``."""

    schema_version: Literal["clio-kit.slurm-job-list.v1"] = "clio-kit.slurm-job-list.v1"
    scheduler: Literal["slurm"] = "slurm"
    filters: JobListFilter
    jobs: list[SlurmJobSummary]
    count: int = Field(ge=0)
    limit: int = Field(ge=1, le=1_000)
    truncated: bool


class SlurmProperty(ClosedModel):
    """One scheduler property from ``scontrol`` or ``sacct``."""

    name: str
    value: str


class SlurmOutput(ClosedModel):
    """A bounded stdout or stderr result for a Slurm job."""

    stream: Literal["stdout", "stderr"]
    path: str
    content: str
    truncated: bool


class SlurmJobDescription(ClosedModel):
    """Unified status, detail, and optional output view for one Slurm job."""

    schema_version: Literal["clio-kit.slurm-job.v1"] = "clio-kit.slurm-job.v1"
    scheduler: Literal["slurm"] = "slurm"
    scheduler_native_id: str
    state: str
    terminal: bool
    reason: str | None
    properties: list[SlurmProperty]
    outputs: list[SlurmOutput]
    diagnostics: list[str]


class SlurmPartition(ClosedModel):
    """Normalized Slurm partition summary."""

    name: str
    availability: str
    time_limit: str
    nodes: str
    state: str
    node_list: str


class SlurmQueueJob(ClosedModel):
    """Normalized job record included in a queue snapshot."""

    scheduler_native_id: str
    state: str
    name: str
    user: str
    partition: str
    elapsed: str
    time_limit: str
    nodes: str
    cpus: str
    priority: str


class SlurmStateCount(ClosedModel):
    """Count of queue jobs in one native Slurm state."""

    state: str
    count: int = Field(ge=0)


class SlurmNode(ClosedModel):
    """Normalized Slurm node summary."""

    name: str
    state: str
    cpus: str
    memory: str
    features: str
    gres: str


class SlurmClusterSnapshot(ClosedModel):
    """Unified partition, queue, and optional node snapshot."""

    schema_version: Literal["clio-kit.slurm-cluster.v1"] = "clio-kit.slurm-cluster.v1"
    scheduler: Literal["slurm"] = "slurm"
    cluster_name: str
    version: str | None
    partition_filter: str | None
    partitions: list[SlurmPartition]
    partition_limit: int = Field(ge=1)
    partitions_truncated: bool
    queue: list[SlurmQueueJob]
    queue_count: int = Field(ge=0)
    queue_limit: int = Field(ge=1, le=1_000)
    queue_truncated: bool
    state_counts: list[SlurmStateCount]
    state_counts_complete: bool
    nodes_included: bool
    nodes: list[SlurmNode]
    node_limit: int = Field(ge=1, le=1_000)
    nodes_truncated: bool


class SlurmCancellation(ClosedModel):
    """Stable acknowledgement returned after Slurm accepts cancellation."""

    schema_version: Literal["clio-kit.slurm-cancellation.v1"] = (
        "clio-kit.slurm-cancellation.v1"
    )
    scheduler: Literal["slurm"] = "slurm"
    scheduler_native_id: str
    result: Literal["cancellation_requested"] = "cancellation_requested"
    confirmation_matched: Literal[True] = True
    reason: str | None


_TERMINAL_STATES = {
    "BOOT_FAIL",
    "CANCELLED",
    "COMPLETED",
    "DEADLINE",
    "FAILED",
    "NODE_FAIL",
    "OUT_OF_MEMORY",
    "PREEMPTED",
    "REVOKED",
    "TIMEOUT",
}


def validate_native_job_id(job_id: str) -> str:
    """Validate and return one scheduler-native Slurm job identifier."""
    normalized = job_id.strip()
    if not _NATIVE_JOB_ID.fullmatch(normalized):
        raise ToolError(
            "job_id must be a scheduler-native Slurm ID such as 12345, "
            "12345_7, 12345+1, or 12345.batch"
        )
    return normalized


def validate_array_spec(array: str | None) -> str | None:
    """Validate a Slurm array specification before writing it to a script."""
    if array is None:
        return None
    normalized = array.strip()
    if len(normalized) > 256 or not _ARRAY_SPEC.fullmatch(normalized):
        raise ToolError(
            "array must be a Slurm task expression such as 0-31, 1-100:2, or 0-99%8"
        )
    return normalized


def _validated_resource_token(value: str | None, field: str) -> str | None:
    if value is None:
        return None
    normalized = value.strip()
    if not normalized or len(normalized) > 128 or not _SAFE_TOKEN.fullmatch(normalized):
        raise ToolError(f"{field} contains unsupported characters")
    return normalized


def _validated_memory(value: str) -> str:
    normalized = value.strip()
    if not _MEMORY.fullmatch(normalized):
        raise ToolError("memory must be a positive Slurm size such as 4096M or 16G")
    return normalized


def _validated_walltime(value: str) -> str:
    normalized = value.strip()
    if not _WALLTIME.fullmatch(normalized):
        raise ToolError("time_limit must use Slurm [days-]hours:minutes:seconds syntax")
    return normalized


def _raise_backend_error(result: dict[str, Any], operation: str) -> None:
    error = result.get("error")
    if error:
        raise ToolError(f"Slurm {operation} failed: {error}")


def submit(
    script_path: str,
    *,
    cores: int = 1,
    memory: str = "1G",
    time_limit: str = "01:00:00",
    job_name: str | None = None,
    partition: str | None = None,
    array: str | None = None,
) -> SlurmSubmission:
    """Submit a single job or array through one stable agent-facing operation."""
    if cores < 1:
        raise ToolError("cores must be positive")
    if cores > 1_048_576:
        raise ToolError("cores exceeds the contract maximum of 1048576")
    normalized_script = str(Path(script_path).expanduser())
    normalized_memory = _validated_memory(memory)
    normalized_time = _validated_walltime(time_limit)
    normalized_name = _validated_resource_token(job_name, "job_name")
    normalized_partition = _validated_resource_token(partition, "partition")
    normalized_array = validate_array_spec(array)
    if normalized_array is None:
        result = submit_slurm_job(
            normalized_script,
            cores,
            normalized_memory,
            normalized_time,
            normalized_name,
            normalized_partition,
        )
        native_id = result.get("job_id")
        kind: Literal["job", "array"] = "job"
    else:
        result = submit_array_job(
            normalized_script,
            normalized_array,
            cores,
            normalized_memory,
            normalized_time,
            normalized_name,
            normalized_partition,
        )
        _raise_backend_error(result, "array submission")
        native_id = result.get("array_job_id") or result.get("job_id")
        kind = "array"
    _raise_backend_error(result, "submission")
    if not isinstance(native_id, (str, int)):
        raise ToolError("Slurm submission did not return a scheduler-native job ID")
    normalized_id = validate_native_job_id(str(native_id))
    return SlurmSubmission(
        scheduler_native_id=normalized_id,
        kind=kind,
        script_path=normalized_script,
        array=normalized_array,
        resources=SubmissionResources(
            cores=cores,
            memory=normalized_memory,
            time_limit=normalized_time,
            partition=normalized_partition,
            job_name=normalized_name,
        ),
    )


def list_jobs(
    *,
    user: str | None = None,
    state: str | None = None,
    partition: str | None = None,
    limit: int = 100,
) -> SlurmJobList:
    """List jobs through a bounded normalized result rather than raw CLI output."""
    normalized_user = _validated_resource_token(user, "user")
    normalized_state = _validated_resource_token(state, "state")
    normalized_partition = _validated_resource_token(partition, "partition")
    if not 1 <= limit <= 1_000:
        raise ToolError("limit must be between 1 and 1000")
    result = list_slurm_jobs(
        normalized_user,
        normalized_state,
        normalized_partition,
        max_records=limit,
    )
    _raise_backend_error(result, "job listing")
    raw_jobs = result.get("jobs")
    if not isinstance(raw_jobs, list):
        raise ToolError("Slurm job listing returned an invalid jobs document")
    jobs: list[SlurmJobSummary] = []
    for raw in raw_jobs[:limit]:
        if not isinstance(raw, dict):
            raise ToolError("Slurm job listing contained a non-object job record")
        jobs.append(
            SlurmJobSummary(
                scheduler_native_id=validate_native_job_id(str(raw.get("job_id", ""))),
                state=str(raw.get("state", "UNKNOWN")),
                name=str(raw.get("name", "")),
                user=str(raw.get("user", "")),
                elapsed=str(raw.get("time", "")),
                time_limit=str(raw.get("time_limit", "")),
                nodes=str(raw.get("nodes", "")),
                cpus=str(raw.get("cpus", "")),
            )
        )
    return SlurmJobList(
        filters=JobListFilter(
            user=normalized_user,
            state=normalized_state,
            partition=normalized_partition,
        ),
        jobs=jobs,
        count=len(jobs),
        limit=limit,
        truncated=bool(result.get("truncated")) or len(raw_jobs) > limit,
    )


def describe_job(
    job_id: str,
    *,
    output: Literal["none", "stdout", "stderr", "both"] = "none",
    max_output_chars: int = 20_000,
) -> SlurmJobDescription:
    """Describe one job using status, properties, and optional bounded output."""
    native_id = validate_native_job_id(job_id)
    if not 1 <= max_output_chars <= 1_000_000:
        raise ToolError("max_output_chars must be between 1 and 1000000")

    status_result = get_job_status(native_id)
    _raise_backend_error(status_result, "job status")
    state = str(status_result.get("status", "UNKNOWN")).upper()
    if state == "ERROR":
        raise ToolError(
            f"Slurm job status failed: {status_result.get('reason', 'unknown error')}"
        )

    diagnostics: list[str] = []
    properties: list[SlurmProperty] = []
    authoritative_detail_state: str | None = None
    details_result = get_job_details(native_id)
    details = details_result.get("details")
    if isinstance(details, dict):
        properties = [
            SlurmProperty(name=str(name), value=str(value))
            for name, value in sorted(details.items(), key=lambda item: str(item[0]))
        ]
        detailed_state = details.get("jobstate") or details.get("state")
        if detailed_state:
            authoritative_detail_state = str(detailed_state).upper()
            state = authoritative_detail_state
    elif details_result.get("error"):
        diagnostics.append(f"details unavailable: {details_result['error']}")

    status_reason = str(status_result.get("reason", ""))
    if (
        state == "COMPLETED"
        and status_reason.startswith("Job not found")
        and authoritative_detail_state is None
    ):
        state = "UNKNOWN"
        diagnostics.append(
            "lifecycle unavailable: job is absent from the live queue and no "
            "accounting record was found"
        )

    streams: tuple[Literal["stdout", "stderr"], ...]
    if output == "both":
        streams = ("stdout", "stderr")
    elif output == "none":
        streams = ()
    else:
        streams = (output,)
    outputs: list[SlurmOutput] = []
    for stream in streams:
        output_result = get_job_output(native_id, stream, max_chars=max_output_chars)
        content = output_result.get("content")
        path = output_result.get("file_path")
        if isinstance(content, str) and isinstance(path, str):
            outputs.append(
                SlurmOutput(
                    stream=stream,
                    path=path,
                    content=content[-max_output_chars:],
                    truncated=bool(output_result.get("truncated"))
                    or len(content) > max_output_chars,
                )
            )
        elif output_result.get("error"):
            diagnostics.append(f"{stream} unavailable: {output_result['error']}")

    reason = status_result.get("reason")
    normalized_state = state.split("+", maxsplit=1)[0].split(maxsplit=1)[0]
    return SlurmJobDescription(
        scheduler_native_id=native_id,
        state=state,
        terminal=normalized_state in _TERMINAL_STATES,
        reason=str(reason) if reason is not None else None,
        properties=properties,
        outputs=outputs,
        diagnostics=diagnostics,
    )


def cluster_snapshot(
    *,
    partition: str | None = None,
    include_nodes: bool = False,
    queue_limit: int = 100,
    node_limit: int = 100,
) -> SlurmClusterSnapshot:
    """Return one coherent cluster, partition, queue, and optional node snapshot."""
    normalized_partition = _validated_resource_token(partition, "partition")
    if not 1 <= queue_limit <= 1_000:
        raise ToolError("queue_limit must be between 1 and 1000")
    if not 1 <= node_limit <= 1_000:
        raise ToolError("node_limit must be between 1 and 1000")
    cluster_result = get_slurm_info(max_records=256)
    _raise_backend_error(cluster_result, "cluster query")
    queue_result = get_queue_info(normalized_partition, max_records=queue_limit)
    _raise_backend_error(queue_result, "queue query")
    node_result: dict[str, Any] = {"nodes": []}
    if include_nodes:
        node_result = get_node_info(max_records=node_limit)
        _raise_backend_error(node_result, "node query")

    raw_partitions = _object_list(cluster_result, "partitions")
    eligible_partitions = [
        raw
        for raw in raw_partitions
        if normalized_partition is None
        or str(raw.get("partition", "")) == normalized_partition
    ]
    raw_queue = _object_list(queue_result, "jobs")
    raw_nodes = _object_list(node_result, "nodes")
    partitions = [
        SlurmPartition(
            name=str(raw.get("partition", "")),
            availability=str(raw.get("avail_idle", "")),
            time_limit=str(raw.get("timelimit", "")),
            nodes=str(raw.get("nodes", "")),
            state=str(raw.get("state", "")),
            node_list=str(raw.get("nodelist", "")),
        )
        for raw in eligible_partitions[:256]
    ]
    queue = [
        SlurmQueueJob(
            scheduler_native_id=validate_native_job_id(str(raw.get("job_id", ""))),
            state=str(raw.get("state", "UNKNOWN")),
            name=str(raw.get("name", "")),
            user=str(raw.get("user", "")),
            partition=str(raw.get("partition", "")),
            elapsed=str(raw.get("time", "")),
            time_limit=str(raw.get("time_limit", "")),
            nodes=str(raw.get("nodes", "")),
            cpus=str(raw.get("cpus", "")),
            priority=str(raw.get("priority", "")),
        )
        for raw in raw_queue[:queue_limit]
    ]
    raw_counts = queue_result.get("state_summary", {})
    if not isinstance(raw_counts, dict):
        raise ToolError("Slurm queue query returned an invalid state summary")
    state_counts = [
        SlurmStateCount(state=str(state), count=int(count))
        for state, count in sorted(raw_counts.items(), key=lambda item: str(item[0]))
    ]
    nodes = [
        SlurmNode(
            name=str(raw.get("node_name", "")),
            state=str(raw.get("state", "")),
            cpus=str(raw.get("cpus", "")),
            memory=str(raw.get("memory", "")),
            features=str(raw.get("features", "")),
            gres=str(raw.get("gres", "")),
        )
        for raw in raw_nodes[:node_limit]
    ]
    version = cluster_result.get("version")
    partitions_truncated = bool(cluster_result.get("truncated")) or len(
        eligible_partitions
    ) > len(partitions)
    queue_truncated = bool(queue_result.get("truncated")) or len(raw_queue) > len(queue)
    nodes_truncated = bool(node_result.get("truncated")) or len(raw_nodes) > len(nodes)
    return SlurmClusterSnapshot(
        cluster_name=str(cluster_result.get("cluster_name", "")),
        version=str(version) if version is not None else None,
        partition_filter=normalized_partition,
        partitions=partitions,
        partition_limit=256,
        partitions_truncated=partitions_truncated,
        queue=queue,
        queue_count=len(queue),
        queue_limit=queue_limit,
        queue_truncated=queue_truncated,
        state_counts=state_counts,
        state_counts_complete=not queue_truncated,
        nodes_included=include_nodes,
        nodes=nodes,
        node_limit=node_limit,
        nodes_truncated=nodes_truncated,
    )


def request_cancellation(
    job_id: str, *, confirm_job_id: str, reason: str | None = None
) -> SlurmCancellation:
    """Request cancellation only after exact native-ID confirmation."""
    native_id = validate_native_job_id(job_id)
    confirmation = validate_native_job_id(confirm_job_id)
    if confirmation != native_id:
        raise ToolError(
            "destructive cancellation rejected: confirm_job_id must exactly match job_id"
        )
    normalized_reason = reason.strip() if reason is not None else None
    if normalized_reason == "":
        normalized_reason = None
    if normalized_reason is not None and len(normalized_reason) > 500:
        raise ToolError("reason must contain at most 500 characters")
    result = cancel_slurm_job(native_id)
    if result.get("status") != "cancelled":
        message = result.get("message") or result.get("error") or "unknown error"
        raise ToolError(f"Slurm cancellation failed: {message}")
    return SlurmCancellation(
        scheduler_native_id=native_id,
        reason=normalized_reason,
    )


def _object_list(document: dict[str, Any], key: str) -> list[dict[str, Any]]:
    value = document.get(key)
    if not isinstance(value, list):
        raise ToolError(f"Slurm response field {key!r} was not a list")
    if not all(isinstance(item, dict) for item in value):
        raise ToolError(f"Slurm response field {key!r} contained a non-object")
    return value


def contract_schemas() -> tuple[type[ClosedModel], ...]:
    """Return every public result model for contract verification tooling."""
    return (
        SlurmSubmission,
        SlurmJobList,
        SlurmJobDescription,
        SlurmClusterSnapshot,
        SlurmCancellation,
    )
