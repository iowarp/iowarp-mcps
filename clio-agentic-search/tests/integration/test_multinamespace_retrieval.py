from __future__ import annotations

from pathlib import Path

import pytest

from clio_agentic_search.connectors.graph_store import (
    GraphEdge,
    GraphNode,
    InMemoryNeo4jClient,
    Neo4jGraphConnector,
)
from clio_agentic_search.connectors.kv_log_store import (
    InMemoryRedisStreamClient,
    RedisLogConnector,
    StreamLogEntry,
)
from clio_agentic_search.core.namespace_registry import NamespaceRegistry, build_default_registry
from clio_agentic_search.retrieval.coordinator import RetrievalCoordinator


def test_composed_query_across_filesystem_and_object_store(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    local_root = tmp_path / "local"
    object_root = tmp_path / "object"
    local_root.mkdir()
    object_root.mkdir()
    (local_root / "local.txt").write_text("phase two filesystem content", encoding="utf-8")
    (object_root / "remote.txt").write_text("phase two object content", encoding="utf-8")

    monkeypatch.setenv("CLIO_LOCAL_ROOT", str(local_root))
    monkeypatch.setenv("CLIO_OBJECT_STORE_ROOT", str(object_root))
    monkeypatch.setenv("CLIO_STORAGE_PATH", str(tmp_path / "multi.duckdb"))

    registry = build_default_registry()
    connectors = [registry.connect("local_fs"), registry.connect("object_s3")]
    for connector in connectors:
        connector.index(full_rebuild=True)

    result = RetrievalCoordinator().query_namespaces(
        connectors=connectors,
        query="phase two content",
        top_k=5,
    )

    assert {citation.namespace for citation in result.citations} == {"local_fs", "object_s3"}
    assert result.trace[0].stage == "multi_query_started"
    assert result.trace[-1].stage == "multi_query_completed"
    registry.teardown()


def test_capability_negotiation_uses_graph_and_log_capabilities() -> None:
    graph_client = InMemoryNeo4jClient()
    log_client = InMemoryRedisStreamClient()

    graph_connector = Neo4jGraphConnector(
        namespace="graph_neo4j",
        database="phase2",
        client=graph_client,
    )
    graph_connector.seed_graph(
        nodes=[
            GraphNode(
                node_id="graph-1",
                document_id="graph-doc-1",
                uri="neo4j://phase2/graph-doc-1",
                text="phase two graph node",
                metadata={"kind": "graph"},
            ),
            GraphNode(
                node_id="graph-2",
                document_id="graph-doc-2",
                uri="neo4j://phase2/graph-doc-2",
                text="connected graph neighbor",
                metadata={"kind": "graph"},
            ),
        ],
        edges=[GraphEdge(source_id="graph-1", target_id="graph-2")],
    )

    log_client.append(
        "events",
        StreamLogEntry(
            entry_id="log-1",
            message="phase two log record",
            metadata={"severity": "info"},
        ),
    )
    kv_connector = RedisLogConnector(namespace="kv_redis", stream="events", client=log_client)

    registry = NamespaceRegistry()
    registry.register("graph_neo4j", graph_connector)
    registry.register("kv_redis", kv_connector)
    connectors = [registry.connect("graph_neo4j"), registry.connect("kv_redis")]
    for connector in connectors:
        connector.index(full_rebuild=True)

    result = RetrievalCoordinator().query_namespaces(
        connectors=connectors,
        query="phase two",
        top_k=5,
    )

    assert {citation.namespace for citation in result.citations} >= {"graph_neo4j", "kv_redis"}
    assert any(
        event.stage == "graph_completed" and event.attributes.get("namespace") == "graph_neo4j"
        for event in result.trace
    )
    assert any(
        event.stage == "log_stream_completed" and event.attributes.get("namespace") == "kv_redis"
        for event in result.trace
    )
    registry.teardown()
