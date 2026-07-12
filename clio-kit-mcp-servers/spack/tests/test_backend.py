"""Unit tests for bounded, structured Spack backend behavior."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from spack_mcp import backend


def _result(stdout: str, *, operation: str = "find") -> backend._CommandResult:
    return backend._CommandResult(
        argv=("spack", operation),
        returncode=0,
        stdout=stdout,
        stderr="",
        duration_seconds=0.25,
    )


def test_find_returns_stable_package_records(monkeypatch: pytest.MonkeyPatch) -> None:
    payload = [
        {
            "name": "lammps",
            "version": "2025.7.22",
            "hash": "abc123",
            "compiler": {"name": "gcc", "version": "13.2.0"},
            "arch": {"platform": "linux", "target": "zen3"},
        }
    ]
    monkeypatch.setattr(backend, "_run_spack", lambda *args, **kwargs: _result(json.dumps(payload)))

    result = backend.find_installed("lammps")

    assert result.count == 1
    assert result.packages[0].dag_hash == "abc123"
    assert result.packages[0].compiler == "gcc@13.2.0"


def test_find_accepts_spack_specs_envelope(monkeypatch: pytest.MonkeyPatch) -> None:
    """Parse the object envelope emitted by supported Spack JSON versions."""
    payload = {
        "specs": [
            {
                "name": "lammps",
                "version": "20250722.1",
                "full_hash": "q7k4z2h6",
                "compiler": {"name": "gcc", "version": "13.3.0"},
                "architecture": {
                    "platform": "linux",
                    "platform_os": "rocky9",
                    "target": "zen3",
                },
            }
        ]
    }
    monkeypatch.setattr(
        backend,
        "_run_spack",
        lambda *args, **kwargs: _result(json.dumps(payload)),
    )

    result = backend.find_installed("lammps@20250722.1")

    assert result.model_dump(mode="json") == {
        "schema_version": "spack.mcp.result.v1",
        "operation": "find",
        "query": "lammps@20250722.1",
        "packages": [
            {
                "name": "lammps",
                "version": "20250722.1",
                "dag_hash": "q7k4z2h6",
                "compiler": "gcc@13.3.0",
                "architecture": ('{"platform":"linux","platform_os":"rocky9","target":"zen3"}'),
            }
        ],
        "count": 1,
    }


def test_find_sorts_package_records_deterministically(monkeypatch: pytest.MonkeyPatch) -> None:
    payload = [
        {"name": "zlib", "version": "1.3", "hash": "z"},
        {"name": "hdf5", "version": "1.14", "hash": "h"},
    ]
    monkeypatch.setattr(backend, "_run_spack", lambda *args, **kwargs: _result(json.dumps(payload)))

    result = backend.find_installed()

    assert [package.name for package in result.packages] == ["hdf5", "zlib"]


def test_locate_requires_one_exact_match(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        backend,
        "find_installed",
        lambda query: backend.SpackFindResult(
            query=query,
            packages=[
                backend.SpackPackage(name="lammps", dag_hash="one"),
                backend.SpackPackage(name="lammps", dag_hash="two"),
            ],
            count=2,
        ),
    )

    with pytest.raises(backend.SpackBackendError) as error:
        backend.locate_installed("lammps")

    assert error.value.code == "ambiguous_spec"
    assert json.loads(error.value.as_json())["error"]["operation"] == "locate"


def test_locate_returns_exact_prefix(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    prefix = tmp_path / "opt" / "spack" / "lammps"
    package = backend.SpackPackage(
        name="lammps",
        version="20250722.1",
        dag_hash="abc123",
    )
    monkeypatch.setattr(
        backend,
        "find_installed",
        lambda query: backend.SpackFindResult(
            query=query,
            packages=[package],
            count=1,
        ),
    )
    observed: list[list[str]] = []

    def fake_run(
        args: list[str],
        *,
        operation: str,
        timeout_seconds: int,
    ) -> backend._CommandResult:
        observed.append(args)
        return _result(str(prefix), operation=operation)

    monkeypatch.setattr(backend, "_run_spack", fake_run)

    result = backend.locate_installed("lammps@20250722.1")

    assert observed == [["location", "-i", "/abc123"]]
    assert result.package == package
    assert result.prefix == str(prefix)
    assert result.load_spec == "/abc123"


def test_specs_are_argv_not_shell_text(monkeypatch: pytest.MonkeyPatch) -> None:
    observed: list[list[str]] = []

    def fake_run(
        args: list[str],
        *,
        operation: str,
        timeout_seconds: int,
    ) -> backend._CommandResult:
        observed.append(args)
        if operation == "install":
            return _result("installed", operation=operation)
        return _result('[{"name":"demo","hash":"hash"}]')

    monkeypatch.setattr(backend, "_run_spack", fake_run)

    backend.install_spec("demo@1.0 +mpi", timeout_seconds=5)

    assert observed[0] == ["install", "--reuse", "demo@1.0 +mpi"]


def test_install_can_explicitly_disable_reuse(monkeypatch: pytest.MonkeyPatch) -> None:
    observed: list[list[str]] = []

    def fake_run(
        args: list[str],
        *,
        operation: str,
        timeout_seconds: int,
    ) -> backend._CommandResult:
        observed.append(args)
        if operation == "install":
            return _result("installed", operation=operation)
        return _result('[{"name":"demo","hash":"hash"}]')

    monkeypatch.setattr(backend, "_run_spack", fake_run)

    result = backend.install_spec("demo@1.0", reuse=False, timeout_seconds=5)

    assert observed[0] == ["install", "demo@1.0"]
    assert result.reuse is False


def test_spack_command_failure_is_structured(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(backend, "_spack_executable", lambda: "/opt/spack/bin/spack")
    monkeypatch.setattr(
        backend,
        "_run_bounded_command",
        lambda *args, **kwargs: backend._CommandResult(
            argv=("/opt/spack/bin/spack", "find"),
            returncode=7,
            stdout="",
            stderr="concretization failed",
            duration_seconds=0.1,
        ),
    )

    with pytest.raises(backend.SpackBackendError) as error:
        backend.find_installed("missing")

    assert error.value.code == "command_failed"
    assert error.value.returncode == 7
    assert error.value.detail == "concretization failed"


def test_spack_command_timeout_is_structured(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(backend, "_spack_executable", lambda: "/opt/spack/bin/spack")

    def time_out(*args: object, **kwargs: object) -> backend._CommandResult:
        raise subprocess.TimeoutExpired(["spack", "find"], timeout=120)

    monkeypatch.setattr(backend, "_run_bounded_command", time_out)

    with pytest.raises(backend.SpackBackendError) as error:
        backend.find_installed("missing")

    assert error.value.code == "timed_out"
    assert error.value.operation == "find"


def test_environment_filter_removes_unchanged_and_secret_values() -> None:
    raw = b"PATH=/spack/bin\0API_TOKEN=secret\0UNCHANGED=same\0SPACK_ROOT=/spack\0"

    result = backend._filtered_environment_delta({"UNCHANGED": "same"}, raw)

    assert result == {"PATH": "/spack/bin", "SPACK_ROOT": "/spack"}


def test_bounded_command_drains_streams_and_retains_only_tail(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(backend, "_MAX_CAPTURE_BYTES", 64)

    result = backend._run_bounded_command(
        [
            sys.executable,
            "-c",
            "import sys; sys.stdout.buffer.write(b'a' * 4096 + b'TAIL'); "
            "sys.stderr.buffer.write(b'b' * 4096 + b'ERR')",
        ],
        env=os.environ.copy(),
        timeout_seconds=10,
    )

    assert result.stdout_truncated is True
    assert result.stderr_truncated is True
    assert result.stdout_bytes is not None
    assert result.stderr_bytes is not None
    assert len(result.stdout_bytes) == 64
    assert len(result.stderr_bytes) == 64
    assert result.stdout_bytes.endswith(b"TAIL")
    assert result.stderr_bytes.endswith(b"ERR")


def test_bounded_command_timeout_terminates_child() -> None:
    with pytest.raises(subprocess.TimeoutExpired):
        backend._run_bounded_command(
            [sys.executable, "-c", "import time; time.sleep(30)"],
            env=os.environ.copy(),
            timeout_seconds=1,
        )


def test_environment_uses_integrity_marker_and_returns_sorted_delta(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    loaded = _result("export PATH=/spack/bin:$PATH", operation="environment")
    captured = backend._CommandResult(
        argv=("bash",),
        returncode=0,
        stdout="",
        stderr="",
        duration_seconds=0.1,
        stdout_bytes=(
            b"ignored warning\n"
            + backend._ENVIRONMENT_MARKER
            + b"SPACK_ROOT=/spack\0PATH=/spack/bin\0API_TOKEN=secret\0"
        ),
    )
    monkeypatch.setattr(backend, "_run_spack", lambda *args, **kwargs: loaded)
    monkeypatch.setattr(backend, "_run_bounded_command", lambda *args, **kwargs: captured)

    result = backend.resolve_environment(["lammps"])

    assert list(result.environment) == ["PATH", "SPACK_ROOT"]
    assert result.variable_names == ["PATH", "SPACK_ROOT"]


def test_environment_rejects_output_without_integrity_marker(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    loaded = _result("export PATH=/spack/bin:$PATH", operation="environment")
    captured = backend._CommandResult(
        argv=("bash",),
        returncode=0,
        stdout="PATH=/spack/bin",
        stderr="",
        duration_seconds=0.1,
        stdout_bytes=b"PATH=/spack/bin\0",
    )
    monkeypatch.setattr(backend, "_run_spack", lambda *args, **kwargs: loaded)
    monkeypatch.setattr(backend, "_run_bounded_command", lambda *args, **kwargs: captured)

    with pytest.raises(backend.SpackBackendError) as error:
        backend.resolve_environment(["lammps"])

    assert error.value.code == "invalid_environment"


def test_find_rejects_excessive_record_count(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(backend, "_MAX_PACKAGE_RECORDS", 1)

    with pytest.raises(backend.SpackBackendError) as error:
        backend._decode_find_records(_result('[{"name":"a"},{"name":"b"}]'))

    assert error.value.code == "response_too_large"


def test_control_characters_are_rejected() -> None:
    with pytest.raises(backend.SpackBackendError) as error:
        backend.find_installed("lammps\nrm -rf /tmp/example")

    assert error.value.code == "invalid_spec"


@pytest.mark.parametrize("spec", ["--help", "-C", "  --config-scope=user"])
def test_option_like_specs_are_rejected(spec: str) -> None:
    with pytest.raises(backend.SpackBackendError) as error:
        backend.find_installed(spec)

    assert error.value.code == "invalid_spec"
