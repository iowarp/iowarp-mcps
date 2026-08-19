"""Artifact location/document/page documents and the artifact query filter."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field
from typing_extensions import NotRequired, TypedDict


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
        "frame",
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
            "frame",
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
