"""Tests for accepting verified JARVIS configuration-input rewrites."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from jarvis_mcp.capabilities.jarvis_handler import (
    _require_persisted_package_config,
)


def _pipeline_with_verifier(verifier: Mock) -> SimpleNamespace:
    package = {"pkg_id": "simulation", "config": {}}
    instance = SimpleNamespace(
        configuration_input_materialization_matches=verifier,
    )
    return SimpleNamespace(
        packages=[package],
        env={},
        _load_package_instance=Mock(return_value=instance),
    )


def test_verified_configuration_input_rewrite_is_accepted() -> None:
    """A package-owned byte-for-byte materialization is valid persistence."""
    verifier = Mock(return_value=True)
    pipeline = _pipeline_with_verifier(verifier)

    _require_persisted_package_config(
        "simulation",
        {"script": "/relay/staging/in.research"},
        {"script": "/jarvis/shared/configuration-inputs/script/digest.research"},
        pipeline=pipeline,
    )

    verifier.assert_called_once_with(
        "script",
        "/relay/staging/in.research",
        "/jarvis/shared/configuration-inputs/script/digest.research",
    )


def test_unverified_configuration_rewrite_still_fails_closed() -> None:
    """A changed value cannot bypass durable configuration verification."""
    pipeline = _pipeline_with_verifier(Mock(return_value=False))

    with pytest.raises(ValueError, match="did not persist settings: script"):
        _require_persisted_package_config(
            "simulation",
            {"script": "/relay/staging/in.research"},
            {"script": "/unowned/changed.research"},
            pipeline=pipeline,
        )
