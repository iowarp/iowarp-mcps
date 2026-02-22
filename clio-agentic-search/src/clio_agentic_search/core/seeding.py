"""Explicit demo/data seeding helpers for connectors."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from clio_agentic_search.connectors.filesystem import FilesystemConnector
from clio_agentic_search.connectors.graph_store import GraphEdge, GraphNode, Neo4jGraphConnector
from clio_agentic_search.connectors.kv_log_store import RedisLogConnector
from clio_agentic_search.connectors.object_store import S3ObjectStoreConnector
from clio_agentic_search.connectors.vector_store import QdrantVectorConnector, VectorPoint


@dataclass(frozen=True, slots=True)
class SeedReport:
    namespace: str
    records_seeded: int
    detail: str


def seed_connector(connector: object) -> SeedReport:
    if isinstance(connector, FilesystemConnector):
        return _seed_filesystem(connector)
    if isinstance(connector, S3ObjectStoreConnector):
        return _seed_object_store(connector)
    if isinstance(connector, QdrantVectorConnector):
        return _seed_vector_store(connector)
    if isinstance(connector, Neo4jGraphConnector):
        return _seed_graph_store(connector)
    if isinstance(connector, RedisLogConnector):
        return _seed_kv_log_store(connector)

    return SeedReport(
        namespace=getattr(connector, "namespace", "unknown"),
        records_seeded=0,
        detail="no seeding routine available",
    )


def _seed_filesystem(connector: FilesystemConnector) -> SeedReport:
    connector.root.mkdir(parents=True, exist_ok=True)
    seed_file = connector.root / "seed-local.txt"
    seed_file.write_text(
        "seeded filesystem document for clio phase workflow",
        encoding="utf-8",
    )
    return SeedReport(
        namespace=connector.namespace,
        records_seeded=1,
        detail=f"wrote {seed_file}",
    )


def _seed_object_store(connector: S3ObjectStoreConnector) -> SeedReport:
    runtime_root = connector._runtime_config.options.get("root", "")  # noqa: SLF001
    if runtime_root:
        root_path = Path(runtime_root)
        root_path.mkdir(parents=True, exist_ok=True)
        seed_file = root_path / "seed-object.txt"
        seed_file.write_text(
            "seeded object store document for clio phase workflow",
            encoding="utf-8",
        )
        return SeedReport(
            namespace=connector.namespace,
            records_seeded=1,
            detail=f"wrote {seed_file}",
        )

    return SeedReport(
        namespace=connector.namespace,
        records_seeded=0,
        detail="missing runtime root for object store seeding",
    )


def _seed_vector_store(connector: QdrantVectorConnector) -> SeedReport:
    text = "seeded vector retrieval record for clio phase workflow"
    connector.seed_points(
        [
            VectorPoint(
                chunk_id="seed-vector-1",
                document_id="seed-vector-doc-1",
                uri="qdrant://seed/seed-vector-doc-1",
                text=text,
                vector=connector.embedder.embed(text),
                metadata={"seed": "true"},
            )
        ]
    )
    return SeedReport(
        namespace=connector.namespace,
        records_seeded=1,
        detail="seeded in-memory vector point",
    )


def _seed_graph_store(connector: Neo4jGraphConnector) -> SeedReport:
    connector.seed_graph(
        nodes=[
            GraphNode(
                node_id="seed-graph-1",
                document_id="seed-graph-doc-1",
                uri="neo4j://seed/seed-graph-doc-1",
                text="seeded graph node for clio phase workflow",
                metadata={"seed": "true"},
            ),
            GraphNode(
                node_id="seed-graph-2",
                document_id="seed-graph-doc-2",
                uri="neo4j://seed/seed-graph-doc-2",
                text="neighbor graph node",
                metadata={"seed": "true"},
            ),
        ],
        edges=[GraphEdge(source_id="seed-graph-1", target_id="seed-graph-2")],
    )
    return SeedReport(
        namespace=connector.namespace,
        records_seeded=2,
        detail="seeded in-memory graph nodes/edges",
    )


def _seed_kv_log_store(connector: RedisLogConnector) -> SeedReport:
    connector.append_log(
        "seeded kv-log entry for clio phase workflow",
        metadata={"seed": "true"},
    )
    return SeedReport(
        namespace=connector.namespace,
        records_seeded=1,
        detail="seeded in-memory log record",
    )
