"""Reusable text processing utilities for connectors."""

from __future__ import annotations

import hashlib
import math
import re
from typing import Any, Protocol

TOKEN_PATTERN = re.compile(r"[a-zA-Z0-9_]+")


def tokenize(text: str) -> list[str]:
    return [token.lower() for token in TOKEN_PATTERN.findall(text)]


def embed_text(text: str, dimensions: int = 16) -> tuple[float, ...]:
    tokens = tokenize(text)
    vector = [0.0] * dimensions
    for token in tokens:
        index = int(hashlib.sha256(token.encode("utf-8")).hexdigest(), 16) % dimensions
        vector[index] += 1.0

    norm = math.sqrt(sum(component * component for component in vector))
    if norm == 0.0:
        return tuple(vector)
    return tuple(component / norm for component in vector)


def cosine_similarity(left: tuple[float, ...], right: tuple[float, ...]) -> float:
    if len(left) != len(right):
        return 0.0
    return sum(left[index] * right[index] for index in range(len(left)))


class Embedder(Protocol):
    @property
    def model_name(self) -> str: ...

    @property
    def dimensions(self) -> int: ...

    def embed(self, text: str) -> tuple[float, ...]: ...


class HashEmbedder:
    @property
    def model_name(self) -> str:
        return "hash16-v1"

    @property
    def dimensions(self) -> int:
        return 16

    def embed(self, text: str) -> tuple[float, ...]:
        return embed_text(text, dimensions=self.dimensions)


class SentenceTransformerEmbedder:
    def __init__(self, model_name: str = "all-MiniLM-L6-v2") -> None:
        self._model_name = model_name
        self._model: Any = None

    @property
    def model_name(self) -> str:
        return self._model_name

    @property
    def dimensions(self) -> int:
        return 384

    def embed(self, text: str) -> tuple[float, ...]:
        if self._model is None:
            try:
                from sentence_transformers import SentenceTransformer  # noqa: I001
            except ImportError as exc:
                raise ImportError(
                    "sentence-transformers is required for SentenceTransformerEmbedder. "
                    "Install with: pip install 'clio-agentic-search[semantic]'"
                ) from exc
            self._model = SentenceTransformer(self._model_name)
        vector = self._model.encode(text)
        return tuple(float(v) for v in vector)
