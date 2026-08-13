"""Bounded inline content reads for JARVIS-owned ``role="log"`` artifacts.

Companion to :mod:`jarvis_mcp.artifacts`, which owns artifact snapshot
validation and paging: that module's artifact page is a content-free
manifest by design (identity, role, state, location only). This module adds
one narrow, additive capability on top of it -- reading a bounded tail of a
log artifact's own file -- kept in its own module rather than appended to
either ``artifacts.py`` or the already-oversized ``jarvis_handler.py`` (see
``scripts/check_file_size.py``'s per-file ratchet).

A failed execution's own generated logs are the single most useful thing an
agent can read after a terminal failure. Only ``role="log"`` artifacts are
eligible: this is a deliberate, narrow scope, not a general remote-file-read
primitive.
"""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path
from typing import Any, cast

ARTIFACT_MAX_CONTENT_BYTES = 64 * 1024


class ArtifactContentError(RuntimeError):
    """One artifact's bounded inline content could not be resolved or read.

    Always caught per-artifact by :func:`artifact_with_content` -- a single
    unreadable log must never fail the whole bounded page.
    """

    def __init__(self, code: str, message: str) -> None:
        """Create a stable per-artifact content error."""
        super().__init__(message)
        self.code = code
        self.message = message


def artifact_with_content(
    item: dict[str, Any],
    *,
    execution_root: Path | None,
    max_bytes: int,
) -> dict[str, Any]:
    """Return one page item enriched with a bounded inline content read.

    Scoped to ``role="log"`` artifacts only -- this is a narrow, bounded log
    reader, not a general remote-file-read primitive. Every other artifact,
    and every log artifact whose content genuinely could not be resolved,
    gets a typed ``content_error`` -- the caller always sees why, never a
    silent gap where content might have been.
    """
    enriched = dict(item)
    role = item.get("role")
    if role != "log":
        enriched.update(
            content=None,
            content_truncated=False,
            content_bytes_read=0,
            content_error=(
                f"artifact role {role!r} is not eligible for inline content "
                '(role must be "log")'
            ),
        )
        return enriched
    location = item.get("location")
    if not isinstance(location, dict):
        enriched.update(
            content=None,
            content_truncated=False,
            content_bytes_read=0,
            content_error="log artifact has no location to read content from",
        )
        return enriched
    try:
        path = resolve_artifact_path(location, execution_root=execution_root)
        text, truncated, bytes_read = read_artifact_tail(path, max_bytes=max_bytes)
    except ArtifactContentError as exc:
        enriched.update(
            content=None,
            content_truncated=False,
            content_bytes_read=0,
            content_error=exc.message,
        )
        return enriched
    enriched.update(
        content=text,
        content_truncated=truncated,
        content_bytes_read=bytes_read,
        content_error=None,
    )
    return enriched


def execution_root_from_record(record_document: dict[str, Any]) -> Path | None:
    """Resolve one execution's own root directory from its durable metadata.

    Grounded, not guessed: ``pipeline_snapshot_path`` is written by JARVIS-CD
    itself as ``execution_root / "runtime"`` for every execution (see
    ``jarvis_cd.core.pipeline.Pipeline._launch``, which also places
    ``stdout.log``/``stderr.log`` directly under that same ``execution_root``
    -- this is the one durable field already present on every record that
    names it, so no path is invented here. Returns ``None`` (never a guess)
    when the field is absent or malformed; callers must treat that as
    "execution-scoped log content is not resolvable for this record", not
    retry with a fabricated path.
    """
    metadata = record_document.get("metadata")
    if not isinstance(metadata, dict):
        return None
    snapshot_path = metadata.get("pipeline_snapshot_path")
    if isinstance(snapshot_path, str) and snapshot_path:
        return Path(snapshot_path).parent
    # Scheduler-mode records: ``pipeline_snapshot_path`` is written by the
    # launch that runs INSIDE the scheduler job, so the submit-side record
    # never carries it. ``metadata.script_path`` is written at submit time as
    # ``execution_root / "submit.slurm"`` (scheduler_submit), so its parent is
    # the same execution root — still a durable field, never a guess.
    script_path = metadata.get("script_path")
    if isinstance(script_path, str) and script_path:
        return Path(script_path).parent
    return None


def resolve_artifact_path(
    location: Mapping[str, Any],
    *,
    execution_root: Path | None,
) -> Path:
    """Resolve one already-validated artifact location to a real filesystem path.

    ``execution_path`` locations were validated on the way in
    (``artifacts.py::_validate_execution_path``) to contain no
    ``..``/absolute component, so joining them onto ``execution_root`` can
    never escape it. ``cluster_path`` locations are already validated
    absolute paths on this same host -- ``jarvis_mcp`` runs co-located with
    the execution it is reporting on, so this is a local read, never a
    second network hop.
    """
    kind = location["kind"]
    value = cast(str, location["value"])
    if kind == "cluster_path":
        return Path(value)
    if kind == "execution_path":
        if execution_root is None:
            raise ArtifactContentError(
                "jarvis_artifact_execution_root_unavailable",
                "this execution's own root directory could not be resolved, "
                "so its relative log path cannot be read",
            )
        return execution_root / value
    raise ArtifactContentError(
        "jarvis_artifact_content_unsupported_location",
        f"artifact location kind {kind!r} does not support inline content",
    )


def read_artifact_tail(path: Path, *, max_bytes: int) -> tuple[str, bool, int]:
    """Read up to ``max_bytes`` from the END of one file (tail semantics).

    A log's most recent lines -- the ones nearest a crash -- are read, not
    its head. Decoded permissively (``errors="replace"``): a partially
    written multi-byte sequence at the tail boundary must not turn a
    genuinely useful read into a hard failure.
    """
    try:
        size = path.stat().st_size
    except OSError as exc:
        raise ArtifactContentError(
            "jarvis_artifact_content_unreadable",
            f"artifact file could not be read: {exc}",
        ) from exc
    truncated = size > max_bytes
    offset = max(0, size - max_bytes)
    try:
        with path.open("rb") as handle:
            handle.seek(offset)
            raw = handle.read(max_bytes)
    except OSError as exc:
        raise ArtifactContentError(
            "jarvis_artifact_content_unreadable",
            f"artifact file could not be read: {exc}",
        ) from exc
    return raw.decode("utf-8", errors="replace"), truncated, len(raw)
