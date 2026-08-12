"""Validation for JARVIS-owned generated-artifact snapshots.

JARVIS-CD owns artifact discovery, lifecycle, and storage semantics. This
module only validates the frozen public snapshot before the MCP server exposes
it to a local agent.
"""

from __future__ import annotations

import base64
import binascii
import hashlib
import json
import math
import re
import stat
import time
from collections.abc import Mapping
from pathlib import Path, PurePosixPath
from typing import Any, cast
from urllib.parse import urlsplit

# Content-reading (``ArtifactContentError``/``artifact_with_content``) lives
# in ``artifact_content.py``, not here: this module owns snapshot VALIDATION
# and paging; that one owns the bounded, ``role="log"``-only file read
# layered on top of a page's results.
from jarvis_mcp.artifact_content import ARTIFACT_MAX_CONTENT_BYTES, artifact_with_content

ARTIFACT_SNAPSHOT_SCHEMA = "jarvis.execution.artifacts.v1"
ARTIFACT_EVENT_SCHEMA = "jarvis.artifact.v1"
ARTIFACT_MAX_EVENT_BYTES = 64 * 1024
ARTIFACT_MAX_TEXT = 4096
ARTIFACT_MAX_METADATA_BYTES = 64 * 1024
ARTIFACT_DEFAULT_PAGE_SIZE = 50
ARTIFACT_MAX_PAGE_SIZE = 100
ARTIFACT_MAX_PAGE_BYTES = 512 * 1024
ARTIFACT_MAX_CURSOR_LENGTH = 1024

_ARTIFACT_ID = re.compile(r"^art_[A-Za-z0-9_-]{22,86}$")
_CHECKSUM = re.compile(r"^[a-z0-9][a-z0-9_-]*:[A-Fa-f0-9]{16,256}$")
_MEDIA_TYPE = re.compile(
    r"^[A-Za-z0-9][A-Za-z0-9!#$&^_.+-]*/[A-Za-z0-9][A-Za-z0-9!#$&^_.+-]*$"
)
_URI_SCHEME = re.compile(r"^[a-z][a-z0-9+.-]*$")
_CURSOR_TEXT = re.compile(r"^[A-Za-z0-9_-]+$")
_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_UNSAFE_URI_SCHEMES = {"data", "file", "javascript"}
_CURSOR_SCHEMA = "clio-kit.jarvis-artifact-cursor.v1"
_EXECUTION_STATES = {
    "preparing",
    "scripted",
    "submitting",
    "submitted",
    "running",
    "completed",
    "failed",
    "canceled",
    "unknown",
}
_ARTIFACT_STATES = {"producing", "available", "finalized", "incomplete", "failed"}
_ARTIFACT_ROLES = {
    "intermediate",
    "output",
    "log",
    "frame",
    "checkpoint",
    "provenance",
    "validation",
}
_ARTIFACT_STRUCTURES = {"file", "directory", "collection", "stream"}
_ARTIFACT_OWNERSHIP = {"execution", "external", "shared"}
_LOCATION_KINDS = {"execution_path", "cluster_path", "external_uri"}
_REQUIRED_EVENT_FIELDS = {
    "schema_version",
    "package_name",
    "package_id",
    "execution_id",
    "artifact_id",
    "logical_name",
    "kind",
    "role",
    "structure",
    "ownership",
    "state",
    "revision",
    "sequence",
    "observed_at_epoch",
    "metadata",
}
_OPTIONAL_EVENT_FIELDS = {
    "location",
    "media_type",
    "format",
    "size_bytes",
    "checksum",
    "message",
}
MAX_EXECUTION_OUTPUT_FILES = 64
_EXECUTION_OUTPUT_TRUNCATION_SCHEMA = "jarvis.execution-output-truncation.v1"
_EXECUTION_OUTPUT_CONTROL_FILES = frozenset({"submit.slurm"})
_EXECUTION_OUTPUT_ROLE_BY_SUFFIX = {
    ".err": "log",
    ".log": "log",
    ".out": "log",
    ".bp": "frame",
    ".dcd": "frame",
    ".dump": "frame",
    ".h5": "frame",
    ".hdf5": "frame",
    ".lammpstrj": "frame",
    ".nc": "frame",
    ".npy": "frame",
    ".npz": "frame",
    ".pdb": "frame",
    ".vti": "frame",
    ".vtk": "frame",
    ".vtu": "frame",
    ".xyz": "frame",
}


