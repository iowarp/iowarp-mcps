"""File-backed, reloadable scientific catalog implementation."""

from __future__ import annotations

import base64
import json
import threading
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from pydantic import ValidationError

from .models import (
    DatasetDescribeResult,
    DatasetSearchResult,
    ScientificCatalog,
    canonical_sha256,
    summary_of,
)

_MAX_CATALOG_BYTES = 16 * 1024 * 1024


class CatalogError(RuntimeError):
    """Raised when a site catalog cannot satisfy an agent request."""


@dataclass(frozen=True, slots=True)
class _LoadedCatalog:
    catalog: ScientificCatalog
    file_identity: tuple[int, int]


class CatalogStore:
    """Load, validate, and atomically refresh one operator catalog file."""

    def __init__(self, path: Path) -> None:
        try:
            self._path = path.expanduser().resolve(strict=True)
        except (OSError, RuntimeError) as exc:
            raise CatalogError(f"scientific catalog does not exist: {path}") from exc
        if not self._path.is_file():
            raise CatalogError(f"scientific catalog is not a file: {self._path}")
        self._lock = threading.Lock()
        self._loaded: _LoadedCatalog | None = None

    def search(
        self,
        *,
        query: str | None = None,
        tags: list[str] | None = None,
        kind: str | None = None,
        format: str | None = None,
        cursor: str | None = None,
        page_size: int = 20,
    ) -> DatasetSearchResult:
        """Search intrinsic discovery metadata with digest-bound pagination."""
        if not 1 <= page_size <= 100:
            raise CatalogError("page_size must be between 1 and 100")
        loaded = self._load()
        catalog = loaded.catalog
        offset = self._decode_cursor(cursor, catalog.canonical_digest)
        terms = tuple(item for item in (query or "").casefold().split() if item)
        requested_tags = {tag.strip().casefold() for tag in tags or [] if tag.strip()}
        matches = []
        for dataset in sorted(catalog.datasets, key=lambda item: item.dataset_id):
            searchable = " ".join(
                (dataset.dataset_id, dataset.title, dataset.summary, *dataset.tags)
            ).casefold()
            if terms and not all(term in searchable for term in terms):
                continue
            if requested_tags and not requested_tags.issubset(set(dataset.tags)):
                continue
            if kind is not None and dataset.descriptor.kind.casefold() != kind.casefold():
                continue
            if format is not None and dataset.descriptor.format.casefold() != format.casefold():
                continue
            matches.append(dataset)
        if offset > len(matches):
            raise CatalogError("catalog cursor offset exceeds the current result set")
        page = matches[offset : offset + page_size]
        next_offset = offset + len(page)
        next_cursor = (
            self._encode_cursor(catalog.canonical_digest, next_offset)
            if next_offset < len(matches)
            else None
        )
        return DatasetSearchResult(
            site_id=catalog.site_id,
            catalog_revision=catalog.revision,
            catalog_sha256=catalog.canonical_digest,
            datasets=[summary_of(dataset) for dataset in page],
            total_matches=len(matches),
            next_cursor=next_cursor,
        )

    def describe(self, dataset_id: str) -> DatasetDescribeResult:
        """Return one exact catalog record by stable identity."""
        catalog = self._load().catalog
        match = next(
            (dataset for dataset in catalog.datasets if dataset.dataset_id == dataset_id),
            None,
        )
        if match is None:
            raise CatalogError(f"scientific dataset not found: {dataset_id}")
        return DatasetDescribeResult(
            site_id=catalog.site_id,
            catalog_revision=catalog.revision,
            catalog_sha256=catalog.canonical_digest,
            dataset=match,
            dataset_descriptor=match.descriptor,
            descriptor_sha256=match.descriptor.canonical_digest,
        )

    def _load(self) -> _LoadedCatalog:
        with self._lock:
            try:
                stat = self._path.stat()
            except OSError as exc:
                raise CatalogError(f"could not stat scientific catalog: {exc}") from exc
            identity = (stat.st_mtime_ns, stat.st_size)
            if self._loaded is not None and self._loaded.file_identity == identity:
                return self._loaded
            if stat.st_size > _MAX_CATALOG_BYTES:
                raise CatalogError("scientific catalog exceeds 16 MiB")
            try:
                payload = self._path.read_bytes()
            except OSError as exc:
                raise CatalogError(f"could not read scientific catalog: {exc}") from exc
            if len(payload) != stat.st_size:
                raise CatalogError("scientific catalog changed while being read; retry")
            try:
                raw = json.loads(payload.decode("utf-8"), object_pairs_hook=_unique_object)
            except (UnicodeDecodeError, json.JSONDecodeError, ValueError) as exc:
                raise CatalogError(
                    f"scientific catalog is not valid duplicate-free JSON: {exc}"
                ) from exc
            try:
                catalog = ScientificCatalog.model_validate(raw)
            except ValidationError as exc:
                raise CatalogError(f"scientific catalog contract validation failed: {exc}") from exc
            loaded = _LoadedCatalog(catalog, identity)
            self._loaded = loaded
            return loaded

    @staticmethod
    def _encode_cursor(catalog_sha256: str, offset: int) -> str:
        payload = {"catalog_sha256": catalog_sha256, "offset": offset}
        raw = json.dumps(payload, separators=(",", ":"), sort_keys=True).encode("utf-8")
        return base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")

    @staticmethod
    def _decode_cursor(cursor: str | None, catalog_sha256: str) -> int:
        if cursor is None:
            return 0
        try:
            padding = "=" * (-len(cursor) % 4)
            raw = base64.b64decode(cursor + padding, altchars=b"-_", validate=True)
            value = json.loads(raw.decode("utf-8"), object_pairs_hook=_unique_object)
        except (ValueError, UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise CatalogError("scientific dataset cursor is invalid") from exc
        if not isinstance(value, dict):
            raise CatalogError("scientific dataset cursor must encode an object")
        if set(value) != {"catalog_sha256", "offset"}:
            raise CatalogError("scientific dataset cursor fields are invalid")
        if value.get("catalog_sha256") != catalog_sha256:
            raise CatalogError("scientific dataset cursor belongs to a different catalog revision")
        offset = value.get("offset")
        if isinstance(offset, bool) or not isinstance(offset, int) or offset < 0:
            raise CatalogError("scientific dataset cursor offset is invalid")
        return offset


def _unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    value: dict[str, Any] = {}
    for key, item in pairs:
        if key in value:
            raise ValueError(f"duplicate JSON key: {key}")
        value[key] = item
    canonical_sha256(value)
    return value


__all__ = ["CatalogError", "CatalogStore"]
