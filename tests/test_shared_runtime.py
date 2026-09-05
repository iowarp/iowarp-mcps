"""Shared launch semantics: no provisioning, explicit dependencies, honest identity."""

from __future__ import annotations

import json
import os
import sys
import tomllib
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest
from click.testing import CliRunner
from packaging.requirements import Requirement

import clio_kit
from clio_kit import shared_runtime as runtime
from clio_kit.runtime_catalog import build_catalog

ROOT = Path(__file__).resolve().parents[1]


def test_extras_match_every_embedded_server() -> None:
    """A tool's declared dependencies must be installable through its root extra."""
    root = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    extras = root["project"]["optional-dependencies"]
    for path in (ROOT / "clio-kit-mcp-servers").glob("*/pyproject.toml"):
        project = tomllib.loads(path.read_text(encoding="utf-8"))["project"]
        assert sorted(extras[path.parent.name]) == sorted(
            raw for raw in project["dependencies"] if not Requirement(raw).url
        )
    assert all(not Requirement(raw).url for deps in extras.values() for raw in deps)


def test_build_catalog_matches_shipped_source() -> None:
    catalog = build_catalog(ROOT / "clio-kit-mcp-servers")
    assert runtime.load_catalog() == catalog["servers"]
    assert "spack-admin" in catalog["servers"]


def _project(tmp_path: Path) -> Path:
    project = tmp_path / "demo"
    source = project / "src"
    source.mkdir(parents=True)
    (project / "pyproject.toml").write_text(
        '[project]\nname="demo-mcp"\nversion="1.0"\nrequires-python=">=3.11"\n'
        'dependencies=["click>=8"]\n[project.scripts]\ndemo-mcp="demo:main"\n',
        encoding="utf-8",
    )
    (source / "demo.py").write_text("def main(): pass\n", encoding="utf-8")
    return source


def test_source_edit_does_not_change_dependency_identity(tmp_path: Path) -> None:
    source = _project(tmp_path)
    before = build_catalog(tmp_path)["servers"]["demo"]
    (source / "demo.py").write_text("def main(): return 42\n", encoding="utf-8")
    after = build_catalog(tmp_path)["servers"]["demo"]
    assert after["source_sha256"] != before["source_sha256"]
    assert after["requirements_sha256"] == before["requirements_sha256"]