def execution_root_from_record(record_document: Mapping[str, Any]) -> Path | None:
    """Resolve the execution directory from the authenticated record metadata."""
    raw_metadata = record_document.get("metadata")
    if not isinstance(raw_metadata, Mapping):
        return None
    for key in ("pipeline_snapshot_path", "script_path"):
        raw_path = raw_metadata.get(key)
        if not isinstance(raw_path, str) or not raw_path.strip():
            continue
        candidate = Path(raw_path)
        if candidate.name:
            return candidate.parent
    return None


class ArtifactSnapshotError(RuntimeError):
    """A JARVIS producer returned an invalid artifact snapshot."""

    def __init__(self, code: str, message: str) -> None:
        """Create a stable producer-snapshot validation error."""
        super().__init__(message)
        self.code = code
        self.message = message


class ArtifactQueryError(RuntimeError):
    """A bounded artifact-page query or cursor was invalid."""

    def __init__(self, code: str, message: str, retryable: bool = False) -> None:
        """Create a stable query error suitable for machine-readable mapping."""
        super().__init__(message)
        self.code = code
        self.message = message
        self.retryable = retryable


def execution_output_artifact_events(
    execution_root: Path,
    *,
    execution_id: str,
    observed_at_epoch: float | None = None,
) -> tuple[list[dict[str, Any]], dict[str, object] | None]:
    """Declare bounded regular files directly under one terminal execution root.

    Discovery is deliberately shallow: the execution root is listed once and
    nested directories are never traversed. File contents are hashed for
    identity, but never embedded in the returned manifest.
    """
    if not execution_root.is_dir():
        return [], None
    observed = time.time() if observed_at_epoch is None else observed_at_epoch
    candidates: list[Path] = []
    for path in sorted(execution_root.iterdir(), key=lambda item: item.name):
        try:
            path_stat = path.lstat()
        except OSError:
            continue
        if (
            path.name.startswith(".")
            or path.name in _EXECUTION_OUTPUT_CONTROL_FILES
            or stat.S_ISLNK(path_stat.st_mode)
            or not stat.S_ISREG(path_stat.st_mode)
        ):
            continue
        candidates.append(path)

    events: list[dict[str, Any]] = []
    for sequence, path in enumerate(candidates[:MAX_EXECUTION_OUTPUT_FILES], start=1):
        digest, size = _hash_regular_file(path)
        relative_path = path.relative_to(execution_root).as_posix()
        role = _EXECUTION_OUTPUT_ROLE_BY_SUFFIX.get(path.suffix.lower(), "output")
        artifact_id = "art_" + hashlib.sha256(
            f"{execution_id}:{relative_path}".encode()
        ).hexdigest()
        events.append(
            {
                "schema_version": ARTIFACT_EVENT_SCHEMA,
                "package_name": "jarvis.execution",
                "package_id": "jarvis.execution",
                "execution_id": execution_id,
                "artifact_id": artifact_id,
                "logical_name": relative_path,
                "kind": "execution-file",
                "role": role,
                "structure": "file",
                "ownership": "execution",
                "state": "finalized",
                "location": {"kind": "execution_path", "value": relative_path},
                "size_bytes": size,
                "checksum": f"sha256:{digest}",
                "revision": 1,
                "sequence": sequence,
                "observed_at_epoch": observed,
                "metadata": {"discovery": "execution-root-direct-file"},
            }
        )

    truncation = None
    if len(candidates) > MAX_EXECUTION_OUTPUT_FILES:
        truncation = {
            "schema_version": _EXECUTION_OUTPUT_TRUNCATION_SCHEMA,
            "limit": MAX_EXECUTION_OUTPUT_FILES,
            "observed_count": len(candidates),
            "omitted_count": len(candidates) - MAX_EXECUTION_OUTPUT_FILES,
        }
        events.append(
            {
                "schema_version": ARTIFACT_EVENT_SCHEMA,
                "package_name": "jarvis.execution",
                "package_id": "jarvis.execution",
                "execution_id": execution_id,
                "artifact_id": "art_"
                + hashlib.sha256(
                    f"{execution_id}:execution-output-truncation".encode()
                ).hexdigest(),
                "logical_name": "__execution-output-truncation__",
                "kind": "execution-output-truncation",
                "role": "validation",
                "structure": "file",
                "ownership": "execution",
                "state": "failed",
                "revision": 1,
                "sequence": len(events) + 1,
                "observed_at_epoch": observed,
                "message": "execution output file declaration cap exceeded",
                "metadata": truncation,
            }
        )
    return events, truncation


