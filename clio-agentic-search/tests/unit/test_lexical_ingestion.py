"""Tests for lexical postings ingestion and pruning behavior."""

from __future__ import annotations

from pathlib import Path

from clio_agentic_search.connectors.filesystem import FilesystemConnector
from clio_agentic_search.connectors.object_store import InMemoryS3Client, S3ObjectStoreConnector
from clio_agentic_search.storage import DuckDBStorage


def test_filesystem_prunes_stopwords_and_high_df_tokens(tmp_path: Path) -> None:
    docs = tmp_path / "docs"
    docs.mkdir()
    (docs / "a.txt").write_text("the common alpha", encoding="utf-8")
    (docs / "b.txt").write_text("the common beta", encoding="utf-8")
    (docs / "c.txt").write_text("the common gamma", encoding="utf-8")

    storage = DuckDBStorage(tmp_path / "lexical-fs.duckdb")
    connector = FilesystemConnector(
        namespace="fs",
        root=docs,
        storage=storage,
        lexical_df_prune_min_chunks=1,
        lexical_df_prune_threshold=0.8,
        lexical_batch_size=2,
    )
    connector.connect()
    try:
        connector.index(full_rebuild=True)
        assert connector.search_lexical("common", top_k=5) == []
        assert connector.search_lexical("the", top_k=5) == []

        alpha_hits = connector.search_lexical("alpha", top_k=5)
        assert len(alpha_hits) == 1
        assert "alpha" in alpha_hits[0].text
    finally:
        connector.teardown()


def test_filesystem_gzip_postings_spool_works(tmp_path: Path) -> None:
    docs = tmp_path / "docs-gzip"
    docs.mkdir()
    (docs / "a.txt").write_text("delta epsilon zeta", encoding="utf-8")

    storage = DuckDBStorage(tmp_path / "lexical-gzip.duckdb")
    connector = FilesystemConnector(
        namespace="fs-gzip",
        root=docs,
        storage=storage,
        lexical_postings_compression="gzip",
        lexical_df_prune_min_chunks=10,
        lexical_batch_size=1,
    )
    connector.connect()
    try:
        connector.index(full_rebuild=True)
        hits = connector.search_lexical("epsilon", top_k=5)
        assert len(hits) == 1
    finally:
        connector.teardown()


def test_object_store_uses_same_pruning_pipeline(tmp_path: Path) -> None:
    client = InMemoryS3Client()
    client.put_object(bucket="bucket", key="docs/a.txt", body=b"the common alpha")
    client.put_object(bucket="bucket", key="docs/b.txt", body=b"the common beta")
    client.put_object(bucket="bucket", key="docs/c.txt", body=b"the common gamma")

    storage = DuckDBStorage(tmp_path / "lexical-s3.duckdb")
    connector = S3ObjectStoreConnector(
        namespace="s3",
        bucket="bucket",
        prefix="docs/",
        storage=storage,
        client=client,
        lexical_df_prune_min_chunks=1,
        lexical_df_prune_threshold=0.8,
        lexical_batch_size=2,
    )
    connector.connect()
    try:
        connector.index(full_rebuild=True)
        assert connector.search_lexical("common", top_k=5) == []
        assert connector.search_lexical("the", top_k=5) == []
        assert len(connector.search_lexical("beta", top_k=5)) == 1
    finally:
        connector.teardown()


def test_token_cap_keeps_highest_frequency_terms(tmp_path: Path) -> None:
    docs = tmp_path / "docs-cap"
    docs.mkdir()
    (docs / "a.txt").write_text("alpha alpha alpha beta gamma", encoding="utf-8")

    storage = DuckDBStorage(tmp_path / "lexical-cap.duckdb")
    connector = FilesystemConnector(
        namespace="fs-cap",
        root=docs,
        storage=storage,
        lexical_max_tokens_per_chunk=1,
        lexical_df_prune_min_chunks=10,
    )
    connector.connect()
    try:
        connector.index(full_rebuild=True)
        assert len(connector.search_lexical("alpha", top_k=5)) == 1
        assert connector.search_lexical("beta", top_k=5) == []
        assert connector.search_lexical("gamma", top_k=5) == []
    finally:
        connector.teardown()
