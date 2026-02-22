"""Shared connector protocol and indexing report."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, runtime_checkable

from clio_agentic_search.models.contracts import CitationRecord, NamespaceDescriptor
from clio_agentic_search.retrieval.capabilities import ScoredChunk


@dataclass(frozen=True, slots=True)
class IndexReport:
    scanned_files: int
    indexed_files: int
    skipped_files: int
    removed_files: int
    elapsed_seconds: float


class NamespaceConnector(Protocol):
    def descriptor(self) -> NamespaceDescriptor:
        """Describe namespace identity and connector type."""

    def connect(self) -> None:
        """Initialize connector resources."""

    def teardown(self) -> None:
        """Release connector resources."""

    def index(self, *, full_rebuild: bool = False) -> IndexReport:
        """Index namespace content."""

    def build_citation(self, chunk: ScoredChunk) -> CitationRecord:
        """Build a citation for a scored chunk."""


@dataclass(frozen=True, slots=True)
class NamespaceAuthConfig:
    scheme: str
    values: dict[str, str]


@dataclass(frozen=True, slots=True)
class NamespaceRuntimeConfig:
    options: dict[str, str]


@runtime_checkable
class ConfigurableConnector(Protocol):
    def configure(
        self,
        *,
        runtime_config: NamespaceRuntimeConfig,
        auth_config: NamespaceAuthConfig | None,
    ) -> None:
        """Apply namespace-scoped runtime configuration and credentials."""
