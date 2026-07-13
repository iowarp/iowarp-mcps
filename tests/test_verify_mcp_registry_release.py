"""Tests for exact MCP Registry duplicate-version verification."""

from __future__ import annotations

import importlib.util
import json
import sys
from copy import deepcopy
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest


def _load_verifier_module() -> ModuleType:
    script = (
        Path(__file__).resolve().parents[1]
        / "scripts"
        / "verify_mcp_registry_release.py"
    )
    spec = importlib.util.spec_from_file_location(
        "clio_kit_verify_mcp_registry_release", script
    )
    if spec is None or spec.loader is None:
        raise RuntimeError(f"could not load registry verifier: {script}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


VERIFIER = _load_verifier_module()
RegistryVerificationError = VERIFIER.RegistryVerificationError


def _local_manifest() -> dict[str, Any]:
    return {
        "$schema": (
            "https://static.modelcontextprotocol.io/schemas/"
            "2025-12-11/server.schema.json"
        ),
        "name": "io.github.iowarp/example-mcp",
        "title": "Example",
        "description": "Example production server",
        "version": "3.0.0+release",
        "repository": {
            "url": "https://github.com/iowarp/clio-kit",
            "source": "github",
        },
        "packages": [
            {
                "registryType": "pypi",
                "identifier": "clio-kit",
                "version": "3.0.0",
                "transport": {"type": "stdio"},
                "packageArguments": [
                    {"type": "positional", "value": "mcp-server"},
                    {"type": "positional", "value": "example"},
                ],
            }
        ],
        "tools": [{"name": "example_tool", "description": "Example"}],
        "tags": ["example"],
    }


def _registered_response(local: dict[str, Any]) -> dict[str, Any]:
    return {
        "server": VERIFIER._registry_manifest_projection(local),
        "_meta": {
            "io.modelcontextprotocol.registry/official": {
                "status": "active",
                "isLatest": True,
            }
        },
    }


def _write_manifest(tmp_path: Path, manifest: dict[str, Any]) -> Path:
    path = tmp_path / "server.json"
    path.write_text(json.dumps(manifest), encoding="utf-8")
    return path


def test_exact_registered_manifest_and_coordinates_are_accepted(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    local = _local_manifest()
    path = _write_manifest(tmp_path, local)
    requested: list[str] = []

    def fetch(url: str, _timeout: float) -> dict[str, Any]:
        requested.append(url)
        return _registered_response(local)

    monkeypatch.setattr(VERIFIER, "_fetch_registry_document", fetch)

    VERIFIER.verify_registry_version(path)

    assert requested == [
        "https://registry.modelcontextprotocol.io/v0.1/servers/"
        "io.github.iowarp%2Fexample-mcp/versions/3.0.0%2Brelease"
    ]


def test_different_registered_package_coordinate_fails_closed(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    local = _local_manifest()
    response = _registered_response(local)
    response["server"]["packages"][0]["identifier"] = "other-package"
    monkeypatch.setattr(
        VERIFIER,
        "_fetch_registry_document",
        lambda _url, _timeout: response,
    )

    with pytest.raises(RegistryVerificationError, match="package coordinates differ"):
        VERIFIER.verify_registry_version(_write_manifest(tmp_path, local))


@pytest.mark.parametrize("difference", ["description", "unexpected-field"])
def test_registered_manifest_drift_fails_closed(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    difference: str,
) -> None:
    local = _local_manifest()
    response = deepcopy(_registered_response(local))
    if difference == "description":
        response["server"]["description"] = "stale release"
    else:
        response["server"]["registryInjected"] = True
    monkeypatch.setattr(
        VERIFIER,
        "_fetch_registry_document",
        lambda _url, _timeout: response,
    )

    with pytest.raises(RegistryVerificationError, match="manifest differs"):
        VERIFIER.verify_registry_version(_write_manifest(tmp_path, local))


def test_inactive_registered_version_fails_closed(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    local = _local_manifest()
    response = _registered_response(local)
    response["_meta"]["io.modelcontextprotocol.registry/official"]["status"] = "deleted"
    monkeypatch.setattr(
        VERIFIER,
        "_fetch_registry_document",
        lambda _url, _timeout: response,
    )

    with pytest.raises(RegistryVerificationError, match="is not active"):
        VERIFIER.verify_registry_version(_write_manifest(tmp_path, local))


def test_non_registry_package_fields_are_rejected(tmp_path: Path) -> None:
    """Legacy launch metadata cannot be silently dropped by the registry."""
    local = _local_manifest()
    local["packages"][0]["arguments"] = ["clio-kit", "mcp-server", "example"]

    with pytest.raises(RegistryVerificationError, match="unregistered fields"):
        VERIFIER.verify_registry_version(_write_manifest(tmp_path, local))


def test_unknown_top_level_fields_are_rejected(tmp_path: Path) -> None:
    """Only deliberate local discovery extensions may be absent remotely."""
    local = _local_manifest()
    local["accidentalReleaseField"] = "drift"

    with pytest.raises(RegistryVerificationError, match="unknown unregistered fields"):
        VERIFIER.verify_registry_version(_write_manifest(tmp_path, local))
