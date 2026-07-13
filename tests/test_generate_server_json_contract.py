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
        server_version="2.0.0",
        pypi_version="2.3.0",
    )

    assert manifest["version"] == "2.0.0"
    assert manifest["packages"] == [
        {
            "registryType": "pypi",
            "identifier": "clio-kit",
            "version": "2.3.0",
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
    expected_server_versions = GENERATOR.read_server_versions(repository_root)
    publish_servers = GENERATOR.read_registry_publish_servers(repository_root)
    marketplace = json.loads(
        (repository_root / ".claude-plugin" / "marketplace.json").read_text(
            encoding="utf-8"
        )
    )
    marketplace_plugins = {
        plugin["name"].removeprefix("clio-"): plugin
        for plugin in marketplace["plugins"]
    }
    gemini_extension = json.loads(
        (repository_root / "gemini-extension.json").read_text(encoding="utf-8")
    )
    readme = (repository_root / "README.md").read_text(encoding="utf-8")

    assert projects
    assert manifests == [project / "server.json" for project in projects]
    assert list(expected_server_versions) == sorted(expected_server_versions)
    assert set(expected_server_versions) == {project.name for project in projects}
    assert publish_servers == ("spack",)
    assert marketplace["metadata"]["version"] == expected_version
    assert set(marketplace_plugins) == set(expected_server_versions)
    assert gemini_extension["version"] == expected_version
    for path in manifests:
        server_name = path.parent.name
        manifest = json.loads(path.read_text(encoding="utf-8"))
        plugin = json.loads(
            (path.parent / ".claude-plugin" / "plugin.json").read_text(encoding="utf-8")
        )
        assert manifest["version"] == expected_server_versions[server_name]
        assert plugin["version"] == expected_server_versions[server_name]
        assert (
            marketplace_plugins[server_name]["version"]
            == expected_server_versions[server_name]
        )
        assert (
            f"| **`{server_name}`** | {expected_server_versions[server_name]} |"
            in readme
        )
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


def test_persistent_configs_use_the_installed_tool() -> None:
    """Long-lived MCP client configurations must not depend on uvx caches."""
    assert GENERATOR.build_claude_desktop_config(["jarvis"]) == {
        "mcpServers": {
            "clio-jarvis": {
                "command": "clio-kit",
                "args": ["mcp-server", "jarvis"],
            }
        }
    }
    extension = GENERATOR.build_gemini_extension(
        ["jarvis"],
        pypi_version="2.3.0",
    )
    assert extension["version"] == "2.3.0"
    assert extension["mcpServers"] == {
        "clio-jarvis": {
            "command": "clio-kit",
            "args": ["mcp-server", "jarvis"],
        }
    }


def test_plugin_versions_distinguish_contracts_from_the_root_wheel(
    tmp_path: Path,
) -> None:
    """Per-server plugins use contract versions while bundles use the wheel version."""
    GENERATOR.write_claude_plugin_files(
        tmp_path,
        "spack",
        {"description": "Spack MCP", "version": "9.9.9"},
        server_version="2.0.0",
    )
    plugin = json.loads(
        (tmp_path / ".claude-plugin" / "plugin.json").read_text(encoding="utf-8")
    )
    marketplace = GENERATOR.build_marketplace_json(
        [{"name": "clio-spack", "version": "2.0.0"}],
        pypi_version="2.3.0",
    )

    assert plugin["version"] == "2.0.0"
    assert marketplace["metadata"]["version"] == "2.3.0"
    assert marketplace["plugins"][0]["version"] == "2.0.0"