def _hash_regular_file(path: Path) -> tuple[str, int]:
    """Hash one stable regular file without retaining its content."""
    digest = hashlib.sha256()
    size = 0
    with path.open("rb") as stream:
        before = path.stat()
        while chunk := stream.read(1024 * 1024):
            digest.update(chunk)
            size += len(chunk)
        after = path.stat()
    if not stat.S_ISREG(before.st_mode) or not stat.S_ISREG(after.st_mode):
        raise RuntimeError("execution output changed from a regular file")
    if before.st_size != size or after.st_size != size:
        raise RuntimeError("execution output changed while hashing")
    return digest.hexdigest(), size


def artifact_snapshot_document(
    snapshot: object,
    *,
    expected_execution_id: str,
    expected_pipeline_id: str,
) -> dict[str, Any]:
    """Return one identity-checked snapshot with bounded artifact events."""
    try:
        return _artifact_snapshot_document(
            snapshot,
            expected_execution_id=expected_execution_id,
            expected_pipeline_id=expected_pipeline_id,
        )
    except ArtifactSnapshotError:
        raise
    except Exception as exc:
        raise ArtifactSnapshotError(
            "jarvis_artifact_snapshot_invalid",
            str(exc),
        ) from exc


def _artifact_snapshot_document(
    snapshot: object,
    *,
    expected_execution_id: str,
    expected_pipeline_id: str,
) -> dict[str, Any]:
    """Validate one native snapshot behind the public error boundary."""
    if isinstance(snapshot, Mapping):
        value = dict(snapshot)
    else:
        to_dict = getattr(snapshot, "to_dict", None)
        if not callable(to_dict):
            raise RuntimeError("JARVIS artifact snapshot is not serializable")
        rendered = to_dict()
        if not isinstance(rendered, dict):
            raise RuntimeError("JARVIS artifact snapshot is not an object")
        value = rendered

    required = {
        "schema_version",
        "execution_id",
        "pipeline_id",
        "execution_state",
        "terminal",
        "artifacts",
    }
    if set(value) != required or value.get("schema_version") != (
        ARTIFACT_SNAPSHOT_SCHEMA
    ):
        raise RuntimeError("JARVIS artifact snapshot schema is unsupported")
    if value.get("execution_id") != expected_execution_id:
        raise RuntimeError("JARVIS artifact execution identity did not match")
    if value.get("pipeline_id") != expected_pipeline_id:
        raise RuntimeError("JARVIS artifact pipeline identity did not match")
    execution_state = value.get("execution_state")
    if not isinstance(execution_state, str) or execution_state not in _EXECUTION_STATES:
        raise RuntimeError("JARVIS artifact execution state is unsupported")
    if not isinstance(value.get("terminal"), bool):
        raise RuntimeError("JARVIS artifact terminal flag is invalid")
    artifacts = value.get("artifacts")
    if not isinstance(artifacts, list):
        raise RuntimeError("JARVIS artifacts must be a list")

    seen_ids: set[str] = set()
    for artifact in artifacts:
        _validate_artifact_event(
            artifact,
            execution_id=expected_execution_id,
            seen_ids=seen_ids,
        )
    return cast(dict[str, Any], value)


