"""Lexical postings ingestion utilities for scalable indexing."""

from __future__ import annotations

import gzip
import tempfile
from collections import Counter
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path
from typing import TextIO

from clio_agentic_search.indexing.text_features import tokenize
from clio_agentic_search.models.contracts import ChunkRecord
from clio_agentic_search.storage.contracts import StorageAdapter

DEFAULT_STOPWORDS: frozenset[str] = frozenset(
    {
        "a",
        "an",
        "and",
        "are",
        "as",
        "at",
        "be",
        "by",
        "for",
        "from",
        "has",
        "he",
        "in",
        "is",
        "it",
        "its",
        "of",
        "on",
        "that",
        "the",
        "to",
        "was",
        "were",
        "will",
        "with",
    }
)


@dataclass(frozen=True, slots=True)
class LexicalIngestionConfig:
    batch_size: int = 50_000
    df_prune_threshold: float = 0.98
    df_prune_min_chunks: int = 200
    max_tokens_per_chunk: int = 96
    prune_stopwords: bool = True
    stopwords: frozenset[str] = DEFAULT_STOPWORDS
    postings_compression: str = "none"


class LexicalPostingsIngestor:
    """Streams chunk postings through a temporary spool to keep memory bounded."""

    def __init__(self, config: LexicalIngestionConfig) -> None:
        self._config = config
        self._df_counter: Counter[str] = Counter()
        self._chunk_count = 0
        self._tmp_path = self._new_tmp_path(config.postings_compression)
        self._writer = self._open_writer(self._tmp_path, config.postings_compression)
        self._closed = False

    def add_chunks(self, chunks: list[ChunkRecord]) -> None:
        for chunk in chunks:
            self._add_chunk(chunk)

    def flush(self, *, namespace: str, storage: StorageAdapter) -> None:
        if self._closed:
            return
        self._writer.close()
        self._closed = True
        blocked_tokens = self._blocked_tokens()
        posting_rows = self._iter_postings(blocked_tokens)
        storage.upsert_lexical_postings_stream(
            namespace,
            posting_rows,
            batch_size=max(1, self._config.batch_size),
        )
        self._cleanup()

    def close(self) -> None:
        if not self._closed:
            self._writer.close()
            self._closed = True
        self._cleanup()

    def _add_chunk(self, chunk: ChunkRecord) -> None:
        frequencies = Counter(tokenize(chunk.text))
        if self._config.prune_stopwords:
            for stopword in self._config.stopwords:
                frequencies.pop(stopword, None)
        filtered: Counter[str] = Counter(
            {
                token: freq
                for token, freq in frequencies.items()
                if token and len(token) > 1 and not token.isnumeric()
            }
        )
        if (
            self._config.max_tokens_per_chunk > 0
            and len(filtered) > self._config.max_tokens_per_chunk
        ):
            selected = sorted(filtered.items(), key=lambda item: (-item[1], item[0]))[
                : self._config.max_tokens_per_chunk
            ]
            filtered = Counter(dict(selected))
        if not filtered:
            return
        self._chunk_count += 1
        self._df_counter.update(filtered.keys())
        for token, term_freq in filtered.items():
            self._writer.write(f"{chunk.chunk_id}\t{token}\t{int(term_freq)}\n")

    def _blocked_tokens(self) -> frozenset[str]:
        if self._chunk_count < self._config.df_prune_min_chunks:
            return frozenset()
        threshold = self._config.df_prune_threshold
        blocked = {
            token for token, df in self._df_counter.items() if (df / self._chunk_count) >= threshold
        }
        return frozenset(blocked)

    def _iter_postings(self, blocked_tokens: frozenset[str]) -> Iterator[tuple[str, str, int]]:
        reader = self._open_reader(self._tmp_path, self._config.postings_compression)
        with reader:
            for line in reader:
                row = line.rstrip("\n")
                if not row:
                    continue
                chunk_id, token, freq = row.split("\t", maxsplit=2)
                if token in blocked_tokens:
                    continue
                yield (chunk_id, token, int(freq))

    def _cleanup(self) -> None:
        if self._tmp_path.exists():
            self._tmp_path.unlink()

    @staticmethod
    def _new_tmp_path(mode: str) -> Path:
        suffix = ".lexical.tsv.gz" if mode == "gzip" else ".lexical.tsv"
        handle = tempfile.NamedTemporaryFile(prefix="clio-", suffix=suffix, delete=False)
        handle.close()
        return Path(handle.name)

    @staticmethod
    def _open_writer(path: Path, mode: str) -> TextIO:
        if mode == "gzip":
            return gzip.open(path, "wt", encoding="utf-8")
        return path.open("w", encoding="utf-8")

    @staticmethod
    def _open_reader(path: Path, mode: str) -> TextIO:
        if mode == "gzip":
            return gzip.open(path, "rt", encoding="utf-8")
        return path.open("r", encoding="utf-8")
