"""Strict data contracts for operator-owned scientific catalogs."""

from __future__ import annotations

import hashlib
import json
import math
import re
from pathlib import PurePosixPath
from typing import Literal, Self

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

_SHA256_PATTERN = re.compile(r"^[0-9a-f]{64}$")
_IDENTITY_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,255}$")
_ARTIFACT_ID_PATTERN = re.compile(r"^art_[A-Za-z0-9_-]{22,86}$")


def _bounded_printable(value: str, label: str) -> str:
    """Reject blank or control-bearing text that JARVIS cannot ingest."""
    if not value.strip() or any(
        ord(character) < 32 or ord(character) == 127 for character in value
    ):
        raise ValueError(f"{label} must be nonblank printable text")
    return value


def canonical_sha256(value: object) -> str:
    """Return the canonical compact JSON SHA-256 for a validated document."""
    payload = json.dumps(
        value,
        allow_nan=False,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


class StrictModel(BaseModel):
    """Base model that refuses silent catalog schema extensions."""

    model_config = ConfigDict(extra="forbid", strict=True)


class DatasetFingerprint(StrictModel):
    """Content or collection identity for one dataset descriptor."""

    algorithm: Literal["sha256"]
    digest: str

    @field_validator("digest")
    @classmethod
    def validate_digest(cls, value: str) -> str:
        """Require a lowercase SHA-256 digest."""
        if _SHA256_PATTERN.fullmatch(value) is None:
            raise ValueError("fingerprint digest must be a lowercase SHA-256")
        return value


class DatasetSourceArtifact(StrictModel):
    """Optional durable JARVIS artifact that owns a dataset."""

    artifact_id: str = Field(pattern=r"^art_[A-Za-z0-9_-]{22,86}$")
    sha256: str

    @field_validator("sha256")
    @classmethod
    def validate_sha256(cls, value: str) -> str:
        """Require a lowercase SHA-256 digest."""
        if _SHA256_PATTERN.fullmatch(value) is None:
            raise ValueError("source artifact sha256 must be a lowercase SHA-256")
        return value

    @field_validator("artifact_id")
    @classmethod
    def validate_artifact_id(cls, value: str) -> str:
        """Mirror JARVIS's opaque artifact identifier contract."""
        if _ARTIFACT_ID_PATTERN.fullmatch(value) is None:
            raise ValueError("source artifact_id is invalid")
        return value


class DatasetMember(StrictModel):
    """One ordered, cluster-local member in the bounded catalog view."""

    index: int = Field(ge=0)
    location: str = Field(min_length=1, max_length=4096)
    timestep: float | None = Field(
        default=None,
        exclude_if=lambda value: value is None,
    )

    @field_validator("location")
    @classmethod
    def validate_location(cls, value: str) -> str:
        """Require normalized absolute POSIX paths without traversal."""
        _bounded_printable(value, "dataset member location")
        path = PurePosixPath(value)
        if (
            "\\" in value
            or not path.is_absolute()
            or path.as_posix() != value
            or ".." in path.parts
        ):
            raise ValueError("dataset member location must be a normalized absolute POSIX path")
        return value

    @field_validator("timestep")
    @classmethod
    def validate_timestep(cls, value: float | None) -> float | None:
        """Reject non-finite temporal coordinates."""
        if value is not None and not math.isfinite(value):
            raise ValueError("dataset member timestep must be finite")
        return value


class DatasetArray(StrictModel):
    """Intrinsic array facts discovered for one dataset."""

    name: str = Field(min_length=1, max_length=512)
    association: Literal["point", "cell", "field"]
    components: int = Field(ge=1, le=64)
    units: str | None = Field(
        default=None,
        min_length=1,
        max_length=256,
        exclude_if=lambda value: value is None,
    )

    @field_validator("name")
    @classmethod
    def validate_name(cls, value: str) -> str:
        """Require the printable array name accepted by JARVIS."""
        return _bounded_printable(value, "dataset array name")

    @field_validator("units")
    @classmethod
    def validate_units(cls, value: str | None) -> str | None:
        """Require printable units when the catalog supplies them."""
        return None if value is None else _bounded_printable(value, "dataset array units")


class DatasetDescriptor(StrictModel):
    """JARVIS-owned intrinsic dataset descriptor without visualization semantics."""

    schema_version: Literal["jarvis.dataset-descriptor.v1"]
    dataset_id: str
    kind: str = Field(min_length=1, max_length=256)
    format: str = Field(min_length=1, max_length=256)
    members: list[DatasetMember] = Field(min_length=1, max_length=512)
    arrays: list[DatasetArray] = Field(default_factory=list, max_length=256)
    bounds: list[float] | None = Field(default=None, min_length=6, max_length=6)
    fingerprint: DatasetFingerprint
    source_artifact: DatasetSourceArtifact | None = None

    @field_validator("dataset_id")
    @classmethod
    def validate_dataset_id(cls, value: str) -> str:
        """Require a stable, agent-safe dataset identity."""
        if _IDENTITY_PATTERN.fullmatch(value) is None:
            raise ValueError("dataset_id is invalid")
        return value

    @field_validator("kind", "format")
    @classmethod
    def validate_intrinsic_text(cls, value: str) -> str:
        """Require printable intrinsic descriptor labels."""
        return _bounded_printable(value, "dataset descriptor text")

    @model_validator(mode="after")
    def validate_intrinsic_metadata(self) -> Self:
        """Require stable ordering, valid bounds, and a recomputable identity."""
        if tuple(member.index for member in self.members) != tuple(range(len(self.members))):
            raise ValueError("dataset members must have contiguous ordered indexes")
        locations = [member.location for member in self.members]
        if len(locations) != len(set(locations)):
            raise ValueError("dataset member locations must be unique")
        arrays = [(array.association, array.name) for array in self.arrays]
        if len(arrays) != len(set(arrays)):
            raise ValueError("dataset array identities must be unique")
        if self.bounds is not None:
            if not all(math.isfinite(item) for item in self.bounds):
                raise ValueError("dataset bounds must be finite")
            for lower, upper in zip(self.bounds[::2], self.bounds[1::2], strict=True):
                if lower > upper:
                    raise ValueError("dataset bound lower values cannot exceed upper values")
        identity_document = self.model_dump(mode="json", exclude={"fingerprint"})
        expected_fingerprint = canonical_sha256(identity_document)
        if self.fingerprint.digest != expected_fingerprint:
            raise ValueError(
                "dataset fingerprint must be the canonical descriptor SHA-256 with "
                "the fingerprint field omitted"
            )
        return self

    @property
    def canonical_digest(self) -> str:
        """Return the digest used to bind this descriptor into JARVIS and relay."""
        return canonical_sha256(self.model_dump(mode="json"))


class CatalogDataset(StrictModel):
    """Human-discoverable metadata around one intrinsic dataset descriptor."""

    dataset_id: str
    title: str = Field(min_length=1, max_length=512)
    summary: str = Field(min_length=1, max_length=4096)
    tags: list[str] = Field(default_factory=list, max_length=64)
    descriptor: DatasetDescriptor

    @field_validator("dataset_id")
    @classmethod
    def validate_dataset_id(cls, value: str) -> str:
        """Require a stable, agent-safe catalog identity."""
        if _IDENTITY_PATTERN.fullmatch(value) is None:
            raise ValueError("catalog dataset_id is invalid")
        return value

    @field_validator("tags")
    @classmethod
    def validate_tags(cls, value: list[str]) -> list[str]:
        """Require normalized unique discovery tags."""
        if any(not tag or tag != tag.strip().lower() or len(tag) > 128 for tag in value):
            raise ValueError("catalog tags must be bounded lowercase text")
        if len(value) != len(set(value)):
            raise ValueError("catalog tags must be unique")
        return value

    @model_validator(mode="after")
    def validate_descriptor_identity(self) -> Self:
        """Prevent a catalog label from substituting another descriptor."""
        if self.dataset_id != self.descriptor.dataset_id:
            raise ValueError("catalog and descriptor dataset_id values must match")
        return self


class ScientificCatalog(StrictModel):
    """One complete operator-maintained site catalog."""

    schema_version: Literal["clio-kit.scientific-dataset-catalog.v1"]
    site_id: str
    revision: str = Field(min_length=1, max_length=256)
    datasets: list[CatalogDataset] = Field(max_length=4096)

    @field_validator("site_id")
    @classmethod
    def validate_site_id(cls, value: str) -> str:
        """Require a stable, agent-safe site identity."""
        if _IDENTITY_PATTERN.fullmatch(value) is None:
            raise ValueError("site_id is invalid")
        return value

    @model_validator(mode="after")
    def validate_unique_datasets(self) -> Self:
        """Reject ambiguous duplicate dataset identities."""
        identities = [dataset.dataset_id for dataset in self.datasets]
        if len(identities) != len(set(identities)):
            raise ValueError("catalog dataset_id values must be unique")
        return self

    @property
    def canonical_digest(self) -> str:
        """Return the digest used to scope pagination cursors."""
        return canonical_sha256(self.model_dump(mode="json"))


class DatasetSummary(StrictModel):
    """Bounded discovery record returned by search."""

    dataset_id: str
    title: str
    summary: str
    tags: list[str]
    kind: str
    format: str
    member_count: int
    first_timestep: float | None
    last_timestep: float | None
    dataset_fingerprint: str
    descriptor_sha256: str


class DatasetSearchResult(StrictModel):
    """Stable paginated response from scientific dataset search."""

    schema_version: Literal["clio-kit.scientific-dataset-search.v1"] = (
        "clio-kit.scientific-dataset-search.v1"
    )
    site_id: str
    catalog_revision: str
    catalog_sha256: str
    datasets: list[DatasetSummary]
    total_matches: int
    next_cursor: str | None


class DatasetDescribeResult(StrictModel):
    """Complete catalog record and exact JARVIS descriptor."""

    schema_version: Literal["clio-kit.scientific-dataset-description.v1"] = (
        "clio-kit.scientific-dataset-description.v1"
    )
    site_id: str
    catalog_revision: str
    catalog_sha256: str
    dataset: CatalogDataset
    dataset_descriptor: DatasetDescriptor
    descriptor_sha256: str

    @model_validator(mode="after")
    def validate_descriptor_handoff(self) -> Self:
        """Keep the explicit JARVIS handoff identical to the catalog record."""
        if self.dataset_descriptor != self.dataset.descriptor:
            raise ValueError("dataset_descriptor must match dataset.descriptor")
        if self.descriptor_sha256 != self.dataset_descriptor.canonical_digest:
            raise ValueError("descriptor_sha256 must identify dataset_descriptor")
        return self


def summary_of(dataset: CatalogDataset) -> DatasetSummary:
    """Project a full catalog record into bounded search metadata."""
    timesteps = [
        member.timestep for member in dataset.descriptor.members if member.timestep is not None
    ]
    return DatasetSummary(
        dataset_id=dataset.dataset_id,
        title=dataset.title,
        summary=dataset.summary,
        tags=dataset.tags,
        kind=dataset.descriptor.kind,
        format=dataset.descriptor.format,
        member_count=len(dataset.descriptor.members),
        first_timestep=timesteps[0] if timesteps else None,
        last_timestep=timesteps[-1] if timesteps else None,
        dataset_fingerprint=dataset.descriptor.fingerprint.digest,
        descriptor_sha256=dataset.descriptor.canonical_digest,
    )


__all__ = [
    "CatalogDataset",
    "DatasetDescribeResult",
    "DatasetDescriptor",
    "DatasetSearchResult",
    "ScientificCatalog",
    "canonical_sha256",
    "summary_of",
]
