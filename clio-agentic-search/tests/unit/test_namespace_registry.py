from __future__ import annotations

from pathlib import Path

import pytest

from clio_agentic_search.connectors.filesystem import FilesystemConnector
from clio_agentic_search.core.namespace_registry import NamespaceRegistry, build_default_registry
from clio_agentic_search.storage import DuckDBStorage


def test_default_registry_registers_local_namespace(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    local_root = tmp_path / "local"
    object_root = tmp_path / "object"
    local_root.mkdir()
    object_root.mkdir()
    monkeypatch.setenv("CLIO_LOCAL_ROOT", str(local_root))
    monkeypatch.setenv("CLIO_OBJECT_STORE_ROOT", str(object_root))
    monkeypatch.setenv("CLIO_OBJECT_ENDPOINT", "http://s3.example.local")
    monkeypatch.setenv("CLIO_STORAGE_PATH", str(tmp_path / "registry.duckdb"))
    registry = build_default_registry()

    assert "local_fs" in registry
    assert "object_s3" in registry
    assert "vector_qdrant" in registry
    assert "graph_neo4j" not in registry
    assert "kv_redis" not in registry
    connector = registry.connect("local_fs")
    assert connector.descriptor().connector_type == "filesystem"
    assert registry.is_connected("local_fs")
    object_connector = registry.connect("object_s3")
    assert object_connector.descriptor().root_uri.startswith("http://s3.example.local")
    registry.teardown("local_fs")
    registry.teardown("object_s3")


def test_register_duplicate_namespace_raises(tmp_path: Path) -> None:
    registry = NamespaceRegistry()
    connector = FilesystemConnector(
        namespace="local_fs",
        root=tmp_path,
        storage=DuckDBStorage(tmp_path / "duplicate.duckdb"),
    )
    registry.register("local_fs", connector)

    with pytest.raises(ValueError, match="already registered"):
        registry.register("local_fs", connector)
