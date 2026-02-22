"""Reusable text processing utilities for connectors."""

from __future__ import annotations

import hashlib
import math
import re

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
