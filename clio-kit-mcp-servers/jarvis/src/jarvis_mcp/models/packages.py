"""Package inventory, description, deployment, and settings documents."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

from typing_extensions import NotRequired, TypedDict

from ._base import _ClosedDocument

PACKAGE_DESCRIPTION_SCHEMA = "jarvis.package-description.v1"
PACKAGE_DEPLOYMENT_SCHEMA = "jarvis.package-deployment.v1"
CONFIGURATION_INPUT_BINDING_SCHEMA = "jarvis.configuration-input-binding.v1"
PACKAGE_SEARCH_MAX_DESCRIPTION_BYTES = 4096


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


@dataclass(frozen=True)
class _PackageAgentMetadata:
    """Package-owned metadata safe to return through the user MCP surface."""

    settings: list[dict[str, Any]] | None
    deployment: dict[str, Any] | None


class JarvisPackageConditionDocument(_ClosedDocument):
    """One package-owned predicate over a canonical configuration setting."""

    parameter: str
    operator: Literal["equals", "greater_than", "is_empty", "is_not_empty"]
    value: str | int | float | bool | None = None


class JarvisPackageReadinessDocument(_ClosedDocument):
    """Observable condition that makes one execution profile ready."""

    mechanism: Literal["process_exit", "progress_event", "service_runtime"]
    condition: str
    capability: str | None = None


class JarvisPackageExecutionProfileDocument(_ClosedDocument):
    """Package-owned execution kind, applicability, requirements, and readiness."""

    name: str
    execution_kind: Literal["batch", "service"]
    when: list[JarvisPackageConditionDocument]
    runtime_requirements: list[str]
    readiness: JarvisPackageReadinessDocument
    description: str | None = None


class JarvisConfigurationInputBindingDocument(_ClosedDocument):
    """Declared client-local input that must be staged before package use."""

    schema_version: Literal["jarvis.configuration-input-binding.v1"]
    kind: Literal["local_file"]
    structure: Literal["regular_file"]


class JarvisRuntimeRequirementStatusDocument(_ClosedDocument):
    """Package observation of whether a runtime requirement can be used."""

    state: Literal["ready", "unavailable", "unknown"]
    usable: bool | None
    reason_code: str


class JarvisProviderQueryDocument(_ClosedDocument):
    """Provider-neutral query that can resolve one runtime requirement."""

    kind: str
    value: str


class JarvisProviderResolutionDocument(_ClosedDocument):
    """One provider and query capable of resolving a runtime requirement."""

    provider: str
    query: JarvisProviderQueryDocument


class JarvisRuntimeRequirementDocument(_ClosedDocument):
    """Runtime capabilities and provider resolutions owned by a package."""

    id: str
    description: str
    required_capabilities: list[str]
    available_capabilities: list[str]
    status: JarvisRuntimeRequirementStatusDocument
    provider_resolutions: list[JarvisProviderResolutionDocument]


class JarvisPackageConfigurationRuleDocument(_ClosedDocument):
    """Conditional requirement over canonical package configuration settings."""

    when: list[JarvisPackageConditionDocument]
    requires: list[JarvisPackageConditionDocument]
    description: str


class JarvisPackageDeploymentDocument(_ClosedDocument):
    """Versioned deployment and readiness contract supplied by JARVIS."""

    schema_version: Literal["jarvis.package-deployment.v1"]
    package: str
    execution_profiles: list[JarvisPackageExecutionProfileDocument]
    runtime_requirements: list[JarvisRuntimeRequirementDocument]
    configuration_rules: list[JarvisPackageConfigurationRuleDocument]


class JarvisPackageSettingDocument(TypedDict):
    """One package parser setting with truthful default and null semantics."""

    name: str
    description: NotRequired[str]
    type: NotRequired[str]
    default: NotRequired[Any]
    choices: NotRequired[list[Any]]
    required: bool
    nullable: bool
    aliases: NotRequired[list[str]]
    input_binding: NotRequired[JarvisConfigurationInputBindingDocument]


class JarvisPackageDescriptionDocument(_ClosedDocument):
    """Path-free package detail returned after selecting one canonical package."""

    schema_version: Literal["jarvis.package-description.v1"]
    name: str
    short_name: str
    description: str | None
    deployment: JarvisPackageDeploymentDocument | None
    settings: list[JarvisPackageSettingDocument] | None = None


class JarvisPackageSummaryDocument(_ClosedDocument):
    """Bounded package identity returned during search."""

    name: str
    short_name: str
    repository: str
    description: str | None = None


# Re-exported for readability at call sites that build Field(...) bounds from it.
__all__ = [
    "PACKAGE_DESCRIPTION_SCHEMA",
    "PACKAGE_DEPLOYMENT_SCHEMA",
    "CONFIGURATION_INPUT_BINDING_SCHEMA",
    "PACKAGE_SEARCH_MAX_DESCRIPTION_BYTES",
    "_PackageInventoryEntry",
    "_PackageAgentMetadata",
    "_bounded_package_search_description",
    "JarvisPackageConditionDocument",
    "JarvisPackageReadinessDocument",
    "JarvisPackageExecutionProfileDocument",
    "JarvisConfigurationInputBindingDocument",
    "JarvisRuntimeRequirementStatusDocument",
    "JarvisProviderQueryDocument",
    "JarvisProviderResolutionDocument",
    "JarvisRuntimeRequirementDocument",
    "JarvisPackageConfigurationRuleDocument",
    "JarvisPackageDeploymentDocument",
    "JarvisPackageSettingDocument",
    "JarvisPackageDescriptionDocument",
    "JarvisPackageSummaryDocument",
]