def artifact_query_page(
    snapshot: dict[str, Any],
    *,
    package_id: str | None = None,
    role: str | None = None,
    state: str | None = None,
    artifact_id: str | None = None,
    page_size: int = ARTIFACT_DEFAULT_PAGE_SIZE,
    cursor: str | None = None,
    content_max_bytes: int | None = None,
    execution_root: Path | None = None,
) -> dict[str, Any]:
    """Filter and page one previously validated native artifact snapshot.

    Cursors bind the exact filters and a digest of the filtered producer
    snapshot. A changed artifact, execution state, or terminal flag makes an
    existing cursor stale instead of silently shifting an offset-based page.

    ``content_max_bytes`` is a response-enrichment knob, not a filter: it is
    deliberately excluded from the cursor's filter digest so a cursor minted
    without it stays valid on a follow-up call that requests it (or vice
    versa). When set, every ``role="log"`` artifact in the returned page gets
    a bounded tail read of its own file (``content``/``content_truncated``/
    ``content_bytes_read``); every other artifact, and every log artifact
    whose content could not be resolved, gets a typed ``content_error``
    instead -- never a silent omission, never a page-wide failure for one
    unreadable file.
    """
    _validate_query_filters(
        package_id=package_id,
        role=role,
        state=state,
        artifact_id=artifact_id,
        page_size=page_size,
        content_max_bytes=content_max_bytes,
    )
    filters = {
        "package_id": package_id,
        "role": role,
        "state": state,
        "artifact_id": artifact_id,
    }
    filter_digest = _sha256(filters)
    decoded_cursor: dict[str, str] | None = None
    anchor: str | None = None
    if cursor is not None:
        decoded_cursor = _decode_cursor(cursor)
        if decoded_cursor["filter_sha256"] != filter_digest:
            raise ArtifactQueryError(
                "jarvis_artifact_cursor_filter_mismatch",
                "JARVIS artifact cursor does not match the requested filters",
            )
        anchor = decoded_cursor["after_artifact_id"]

    snapshot_hasher = hashlib.sha256()
    snapshot_hasher.update(b"clio-kit.jarvis-artifact-snapshot-digest.v2\0")
    digest_header = _canonical_json_bytes(
        {
            "producer_schema_version": snapshot["schema_version"],
            "execution_id": snapshot["execution_id"],
            "pipeline_id": snapshot["pipeline_id"],
            "execution_state": snapshot["execution_state"],
            "terminal": snapshot["terminal"],
            "filters": filters,
        }
    )
    snapshot_hasher.update(len(digest_header).to_bytes(8, "big"))
    snapshot_hasher.update(digest_header)

    page: list[dict[str, Any]] = []
    page_bytes = 2
    matching_artifact_count = 0
    anchor_found = anchor is None
    has_more = False
    page_full = False
    artifacts = cast(list[dict[str, Any]], snapshot["artifacts"])
    for item in artifacts:
        if not (
            (package_id is None or item["package_id"] == package_id)
            and (role is None or item["role"] == role)
            and (state is None or item["state"] == state)
            and (artifact_id is None or item["artifact_id"] == artifact_id)
        ):
            continue
        matching_artifact_count += 1
        encoded_item = _canonical_json_bytes(item)
        snapshot_hasher.update(len(encoded_item).to_bytes(8, "big"))
        snapshot_hasher.update(encoded_item)
        if not anchor_found:
            if item["artifact_id"] == anchor:
                anchor_found = True
            continue
        if page_full:
            has_more = True
            continue
        encoded_size = len(encoded_item) + (1 if page else 0)
        if page_bytes + encoded_size > ARTIFACT_MAX_PAGE_BYTES:
            if not page:
                raise ArtifactQueryError(
                    "jarvis_artifact_page_item_too_large",
                    "one JARVIS artifact exceeded the MCP page byte limit",
                )
            page_full = True
            has_more = True
            continue
        page.append(item)
        page_bytes += encoded_size
        if len(page) == page_size:
            page_full = True

    snapshot_digest = snapshot_hasher.hexdigest()
    if decoded_cursor is not None:
        if decoded_cursor["snapshot_sha256"] != snapshot_digest:
            raise ArtifactQueryError(
                "jarvis_artifact_cursor_stale",
                "JARVIS artifact cursor is stale because the filtered snapshot changed",
                retryable=True,
            )
        if not anchor_found:
            raise ArtifactQueryError(
                "jarvis_artifact_cursor_stale",
                "JARVIS artifact cursor is stale because its anchor disappeared",
                retryable=True,
            )

    next_cursor = None
    if has_more:
        if not page:
            raise ArtifactQueryError(
                "jarvis_artifact_page_item_too_large",
                "one JARVIS artifact exceeded the MCP page byte limit",
            )
        next_cursor = _encode_cursor(
            after_artifact_id=page[-1]["artifact_id"],
            filter_digest=filter_digest,
            snapshot_digest=snapshot_digest,
        )
    if content_max_bytes is not None:
        page = [
            artifact_with_content(
                item, execution_root=execution_root, max_bytes=content_max_bytes
            )
            for item in page
        ]
    return {
        "producer_schema_version": snapshot["schema_version"],
        "pipeline_id": snapshot["pipeline_id"],
        "execution_id": snapshot["execution_id"],
        "execution_state": snapshot["execution_state"],
        "terminal": snapshot["terminal"],
        "artifacts": page,
        "matching_artifact_count": matching_artifact_count,
        "returned_artifact_count": len(page),
        "next_cursor": next_cursor,
    }


