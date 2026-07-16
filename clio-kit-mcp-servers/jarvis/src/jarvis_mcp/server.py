import argparse
import base64
import binascii
import hashlib
import importlib
import json
import os
import re
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Annotated, Any, Literal, Optional, cast

from typing_extensions import NotRequired, TypedDict

from dotenv import load_dotenv
from fastmcp import Context, FastMCP
from fastmcp.exceptions import ToolError
from fastmcp.prompts import Message
from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    ValidationError,
    field_validator,
    model_validator,
)

from .capabilities.jarvis_handler import (
    create_pipeline,
    load_pipeline,
    export_pipeline,
    append_pkg,
    configure_pkg,
    unlink_pkg,
    remove_pkg,
    run_pipeline,
    get_execution,
    destroy_pipeline,
    get_pkg_config,
    update_pipeline,
    build_pipeline_env,
)


class _CurrentJarvisManager:
    """Compatibility adapter over the current JARVIS-CD Jarvis singleton."""

    @classmethod
    def get_instance(cls) -> "_CurrentJarvisManager":
        jarvis_module = importlib.import_module("jarvis_cd.core.config")
        return cls(jarvis_module.Jarvis.get_instance())

    def __init__(self, jarvis: Any) -> None:
        self.jarvis = jarvis

    def create(
        self, config_dir: str, private_dir: str, shared_dir: Optional[str] = None
    ) -> "_CurrentJarvisManager":
        self.jarvis.initialize(
            config_dir=config_dir,
            private_dir=private_dir,
            shared_dir=shared_dir or private_dir,
        )
        return self

    def load(self) -> "_CurrentJarvisManager":
        _ = self.jarvis.config
        return self

    def save(self) -> "_CurrentJarvisManager":
        if getattr(self.jarvis, "_config", None) is not None:
            self.jarvis.save_config(self.jarvis.config)
        if getattr(self.jarvis, "_repos", None) is not None:
            self.jarvis.save_repos(self.jarvis.repos)
        return self

    def set_hostfile(self, path: str) -> "_CurrentJarvisManager":
        self.jarvis.set_hostfile(path)
        return self

    def bootstrap_from(self, machine: str) -> "_CurrentJarvisManager":
        raise NotImplementedError(
            f"bootstrap templates are not exposed by current JARVIS-CD: {machine}"
        )

    def bootstrap_list(self) -> list[str]:
        return []

    def reset(self) -> "_CurrentJarvisManager":
        raise NotImplementedError(
            "reset is not exposed through the compatibility adapter"
        )

    def list_pipelines(self) -> list[str]:
        pipelines_dir = self.jarvis.get_pipelines_dir()
        if not pipelines_dir.exists():
            return []
        return sorted(path.name for path in pipelines_dir.iterdir() if path.is_dir())

    def cd(self, pipeline_id: str) -> "_CurrentJarvisManager":
        self.jarvis.set_current_pipeline(pipeline_id)
        return self

    def list_repos(self) -> list[str]:
        return list(self.jarvis.repos.get("repos", []))

    def add_repo(self, path: str, force: bool = False) -> "_CurrentJarvisManager":
        self.jarvis.add_repo(path, force=force)
        return self

    def remove_repo(self, repo_name: str) -> "_CurrentJarvisManager":
        repo_paths = list(self.jarvis.repos.get("repos", []))
        matches = [
            repo_path
            for repo_path in repo_paths
            if repo_path == repo_name or Path(repo_path).name == repo_name
        ]
        if not matches:
            self.jarvis.remove_repo(repo_name)
        for repo_path in matches:
            self.jarvis.remove_repo(repo_path)
        return self

    def promote_repo(self, repo_name: str) -> "_CurrentJarvisManager":
        repos = self.jarvis.repos.copy()
        repo_paths = list(repos.get("repos", []))
        matches = [
            repo_path
            for repo_path in repo_paths
            if repo_path == repo_name or Path(repo_path).name == repo_name
        ]
        if not matches:
            raise ValueError(f"repository not found: {repo_name}")
        for repo_path in reversed(matches):
            repo_paths.remove(repo_path)
            repo_paths.insert(0, repo_path)
        repos["repos"] = repo_paths
        self.jarvis.save_repos(repos)
        return self

    def get_repo(self, repo_name: str) -> dict[str, Any] | None:
        for index, repo_path in enumerate(self.jarvis.repos.get("repos", []), start=1):
            if repo_path == repo_name or Path(repo_path).name == repo_name:
                return {
                    "index": index,
                    "name": Path(repo_path).name,
                    "path": repo_path,
                    "exists": Path(repo_path).exists(),
                }
        return None

    def construct_pkg(self, pkg_type: str) -> Any:
        raise NotImplementedError(
            f"package construction is not exposed by current JARVIS-CD: {pkg_type}"
        )

    def resource_graph_show(self) -> dict[str, Any]:
        return self.jarvis.resource_graph

    def resource_graph_build(self, net_sleep: float) -> dict[str, Any]:
        _ = net_sleep
        raise NotImplementedError(
            "resource graph build is not exposed through the compatibility adapter"
        )

    def resource_graph_modify(self, net_sleep: float) -> dict[str, Any]:
        _ = net_sleep
        raise NotImplementedError(
            "resource graph modify is not exposed through the compatibility adapter"
        )


def _load_jarvis_manager_class() -> Any:
    try:
        module = importlib.import_module("jarvis_cd.basic.jarvis_manager")
        return module.JarvisManager
    except ModuleNotFoundError:
        return _CurrentJarvisManager


# Load environment variables from .env file
load_dotenv()

# Initialize FastMCP server instance
mcp: FastMCP = FastMCP(
    "jarvis",
    instructions=(
        "Manages JARVIS data pipelines for scientific computing. "
        "Create, configure, monitor, and manage data processing pipelines."
    ),
    list_page_size=10,
)
MCP_METADATA_PROFILE = "user"

PACKAGE_SEARCH_SCHEMA = "jarvis.package-search.v1"
PACKAGE_SEARCH_CURSOR_SCHEMA = "clio-kit.jarvis-package-search-cursor.v1"
PACKAGE_SEARCH_DEFAULT_PAGE_SIZE = 10
PACKAGE_SEARCH_MAX_PAGE_SIZE = 25
PACKAGE_SEARCH_MAX_RESULT_BYTES = 64 * 1024
PACKAGE_SEARCH_MAX_CURSOR_LENGTH = 1024
PACKAGE_SEARCH_MAX_DESCRIPTION_BYTES = 4096
_PACKAGE_SEARCH_CURSOR_TEXT = re.compile(r"^[A-Za-z0-9_-]+$")
_PACKAGE_SEARCH_SHA256 = re.compile(r"^[0-9a-f]{64}$")


@dataclass(frozen=True)
class _PackageInventoryEntry:
    """Lightweight package identity discovered from one registered repository."""

    name: str
    short_name: str
    repository: str
    description: str | None
    repo: Path
    package_file: Path

    def summary(self) -> dict[str, Any]:
        """Return the bounded search representation without package settings."""

        summary: dict[str, Any] = {
            "name": self.name,
            "short_name": self.short_name,
            "repository": self.repository,
            "description": _bounded_package_search_description(self.description),
        }
        return {key: value for key, value in summary.items() if value is not None}


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


