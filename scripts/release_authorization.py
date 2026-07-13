"""Validate a short-lived administrator authorization for an immutable release."""

from __future__ import annotations

import argparse
import json
import re
import sys
import time
from collections.abc import Sequence
from typing import Any, cast

AUTHORIZATION_SCHEMA = "clio-kit.release.authorization.v1"
MAX_AUTHORIZATION_BYTES = 4_096
AUTHORIZATION_KEYS = {
    "commit",
    "immutable_releases",
    "repository",
    "schema_version",
    "tag",
    "verified_at_epoch",
}
STABLE_TAG_PATTERN = re.compile(
    r"^v(?:0|[1-9][0-9]*)\.(?:0|[1-9][0-9]*)\.(?:0|[1-9][0-9]*)$"
)
COMMIT_PATTERN = re.compile(r"^[0-9a-f]{40}$")


class ReleaseAuthorizationError(ValueError):
    """Raised when an administrator release authorization is invalid."""


def _object_without_duplicate_keys(
    pairs: list[tuple[str, Any]],
) -> dict[str, Any]:
    """Build a JSON object while rejecting duplicate field names."""
    record: dict[str, Any] = {}
    for key, value in pairs:
        if key in record:
            raise ReleaseAuthorizationError(
                f"release authorization contains duplicate field {key!r}"
            )
        record[key] = value
    return record


def validate_release_authorization(
    raw: str,
    *,
    repository: str,
    tag: str,
    commit: str,
    now_epoch: int,
    max_age_seconds: int,
) -> dict[str, Any]:
    """Return an exact release authorization after validating every field."""
    if len(raw.encode("utf-8")) > MAX_AUTHORIZATION_BYTES:
        raise ReleaseAuthorizationError("release authorization exceeds its byte limit")
    if STABLE_TAG_PATTERN.fullmatch(tag) is None:
        raise ReleaseAuthorizationError("release tag must be a stable vX.Y.Z tag")
    if COMMIT_PATTERN.fullmatch(commit) is None:
        raise ReleaseAuthorizationError(
            "release commit must be a lowercase 40-byte hex SHA"
        )
    if max_age_seconds <= 0:
        raise ReleaseAuthorizationError("maximum authorization age must be positive")
    try:
        document = json.loads(raw, object_pairs_hook=_object_without_duplicate_keys)
    except json.JSONDecodeError as exc:
        raise ReleaseAuthorizationError(
            "release authorization is not valid JSON"
        ) from exc
    if not isinstance(document, dict):
        raise ReleaseAuthorizationError("release authorization must be a JSON object")
    record = cast(dict[str, Any], document)
    if set(record) != AUTHORIZATION_KEYS:
        raise ReleaseAuthorizationError("release authorization field set is not exact")
    if record["schema_version"] != AUTHORIZATION_SCHEMA:
        raise ReleaseAuthorizationError("release authorization schema is not supported")
    if record["repository"] != repository:
        raise ReleaseAuthorizationError(
            "release authorization repository does not match"
        )
    if record["tag"] != tag:
        raise ReleaseAuthorizationError("release authorization tag does not match")
    if record["commit"] != commit:
        raise ReleaseAuthorizationError("release authorization commit does not match")
    if record["immutable_releases"] is not True:
        raise ReleaseAuthorizationError(
            "immutable releases were not administrator-verified"
        )
    verified_at = record["verified_at_epoch"]
    if type(verified_at) is not int:
        raise ReleaseAuthorizationError(
            "release authorization time must be an integer epoch"
        )
    age = now_epoch - verified_at
    if age < 0:
        raise ReleaseAuthorizationError("release authorization time is in the future")
    if age > max_age_seconds:
        raise ReleaseAuthorizationError("release authorization has expired")
    return record


def canonical_release_authorization(
    raw: str,
    *,
    repository: str,
    tag: str,
    commit: str,
    now_epoch: int,
    max_age_seconds: int,
) -> str:
    """Validate and return a canonical single-line authorization record."""
    record = validate_release_authorization(
        raw,
        repository=repository,
        tag=tag,
        commit=commit,
        now_epoch=now_epoch,
        max_age_seconds=max_age_seconds,
    )
    return json.dumps(record, ensure_ascii=True, separators=(",", ":"), sort_keys=True)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repository", required=True)
    parser.add_argument("--tag", required=True)
    parser.add_argument("--commit", required=True)
    parser.add_argument("--max-age-seconds", required=True, type=int)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """Validate standard-input authorization and print its canonical form."""
    parser = _parser()
    arguments = parser.parse_args(argv)
    raw = sys.stdin.read(MAX_AUTHORIZATION_BYTES + 1)
    try:
        canonical = canonical_release_authorization(
            raw,
            repository=arguments.repository,
            tag=arguments.tag,
            commit=arguments.commit,
            now_epoch=int(time.time()),
            max_age_seconds=arguments.max_age_seconds,
        )
    except ReleaseAuthorizationError as exc:
        parser.error(str(exc))
    print(canonical)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