def _validate_query_filters(
    *,
    package_id: str | None,
    role: str | None,
    state: str | None,
    artifact_id: str | None,
    page_size: int,
    content_max_bytes: int | None = None,
) -> None:
    if content_max_bytes is not None and (
        isinstance(content_max_bytes, bool)
        or not isinstance(content_max_bytes, int)
        or not 1 <= content_max_bytes <= ARTIFACT_MAX_CONTENT_BYTES
    ):
        raise ArtifactQueryError(
            "jarvis_artifact_content_max_bytes_invalid",
            f"JARVIS artifact content_max_bytes must be between 1 and "
            f"{ARTIFACT_MAX_CONTENT_BYTES}",
        )
    if package_id is not None:
        try:
            _validate_text(package_id, field="package_id filter", maximum=256)
        except RuntimeError as exc:
            raise ArtifactQueryError(
                "jarvis_artifact_filter_invalid",
                str(exc),
            ) from exc
    if role is not None and role not in _ARTIFACT_ROLES:
        raise ArtifactQueryError(
            "jarvis_artifact_filter_invalid",
            "JARVIS artifact role filter is unsupported",
        )
    if state is not None and state not in _ARTIFACT_STATES:
        raise ArtifactQueryError(
            "jarvis_artifact_filter_invalid",
            "JARVIS artifact state filter is unsupported",
        )
    if artifact_id is not None and _ARTIFACT_ID.fullmatch(artifact_id) is None:
        raise ArtifactQueryError(
            "jarvis_artifact_filter_invalid",
            "JARVIS artifact ID filter is invalid",
        )
    if (
        isinstance(page_size, bool)
        or not isinstance(page_size, int)
        or not 1 <= page_size <= ARTIFACT_MAX_PAGE_SIZE
    ):
        raise ArtifactQueryError(
            "jarvis_artifact_page_size_invalid",
            f"JARVIS artifact page_size must be between 1 and {ARTIFACT_MAX_PAGE_SIZE}",
        )


def _encode_cursor(
    *,
    after_artifact_id: str,
    filter_digest: str,
    snapshot_digest: str,
) -> str:
    payload = _canonical_json_bytes(
        {
            "schema_version": _CURSOR_SCHEMA,
            "after_artifact_id": after_artifact_id,
            "filter_sha256": filter_digest,
            "snapshot_sha256": snapshot_digest,
        }
    )
    cursor = base64.urlsafe_b64encode(payload).decode("ascii").rstrip("=")
    if len(cursor) > ARTIFACT_MAX_CURSOR_LENGTH:
        raise ArtifactQueryError(
            "jarvis_artifact_cursor_invalid",
            "JARVIS artifact cursor exceeded its byte limit",
        )
    return cursor


def _decode_cursor(cursor: str) -> dict[str, str]:
    if (
        not isinstance(cursor, str)
        or not cursor
        or len(cursor) > ARTIFACT_MAX_CURSOR_LENGTH
        or _CURSOR_TEXT.fullmatch(cursor) is None
    ):
        raise ArtifactQueryError(
            "jarvis_artifact_cursor_invalid",
            "JARVIS artifact cursor is invalid",
        )
    padding = "=" * (-len(cursor) % 4)
    try:
        payload = base64.b64decode(
            cursor + padding,
            altchars=b"-_",
            validate=True,
        )
        if len(payload) > ARTIFACT_MAX_CURSOR_LENGTH:
            raise ArtifactQueryError(
                "jarvis_artifact_cursor_invalid",
                "JARVIS artifact cursor exceeded its byte limit",
            )
        value = json.loads(
            payload.decode("utf-8"),
            object_pairs_hook=_reject_duplicate_keys,
        )
    except ArtifactQueryError:
        raise
    except (
        binascii.Error,
        UnicodeDecodeError,
        json.JSONDecodeError,
        ValueError,
    ) as exc:
        raise ArtifactQueryError(
            "jarvis_artifact_cursor_invalid",
            "JARVIS artifact cursor is invalid",
        ) from exc
    if not isinstance(value, dict) or set(value) != {
        "schema_version",
        "after_artifact_id",
        "filter_sha256",
        "snapshot_sha256",
    }:
        raise ArtifactQueryError(
            "jarvis_artifact_cursor_invalid",
            "JARVIS artifact cursor schema is invalid",
        )
    if value.get("schema_version") != _CURSOR_SCHEMA:
        raise ArtifactQueryError(
            "jarvis_artifact_cursor_invalid",
            "JARVIS artifact cursor schema is unsupported",
        )
    after_artifact_id = value.get("after_artifact_id")
    filter_digest = value.get("filter_sha256")
    snapshot_digest = value.get("snapshot_sha256")
    if (
        not isinstance(after_artifact_id, str)
        or _ARTIFACT_ID.fullmatch(after_artifact_id) is None
        or not isinstance(filter_digest, str)
        or _SHA256.fullmatch(filter_digest) is None
        or not isinstance(snapshot_digest, str)
        or _SHA256.fullmatch(snapshot_digest) is None
    ):
        raise ArtifactQueryError(
            "jarvis_artifact_cursor_invalid",
            "JARVIS artifact cursor fields are invalid",
        )
    return {
        "after_artifact_id": after_artifact_id,
        "filter_sha256": filter_digest,
        "snapshot_sha256": snapshot_digest,
    }


