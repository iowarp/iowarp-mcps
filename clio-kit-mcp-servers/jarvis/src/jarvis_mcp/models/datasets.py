"""JARVIS-owned dataset descriptor documents."""

from __future__ import annotations

import hashlib
import json
from pathlib import PurePosixPath
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


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
