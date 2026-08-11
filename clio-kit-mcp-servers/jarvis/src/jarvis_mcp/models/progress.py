"""Package progress event and execution-scoped progress snapshot documents."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


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