class JarvisProgressEventDocument(BaseModel):
    """One closed, JARVIS-owned package progress observation."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    schema_version: Literal["jarvis.progress.v1"]
    package_name: str = Field(min_length=1, max_length=256)
    package_id: str = Field(min_length=1, max_length=256)
    execution_id: str = Field(min_length=1, max_length=256)
    label: str = Field(min_length=1, max_length=256)
    state: Literal[
        "pending",
        "starting",
        "running",
        "ready",
        "completed",
        "failed",
        "canceled",
    ]
    current: float | None = Field(default=None, ge=0, allow_inf_nan=False)
    total: float | None = Field(default=None, gt=0, allow_inf_nan=False)
    unit: str | None = Field(default=None, min_length=1, max_length=256)
    message: str | None = Field(default=None, min_length=1, max_length=4096)
    sequence: int = Field(ge=0)
    observed_at_epoch: float = Field(ge=0, allow_inf_nan=False)
    determinate: bool
    metadata: dict[str, Any]

    @field_validator(
        "package_name",
        "package_id",
        "execution_id",
        "label",
        "unit",
        "message",
        mode="after",
    )
    @classmethod
    def validate_nonblank_text(cls, value: str | None) -> str | None:
        """Reject whitespace-only text while preserving producer spelling."""
        if value is not None and not value.strip():
            raise ValueError("progress text fields must not be blank")
        return value

    @model_validator(mode="after")
    def validate_quantitative_progress(self) -> "JarvisProgressEventDocument":
        """Keep the public determination flag consistent with numeric fields."""
        if self.total is not None and self.current is None:
            raise ValueError("progress total requires current")
        if (
            self.current is not None
            and self.total is not None
            and self.current > self.total
        ):
            raise ValueError("progress current cannot exceed total")
        expected = self.current is not None and self.total is not None
        if self.determinate is not expected:
            raise ValueError(
                "progress determinate must match the presence of current and total"
            )
        return self


class JarvisPackageProgressDocument(BaseModel):
    """Latest stable progress observation for one package alias."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    package_id: str = Field(min_length=1, max_length=256)
    package_name: str = Field(min_length=1, max_length=256)
    event_count: int = Field(ge=0)
    latest: JarvisProgressEventDocument | None

    @model_validator(mode="after")
    def validate_latest_event(self) -> "JarvisPackageProgressDocument":
        """Cross-check the package identity and event-count sentinel."""
        if self.latest is None:
            if self.event_count != 0:
                raise ValueError("progress event count requires a latest event")
            return self
        if self.event_count == 0:
            raise ValueError("latest progress event requires a positive event count")
        if (
            self.latest.package_id != self.package_id
            or self.latest.package_name != self.package_name
        ):
            raise ValueError("latest progress event package identity did not match")
        return self