def test_launch_in_current_process_without_cache_or_subprocess(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source = _project(tmp_path)
    (source / "demo.py").write_text(
        "import json, os, sys\n"
        "def main():\n"
        " print(json.dumps(dict(pid=os.getpid(), prefix=sys.prefix, argv=sys.argv, "
        "cwd=os.getcwd(), artifact=os.environ['CLIO_KIT_ARTIFACTS'], "
        "schema=os.environ['CLIO_KIT_RUNTIME_SCHEMA'], "
        "legacy=any(k.startswith('CLIO_KIT_LOCKED_SERVER_') for k in os.environ))))\n",
        encoding="utf-8",
    )
    catalog = build_catalog(tmp_path)["servers"]
    monkeypatch.setattr(runtime, "load_catalog", lambda: catalog)
    monkeypatch.setattr(clio_kit, "get_servers_path", lambda: tmp_path)
    monkeypatch.setattr(sys, "argv", [])
    monkeypatch.setattr(sys, "path", sys.path.copy())
    monkeypatch.setattr(os, "environ", os.environ.copy())
    monkeypatch.setenv("CLIO_KIT_ARTIFACTS", str(tmp_path / "artifacts"))
    monkeypatch.setenv("CLIO_KIT_CACHE_DIR", str(tmp_path / "cache"))
    monkeypatch.setenv("CLIO_KIT_LOCKED_SERVER_SCHEMA", "stale")
    monkeypatch.chdir(tmp_path)

    def forbidden(*args: Any, **kwargs: Any) -> None:
        pytest.fail("shared launch tried to provision or spawn a child")

    monkeypatch.setattr(clio_kit, "_run_locked_local_server", forbidden)
    monkeypatch.setattr(clio_kit.subprocess, "run", forbidden)
    monkeypatch.setattr(clio_kit.subprocess, "Popen", forbidden)
    try:
        result = CliRunner().invoke(
            clio_kit.main, ["mcp-server", "demo", "--", "--profile", "admin"]
        )
        assert result.exit_code == 0, result.output
        data = json.loads(result.output)
        assert data == {
            "pid": os.getpid(),
            "prefix": sys.prefix,
            "argv": ["demo-mcp", "--profile", "admin"],
            "cwd": str(tmp_path),
            "artifact": str(tmp_path / "artifacts"),
            "schema": runtime.RUNTIME_SCHEMA,
            "legacy": False,
        }
        assert not (tmp_path / "cache").exists()
    finally:
        sys.modules.pop("demo", None)


def test_missing_dependencies_fail_without_provisioning(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def missing(name: str) -> str:
        raise runtime.metadata.PackageNotFoundError(name)

    monkeypatch.setattr(runtime.metadata, "version", missing)
    result = CliRunner().invoke(clio_kit.main, ["mcp-server", "pandas"])
    assert result.exit_code != 0
    assert "clio-kit[pandas]" in result.output
    assert "No environment was created" in result.output


def test_isolation_requires_explicit_opt_in(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[tuple[Any, ...]] = []
    monkeypatch.setattr(
        clio_kit, "_run_locked_local_server", lambda *args: calls.append(args)
    )
    result = CliRunner().invoke(clio_kit.main, ["mcp-server", "pandas", "--isolated"])
    assert result.exit_code == 0, result.output
    assert len(calls) == 1


def test_dependency_markers_and_versions(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(runtime.metadata, "version", lambda name: "1.0")
    spec = {
        "requires_python": ">=3.11",
        "requirements": ["click>=2", "absent; python_version < '3'"],
    }
    assert runtime.dependency_problems(spec) == ["click>=2 required (installed 1.0)"]


@pytest.mark.parametrize("valid_origin", [False, True])
def test_external_artifact_requires_matching_installation_evidence(
    monkeypatch: pytest.MonkeyPatch, valid_origin: bool
) -> None:
    origin = {
        "url": "https://example.org/tool.whl",
        "archive_info": {"hashes": {"sha256": "abc"}},
    }
    monkeypatch.setattr(runtime.metadata, "version", lambda name: "1.0")
    monkeypatch.setattr(
        runtime.metadata,
        "distribution",
        lambda name: SimpleNamespace(
            read_text=lambda filename: json.dumps(origin) if valid_origin else None
        ),
    )
    spec = {
        "requires_python": ">=3.11",
        "requirements": ["external @ https://example.org/tool.whl#sha256=abc"],
    }
    assert bool(runtime.dependency_problems(spec)) is not valid_origin


def test_toolkit_version_is_separate_from_dependency_inventory(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    distributions = [
        SimpleNamespace(metadata={"Name": "clio-kit"}, version="1.0"),
        SimpleNamespace(metadata={"Name": "click"}, version="8.3.3"),
    ]
    monkeypatch.setattr(runtime.metadata, "distributions", lambda: distributions)
    monkeypatch.setattr(runtime, "dependency_problems", lambda spec: [])
    before = runtime.runtime_info(("pandas",))
    distributions[0].version = "2.0"
    after = runtime.runtime_info(("pandas",))
    assert before["dependency_sha256"] == after["dependency_sha256"]
    distributions[1].version = "8.4"
    assert (
        runtime.runtime_info(("pandas",))["dependency_sha256"]
        != before["dependency_sha256"]
    )
    assert before["dependency_evidence"] == "installed-version-inventory"


def test_normal_source_lookup_does_not_scan_distribution_records(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def forbidden(name: str) -> list[Path]:
        pytest.fail("warm path enumerated distribution RECORD")

    monkeypatch.setattr(clio_kit, "_distribution_shared_data_roots", forbidden)
    assert clio_kit.get_servers_path() == ROOT / "clio-kit-mcp-servers"
