"""Core package."""

from __future__ import annotations

from clio_agentic_search.core.connectors import (
    ConfigurableConnector,
    IndexReport,
    NamespaceAuthConfig,
    NamespaceConnector,
    NamespaceRuntimeConfig,
)
from clio_agentic_search.core.namespace_config import (
    NamespaceConfigBundle,
    load_default_namespace_bundles,
)

__all__ = [
    "ConfigurableConnector",
    "IndexReport",
    "NamespaceAuthConfig",
    "NamespaceConfigBundle",
    "NamespaceConnector",
    "NamespaceRegistry",
    "NamespaceRuntimeConfig",
    "SeedReport",
    "build_default_registry",
    "load_default_namespace_bundles",
    "seed_connector",
]


def __getattr__(name: str) -> object:
    if name in {"NamespaceRegistry", "build_default_registry"}:
        from clio_agentic_search.core.namespace_registry import (
            NamespaceRegistry,
            build_default_registry,
        )

        exports = {
            "NamespaceRegistry": NamespaceRegistry,
            "build_default_registry": build_default_registry,
        }
        return exports[name]
    if name in {"SeedReport", "seed_connector"}:
        from clio_agentic_search.core.seeding import SeedReport, seed_connector

        exports = {
            "SeedReport": SeedReport,
            "seed_connector": seed_connector,
        }
        return exports[name]
    raise AttributeError(name)
