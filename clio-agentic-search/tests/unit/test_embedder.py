"""Tests for R1: pluggable embedding model."""

from __future__ import annotations

from clio_agentic_search.indexing.text_features import (
    HashEmbedder,
    SentenceTransformerEmbedder,
    embed_text,
)


def test_hash_embedder_matches_embed_text() -> None:
    embedder = HashEmbedder()
    text = "test sentence for embedding"
    assert embedder.embed(text) == embed_text(text)


def test_hash_embedder_properties() -> None:
    embedder = HashEmbedder()
    assert embedder.model_name == "hash16-v1"
    assert embedder.dimensions == 16


def test_sentence_transformer_raises_clear_import_error() -> None:
    embedder = SentenceTransformerEmbedder()
    assert embedder.model_name == "all-MiniLM-L6-v2"
    assert embedder.dimensions == 384
    try:
        embedder.embed("test")
    except ImportError as exc:
        assert "sentence-transformers" in str(exc)
    else:
        # If sentence-transformers IS installed, embedding should succeed
        pass


def test_connector_uses_custom_embedder() -> None:
    """Verify connector uses its embedder field, not the global embed_text."""
    from pathlib import Path
    from unittest.mock import MagicMock

    from clio_agentic_search.connectors.filesystem import FilesystemConnector

    mock_embedder = MagicMock()
    mock_embedder.embed.return_value = tuple([0.5] * 16)
    mock_embedder.model_name = "mock-v1"
    mock_embedder.dimensions = 16

    connector = FilesystemConnector(
        namespace="test",
        root=Path("/nonexistent"),
        storage=MagicMock(),
        embedder=mock_embedder,
    )
    # search_vector calls self.embedder.embed()
    connector._connected = True
    connector.storage.list_embeddings.return_value = {}
    connector.storage.list_chunks.return_value = []
    connector.search_vector("query", top_k=3)
    mock_embedder.embed.assert_called_once_with("query")