def _validate_artifact_event(
    value: object,
    *,
    execution_id: str,
    seen_ids: set[str],
) -> None:
    if not isinstance(value, dict) or not _REQUIRED_EVENT_FIELDS.issubset(value):
        raise RuntimeError("JARVIS artifact event is invalid")
    if not set(value).issubset(_REQUIRED_EVENT_FIELDS | _OPTIONAL_EVENT_FIELDS):
        raise RuntimeError("JARVIS artifact event fields are invalid")
    if value.get("schema_version") != ARTIFACT_EVENT_SCHEMA:
        raise RuntimeError("JARVIS artifact event schema is unsupported")
    if value.get("execution_id") != execution_id:
        raise RuntimeError("JARVIS artifact event identity did not match")

    for field_name in ("package_name", "package_id", "logical_name", "kind"):
        _validate_text(value.get(field_name), field=field_name, maximum=256)
    artifact_id = value.get("artifact_id")
    if (
        not isinstance(artifact_id, str)
        or _ARTIFACT_ID.fullmatch(artifact_id) is None
        or artifact_id in seen_ids
    ):
        raise RuntimeError("JARVIS artifact identity is invalid")
    seen_ids.add(artifact_id)

    _validate_enum(value, "role", _ARTIFACT_ROLES)
    _validate_enum(value, "structure", _ARTIFACT_STRUCTURES)
    _validate_enum(value, "ownership", _ARTIFACT_OWNERSHIP)
    _validate_enum(value, "state", _ARTIFACT_STATES)
    for field_name in ("revision", "sequence"):
        item = value.get(field_name)
        if isinstance(item, bool) or not isinstance(item, int) or item < 1:
            raise RuntimeError(f"JARVIS artifact {field_name} is invalid")
    if not _finite_nonnegative(value.get("observed_at_epoch")):
        raise RuntimeError("JARVIS artifact observation time is invalid")

    metadata = value.get("metadata")
    if not isinstance(metadata, dict):
        raise RuntimeError("JARVIS artifact metadata is invalid")
    _bounded_json(
        metadata,
        maximum=ARTIFACT_MAX_METADATA_BYTES,
        message="JARVIS artifact metadata",
    )
    _validate_location_and_ownership(value)
    _validate_optional_fields(value)
    _bounded_json(
        value,
        maximum=ARTIFACT_MAX_EVENT_BYTES,
        message="JARVIS artifact event",
    )


def _validate_location_and_ownership(value: dict[str, Any]) -> None:
    location = value.get("location")
    state = value["state"]
    if location is None:
        if state in {"available", "finalized"}:
            raise RuntimeError(f"JARVIS artifact state {state!r} requires a location")
        return
    if not isinstance(location, dict) or set(location) != {"kind", "value"}:
        raise RuntimeError("JARVIS artifact location is invalid")
    kind = location.get("kind")
    _validate_enum(location, "kind", _LOCATION_KINDS)
    location_value = location.get("value")
    _validate_text(location_value, field="location", maximum=ARTIFACT_MAX_TEXT)
    location_value = cast(str, location_value)
    if kind == "execution_path":
        _validate_execution_path(location_value)
    elif kind == "cluster_path":
        _validate_cluster_path(location_value)
    else:
        _validate_external_uri(location_value)
    ownership = value["ownership"]
    if (kind == "execution_path") is not (ownership == "execution"):
        raise RuntimeError("JARVIS artifact location ownership is invalid")


