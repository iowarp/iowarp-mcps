"""Cross-server contract tests for Spack discovery and JARVIS execution."""

from __future__ import annotations

import importlib
import json
import os
import stat
import sys
from pathlib import Path
from types import ModuleType

import pytest

from jarvis_mcp.capabilities import jarvis_handler


def _load_spack_backend(monkeypatch: pytest.MonkeyPatch) -> ModuleType:
    """Import the sibling Spack MCP backend from this clio-kit checkout."""
    servers_root = Path(__file__).resolve().parents[2]
    monkeypatch.syspath_prepend(str(servers_root / "spack" / "src"))
    return importlib.import_module("spack_mcp.backend")


def _fake_spack_command(tmp_path: Path) -> tuple[Path, Path]:
    """Create a real subprocess shim implementing the tested Spack commands."""
    script = tmp_path / "fake_spack.py"
    log = tmp_path / "spack-argv.jsonl"
    script.write_text(
        """from __future__ import annotations

import json
import os
import sys

args = sys.argv[1:]
with open(os.environ["FAKE_SPACK_LOG"], "a", encoding="utf-8") as stream:
    stream.write(json.dumps(args, separators=(",", ":")) + "\\n")

if args[:2] == ["find", "--json"]:
    print(json.dumps([{"name": "lammps", "version": "1.0", "hash": "abc123"}]))
elif args == ["location", "-i", "/abc123"]:
    print(os.environ["FAKE_SPACK_PREFIX"])
elif args == ["load", "--sh", "/abc123"]:
    sys.stdout.buffer.write(
        b'export PATH=/spack/abc123/bin:"$PATH"\\nexport SPACK_ROOT=/spack\\n'
    )
else:
    print(f"unsupported fake Spack arguments: {args!r}", file=sys.stderr)
    raise SystemExit(23)
""",
        encoding="utf-8",
    )
    if os.name == "nt":
        command = tmp_path / "fake-spack.cmd"
        command.write_text(
            f'@echo off\n"{sys.executable}" "{script}" %*\n',
            encoding="utf-8",
        )
    else:
        command = tmp_path / "fake-spack"
        command.write_text(
            f"#!/usr/bin/env sh\nexec '{sys.executable}' '{script}' \"$@\"\n",
            encoding="utf-8",
        )
        command.chmod(command.stat().st_mode | stat.S_IXUSR)
    return command, log


@pytest.mark.integration
def test_locate_load_spec_is_consumed_by_jarvis_execution(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """A canonical Spack locate result is passed unchanged to JARVIS load."""
    backend = _load_spack_backend(monkeypatch)
    command, log = _fake_spack_command(tmp_path)
    prefix = (tmp_path / "installed" / "lammps").resolve()
    monkeypatch.setenv("SPACK_MCP_COMMAND", str(command))
    monkeypatch.setenv("JARVIS_MCP_SPACK_COMMAND", str(command))
    monkeypatch.setenv("FAKE_SPACK_LOG", str(log))
    monkeypatch.setenv("FAKE_SPACK_PREFIX", str(prefix))

    located = backend.locate_installed("lammps@1.0")
    if os.name == "nt":
        bash = Path(jarvis_handler._bash_executable()).resolve()
        assert "system32" not in {part.casefold() for part in bash.parts}
    environment = jarvis_handler._capture_spack_environment([located.load_spec])

    assert located.load_spec == "/abc123"
    assert located.prefix == str(prefix)
    assert environment["SPACK_ROOT"] == "/spack"
    assert environment["PATH"].startswith("/spack/abc123/bin:")
    calls = [json.loads(line) for line in log.read_text(encoding="utf-8").splitlines()]
    assert calls == [
        ["find", "--json", "lammps@1.0"],
        ["location", "-i", "/abc123"],
        ["load", "--sh", "/abc123"],
    ]
