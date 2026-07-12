"""Registry contract tests for deterministic server.json generation."""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path
from types import ModuleType
from typing import IO, Any

import pytest


def _load_generator() -> ModuleType:
    script = Path(__file__).resolve().parents[1] / "scripts" / "generate_server_json.py"
    spec = importlib.util.spec_from_file_location("clio_kit_manifest_generator", script)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"could not load manifest generator: {script}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


GENERATOR = _load_generator()


def test_json_writer_requests_platform_independent_newlines(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Generated release metadata must remain byte-identical on Windows."""
    real_open = open
    observed: dict[str, Any] = {}

    def checked_open(*args: Any, **kwargs: Any) -> IO[str]:
        observed["newline"] = kwargs.get("newline")
        return real_open(*args, **kwargs)

    monkeypatch.setattr(GENERATOR, "open", checked_open, raising=False)
    output = tmp_path / "manifest.json"
    GENERATOR._write_json(output, {"name": "demo"})

    assert observed["newline"] == "\n"
    assert output.read_bytes() == b'{\n  "name": "demo"\n}\n'


def test_pypi_manifest_uses_standard_fixed_package_arguments() -> None:
    """Registry clients can launch one selected server from the shared wheel."""
    manifest = GENERATOR.build_server_json(
        "spack",
        {"description": "Spack MCP"},
        {"tools": []},
        pypi_version="3.0.0",
    )

    assert manifest["packages"] == [
        {
            "registryType": "pypi",
            "identifier": "clio-kit",
            "version": "3.0.0",
            "transport": {"type": "stdio"},
            "packageArguments": [
                {"type": "positional", "value": "mcp-server"},
                {"type": "positional", "value": "spack"},
            ],
        }
    ]


def test_every_committed_server_has_an_agent_runnable_package_coordinate() -> None:
    """Every registry record selects its exact server from the shared wheel."""
    repository_root = Path(__file__).resolve().parents[1]
    servers_root = repository_root / "clio-kit-mcp-servers"
    projects = sorted(path.parent for path in servers_root.glob("*/pyproject.toml"))
    manifests = sorted(servers_root.glob("*/server.json"))
    expected_version = GENERATOR.read_root_version(repository_root)

    assert projects
    assert manifests == [project / "server.json" for project in projects]
    for path in manifests:
        manifest = json.loads(path.read_text(encoding="utf-8"))
        assert manifest["packages"] == [
            {
                "registryType": "pypi",
                "identifier": "clio-kit",
                "version": expected_version,
                "transport": {"type": "stdio"},
                "packageArguments": [
                    {"type": "positional", "value": "mcp-server"},
                    {"type": "positional", "value": path.parent.name},
                ],
            }
        ]