def _validate_optional_fields(value: dict[str, Any]) -> None:
    for field_name, maximum in (("format", 256), ("message", ARTIFACT_MAX_TEXT)):
        if field_name in value:
            _validate_text(value[field_name], field=field_name, maximum=maximum)
    if "media_type" in value and (
        not isinstance(value["media_type"], str)
        or _MEDIA_TYPE.fullmatch(value["media_type"]) is None
    ):
        raise RuntimeError("JARVIS artifact media_type is invalid")
    if "size_bytes" in value:
        size = value["size_bytes"]
        if isinstance(size, bool) or not isinstance(size, int) or size < 0:
            raise RuntimeError("JARVIS artifact size_bytes is invalid")
    if "checksum" in value and (
        not isinstance(value["checksum"], str)
        or _CHECKSUM.fullmatch(value["checksum"]) is None
    ):
        raise RuntimeError("JARVIS artifact checksum is invalid")


def _validate_execution_path(value: str) -> None:
    path = PurePosixPath(value)
    if (
        "\\" in value
        or path.is_absolute()
        or value.startswith("/")
        or value.endswith("/")
        or "//" in value
        or any(part in {"", ".", ".."} for part in path.parts)
        or (bool(path.parts) and ":" in path.parts[0])
        or path.as_posix() != value
    ):
        raise RuntimeError("JARVIS execution artifact path is invalid")


def _validate_cluster_path(value: str) -> None:
    path = PurePosixPath(value)
    if (
        "\\" in value
        or not path.is_absolute()
        or not value.startswith("/")
        or value == "/"
        or value.endswith("/")
        or "//" in value
        or any(part in {"", ".", ".."} for part in path.parts[1:])
        or path.as_posix() != value
    ):
        raise RuntimeError("JARVIS cluster artifact path is invalid")


def _validate_external_uri(value: str) -> None:
    try:
        parsed = urlsplit(value)
        has_user_information = (
            parsed.username is not None or parsed.password is not None
        )
    except ValueError as exc:
        raise RuntimeError("JARVIS external artifact URI is invalid") from exc
    scheme = parsed.scheme.lower()
    if (
        not scheme
        or _URI_SCHEME.fullmatch(scheme) is None
        or len(scheme) == 1
        or scheme in _UNSAFE_URI_SCHEMES
        or has_user_information
        or (scheme in {"gs", "http", "https", "s3"} and not parsed.netloc)
    ):
        raise RuntimeError("JARVIS external artifact URI is invalid")


def _validate_text(value: object, *, field: str, maximum: int) -> None:
    if (
        not isinstance(value, str)
        or not value.strip()
        or len(value) > maximum
        or any(ord(character) < 32 for character in value)
    ):
        raise RuntimeError(f"JARVIS artifact {field} is invalid")


def _validate_enum(value: dict[str, Any], field: str, allowed: set[str]) -> None:
    item = value.get(field)
    if not isinstance(item, str) or item not in allowed:
        raise RuntimeError(f"JARVIS artifact {field} is unsupported")


def _bounded_json(value: object, *, maximum: int, message: str) -> None:
    try:
        encoded = _canonical_json_bytes(value)
    except (TypeError, ValueError, OverflowError, RecursionError) as exc:
        raise RuntimeError(f"{message} is not bounded JSON") from exc
    if len(encoded) > maximum:
        raise RuntimeError(f"{message} exceeded its byte limit")


def _canonical_json_bytes(value: object) -> bytes:
    return json.dumps(
        value,
        allow_nan=False,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")


def _sha256(value: object) -> str:
    return hashlib.sha256(_canonical_json_bytes(value)).hexdigest()


def _reject_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    value: dict[str, Any] = {}
    for key, item in pairs:
        if key in value:
            raise ValueError(f"duplicate cursor key: {key}")
        value[key] = item
    return value


def _finite_nonnegative(value: object) -> bool:
    return (
        not isinstance(value, bool)
        and isinstance(value, (int, float))
        and math.isfinite(float(value))
        and float(value) >= 0
    )

