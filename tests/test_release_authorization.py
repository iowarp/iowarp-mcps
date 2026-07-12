"""Tests for exact immutable-release administrator authorization."""

from __future__ import annotations

import json
import importlib.util
import sys
from collections.abc import Callable
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest


def _load_authorization_module() -> ModuleType:
    script = (
        Path(__file__).resolve().parents[1] / "scripts" / "release_authorization.py"
    )
    spec = importlib.util.spec_from_file_location(
        "clio_kit_release_authorization", script
    )
    if spec is None or spec.loader is None:
        raise RuntimeError(f"could not load release authorization validator: {script}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


_AUTHORIZATION_MODULE = _load_authorization_module()
AUTHORIZATION_SCHEMA = _AUTHORIZATION_MODULE.AUTHORIZATION_SCHEMA
ReleaseAuthorizationError = _AUTHORIZATION_MODULE.ReleaseAuthorizationError
canonical_release_authorization = _AUTHORIZATION_MODULE.canonical_release_authorization
validate_release_authorization = _AUTHORIZATION_MODULE.validate_release_authorization

REPOSITORY = "iowarp/clio-kit"
TAG = "v3.0.0"
COMMIT = "a" * 40
NOW = 1_800_000_000


def _record() -> dict[str, Any]:
    return {
        "schema_version": AUTHORIZATION_SCHEMA,
        "repository": REPOSITORY,
        "tag": TAG,
        "commit": COMMIT,
        "immutable_releases": True,
        "verified_at_epoch": NOW - 30,
    }


def _validate(
    record: object,
    *,
    repository: str = REPOSITORY,
    tag: str = TAG,
    commit: str = COMMIT,
    now_epoch: int = NOW,
    max_age_seconds: int = 3_600,
) -> dict[str, Any]:
    return validate_release_authorization(
        json.dumps(record),
        repository=repository,
        tag=tag,
        commit=commit,
        now_epoch=now_epoch,
        max_age_seconds=max_age_seconds,
    )


def test_valid_authorization_is_canonicalized() -> None:
    record = _record()

    canonical = canonical_release_authorization(
        json.dumps(record, indent=2),
        repository=REPOSITORY,
        tag=TAG,
        commit=COMMIT,
        now_epoch=NOW,
        max_age_seconds=3_600,
    )

    assert canonical == json.dumps(record, separators=(",", ":"), sort_keys=True)
    assert _validate(record) == record


@pytest.mark.parametrize(
    ("mutate", "message"),
    [
        (lambda value: value.update(extra=True), "field set"),
        (lambda value: value.pop("commit"), "field set"),
        (lambda value: value.update(schema_version="other"), "schema"),
        (lambda value: value.update(repository="other/repo"), "repository"),
        (lambda value: value.update(repository=1), "repository"),
        (lambda value: value.update(tag="v3.0.1"), "tag"),
        (lambda value: value.update(commit="b" * 40), "commit"),
        (
            lambda value: value.update(immutable_releases=False),
            "not administrator-verified",
        ),
        (
            lambda value: value.update(immutable_releases=1),
            "not administrator-verified",
        ),
        (lambda value: value.update(verified_at_epoch=1.0), "integer epoch"),
        (lambda value: value.update(verified_at_epoch=True), "integer epoch"),
    ],
)
def test_authorization_rejects_field_drift(
    mutate: Callable[[dict[str, Any]], object],
    message: str,
) -> None:
    record = _record()
    mutate(record)

    with pytest.raises(ReleaseAuthorizationError, match=message):
        _validate(record)


def test_authorization_rejects_future_and_expired_records() -> None:
    future = _record()
    future["verified_at_epoch"] = NOW + 1
    with pytest.raises(ReleaseAuthorizationError, match="future"):
        _validate(future)

    expired = _record()
    expired["verified_at_epoch"] = NOW - 3_601
    with pytest.raises(ReleaseAuthorizationError, match="expired"):
        _validate(expired)


def test_authorization_accepts_exact_one_hour_boundary() -> None:
    boundary = _record()
    boundary["verified_at_epoch"] = NOW - 3_600

    assert _validate(boundary) == boundary


@pytest.mark.parametrize("tag", ["3.0.0", "v3.0", "v3.0.0rc1", "v03.0.0"])
def test_authorization_rejects_nonstable_expected_tag(tag: str) -> None:
    with pytest.raises(ReleaseAuthorizationError, match="stable"):
        _validate(_record(), tag=tag)


def test_authorization_rejects_malformed_or_oversized_json() -> None:
    with pytest.raises(ReleaseAuthorizationError, match="valid JSON"):
        validate_release_authorization(
            "{",
            repository=REPOSITORY,
            tag=TAG,
            commit=COMMIT,
            now_epoch=NOW,
            max_age_seconds=3_600,
        )
    with pytest.raises(ReleaseAuthorizationError, match="byte limit"):
        validate_release_authorization(
            " " * 4_097,
            repository=REPOSITORY,
            tag=TAG,
            commit=COMMIT,
            now_epoch=NOW,
            max_age_seconds=3_600,
        )


def test_authorization_rejects_nonobject_and_duplicate_fields() -> None:
    with pytest.raises(ReleaseAuthorizationError, match="JSON object"):
        _validate([])

    duplicate = json.dumps(_record())[:-1] + ',"commit":"' + COMMIT + '"}'
    with pytest.raises(ReleaseAuthorizationError, match="duplicate field"):
        validate_release_authorization(
            duplicate,
            repository=REPOSITORY,
            tag=TAG,
            commit=COMMIT,
            now_epoch=NOW,
            max_age_seconds=3_600,
        )
