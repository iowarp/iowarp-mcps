"""DuckDB-backed local persistence."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import duckdb

from clio_agentic_search.models.contracts import (
    ChunkRecord,
    DocumentRecord,
    EmbeddingRecord,
    MetadataRecord,
)
from clio_agentic_search.storage.contracts import FileIndexState


class DuckDBStorage:
    def __init__(self, database_path: Path) -> None:
        self._database_path = database_path
        self._connection: duckdb.DuckDBPyConnection | None = None

    def connect(self) -> None:
        self._database_path.parent.mkdir(parents=True, exist_ok=True)
        self._connection = duckdb.connect(str(self._database_path))
        connection = self._require_connection()
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS documents (
                namespace TEXT,
                document_id TEXT,
                uri TEXT,
                checksum TEXT,
                modified_at_ns BIGINT,
                PRIMARY KEY (namespace, document_id)
            )
            """
        )
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS chunks (
                namespace TEXT,
                chunk_id TEXT,
                document_id TEXT,
                chunk_index INTEGER,
                text TEXT,
                start_offset INTEGER,
                end_offset INTEGER,
                PRIMARY KEY (namespace, chunk_id)
            )
            """
        )
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS embeddings (
                namespace TEXT,
                chunk_id TEXT,
                model TEXT,
                vector_json TEXT,
                PRIMARY KEY (namespace, chunk_id, model)
            )
            """
        )
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS metadata (
                namespace TEXT,
                record_id TEXT,
                scope TEXT,
                key TEXT,
                value TEXT,
                PRIMARY KEY (namespace, record_id, scope, key)
            )
            """
        )
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS file_index (
                namespace TEXT,
                path TEXT,
                document_id TEXT,
                mtime_ns BIGINT,
                content_hash TEXT,
                PRIMARY KEY (namespace, path)
            )
            """
        )

    def teardown(self) -> None:
        if self._connection is not None:
            self._connection.close()
            self._connection = None

    def clear_namespace(self, namespace: str) -> None:
        connection = self._require_connection()
        connection.execute("DELETE FROM embeddings WHERE namespace = ?", [namespace])
        connection.execute("DELETE FROM metadata WHERE namespace = ?", [namespace])
        connection.execute("DELETE FROM chunks WHERE namespace = ?", [namespace])
        connection.execute("DELETE FROM documents WHERE namespace = ?", [namespace])
        connection.execute("DELETE FROM file_index WHERE namespace = ?", [namespace])

    def upsert_document_bundle(
        self,
        document: DocumentRecord,
        chunks: list[ChunkRecord],
        embeddings: list[EmbeddingRecord],
        metadata: list[MetadataRecord],
        file_state: FileIndexState,
    ) -> None:
        connection = self._require_connection()
        self._delete_document(document.namespace, document.document_id)

        connection.execute(
            """
            INSERT OR REPLACE INTO documents(namespace, document_id, uri, checksum, modified_at_ns)
            VALUES (?, ?, ?, ?, ?)
            """,
            [
                document.namespace,
                document.document_id,
                document.uri,
                document.checksum,
                document.modified_at_ns,
            ],
        )

        if chunks:
            connection.executemany(
                """
                INSERT OR REPLACE INTO chunks(
                    namespace, chunk_id, document_id, chunk_index, text, start_offset, end_offset
                )
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                [
                    (
                        chunk.namespace,
                        chunk.chunk_id,
                        chunk.document_id,
                        chunk.chunk_index,
                        chunk.text,
                        chunk.start_offset,
                        chunk.end_offset,
                    )
                    for chunk in chunks
                ],
            )

        if embeddings:
            connection.executemany(
                """
                INSERT OR REPLACE INTO embeddings(namespace, chunk_id, model, vector_json)
                VALUES (?, ?, ?, ?)
                """,
                [
                    (
                        embedding.namespace,
                        embedding.chunk_id,
                        embedding.model,
                        json.dumps(list(embedding.vector)),
                    )
                    for embedding in embeddings
                ],
            )

        if metadata:
            connection.executemany(
                """
                INSERT OR REPLACE INTO metadata(namespace, record_id, scope, key, value)
                VALUES (?, ?, ?, ?, ?)
                """,
                [
                    (
                        metadata_item.namespace,
                        metadata_item.record_id,
                        metadata_item.scope,
                        metadata_item.key,
                        metadata_item.value,
                    )
                    for metadata_item in metadata
                ],
            )

        connection.execute(
            """
            INSERT OR REPLACE INTO file_index(namespace, path, document_id, mtime_ns, content_hash)
            VALUES (?, ?, ?, ?, ?)
            """,
            [
                file_state.namespace,
                file_state.path,
                file_state.document_id,
                file_state.mtime_ns,
                file_state.content_hash,
            ],
        )

    def get_file_state(self, namespace: str, path: str) -> FileIndexState | None:
        connection = self._require_connection()
        row = connection.execute(
            """
            SELECT namespace, path, document_id, mtime_ns, content_hash
            FROM file_index
            WHERE namespace = ? AND path = ?
            """,
            [namespace, path],
        ).fetchone()

        if row is None:
            return None

        namespace_value, path_value, document_id, mtime_ns, content_hash = row
        return FileIndexState(
            namespace=str(namespace_value),
            path=str(path_value),
            document_id=str(document_id),
            mtime_ns=int(mtime_ns),
            content_hash=str(content_hash),
        )

    def remove_missing_paths(self, namespace: str, existing_paths: set[str]) -> int:
        connection = self._require_connection()
        rows = connection.execute(
            "SELECT path, document_id FROM file_index WHERE namespace = ?",
            [namespace],
        ).fetchall()

        removed_count = 0
        for path_value, document_id in rows:
            path_str = str(path_value)
            if path_str in existing_paths:
                continue
            self._delete_document(namespace, str(document_id))
            connection.execute(
                "DELETE FROM file_index WHERE namespace = ? AND path = ?",
                [namespace, path_str],
            )
            removed_count += 1

        return removed_count

    def list_chunks(self, namespace: str) -> list[ChunkRecord]:
        connection = self._require_connection()
        rows = connection.execute(
            """
            SELECT namespace, chunk_id, document_id, chunk_index, text, start_offset, end_offset
            FROM chunks
            WHERE namespace = ?
            ORDER BY chunk_id
            """,
            [namespace],
        ).fetchall()

        return [self._row_to_chunk_record(row) for row in rows]

    def list_embeddings(self, namespace: str, model: str) -> dict[str, tuple[float, ...]]:
        connection = self._require_connection()
        rows = connection.execute(
            """
            SELECT chunk_id, vector_json
            FROM embeddings
            WHERE namespace = ? AND model = ?
            ORDER BY chunk_id
            """,
            [namespace, model],
        ).fetchall()

        vectors: dict[str, tuple[float, ...]] = {}
        for chunk_id, vector_json in rows:
            vector_list = json.loads(str(vector_json))
            if not isinstance(vector_list, list):
                continue
            vectors[str(chunk_id)] = tuple(float(component) for component in vector_list)
        return vectors

    def get_chunk(self, namespace: str, chunk_id: str) -> ChunkRecord:
        connection = self._require_connection()
        row = connection.execute(
            """
            SELECT namespace, chunk_id, document_id, chunk_index, text, start_offset, end_offset
            FROM chunks
            WHERE namespace = ? AND chunk_id = ?
            """,
            [namespace, chunk_id],
        ).fetchone()
        if row is None:
            raise KeyError(f"Missing chunk '{chunk_id}' in namespace '{namespace}'")
        return self._row_to_chunk_record(row)

    def get_chunk_metadata(self, namespace: str, chunk_id: str) -> dict[str, str]:
        connection = self._require_connection()
        rows = connection.execute(
            """
            SELECT key, value
            FROM metadata
            WHERE namespace = ? AND scope = 'chunk' AND record_id = ?
            ORDER BY key
            """,
            [namespace, chunk_id],
        ).fetchall()
        return {str(key): str(value) for key, value in rows}

    def get_document_uri(self, namespace: str, document_id: str) -> str:
        connection = self._require_connection()
        row = connection.execute(
            """
            SELECT uri
            FROM documents
            WHERE namespace = ? AND document_id = ?
            """,
            [namespace, document_id],
        ).fetchone()
        if row is None:
            raise KeyError(f"Missing document '{document_id}' in namespace '{namespace}'")
        return str(row[0])

    def _delete_document(self, namespace: str, document_id: str) -> None:
        connection = self._require_connection()
        connection.execute(
            """
            DELETE FROM embeddings
            WHERE namespace = ?
            AND chunk_id IN (
                SELECT chunk_id FROM chunks WHERE namespace = ? AND document_id = ?
            )
            """,
            [namespace, namespace, document_id],
        )
        connection.execute(
            """
            DELETE FROM metadata
            WHERE namespace = ? AND scope = 'chunk'
            AND record_id IN (
                SELECT chunk_id FROM chunks WHERE namespace = ? AND document_id = ?
            )
            """,
            [namespace, namespace, document_id],
        )
        connection.execute(
            "DELETE FROM chunks WHERE namespace = ? AND document_id = ?",
            [namespace, document_id],
        )
        connection.execute(
            """
            DELETE FROM metadata
            WHERE namespace = ? AND scope = 'document' AND record_id = ?
            """,
            [namespace, document_id],
        )
        connection.execute(
            "DELETE FROM documents WHERE namespace = ? AND document_id = ?",
            [namespace, document_id],
        )

    def _require_connection(self) -> duckdb.DuckDBPyConnection:
        if self._connection is None:
            raise RuntimeError("Storage is not connected")
        return self._connection

    @staticmethod
    def _row_to_chunk_record(row: tuple[Any, ...]) -> ChunkRecord:
        namespace, chunk_id, document_id, chunk_index, text, start_offset, end_offset = row
        return ChunkRecord(
            namespace=str(namespace),
            chunk_id=str(chunk_id),
            document_id=str(document_id),
            chunk_index=int(chunk_index),
            text=str(text),
            start_offset=int(start_offset),
            end_offset=int(end_offset),
        )
