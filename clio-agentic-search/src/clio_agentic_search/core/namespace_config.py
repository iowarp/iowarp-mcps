"""Namespace-scoped configuration and auth loading."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from clio_agentic_search.core.connectors import NamespaceAuthConfig, NamespaceRuntimeConfig


@dataclass(frozen=True, slots=True)
class NamespaceConfigBundle:
    namespace: str
    connector_type: str
    runtime: NamespaceRuntimeConfig
    auth: NamespaceAuthConfig | None = None


def load_default_namespace_bundles() -> dict[str, NamespaceConfigBundle]:
    local_root = Path(os.environ.get("CLIO_LOCAL_ROOT", ".")).resolve()
    object_root = Path(os.environ.get("CLIO_OBJECT_STORE_ROOT", local_root)).resolve()
    vector_collection = os.environ.get("CLIO_VECTOR_COLLECTION", "local_collection")
    graph_namespace = os.environ.get("CLIO_GRAPH_NAMESPACE", "graph_default")
    kv_stream = os.environ.get("CLIO_KV_STREAM", "events")
    hdf5_root = Path(os.environ.get("CLIO_HDF5_ROOT", local_root)).resolve()
    netcdf_root = Path(os.environ.get("CLIO_NETCDF_ROOT", local_root)).resolve()

    return {
        "local_fs": NamespaceConfigBundle(
            namespace="local_fs",
            connector_type="filesystem",
            runtime=NamespaceRuntimeConfig(options={"root": str(local_root)}),
        ),
        "object_s3": NamespaceConfigBundle(
            namespace="object_s3",
            connector_type="object_store",
            runtime=NamespaceRuntimeConfig(
                options={
                    "bucket": os.environ.get("CLIO_OBJECT_BUCKET", "local-bucket"),
                    "prefix": os.environ.get("CLIO_OBJECT_PREFIX", ""),
                    "root": str(object_root),
                    "endpoint_url": os.environ.get("CLIO_OBJECT_ENDPOINT", "http://localhost:9000"),
                }
            ),
            auth=_optional_auth(
                scheme="s3",
                mapping={
                    "access_key_id": "CLIO_OBJECT_ACCESS_KEY_ID",
                    "secret_access_key": "CLIO_OBJECT_SECRET_ACCESS_KEY",
                    "session_token": "CLIO_OBJECT_SESSION_TOKEN",
                },
            ),
        ),
        "vector_qdrant": NamespaceConfigBundle(
            namespace="vector_qdrant",
            connector_type="vector_store",
            runtime=NamespaceRuntimeConfig(
                options={
                    "collection": vector_collection,
                    "url": os.environ.get("CLIO_QDRANT_URL", "http://localhost:6333"),
                }
            ),
            auth=_optional_auth(
                scheme="qdrant_api_key",
                mapping={"api_key": "CLIO_QDRANT_API_KEY"},
            ),
        ),
        "graph_neo4j": NamespaceConfigBundle(
            namespace="graph_neo4j",
            connector_type="graph_store",
            runtime=NamespaceRuntimeConfig(
                options={
                    "database": graph_namespace,
                    "uri": os.environ.get("CLIO_NEO4J_URI", "bolt://localhost:7687"),
                }
            ),
            auth=_optional_auth(
                scheme="neo4j_basic",
                mapping={
                    "username": "CLIO_NEO4J_USERNAME",
                    "password": "CLIO_NEO4J_PASSWORD",
                },
            ),
        ),
        "hdf5_data": NamespaceConfigBundle(
            namespace="hdf5_data",
            connector_type="hdf5",
            runtime=NamespaceRuntimeConfig(options={"root": str(hdf5_root)}),
        ),
        "netcdf_data": NamespaceConfigBundle(
            namespace="netcdf_data",
            connector_type="netcdf",
            runtime=NamespaceRuntimeConfig(options={"root": str(netcdf_root)}),
        ),
        "kv_redis": NamespaceConfigBundle(
            namespace="kv_redis",
            connector_type="kv_log_store",
            runtime=NamespaceRuntimeConfig(
                options={
                    "stream": kv_stream,
                    "url": os.environ.get("CLIO_REDIS_URL", "redis://localhost:6379/0"),
                }
            ),
            auth=_optional_auth(
                scheme="redis_password",
                mapping={"password": "CLIO_REDIS_PASSWORD"},
            ),
        ),
    }


def _optional_auth(scheme: str, mapping: dict[str, str]) -> NamespaceAuthConfig | None:
    values: dict[str, str] = {}
    for field_name, env_name in mapping.items():
        value = os.environ.get(env_name)
        if value:
            values[field_name] = value
    if not values:
        return None
    return NamespaceAuthConfig(scheme=scheme, values=values)