class JarvisProgressSnapshotDocument(BaseModel):
    """Stable aggregate returned by JARVIS-CD's execution progress API."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    schema_version: Literal["jarvis.execution.progress.v1"]
    execution_id: str = Field(min_length=1, max_length=256)
    pipeline_id: str = Field(min_length=1, max_length=256)
    execution_state: Literal[
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
    terminal: bool
    packages: list[JarvisPackageProgressDocument] = Field(max_length=4096)

    @model_validator(mode="after")
    def validate_package_identities(self) -> "JarvisProgressSnapshotDocument":
        """Bind every package event to this execution and reject aliases twice."""
        package_ids: set[str] = set()
        for package in self.packages:
            if package.package_id in package_ids:
                raise ValueError("progress package aliases must be unique")
            package_ids.add(package.package_id)
            if (
                package.latest is not None
                and package.latest.execution_id != self.execution_id
            ):
                raise ValueError("progress event execution identity did not match")
        return self


class JarvisArtifactLocationDocument(TypedDict):
    """Transport-neutral location in a JARVIS artifact manifest."""

    kind: Literal["execution_path", "cluster_path", "external_uri"]
    value: str


class JarvisArtifactDocument(TypedDict):
    """Current JARVIS-owned lifecycle observation for one generated artifact."""

    schema_version: Literal["jarvis.artifact.v1"]
    package_name: str
    package_id: str
    execution_id: str
    artifact_id: str
    logical_name: str
    kind: str
    role: Literal[
        "intermediate",
        "output",
        "log",
        "checkpoint",
        "provenance",
        "validation",
    ]
    structure: Literal["file", "directory", "collection", "stream"]
    ownership: Literal["execution", "external", "shared"]
    state: Literal["producing", "available", "finalized", "incomplete", "failed"]
    revision: int
    sequence: int
    observed_at_epoch: float
    metadata: dict[str, Any]
    location: NotRequired[JarvisArtifactLocationDocument]
    media_type: NotRequired[str]
    format: NotRequired[str]
    size_bytes: NotRequired[int]
    checksum: NotRequired[str]
    message: NotRequired[str]


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


class JarvisExecutionArtifactPageDocument(BaseModel):
    """Bounded artifact page nested in a unified execution query."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    producer_schema_version: Literal["jarvis.execution.artifacts.v1"]
    pipeline_id: str
    execution_id: str
    execution_state: Literal[
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
    terminal: bool
    artifacts: list[JarvisArtifactDocument]
    matching_artifact_count: int
    returned_artifact_count: int
    next_cursor: str | None


class JarvisDatasetMemberDocument(BaseModel):
    """One ordered member in a JARVIS service dataset descriptor."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    index: int = Field(ge=0)
    location: str = Field(min_length=1, max_length=4096)
    timestep: float | None = Field(default=None, allow_inf_nan=False)

    @field_validator("location")
    @classmethod
    def validate_cluster_location(cls, value: str) -> str:
        """Require the normalized absolute POSIX path emitted by JARVIS."""
        path = PurePosixPath(value)
        if (
            "\\" in value
            or not path.is_absolute()
            or path.as_posix() != value
            or ".." in path.parts
        ):
            raise ValueError(
                "dataset member location must be a normalized absolute path"
            )
        return value


class JarvisDatasetArrayDocument(BaseModel):
    """One intrinsic array exposed by a JARVIS-owned service."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    name: str = Field(min_length=1, max_length=512)
    association: Literal["point", "cell", "field"]
    components: int = Field(ge=1, le=64)
    units: str | None = Field(default=None, min_length=1, max_length=256)


class JarvisDatasetFingerprintDocument(BaseModel):
    """Canonical identity digest for one bounded dataset descriptor."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    algorithm: Literal["sha256"]
    digest: str = Field(pattern=r"^[0-9a-f]{64}$")


class JarvisDatasetSourceArtifactDocument(BaseModel):
    """Optional content identity of a JARVIS-generated source artifact."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    artifact_id: str = Field(pattern=r"^art_[A-Za-z0-9_-]{22,86}$")
    sha256: str = Field(pattern=r"^[0-9a-f]{64}$")


class JarvisDatasetDescriptorDocument(BaseModel):
    """Intrinsic, recipe-free dataset identity owned by JARVIS."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    schema_version: Literal["jarvis.dataset-descriptor.v1"]
    dataset_id: str = Field(min_length=1, max_length=256)
    kind: str = Field(min_length=1, max_length=256)
    format: str = Field(min_length=1, max_length=256)
    members: list[JarvisDatasetMemberDocument] = Field(min_length=1, max_length=512)
    arrays: list[JarvisDatasetArrayDocument] = Field(max_length=256)
    bounds: list[float] | None = Field(default=None, min_length=6, max_length=6)
    fingerprint: JarvisDatasetFingerprintDocument
    source_artifact: JarvisDatasetSourceArtifactDocument | None

    @model_validator(mode="after")
    def validate_intrinsic_identity(self) -> "JarvisDatasetDescriptorDocument":
        """Reject ambiguous ordering and verify the canonical fingerprint."""
        if [member.index for member in self.members] != list(range(len(self.members))):
            raise ValueError("dataset member indexes must be contiguous and ordered")
        locations = [member.location for member in self.members]
        if len(locations) != len(set(locations)):
            raise ValueError("dataset member locations must be unique")
        array_keys = [(array.association, array.name) for array in self.arrays]
        if len(array_keys) != len(set(array_keys)):
            raise ValueError("dataset array identities must be unique")
        if self.bounds is not None:
            for lower, upper in zip(self.bounds[::2], self.bounds[1::2]):
                if lower > upper:
                    raise ValueError("dataset bounds must be ordered")
        members: list[dict[str, Any]] = []
        for member in self.members:
            value: dict[str, Any] = {
                "index": member.index,
                "location": member.location,
            }
            if member.timestep is not None:
                value["timestep"] = member.timestep
            members.append(value)
        arrays: list[dict[str, Any]] = []
        for array in self.arrays:
            value = {
                "name": array.name,
                "association": array.association,
                "components": array.components,
            }
            if array.units is not None:
                value["units"] = array.units
            arrays.append(value)
        canonical = {
            "schema_version": self.schema_version,
            "dataset_id": self.dataset_id,
            "kind": self.kind,
            "format": self.format,
            "members": members,
            "arrays": arrays,
            "bounds": list(self.bounds) if self.bounds is not None else None,
            "source_artifact": (
                self.source_artifact.model_dump(mode="json")
                if self.source_artifact is not None
                else None
            ),
        }
        digest = hashlib.sha256(
            json.dumps(
                canonical,
                allow_nan=False,
                ensure_ascii=False,
                separators=(",", ":"),
                sort_keys=True,
            ).encode("utf-8")
        ).hexdigest()
        if digest != self.fingerprint.digest:
            raise ValueError("dataset fingerprint did not match its descriptor")
        return self


class JarvisServiceRuntimeDocument(BaseModel):
    """Latest durable observation of one execution-owned service."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    schema_version: Literal["jarvis.service-runtime.v1"]
    execution_id: str = Field(min_length=1, max_length=256)
    package_name: str = Field(min_length=1, max_length=256)
    package_id: str = Field(min_length=1, max_length=256)
    service_instance_id: str = Field(min_length=1, max_length=256)
    revision: int = Field(ge=1)
    lifecycle: Literal["starting", "ready", "degraded", "stopping", "stopped", "failed"]
    host: str = Field(min_length=1, max_length=255)
    port: int = Field(ge=1, le=65535)
    protocol: Literal["http", "https"]
    health_path: str = Field(min_length=1, max_length=256)
    live_data_path: str = Field(min_length=1, max_length=256)
    events_path: str = Field(min_length=1, max_length=256)
    state_path: str = Field(min_length=1, max_length=256)
    command_path: str = Field(min_length=1, max_length=256)
    delivery_mode: Literal["push"]
    dataset_descriptor: JarvisDatasetDescriptorDocument
    message: str | None = Field(default=None, min_length=1, max_length=4096)
    observed_at_epoch: float = Field(ge=0, allow_inf_nan=False)

    @model_validator(mode="after")
    def validate_private_endpoint_metadata(self) -> "JarvisServiceRuntimeDocument":
        """Reject wildcard hosts and ambiguous or duplicated HTTP paths."""
        if self.host in {"0.0.0.0", "::", "*", "localhost"}:
            raise ValueError("service runtime host cannot be a wildcard or alias")
        paths = (
            self.health_path,
            self.live_data_path,
            self.events_path,
            self.state_path,
            self.command_path,
        )
        if len(set(paths)) != len(paths):
            raise ValueError("service runtime endpoint paths must be distinct")
        for value in paths:
            path = PurePosixPath(value)
            if (
                not value.startswith("/")
                or value.startswith("//")
                or path.as_posix() != value
                or ".." in path.parts
                or any(character in value for character in "?#\\")
            ):
                raise ValueError("service runtime endpoint path is invalid")
        return self


class JarvisServiceRuntimeSnapshotDocument(BaseModel):
    """Execution-bound current service runtimes returned by JARVIS."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    schema_version: Literal["jarvis.execution.service-runtimes.v1"]
    execution_id: str = Field(min_length=1, max_length=256)
    pipeline_id: str = Field(min_length=1, max_length=256)
    execution_state: Literal[
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
    terminal: bool
    service_runtimes: list[JarvisServiceRuntimeDocument] = Field(max_length=4096)

    @model_validator(mode="after")
    def validate_runtime_identities(self) -> "JarvisServiceRuntimeSnapshotDocument":
        """Bind every service to this execution and reject duplicate instances."""
        identities: set[str] = set()
        for runtime in self.service_runtimes:
            if runtime.execution_id != self.execution_id:
                raise ValueError("service runtime execution identity did not match")
            if runtime.service_instance_id in identities:
                raise ValueError("service runtime instance identities must be unique")
            identities.add(runtime.service_instance_id)
        return self


class JarvisExecutionResult(BaseModel):
    """Frozen top-level result envelope for a selectable execution query."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal["clio-kit.jarvis-execution.v2"]
    pipeline_id: str
    execution_id: str
    execution_handle: JarvisExecutionHandleDocument
    execution_record: JarvisExecutionRecordDocument
    runtime_metadata: dict[str, Any]
    progress: JarvisProgressSnapshotDocument | None
    artifact_page: JarvisExecutionArtifactPageDocument | None
    service_runtimes: JarvisServiceRuntimeSnapshotDocument | None


# Resolve the JARVIS manager lazily so MCP metadata discovery does not require a
# functional JARVIS-CD installation. Admin tools still fail clearly at call time
# if the installed JARVIS version lacks the needed manager API.
JarvisManager = _load_jarvis_manager_class()
manager: Any | None = None
_manager: Any | None = None


def get_manager() -> Any:
    """Return the process-local JARVIS manager singleton."""
    global _manager
    if manager is not None:
        return manager
    if _manager is None:
        _manager = JarvisManager.get_instance()
    return _manager


USER_TOOLS = {
    "jarvis_create_pipeline",
    "jarvis_describe",
    "jarvis_add_step",
    "jarvis_edit_step",
    "jarvis_run",
    "jarvis_get_execution",
}

ADMIN_TOOLS = {
    "update_pipeline",
    "build_pipeline_env",
    "create_pipeline",
    "load_pipeline",
    "export_pipeline",
    "get_pkg_config",
    "append_pkg",
    "configure_pkg",
    "unlink_pkg",
    "remove_pkg",
    "run_pipeline",
    "jm_list_pipelines",
    "jm_list_repos",
    "jm_get_repo",
    "jm_create_config",
    "jm_load_config",
    "jm_save_config",
    "jm_set_hostfile",
    "jm_bootstrap_from",
    "jm_bootstrap_list",
    "jm_reset",
    "jm_cd",
    "jm_add_repo",
    "jm_remove_repo",
    "jm_promote_repo",
    "jm_construct_pkg",
    "jm_graph_show",
    "jm_graph_build",
    "jm_graph_modify",
    "destroy_pipeline",
}


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


class ExecutionArtifactQuery(BaseModel):
    """Optional filters for one bounded page of execution artifacts."""

    model_config = ConfigDict(extra="forbid", strict=True)

    package_id: str | None = Field(
        default=None,
        description="Exact JARVIS package alias filter.",
        max_length=256,
    )
    role: (
        Literal[
            "intermediate",
            "output",
            "log",
            "checkpoint",
            "provenance",
            "validation",
        ]
        | None
    ) = None
    state: (
        Literal[
            "producing",
            "available",
            "finalized",
            "incomplete",
            "failed",
        ]
        | None
    ) = None
    artifact_id: str | None = Field(
        default=None,
        description="Exact opaque JARVIS artifact ID filter.",
        max_length=90,
    )
    page_size: int = Field(
        default=50,
        description="Maximum artifacts to return in this page.",
        ge=1,
        le=100,
    )
    cursor: str | None = Field(
        default=None,
        description="Opaque next-page cursor.",
        max_length=1024,
    )


# ─── RESOURCE ────────────────────────────────────────────────────────────────


@mcp.resource("jarvis://capabilities")
def jarvis_capabilities() -> dict:
    """JARVIS data pipeline capabilities."""
    return {
        "pipeline_types": ["streaming", "batch", "real-time"],
        "operations": ["create", "configure", "deploy", "monitor", "destroy"],
    }


# ─── PROMPT ──────────────────────────────────────────────────────────────────


@mcp.prompt()
def create_pipeline_workflow(name: str) -> list[Message]:
    """Guided workflow for creating and deploying a JARVIS pipeline."""
    return [
        Message(
            f"I need to create a new JARVIS pipeline called '{name}'. "
            "Help me configure it, set up the processing stages, deploy it, "
            "and verify it's running correctly."
        ),
    ]


# ─── PIPELINE TOOLS ─────────────────────────────────────────────────────────────


@mcp.tool(
    name="update_pipeline",
    description="Re-apply environment and configuration to every package in a pipeline.",
    annotations={
        "readOnlyHint": False,
        "destructiveHint": False,
        "idempotentHint": False,
    },
    tags={"jarvis", "pipeline"},
)
async def update_pipeline_tool(pipeline_id: str) -> dict:
    """Re-apply environment and configuration to every package in a Jarvis pipeline."""
    return await update_pipeline(pipeline_id)


@mcp.tool(
    name="build_pipeline_env",
    description="Rebuild a pipeline's env.yaml, capturing CMAKE_PREFIX_PATH and PATH.",
    annotations={
        "readOnlyHint": False,
        "destructiveHint": False,
        "idempotentHint": False,
    },
    tags={"jarvis", "pipeline"},
)
async def build_pipeline_env_tool(pipeline_id: str) -> dict:
    """Build the pipeline execution environment for a given pipeline."""
    return await build_pipeline_env(pipeline_id)


@mcp.tool(
    name="create_pipeline",
    description="Create a new Jarvis-CD pipeline environment.",
    annotations={
        "readOnlyHint": False,
        "destructiveHint": False,
        "idempotentHint": False,
    },
    tags={"jarvis", "pipeline"},
)
async def create_pipeline_tool(pipeline_id: str) -> dict:
    """Create a new pipeline environment for data-centric workflows."""
    return await create_pipeline(pipeline_id)


@mcp.tool(
    name="load_pipeline",
    description="Load an existing Jarvis-CD pipeline environment.",
    annotations={
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
    },
    tags={"jarvis", "pipeline"},
)
async def load_pipeline_tool(pipeline_id: Optional[str] = None) -> dict:
    """Load an existing pipeline environment by ID, or the current one if not specified."""
    return await load_pipeline(pipeline_id)


@mcp.tool(
    name="export_pipeline",
    description="Export a structured snapshot of a Jarvis-CD pipeline.",
    annotations={
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
    },
    tags={"jarvis", "pipeline"},
)
async def export_pipeline_tool(pipeline_id: str, include_yaml: bool = True) -> dict:
    """Export pipeline metadata, packages, configs, and optional source YAML."""
    return await export_pipeline(pipeline_id, include_yaml=include_yaml)


@mcp.tool(
    name="get_pkg_config",
    description="Retrieve the configuration of a specific package in a pipeline.",
    annotations={
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
    },
    tags={"jarvis", "pipeline"},
)
async def get_pkg_config_tool(pipeline_id: str, pkg_id: str) -> dict:
    """Retrieve the configuration of a specific package in a pipeline."""
    return await get_pkg_config(pipeline_id, pkg_id)


@mcp.tool(
    name="append_pkg",
    description="Append a package to a Jarvis-CD pipeline.",
    annotations={
        "readOnlyHint": False,
        "destructiveHint": False,
        "idempotentHint": False,
    },
    tags={"jarvis", "pipeline"},
)
async def append_pkg_tool(
    pipeline_id: str,
    pkg_type: str,
    pkg_id: Optional[str] = None,
    do_configure: bool = True,
    extra_args: Optional[dict] = None,
) -> dict:
    """Add a package to a pipeline for execution or analysis."""
    return await append_pkg(
        pipeline_id,
        pkg_type,
        pkg_id=pkg_id,
        do_configure=do_configure,
        **(extra_args or {}),
    )


@mcp.tool(
    name="configure_pkg",
    description="Configure a package in a Jarvis-CD pipeline.",
    annotations={
        "readOnlyHint": False,
        "destructiveHint": False,
        "idempotentHint": False,
    },
    tags={"jarvis", "pipeline"},
)
async def configure_pkg_tool(
    pipeline_id: str, pkg_id: str, extra_args: Optional[dict] = None
) -> dict:
    """Configure a package in a pipeline with new settings."""
    return await configure_pkg(pipeline_id, pkg_id, **(extra_args or {}))


@mcp.tool(
    name="unlink_pkg",
    description="Unlink a package from a pipeline (preserve files).",
    annotations={
        "readOnlyHint": False,
        "destructiveHint": False,
        "idempotentHint": False,
    },
    tags={"jarvis", "pipeline"},
)
async def unlink_pkg_tool(pipeline_id: str, pkg_id: str) -> dict:
    """Unlink a package from a pipeline without deleting its files."""
    return await unlink_pkg(pipeline_id, pkg_id)


@mcp.tool(
    name="remove_pkg",
    description=(
        "Delete a package through JARVIS-CD's destructive removal API. Fails "
        "explicitly when the installed JARVIS-CD only supports non-destructive unlinking."
    ),
    annotations={
        "readOnlyHint": False,
        "destructiveHint": True,
        "idempotentHint": True,
    },
    tags={"jarvis", "pipeline"},
)
async def remove_pkg_tool(pipeline_id: str, pkg_id: str) -> dict:
    """Delete a package only when JARVIS-CD provides destructive removal semantics."""
    return await remove_pkg(pipeline_id, pkg_id)


@mcp.tool(
    name="run_pipeline",
    description="Execute a Jarvis-CD pipeline end-to-end.",
    annotations={
        "readOnlyHint": False,
        "destructiveHint": False,
        "idempotentHint": False,
    },
    tags={"jarvis", "pipeline"},
)
async def run_pipeline_tool(pipeline_id: str) -> dict:
    """Execute the pipeline, running all configured steps."""
    return await run_pipeline(pipeline_id)


@mcp.tool(
    name="jarvis_create_pipeline",
    description=(
        "Create a JARVIS pipeline. Optionally pass execution intent such as "
        "local, cluster, or hostfile mode; backend details are resolved where "
        "the MCP server runs."
    ),
    annotations={
        "readOnlyHint": False,
        "destructiveHint": False,
        "idempotentHint": False,
    },
    tags={"jarvis", "pipeline", "user"},
)
async def jarvis_create_pipeline_tool(
    pipeline_id: str, execution: ExecutionIntent | None = None
) -> dict:
    """Create a new JARVIS pipeline, optionally seeding execution intent."""
    initial_config = (
        _execution_intent_to_pipeline_config(execution)
        if execution is not None
        else None
    )
    return await create_pipeline(pipeline_id, initial_config=initial_config)


@mcp.tool(
    name="jarvis_describe",
    description=(
        "Describe JARVIS packages, one package, a pipeline, or one pipeline step. "
        "For a named application, first use target='package' with its unique short name "
        "or fully qualified package name. Use target='package_search' for bounded "
        "discovery, then describe the selected canonical name. target='packages' is an "
        "exhaustive legacy inventory with every package's settings and can be large; "
        "use it only when the complete installed catalog is explicitly required."
    ),
    annotations={
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
    },
    tags={"jarvis", "pipeline", "user"},
)
async def jarvis_describe_tool(
    target: Annotated[
        Literal["packages", "package_search", "package", "pipeline", "step"],
        Field(
            description=(
                "Object to describe. Prefer package for a named application and "
                "package_search for discovery; packages is exhaustive and unbounded."
            )
        ),
    ],
    pipeline_id: Annotated[
        Optional[str],
        Field(
            min_length=1,
            max_length=256,
            description="Pipeline identifier for target='pipeline' or target='step'.",
        ),
    ] = None,
    step_id: Annotated[
        Optional[str],
        Field(
            min_length=1,
            max_length=256,
            description="Pipeline step identifier for target='step'.",
        ),
    ] = None,
    package_name: Annotated[
        Optional[str],
        Field(
            min_length=1,
            max_length=512,
            description=(
                "Case-insensitive unique short name or fully qualified package name for "
                "target='package', for example paraview or builtin.paraview. Ambiguous "
                "short names fail with canonical candidates."
            ),
        ),
    ] = None,
    query: Annotated[
        Optional[str],
        Field(
            min_length=1,
            max_length=256,
            description=(
                "Natural-language or package-name query required for "
                "target='package_search'."
            ),
        ),
    ] = None,
    page_size: Annotated[
        int,
        Field(
            ge=1,
            le=PACKAGE_SEARCH_MAX_PAGE_SIZE,
            description=(
                "Maximum summary matches returned by target='package_search'; "
                f"bounded to {PACKAGE_SEARCH_MAX_PAGE_SIZE}."
            ),
        ),
    ] = PACKAGE_SEARCH_DEFAULT_PAGE_SIZE,
    cursor: Annotated[
        Optional[str],
        Field(
            min_length=1,
            max_length=PACKAGE_SEARCH_MAX_CURSOR_LENGTH,
            description=(
                "Opaque next-page cursor returned by an earlier package_search with "
                "the identical query."
            ),
        ),
    ] = None,
    include_yaml: Annotated[
        bool,
        Field(
            description=(
                "Include stored pipeline YAML only for target='pipeline'; ignored for "
                "package and package discovery targets."
            )
        ),
    ] = True,
) -> dict[str, Any]:
    """Describe user-level JARVIS objects without exposing repository administration."""
    normalized = target.strip().lower()
    if normalized == "packages":
        return {"target": "packages", "packages": _discover_packages()}
    if normalized == "package_search":
        if query is None or not query.strip():
            raise ToolError("query is required when target='package_search'")
        return _search_packages(query=query, page_size=page_size, cursor=cursor)
    if normalized == "package":
        if not package_name:
            raise ToolError("package_name is required when target='package'")
        package = _find_package_description(package_name)
        if package is None:
            raise ToolError(f"package not found: {package_name}")
        return {"target": "package", "package": package}
    if normalized == "pipeline":
        if not pipeline_id:
            raise ToolError("pipeline_id is required when target='pipeline'")
        snapshot = await export_pipeline(pipeline_id, include_yaml=include_yaml)
        return {"target": "pipeline", "pipeline": snapshot}
    if normalized == "step":
        if not pipeline_id or not step_id:
            raise ToolError("pipeline_id and step_id are required when target='step'")
        snapshot = await export_pipeline(pipeline_id, include_yaml=False)
        step = _step_snapshot(snapshot, step_id)
        if step is None:
            raise ToolError(f"step not found in pipeline {pipeline_id}: {step_id}")
        config = await get_pkg_config(pipeline_id, step_id)
        return {"target": "step", "step": step, "config": config}
    raise ToolError(
        "target must be one of: packages, package_search, package, pipeline, step"
    )


@mcp.tool(
    name="jarvis_add_step",
    description=(
        "Add a package-backed step to a JARVIS pipeline and optionally configure "
        "that step with package-owned settings."
    ),
    annotations={
        "readOnlyHint": False,
        "destructiveHint": False,
        "idempotentHint": False,
    },
    tags={"jarvis", "pipeline", "user"},
)
async def jarvis_add_step_tool(
    pipeline_id: str,
    package_name: str,
    step_id: Optional[str] = None,
    config: Optional[dict[str, Any]] = None,
    do_configure: bool = True,
) -> dict:
    """Add a step to a pipeline."""
    return await append_pkg(
        pipeline_id,
        package_name,
        pkg_id=step_id,
        do_configure=do_configure,
        **(config or {}),
    )


@mcp.tool(
    name="jarvis_edit_step",
    description=(
        "Edit or remove a step in a JARVIS pipeline. Use operation='edit' with "
        "config, or operation='remove' without config."
    ),
    annotations={
        "readOnlyHint": False,
        "destructiveHint": True,
        "idempotentHint": False,
    },
    tags={"jarvis", "pipeline", "user"},
)
async def jarvis_edit_step_tool(
    pipeline_id: str,
    step_id: str,
    config: Optional[dict[str, Any]] = None,
    operation: Literal["edit", "remove"] = "edit",
) -> dict:
    """Edit or remove one pipeline step with explicit conditional arguments."""
    if operation == "edit":
        if config is None:
            raise ToolError("config is required when operation='edit'")
        return await configure_pkg(pipeline_id, step_id, **config)
    if config not in (None, {}):
        raise ToolError("config is not accepted when operation='remove'")
    return await unlink_pkg(pipeline_id, step_id)


@mcp.tool(
    name="jarvis_run",
    description=(
        "Run a configured JARVIS pipeline. Optional execution intent selects "
        "local, cluster, or hostfile mode without exposing scheduler internals. "
        "Optional spack_specs are resolved into a filtered environment that JARVIS "
        "persists before direct or scheduler execution."
    ),
    annotations={
        "readOnlyHint": False,
        "destructiveHint": False,
        "idempotentHint": False,
    },
    tags={"jarvis", "pipeline", "user"},
)
async def jarvis_run_tool(
    pipeline_id: str,
    execution: ExecutionIntent | None = None,
    submit: bool = True,
    wait: bool = False,
    execution_id: str | None = None,
    spack_specs: Optional[list[str]] = None,
    ctx: Context | None = None,
) -> JarvisRunResult:
    """Run or submit a pipeline after persisting any requested Spack environment."""
    mode = "auto"
    if execution is not None:
        intent = _validated_execution_intent(execution)
        requested_mode = intent.mode
        mode = {
            "cluster": "scheduler",
            "local": "direct",
            "hostfile": "direct",
        }.get(requested_mode, requested_mode)
        run_arguments_config = _execution_intent_to_pipeline_config(intent)
    else:
        run_arguments_config = None

    async def report_progress(
        current: float,
        total: float | None,
        message: str,
    ) -> None:
        if ctx is not None:
            await ctx.report_progress(current, total, message)

    run_arguments: dict[str, Any] = {
        "mode": mode,
        "submit": submit,
        "wait": wait,
        "execution_id": execution_id,
        "spack_specs": spack_specs,
        "pipeline_config": run_arguments_config,
    }
    if _context_has_progress_token(ctx):
        run_arguments["progress_reporter"] = report_progress
    return cast(JarvisRunResult, await run_pipeline(pipeline_id, **run_arguments))


@mcp.tool(
    name="jarvis_get_execution",
    description=(
        "Query one JARVIS execution handle, durable lifecycle record, and "
        "runtime metadata. Progress is included by default and can be omitted. "
        "Set include_service_runtimes=true to include execution-owned network "
        "services such as an interactive ParaView runtime. "
        "Set artifacts to {} or filters to include one bounded artifact page; "
        "omit artifacts to avoid querying the artifact manifest."
    ),
    annotations={
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
    },
    tags={"jarvis", "pipeline", "execution", "user"},
)
async def jarvis_get_execution_tool(
    pipeline_id: str,
    execution_id: str,
    include_progress: bool = True,
    include_service_runtimes: bool = False,
    artifacts: ExecutionArtifactQuery | None = None,
) -> JarvisExecutionResult:
    """Query a selectable JARVIS-owned execution view in one locked load."""
    return JarvisExecutionResult.model_validate(
        await get_execution(
            pipeline_id,
            execution_id,
            include_progress=include_progress,
            include_service_runtimes=include_service_runtimes,
            artifacts=artifacts.model_dump() if artifacts is not None else None,
        )
    )


def _context_has_progress_token(ctx: Context | None) -> bool:
    """Return whether this MCP request explicitly negotiated live progress."""
    if ctx is None:
        return False
    request_context = ctx.request_context
    return (
        request_context is not None
        and request_context.meta is not None
        and request_context.meta.progressToken is not None
    )


@mcp.tool(
    name="destroy_pipeline",
    description="Destroy a pipeline environment and clean up files.",
    annotations={
        "readOnlyHint": False,
        "destructiveHint": True,
        "idempotentHint": True,
    },
    tags={"jarvis", "pipeline"},
)
async def destroy_pipeline_tool(pipeline_id: str) -> dict:
    """Destroy a pipeline and clean up all associated files and resources."""
    return await destroy_pipeline(pipeline_id)


@mcp.tool(
    name="jm_create_config",
    description="Initialize JarvisManager config directories.",
    annotations={
        "readOnlyHint": False,
        "destructiveHint": False,
        "idempotentHint": False,
    },
    tags={"jarvis", "management"},
)
def jm_create_config(
    config_dir: str, private_dir: str, shared_dir: Optional[str] = None
) -> list:
    """Initialize manager directories and persist configuration."""
    try:
        with _protocol_stdout_to_stderr():
            manager = get_manager()
            manager.create(config_dir, private_dir, shared_dir)
            manager.save()
        return [{"type": "text", "text": "Jarvis configuration initialized."}]
    except Exception as e:
        raise ToolError(f"Error: {e}")


@mcp.tool(
    name="jm_load_config",
    description="Load existing JarvisManager configuration.",
    annotations={
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
    },
    tags={"jarvis", "management"},
)
def jm_load_config() -> list:
    """Load manager configuration from saved state."""
    try:
        manager = get_manager()
        manager.load()
        return [{"type": "text", "text": "Configuration loaded."}]
    except Exception as e:
        raise ToolError(f"Error: {e}")


@mcp.tool(
    name="jm_save_config",
    description="Save current JarvisManager configuration.",
    annotations={
        "readOnlyHint": False,
        "destructiveHint": False,
        "idempotentHint": True,
    },
    tags={"jarvis", "management"},
)
def jm_save_config() -> list:
    """Save current configuration state to disk."""
    try:
        manager = get_manager()
        manager.save()
        return [{"type": "text", "text": "Configuration saved."}]
    except Exception as e:
        raise ToolError(f"Error: {e}")


@mcp.tool(
    name="jm_set_hostfile",
    description="Set hostfile path for JarvisManager.",
    annotations={
        "readOnlyHint": False,
        "destructiveHint": False,
        "idempotentHint": True,
    },
    tags={"jarvis", "management"},
)
def jm_set_hostfile(path: str) -> list:
    """Set and save the path to the hostfile for deployments."""
    try:
        manager = get_manager()
        manager.set_hostfile(path)
        manager.save()
        return [{"type": "text", "text": f"Hostfile set to '{path}'"}]
    except Exception as e:
        raise ToolError(f"Error: {e}")


@mcp.tool(
    name="jm_bootstrap_from",
    description="Bootstrap Jarvis config from a machine template.",
    annotations={
        "readOnlyHint": False,
        "destructiveHint": False,
        "idempotentHint": False,
    },
    tags={"jarvis", "management"},
)
def jm_bootstrap_from(machine: str) -> list:
    """Bootstrap configuration based on a predefined machine template."""
    try:
        manager = get_manager()
        manager.bootstrap_from(machine)
        return [{"type": "text", "text": f"Bootstrapped from '{machine}'"}]
    except Exception as e:
        raise ToolError(f"Error: {e}")


@mcp.tool(
    name="jm_bootstrap_list",
    description="List available bootstrap machine templates.",
    annotations={
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
    },
    tags={"jarvis", "management"},
)
def jm_bootstrap_list() -> list:
    """List all bootstrap templates available."""
    try:
        manager = get_manager()
        return [{"type": "text", "text": m} for m in manager.bootstrap_list()]
    except Exception as e:
        raise ToolError(f"Error: {e}")


@mcp.tool(
    name="jm_reset",
    description="Reset JarvisManager (destroy all pipelines and data).",
    annotations={
        "readOnlyHint": False,
        "destructiveHint": True,
        "idempotentHint": True,
    },
    tags={"jarvis", "management"},
)
def jm_reset() -> list:
    """Reset manager to a clean state by destroying all pipelines and config."""
    try:
        manager = get_manager()
        manager.reset()
        return [{"type": "text", "text": "All pipelines and data reset."}]
    except Exception as e:
        raise ToolError(f"Error: {e}")


@mcp.tool(
    name="jm_list_pipelines",
    description="List all existing Jarvis pipelines.",
    annotations={
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
    },
    tags={"jarvis", "monitoring"},
)
async def jm_list_pipelines() -> dict[str, Any]:
    """List all current pipelines under management."""
    try:
        manager = get_manager()
        pipelines = [str(pipeline) for pipeline in manager.list_pipelines()]
        return {"pipelines": pipelines, "count": len(pipelines)}
    except Exception as e:
        raise ToolError(f"Error: {e}")


@mcp.tool(
    name="jm_cd",
    description="Change current Jarvis pipeline context.",
    annotations={
        "readOnlyHint": False,
        "destructiveHint": False,
        "idempotentHint": True,
    },
    tags={"jarvis", "management"},
)
def jm_cd(pipeline_id: str) -> list:
    """Set the working pipeline context."""
    try:
        manager = get_manager()
        manager.cd(pipeline_id)
        manager.save()
        return [{"type": "text", "text": f"Current pipeline set to '{pipeline_id}'"}]
    except Exception as e:
        raise ToolError(f"Error: {e}")


@mcp.tool(
    name="jm_list_repos",
    description="List all Jarvis repositories.",
    annotations={
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
    },
    tags={"jarvis", "monitoring"},
)
async def jm_list_repos() -> dict[str, Any]:
    """List all registered repositories."""
    try:
        manager = get_manager()
        repos = [str(repo) for repo in manager.list_repos()]
        return {"repos": repos, "count": len(repos)}
    except Exception as e:
        raise ToolError(f"Error: {e}")


@mcp.tool(
    name="jm_add_repo",
    description="Add a repository to JarvisManager.",
    annotations={
        "readOnlyHint": False,
        "destructiveHint": False,
        "idempotentHint": False,
    },
    tags={"jarvis", "management"},
)
def jm_add_repo(path: str, force: bool = False) -> list:
    """Add a repository path to the manager."""
    try:
        manager = get_manager()
        manager.add_repo(path, force)
        manager.save()
        return [{"type": "text", "text": f"Repo added: {path}"}]
    except Exception as e:
        raise ToolError(f"Error: {e}")


@mcp.tool(
    name="jm_remove_repo",
    description="Remove a repository from JarvisManager.",
    annotations={
        "readOnlyHint": False,
        "destructiveHint": True,
        "idempotentHint": True,
    },
    tags={"jarvis", "management"},
)
def jm_remove_repo(repo_name: str) -> list:
    """Remove a repository from configuration."""
    try:
        manager = get_manager()
        manager.remove_repo(repo_name)
        manager.save()
        return [{"type": "text", "text": f"Repo removed: {repo_name}"}]
    except Exception as e:
        raise ToolError(f"Error: {e}")


@mcp.tool(
    name="jm_promote_repo",
    description="Promote a repository in JarvisManager.",
    annotations={
        "readOnlyHint": False,
        "destructiveHint": False,
        "idempotentHint": True,
    },
    tags={"jarvis", "management"},
)
def jm_promote_repo(repo_name: str) -> list:
    """Promote a repository to higher priority."""
    try:
        manager = get_manager()
        manager.promote_repo(repo_name)
        manager.save()
        return [{"type": "text", "text": f"Repo promoted: {repo_name}"}]
    except Exception as e:
        raise ToolError(f"Error: {e}")


@mcp.tool(
    name="jm_get_repo",
    description="Get repository info from JarvisManager.",
    annotations={
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
    },
    tags={"jarvis", "monitoring"},
)
async def jm_get_repo(repo_name: str) -> dict[str, Any]:
    """Get detailed information about a repository."""
    try:
        manager = get_manager()
        repo = manager.get_repo(repo_name)
        return {"repo": repo if isinstance(repo, dict) else str(repo)}
    except Exception as e:
        raise ToolError(f"Error: {e}")


@mcp.tool(
    name="jm_construct_pkg",
    description="Construct a package skeleton in JarvisManager.",
    annotations={
        "readOnlyHint": False,
        "destructiveHint": False,
        "idempotentHint": False,
    },
    tags={"jarvis", "pipeline"},
)
def jm_construct_pkg(pkg_type: str) -> list:
    """Generate a new package skeleton by type."""
    try:
        manager = get_manager()
        obj = manager.construct_pkg(pkg_type)
        return [{"type": "text", "text": f"Constructed pkg: {obj.__class__.__name__}"}]
    except Exception as e:
        raise ToolError(f"Error: {e}")


@mcp.tool(
    name="jm_graph_show",
    description="Print the current resource graph frames.",
    annotations={
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
    },
    tags={"jarvis", "monitoring"},
)
def jm_graph_show() -> list:
    """Print the resource graph to the console."""
    try:
        manager = get_manager()
        manager.resource_graph_show()
        return [{"type": "text", "text": "Resource graph printed to console."}]
    except Exception as e:
        raise ToolError(f"Error: {e}")


@mcp.tool(
    name="jm_graph_build",
    description="Build or rebuild the resource graph with a net sleep interval.",
    annotations={
        "readOnlyHint": False,
        "destructiveHint": False,
        "idempotentHint": False,
    },
    tags={"jarvis", "pipeline"},
)
def jm_graph_build(net_sleep: float) -> list:
    """Construct or rebuild the graph with a given sleep delay."""
    try:
        manager = get_manager()
        manager.resource_graph_build(net_sleep)
        return [{"type": "text", "text": "Resource graph built."}]
    except Exception as e:
        raise ToolError(f"Error: {e}")


@mcp.tool(
    name="jm_graph_modify",
    description="Modify the resource graph using a net sleep interval.",
    annotations={
        "readOnlyHint": False,
        "destructiveHint": False,
        "idempotentHint": False,
    },
    tags={"jarvis", "pipeline"},
)
def jm_graph_modify(net_sleep: float) -> list:
    """Modify the current resource graph with a delay between operations."""
    try:
        manager = get_manager()
        manager.resource_graph_modify(net_sleep)
        return [{"type": "text", "text": "Resource graph modified."}]
    except Exception as e:
        raise ToolError(f"Error: {e}")


def _discover_packages() -> list[dict[str, Any]]:
    """Return the legacy exhaustive package descriptions with full settings."""

    return [
        _package_description_from_inventory(entry)
        for entry in _discover_package_inventory()
    ]


def _discover_package_inventory() -> list[_PackageInventoryEntry]:
    """Discover lightweight package identities without importing package classes."""

    packages: list[_PackageInventoryEntry] = []
    seen: set[str] = set()
    try:
        manager = get_manager()
        repos = [Path(str(repo)) for repo in manager.list_repos()]
    except Exception:
        repos = []
    for repo in repos:
        if not repo.exists():
            continue
        package_files = sorted(
            (*repo.rglob("pkg.py"), *repo.rglob("package.py")),
            key=lambda path: (path.parent.as_posix(), path.name != "pkg.py"),
        )
        for pkg_file in package_files:
            package = _package_inventory_entry(repo, pkg_file)
            name = package.name
            if not name or name in seen:
                continue
            seen.add(name)
            packages.append(package)
    return sorted(packages, key=lambda package: (package.name.casefold(), package.name))


def _find_package_description(package_name: str) -> dict[str, Any] | None:
    """Resolve one exact canonical or short name and load only its settings."""

    normalized = package_name.strip().casefold()
    inventory = _discover_package_inventory()
    canonical = next(
        (package for package in inventory if package.name.casefold() == normalized),
        None,
    )
    if canonical is not None:
        return _package_description_from_inventory(canonical)

    short_matches = [
        package for package in inventory if package.short_name.casefold() == normalized
    ]
    if len(short_matches) == 1:
        return _package_description_from_inventory(short_matches[0])
    if len(short_matches) > 1:
        candidates = ", ".join(package.name for package in short_matches)
        raise ToolError(
            f"package short name is ambiguous: {package_name}; use one of: {candidates}"
        )
    return None


def _package_from_pkg_file(repo: Path, pkg_file: Path) -> dict[str, Any]:
    """Build one full package description from a repository source file."""

    return _package_description_from_inventory(_package_inventory_entry(repo, pkg_file))


def _package_inventory_entry(repo: Path, pkg_file: Path) -> _PackageInventoryEntry:
    """Build one lightweight package inventory entry from its source location."""

    relative = pkg_file.relative_to(repo)
    parts = list(relative.parts[:-1])
    short_name = parts[-1] if parts else repo.name
    dotted = ".".join(parts) if parts else short_name
    description = _first_docstring_or_comment(pkg_file)
    repository = parts[0] if parts else repo.name
    return _PackageInventoryEntry(
        name=dotted,
        short_name=short_name,
        repository=repository,
        description=description,
        repo=repo,
        package_file=pkg_file,
    )


def _package_description_from_inventory(
    entry: _PackageInventoryEntry,
) -> dict[str, Any]:
    """Load the package-owned settings for one selected inventory entry."""

    package: dict[str, Any] = {
        "name": entry.name,
        "short_name": entry.short_name,
        "description": entry.description,
        "path": str(entry.package_file),
    }
    menu = _package_settings(package["name"])
    if menu is None and package["name"] != package["short_name"]:
        menu = _package_settings(package["short_name"])
    if menu is not None:
        package["settings"] = menu
    return package


def _search_packages(
    *,
    query: str,
    page_size: int = PACKAGE_SEARCH_DEFAULT_PAGE_SIZE,
    cursor: str | None = None,
) -> dict[str, Any]:
    """Return a bounded, summary-only page from the registered package inventory."""

    normalized_query = " ".join(query.split())
    if not normalized_query:
        raise ToolError("package_search query must not be blank")
    if (
        isinstance(page_size, bool)
        or not isinstance(page_size, int)
        or not 1 <= page_size <= PACKAGE_SEARCH_MAX_PAGE_SIZE
    ):
        raise ToolError(
            "package_search page_size must be between 1 and "
            f"{PACKAGE_SEARCH_MAX_PAGE_SIZE}"
        )

    inventory = _discover_package_inventory()
    inventory_revision = _package_inventory_revision(inventory)
    query_sha256 = hashlib.sha256(
        normalized_query.casefold().encode("utf-8")
    ).hexdigest()
    ranked = sorted(
        (
            (rank, package)
            for package in inventory
            if (rank := _package_search_rank(package, normalized_query)) is not None
        ),
        key=lambda item: (item[0], item[1].name.casefold(), item[1].name),
    )
    matches = [package for _, package in ranked]

    start = 0
    if cursor is not None:
        decoded = _decode_package_search_cursor(cursor)
        if decoded["query_sha256"] != query_sha256:
            raise ToolError("package_search cursor does not match the requested query")
        if decoded["inventory_revision"] != inventory_revision:
            raise ToolError(
                "package_search cursor is stale because the package inventory changed"
            )
        anchor = decoded["after_package_name"]
        try:
            start = next(
                index + 1
                for index, package in enumerate(matches)
                if package.name == anchor
            )
        except StopIteration as exc:
            raise ToolError(
                "package_search cursor is stale because its package anchor disappeared"
            ) from exc

    page = [package.summary() for package in matches[start : start + page_size]]
    while True:
        has_more = start + len(page) < len(matches)
        next_cursor = None
        if has_more and page:
            next_cursor = _encode_package_search_cursor(
                after_package_name=str(page[-1]["name"]),
                query_sha256=query_sha256,
                inventory_revision=inventory_revision,
            )
        result: dict[str, Any] = {
            "schema_version": PACKAGE_SEARCH_SCHEMA,
            "target": "package_search",
            "query": normalized_query,
            "inventory_revision": inventory_revision,
            "packages": page,
            "total_matches": len(matches),
            "returned_count": len(page),
            "next_cursor": next_cursor,
        }
        if len(_package_search_json_bytes(result)) <= PACKAGE_SEARCH_MAX_RESULT_BYTES:
            return result
        if len(page) <= 1:
            raise ToolError(
                "one package_search result exceeded the response byte limit"
            )
        page.pop()


def _package_search_rank(
    package: _PackageInventoryEntry,
    query: str,
) -> int | None:
    """Return a deterministic relevance rank, or ``None`` when no field matches."""

    folded_query = query.casefold()
    folded_name = package.name.casefold()
    folded_short_name = package.short_name.casefold()
    if folded_query in {folded_name, folded_short_name}:
        return 0
    if folded_name.startswith(folded_query) or folded_short_name.startswith(
        folded_query
    ):
        return 1
    if folded_query in folded_name or folded_query in folded_short_name:
        return 2
    folded_description = (package.description or "").casefold()
    if folded_query in folded_description:
        return 3

    normalized_query = _package_search_terms(folded_query)
    if not normalized_query:
        return None
    searchable = _package_search_terms(
        " ".join(
            (
                package.name,
                package.short_name,
                package.description or "",
            )
        ).casefold()
    )
    if all(term in searchable for term in normalized_query):
        return 4
    return None


def _package_search_terms(value: str) -> list[str]:
    """Tokenize package names and prose without locale-dependent behavior."""

    return [term for term in re.split(r"[^a-z0-9]+", value) if term]


def _package_inventory_revision(inventory: list[_PackageInventoryEntry]) -> str:
    """Hash the full lightweight inventory used to rank and page package search."""

    hasher = hashlib.sha256()
    hasher.update(b"clio-kit.jarvis-package-inventory.v1\0")
    for package in inventory:
        encoded = _package_search_json_bytes(
            {
                "name": package.name,
                "short_name": package.short_name,
                "repository": package.repository,
                "description": package.description,
            }
        )
        hasher.update(len(encoded).to_bytes(8, "big"))
        hasher.update(encoded)
    return hasher.hexdigest()


def _encode_package_search_cursor(
    *,
    after_package_name: str,
    query_sha256: str,
    inventory_revision: str,
) -> str:
    """Encode an opaque cursor bound to one query and inventory revision."""

    payload = _package_search_json_bytes(
        {
            "schema_version": PACKAGE_SEARCH_CURSOR_SCHEMA,
            "after_package_name": after_package_name,
            "query_sha256": query_sha256,
            "inventory_revision": inventory_revision,
        }
    )
    cursor = base64.urlsafe_b64encode(payload).decode("ascii").rstrip("=")
    if len(cursor) > PACKAGE_SEARCH_MAX_CURSOR_LENGTH:
        raise ToolError("package_search cursor exceeded its byte limit")
    return cursor


def _decode_package_search_cursor(cursor: str) -> dict[str, str]:
    """Decode and strictly validate one package-search cursor."""

    if (
        not cursor
        or len(cursor) > PACKAGE_SEARCH_MAX_CURSOR_LENGTH
        or _PACKAGE_SEARCH_CURSOR_TEXT.fullmatch(cursor) is None
    ):
        raise ToolError("package_search cursor is invalid")
    padding = "=" * (-len(cursor) % 4)
    try:
        payload = base64.b64decode(
            cursor + padding,
            altchars=b"-_",
            validate=True,
        )
        if len(payload) > PACKAGE_SEARCH_MAX_CURSOR_LENGTH:
            raise ToolError("package_search cursor exceeded its byte limit")
        value = json.loads(
            payload.decode("utf-8"),
            object_pairs_hook=_reject_package_search_duplicate_keys,
        )
    except ToolError:
        raise
    except (
        binascii.Error,
        UnicodeDecodeError,
        json.JSONDecodeError,
        ValueError,
    ) as exc:
        raise ToolError("package_search cursor is invalid") from exc
    expected_fields = {
        "schema_version",
        "after_package_name",
        "query_sha256",
        "inventory_revision",
    }
    if not isinstance(value, dict) or set(value) != expected_fields:
        raise ToolError("package_search cursor schema is invalid")
    if value.get("schema_version") != PACKAGE_SEARCH_CURSOR_SCHEMA:
        raise ToolError("package_search cursor schema is unsupported")
    after_package_name = value.get("after_package_name")
    query_sha256 = value.get("query_sha256")
    inventory_revision = value.get("inventory_revision")
    if (
        not isinstance(after_package_name, str)
        or not after_package_name
        or not isinstance(query_sha256, str)
        or _PACKAGE_SEARCH_SHA256.fullmatch(query_sha256) is None
        or not isinstance(inventory_revision, str)
        or _PACKAGE_SEARCH_SHA256.fullmatch(inventory_revision) is None
    ):
        raise ToolError("package_search cursor fields are invalid")
    return {
        "after_package_name": after_package_name,
        "query_sha256": query_sha256,
        "inventory_revision": inventory_revision,
    }


def _bounded_package_search_description(value: str | None) -> str | None:
    """Truncate only search summaries to their documented UTF-8 byte ceiling."""

    if value is None:
        return None
    encoded = value.encode("utf-8")
    if len(encoded) <= PACKAGE_SEARCH_MAX_DESCRIPTION_BYTES:
        return value
    suffix = "..."
    budget = PACKAGE_SEARCH_MAX_DESCRIPTION_BYTES - len(suffix)
    prefix = encoded[:budget]
    while prefix:
        try:
            return prefix.decode("utf-8") + suffix
        except UnicodeDecodeError:
            prefix = prefix[:-1]
    return suffix


def _package_search_json_bytes(value: object) -> bytes:
    """Serialize bounded search state using a deterministic UTF-8 encoding."""

    return json.dumps(
        value,
        allow_nan=False,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")


def _reject_package_search_duplicate_keys(
    pairs: list[tuple[str, Any]],
) -> dict[str, Any]:
    """Reject ambiguous JSON objects inside opaque package-search cursors."""

    value: dict[str, Any] = {}
    for key, item in pairs:
        if key in value:
            raise ValueError(f"duplicate package_search cursor key: {key}")
        value[key] = item
    return value


def _first_docstring_or_comment(path: Path) -> str | None:
    try:
        lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        return None
    in_docstring = False
    docstring_quote: str | None = None
    collected: list[str] = []
    for raw_line in lines[:80]:
        line = raw_line.strip()
        if not line:
            continue
        if line.startswith("#"):
            comment = line.lstrip("#").strip()
            if comment:
                return comment
            continue
        if in_docstring and docstring_quote is not None:
            if line.endswith(docstring_quote):
                line = line[: -len(docstring_quote)]
                if line:
                    collected.append(line.strip())
                return " ".join(collected).strip() or None
            collected.append(line)
            continue
        if line.startswith(('"""', "'''")):
            docstring_quote = line[:3]
            remainder = line[3:]
            if remainder.endswith(docstring_quote):
                remainder = remainder[:-3]
                return remainder.strip() or None
            in_docstring = True
            if remainder:
                collected.append(remainder.strip())
            continue
        return None
    return " ".join(collected).strip() or None


def _step_snapshot(
    pipeline_snapshot: dict[str, Any], step_id: str
) -> dict[str, Any] | None:
    for package in pipeline_snapshot.get("packages", []):
        if not isinstance(package, dict):
            continue
        identifiers = {
            str(package.get("pkg_id", "")),
            str(package.get("global_id", "")),
        }
        if step_id in identifiers:
            return package
    return None


def _package_settings(package_name: str) -> list[dict[str, Any]] | None:
    try:
        from jarvis_cd.core.pkg import Pkg  # type: ignore[import-untyped]

        pkg = Pkg.load_standalone(package_name)
        return [_setting_from_menu_item(item) for item in pkg.configure_menu()]
    except Exception:
        return None


def _setting_from_menu_item(item: dict[str, Any]) -> dict[str, Any]:
    setting: dict[str, Any] = {
        "name": item.get("name"),
        "description": item.get("msg"),
    }
    kind = item.get("type")
    if isinstance(kind, type):
        setting["type"] = kind.__name__
    elif kind is not None:
        setting["type"] = str(kind)
    if "default" in item:
        setting["default"] = item["default"]
    return {key: value for key, value in setting.items() if value is not None}


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
        if set(values) <= {"mode"}:
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


def _protocol_stdout_to_stderr() -> Any:
    from contextlib import redirect_stdout
    import sys

    return redirect_stdout(sys.stderr)


def add_spack_command_argument(parser: argparse.ArgumentParser) -> None:
    """Add the shared validated Spack executable option to a CLI parser."""
    parser.add_argument(
        "--spack-command",
        type=_spack_command_path,
        default=None,
        help="Absolute or user-relative path to the audited Spack executable.",
    )


def configure_spack_command(spack_command: str | None) -> None:
    """Apply an explicitly validated Spack command for later JARVIS runs."""
    if spack_command is not None:
        os.environ["JARVIS_MCP_SPACK_COMMAND"] = spack_command


def _spack_command_path(value: str) -> str:
    """Resolve and validate an operator-supplied Spack executable path."""
    candidate = Path(value).expanduser()
    try:
        resolved = candidate.resolve(strict=True)
    except (OSError, RuntimeError) as exc:
        raise argparse.ArgumentTypeError(
            f"Spack command does not exist: {candidate}"
        ) from exc
    if not resolved.is_file():
        raise argparse.ArgumentTypeError(f"Spack command is not a file: {resolved}")
    if os.name != "nt" and not os.access(resolved, os.X_OK):
        raise argparse.ArgumentTypeError(f"Spack command is not executable: {resolved}")
    return str(resolved)


def main() -> None:
    """Main entry point for the Jarvis MCP server."""
    parser = argparse.ArgumentParser(description="Jarvis MCP Server")
    parser.add_argument("--transport", choices=["stdio", "http"], default=None)
    parser.add_argument(
        "--profile",
        choices=["all", "user", "admin"],
        default=None,
        help=(
            "Tool surface to expose. 'user' exposes pipeline authoring and read-only "
            "discovery tools. 'admin' exposes manager and destructive operations. "
            "'all' preserves the full legacy surface."
        ),
    )
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--port", type=int, default=8000)
    add_spack_command_argument(parser)
    args = parser.parse_args()
    configure_spack_command(args.spack_command)
    transport = args.transport or os.getenv("MCP_TRANSPORT", "stdio")
    profile = args.profile or os.getenv("JARVIS_MCP_PROFILE", "user")
    apply_tool_profile(profile)
    if transport == "http":
        mcp.run(transport="http", host=args.host, port=args.port)
    else:
        mcp.run(transport="stdio")


def admin_main() -> None:
    """Main entry point for the Jarvis admin MCP server."""
    os.environ.setdefault("JARVIS_MCP_PROFILE", "admin")
    main()


def apply_tool_profile(profile: str) -> None:
    """Restrict the registered tool set for user or admin MCP modes."""
    normalized = profile.strip().lower()
    if normalized == "all":
        return
    if normalized == "user":
        allowed = USER_TOOLS
    elif normalized == "admin":
        allowed = ADMIN_TOOLS
    else:
        raise ValueError("profile must be one of: all, user, admin")
    for tool in _registered_tools():
        if tool.name not in allowed:
            mcp.local_provider.remove_tool(tool.name)


def _registered_tools() -> list:
    components = getattr(mcp.local_provider, "_components", {})
    return [
        component
        for key, component in components.items()
        if isinstance(key, str) and key.startswith("tool:")
    ]


if __name__ == "__main__":
    main()
