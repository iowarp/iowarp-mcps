"""Namespace registry and connector lifecycle management."""

from __future__ import annotations

import hashlib
import os
from dataclasses import dataclass, field
from pathlib import Path

from clio_agentic_search.connectors.filesystem import FilesystemConnector
from clio_agentic_search.connectors.object_store import InMemoryS3Client, S3ObjectStoreConnector
from clio_agentic_search.connectors.vector_store import (
    InMemoryQdrantClient,
    QdrantVectorConnector,
)
from clio_agentic_search.core.connectors import (
    ConfigurableConnector,
    NamespaceAuthConfig,
    NamespaceConnector,
    NamespaceRuntimeConfig,
)
from clio_agentic_search.core.namespace_config import load_default_namespace_bundles
from clio_agentic_search.indexing.text_features import Embedder, HashEmbedder
from clio_agentic_search.storage import DuckDBStorage


@dataclass(slots=True)
class NamespaceRegistry:
    _connectors: dict[str, NamespaceConnector] = field(default_factory=dict)
    _runtime_configs: dict[str, NamespaceRuntimeConfig] = field(default_factory=dict)
    _auth_configs: dict[str, NamespaceAuthConfig | None] = field(default_factory=dict)
    _connected_namespaces: set[str] = field(default_factory=set)

    def register(
        self,
        name: str,
        connector: NamespaceConnector,
        *,
        runtime_config: NamespaceRuntimeConfig | None = None,
        auth_config: NamespaceAuthConfig | None = None,
    ) -> None:
        if name in self._connectors:
            raise ValueError(f"Namespace '{name}' is already registered")
        descriptor = connector.descriptor()
        if descriptor.name != name:
            raise ValueError(
                f"Connector descriptor name '{descriptor.name}' does not match '{name}'"
            )
        self._connectors[name] = connector
        self._runtime_configs[name] = runtime_config or NamespaceRuntimeConfig(options={})
        self._auth_configs[name] = auth_config

    def connect(self, name: str) -> NamespaceConnector:
        connector = self.get(name)
        if name in self._connected_namespaces:
            return connector
        runtime_config = self._runtime_configs.get(name, NamespaceRuntimeConfig(options={}))
        auth_config = self._auth_configs.get(name)
        if isinstance(connector, ConfigurableConnector):
            connector.configure(runtime_config=runtime_config, auth_config=auth_config)
        connector.connect()
        self._connected_namespaces.add(name)
        return connector

    def teardown(self, name: str | None = None) -> None:
        if name is not None:
            if name in self._connected_namespaces:
                self._connectors[name].teardown()
                self._connected_namespaces.remove(name)
            return

        for namespace in sorted(self._connected_namespaces):
            self._connectors[namespace].teardown()
        self._connected_namespaces.clear()

    def get(self, name: str) -> NamespaceConnector:
        return self._connectors[name]

    def list_namespaces(self) -> tuple[str, ...]:
        return tuple(sorted(self._connectors))

    def __contains__(self, name: str) -> bool:
        return name in self._connectors

    def is_connected(self, name: str) -> bool:
        return name in self._connected_namespaces

    def get_connected(self, name: str) -> NamespaceConnector:
        return self.connect(name)


def _default_embedder() -> Embedder:
    try:
        import sentence_transformers  # noqa: F401

        from clio_agentic_search.indexing.text_features import SentenceTransformerEmbedder

        return SentenceTransformerEmbedder()
    except ImportError:
        return HashEmbedder()


def build_default_registry() -> NamespaceRegistry:
    bundles = load_default_namespace_bundles()
    storage_path = Path(os.environ.get("CLIO_STORAGE_PATH", ".clio-agentic-search.duckdb"))
    embedder = _default_embedder()

    registry = NamespaceRegistry()
    local_bundle = bundles["local_fs"]
    local_connector = FilesystemConnector(
        namespace="local_fs",
        root=Path(local_bundle.runtime.options["root"]),
        storage=DuckDBStorage(database_path=storage_path),
        embedder=embedder,
        embedding_model=embedder.model_name,
    )
    registry.register(
        "local_fs",
        local_connector,
        runtime_config=local_bundle.runtime,
        auth_config=local_bundle.auth,
    )

    object_bundle = bundles["object_s3"]
    object_client = InMemoryS3Client()
    object_connector = S3ObjectStoreConnector(
        namespace="object_s3",
        bucket=object_bundle.runtime.options["bucket"],
        prefix=object_bundle.runtime.options["prefix"],
        storage=DuckDBStorage(database_path=_namespaced_storage_path(storage_path, "object_s3")),
        client=object_client,
        embedder=embedder,
        embedding_model=embedder.model_name,
    )
    _seed_object_store_from_root(
        client=object_client,
        bucket=object_bundle.runtime.options["bucket"],
        prefix=object_bundle.runtime.options["prefix"],
        root=Path(object_bundle.runtime.options["root"]),
    )
    registry.register(
        "object_s3",
        object_connector,
        runtime_config=object_bundle.runtime,
        auth_config=object_bundle.auth,
    )

    vector_bundle = bundles["vector_qdrant"]
    vector_connector = QdrantVectorConnector(
        namespace="vector_qdrant",
        collection=vector_bundle.runtime.options["collection"],
        client=InMemoryQdrantClient(),
        embedder=embedder,
    )
    registry.register(
        "vector_qdrant",
        vector_connector,
        runtime_config=vector_bundle.runtime,
        auth_config=vector_bundle.auth,
    )

    return registry


def _namespaced_storage_path(base_path: Path, namespace: str) -> Path:
    if base_path.suffix:
        return base_path.with_name(f"{base_path.stem}-{namespace}{base_path.suffix}")
    return Path(f"{base_path}-{namespace}.duckdb")


def _seed_object_store_from_root(
    *,
    client: InMemoryS3Client,
    bucket: str,
    prefix: str,
    root: Path,
) -> None:
    if not root.exists() or not root.is_dir():
        return

    normalized_prefix = prefix.rstrip("/")
    for file_path in sorted(path for path in root.rglob("*") if path.is_file()):
        relative_path = file_path.relative_to(root).as_posix()
        object_key = f"{normalized_prefix}/{relative_path}" if normalized_prefix else relative_path
        body = file_path.read_bytes()
        client.put_object(
            bucket=bucket,
            key=object_key,
            body=body,
            metadata={"sha1": hashlib.sha1(body).hexdigest()},
        )
