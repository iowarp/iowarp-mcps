"""Execution-owned service-runtime documents."""

from __future__ import annotations

from pathlib import PurePosixPath
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from .datasets import JarvisDatasetDescriptorDocument


class JarvisServiceAuthorizationDocument(BaseModel):
    """Non-secret fingerprint for an execution-owned runtime capability."""

    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
        strict=True,
        hide_input_in_errors=True,
    )

    scheme: Literal["bearer"]
    token_sha256: str = Field(
        min_length=64,
        max_length=64,
        pattern=r"^[0-9a-f]{64}$",
        repr=False,
    )


class _JarvisServiceRuntimeDocumentBase(BaseModel):
    """Fields shared by every released JARVIS service-runtime revision."""

    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
        strict=True,
        hide_input_in_errors=True,
    )

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
    def validate_private_endpoint_metadata(
        self,
    ) -> "_JarvisServiceRuntimeDocumentBase":
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


class JarvisServiceRuntimeV1Document(_JarvisServiceRuntimeDocumentBase):
    """Released unauthenticated service-runtime v1 document."""

    schema_version: Literal["jarvis.service-runtime.v1"]


class JarvisServiceRuntimeV2Document(_JarvisServiceRuntimeDocumentBase):
    """Service-runtime v2 document with a non-secret capability fingerprint."""

    schema_version: Literal["jarvis.service-runtime.v2"]
    authorization: JarvisServiceAuthorizationDocument


JarvisServiceRuntimeDocument = Annotated[
    JarvisServiceRuntimeV1Document | JarvisServiceRuntimeV2Document,
    Field(discriminator="schema_version"),
]


class JarvisServiceRuntimeSnapshotDocument(BaseModel):
    """Execution-bound current service runtimes returned by JARVIS."""

    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
        strict=True,
        hide_input_in_errors=True,
    )

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
