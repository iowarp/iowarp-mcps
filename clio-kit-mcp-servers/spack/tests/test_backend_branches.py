"""Focused failure-path tests for the bounded Spack backend."""

from __future__ import annotations

import io
import os
import subprocess
import sys
from collections import deque
from pathlib import Path
from types import SimpleNamespace

import pytest

from spack_mcp import backend


def _result(
    stdout: str = "",
    *,
    stderr: str = "",
    returncode: int = 0,
    truncated: bool = False,
    stdout_bytes: bytes | None = None,
) -> backend._CommandResult:
    return backend._CommandResult(
        argv=("spack",),
        returncode=returncode,
        stdout=stdout,
        stderr=stderr,
        duration_seconds=0.1,
        stdout_truncated=truncated,
        stdout_bytes=stdout_bytes,
    )


class _BrokenStream:
    def read(self, _size: int) -> bytes:
        raise OSError("read failed")


def test_bounded_capture_handles_read_errors_and_both_trim_paths(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    broken = backend._BoundedCapture(_BrokenStream())  # type: ignore[arg-type]
    broken.drain()
    assert isinstance(broken.error, OSError)

    monkeypatch.setattr(backend, "_MAX_CAPTURE_BYTES", 3)
    capture = backend._BoundedCapture(io.BytesIO())
    capture.chunks = deque([b"ab", b"cdef"])
    capture.size = 6
    capture._trim()
    assert capture.raw() == b"def"
    assert capture.text() == "[tail truncated]\ndef"

    capture = backend._BoundedCapture(io.BytesIO())
    capture.chunks = deque([b"abcdef"])
    capture.size = 6
    capture._trim()
    assert capture.raw() == b"def"


def test_locate_rejects_missing_and_invalid_prefix(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        backend,
        "find_installed",
        lambda query: backend.SpackFindResult(query=query, packages=[], count=0),
    )
    with pytest.raises(backend.SpackBackendError, match="no installed") as missing:
        backend.locate_installed("missing")
    assert missing.value.code == "not_installed"

    package = backend.SpackPackage(name="demo")
    monkeypatch.setattr(
        backend,
        "find_installed",
        lambda query: backend.SpackFindResult(query=query, packages=[package], count=1),
    )
    monkeypatch.setattr(backend, "_run_spack", lambda *args, **kwargs: _result("relative"))
    with pytest.raises(backend.SpackBackendError, match="invalid") as invalid:
        backend.locate_installed("demo")
    assert invalid.value.code == "invalid_prefix"


def test_install_validates_timeout_observation_and_excerpt(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    for timeout in (0, backend._MAX_INSTALL_TIMEOUT_SECONDS + 1):
        with pytest.raises(backend.SpackBackendError, match="timeout_seconds"):
            backend.install_spec("demo", timeout_seconds=timeout)

    monkeypatch.setattr(backend, "_run_spack", lambda *args, **kwargs: _result())
    monkeypatch.setattr(
        backend,
        "find_installed",
        lambda query: backend.SpackFindResult(query=query, packages=[], count=0),
    )
    with pytest.raises(backend.SpackBackendError) as not_observed:
        backend.install_spec("demo", timeout_seconds=1)
    assert not_observed.value.code == "install_not_observed"

    package = backend.SpackPackage(name="demo")
    monkeypatch.setattr(
        backend,
        "find_installed",
        lambda query: backend.SpackFindResult(query=query, packages=[package], count=1),
    )
    monkeypatch.setattr(backend, "_run_spack", lambda *args, **kwargs: _result("x" * 5000))
    installed = backend.install_spec("demo", timeout_seconds=1)
    assert installed.stdout_excerpt is not None
    assert installed.stdout_excerpt.startswith("[tail truncated]")
    assert len(installed.stdout_excerpt) < 4100


def test_environment_rejects_invalid_input_and_spack_script(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    for specs in ([], ["demo"] * 33):
        with pytest.raises(backend.SpackBackendError) as invalid:
            backend.resolve_environment(specs)
        assert invalid.value.code == "invalid_specs"

    monkeypatch.setattr(backend, "_run_spack", lambda *args, **kwargs: _result(truncated=True))
    with pytest.raises(backend.SpackBackendError) as too_large:
        backend.resolve_environment(["demo"])
    assert too_large.value.code == "response_too_large"

    monkeypatch.setattr(
        backend,
        "_run_spack",
        lambda *args, **kwargs: _result(stdout_bytes=b"\xff"),
    )
    with pytest.raises(backend.SpackBackendError) as invalid_utf8:
        backend.resolve_environment(["demo"])
    assert invalid_utf8.value.code == "invalid_environment"


@pytest.mark.parametrize("failure", [OSError("no bash"), RuntimeError("capture")])
def test_environment_wraps_capture_failures(
    monkeypatch: pytest.MonkeyPatch, failure: Exception
) -> None:
    monkeypatch.setattr(backend, "_run_spack", lambda *args, **kwargs: _result("true"))

    def fail(*_args: object, **_kwargs: object) -> backend._CommandResult:
        raise failure

    monkeypatch.setattr(backend, "_run_bounded_command", fail)
    with pytest.raises(backend.SpackBackendError) as raised:
        backend.resolve_environment(["demo"])
    assert raised.value.code == "environment_capture_failed"
    assert raised.value.detail


def test_environment_rejects_failed_truncated_and_oversized_capture(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(backend, "_run_spack", lambda *args, **kwargs: _result("true"))
    monkeypatch.setattr(
        backend,
        "_run_bounded_command",
        lambda *args, **kwargs: _result(stderr="failed", returncode=7),
    )
    with pytest.raises(backend.SpackBackendError) as failed:
        backend.resolve_environment(["demo"])
    assert failed.value.returncode == 7

    monkeypatch.setattr(
        backend,
        "_run_bounded_command",
        lambda *args, **kwargs: _result(truncated=True),
    )
    with pytest.raises(backend.SpackBackendError) as truncated:
        backend.resolve_environment(["demo"])
    assert truncated.value.code == "environment_too_large"

    monkeypatch.setattr(backend, "_MAX_CAPTURE_BYTES", 1)
    monkeypatch.setattr(
        backend,
        "_run_bounded_command",
        lambda *args, **kwargs: _result(stdout_bytes=backend._ENVIRONMENT_MARKER + b"NEW=value\0"),
    )
    with pytest.raises(backend.SpackBackendError) as oversized:
        backend.resolve_environment(["demo"])
    assert oversized.value.code == "environment_too_large"


@pytest.mark.parametrize(
    ("failure", "code"),
    [
        (OSError("launch"), "launch_failed"),
        (RuntimeError("capture"), "capture_failed"),
    ],
)
def test_run_spack_wraps_launch_and_capture_failures(
    monkeypatch: pytest.MonkeyPatch, failure: Exception, code: str
) -> None:
    monkeypatch.setattr(backend, "_spack_executable", lambda: "spack")

    def fail(*_args: object, **_kwargs: object) -> backend._CommandResult:
        raise failure

    monkeypatch.setattr(backend, "_run_bounded_command", fail)
    with pytest.raises(backend.SpackBackendError) as raised:
        backend._run_spack(["find"], operation="find", timeout_seconds=1)
    assert raised.value.code == code


def test_run_spack_returns_successful_command(monkeypatch: pytest.MonkeyPatch) -> None:
    expected = _result("[]")
    monkeypatch.setattr(backend, "_spack_executable", lambda: "spack")
    monkeypatch.setattr(backend, "_run_bounded_command", lambda *args, **kwargs: expected)
    assert backend._run_spack(["find"], operation="find", timeout_seconds=1) is expected


def test_bounded_command_accepts_stdin_and_rejects_excessive_input(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    result = backend._run_bounded_command(
        [
            sys.executable,
            "-c",
            "import sys; sys.stdout.buffer.write(sys.stdin.buffer.read())",
        ],
        env=os.environ.copy(),
        timeout_seconds=10,
        stdin_payload=b"payload",
    )
    assert result.stdout_bytes == b"payload"

    monkeypatch.setattr(backend, "_MAX_CAPTURE_BYTES", 1)
    with pytest.raises(ValueError, match="input exceeded"):
        backend._run_bounded_command(
            ["unused"],
            env={},
            timeout_seconds=1,
            stdin_payload=b"x" * 66,
        )


def test_bounded_command_closes_owned_input_when_launch_fails(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    stream = io.BytesIO()
    monkeypatch.setattr(backend.tempfile, "TemporaryFile", lambda **_kwargs: stream)
    monkeypatch.setattr(
        backend.subprocess,
        "Popen",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(OSError("launch")),
    )
    with pytest.raises(OSError, match="launch"):
        backend._run_bounded_command(["spack"], env={}, timeout_seconds=1, stdin_payload=b"input")
    assert stream.closed


def test_decode_find_records_rejects_invalid_responses(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    with pytest.raises(backend.SpackBackendError) as truncated:
        backend._decode_find_records(_result("[]", truncated=True))
    assert truncated.value.code == "response_too_large"

    with pytest.raises(backend.SpackBackendError) as invalid_json:
        backend._decode_find_records(_result("{"))
    assert invalid_json.value.code == "invalid_json"

    for payload in ('{"specs": {}}', '["not-an-object"]'):
        with pytest.raises(backend.SpackBackendError) as invalid_shape:
            backend._decode_find_records(_result(payload))
        assert invalid_shape.value.code == "invalid_json_shape"


def test_package_summary_validates_and_normalizes_optional_fields() -> None:
    with pytest.raises(backend.SpackBackendError) as missing:
        backend._package_summary({})
    assert missing.value.code == "invalid_package_record"

    package = backend._package_summary(
        {
            "name": "demo",
            "compiler": "gcc",
            "architecture": "zen3",
            "dag_hash": "abc",
        }
    )
    assert package.compiler == "gcc"
    assert package.architecture == "zen3"
    assert package.dag_hash == "abc"


def test_spack_executable_resolves_all_supported_sources(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    command = tmp_path / "spack"
    command.write_text("", encoding="utf-8")
    monkeypatch.setenv("SPACK_MCP_COMMAND", str(command))
    assert backend._spack_executable() == str(command)

    monkeypatch.setenv("SPACK_MCP_COMMAND", str(tmp_path / "missing"))
    with pytest.raises(backend.SpackBackendError) as configured_missing:
        backend._spack_executable()
    assert configured_missing.value.code == "command_not_found"

    monkeypatch.delenv("SPACK_MCP_COMMAND")
    monkeypatch.setattr(backend.shutil, "which", lambda _name: "/usr/bin/spack")
    assert backend._spack_executable() == "/usr/bin/spack"

    monkeypatch.setattr(backend.shutil, "which", lambda _name: None)
    root = tmp_path / "root"
    rooted = root / "bin" / "spack"
    rooted.parent.mkdir(parents=True)
    rooted.write_text("", encoding="utf-8")
    monkeypatch.setenv("SPACK_ROOT", str(root))
    assert backend._spack_executable() == str(rooted)

    monkeypatch.delenv("SPACK_ROOT")
    monkeypatch.setattr(Path, "home", lambda: tmp_path / "empty-home")
    monkeypatch.setattr(Path, "is_file", lambda _path: False)
    with pytest.raises(backend.SpackBackendError) as absent:
        backend._spack_executable()
    assert absent.value.code == "command_not_found"


@pytest.mark.parametrize("spec", ["", "x" * 1025])
def test_specs_reject_empty_and_overlong_values(spec: str) -> None:
    with pytest.raises(backend.SpackBackendError) as invalid:
        backend._validated_spec(spec)
    assert invalid.value.code == "invalid_spec"


def test_environment_delta_rejects_invalid_encoding_and_limits(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    with pytest.raises(backend.SpackBackendError) as invalid_utf8:
        backend._filtered_environment_delta({}, b"NAME=\xff\0")
    assert invalid_utf8.value.code == "invalid_environment"

    monkeypatch.setattr(backend, "_MAX_ENVIRONMENT_VALUE_BYTES", 1)
    with pytest.raises(backend.SpackBackendError) as value_too_large:
        backend._filtered_environment_delta({}, b"NAME=xx\0")
    assert value_too_large.value.code == "environment_value_too_large"

    monkeypatch.setattr(backend, "_MAX_ENVIRONMENT_VALUE_BYTES", 10)
    monkeypatch.setattr(backend, "_MAX_ENVIRONMENT_VARIABLES", 1)
    with pytest.raises(backend.SpackBackendError) as too_many:
        backend._filtered_environment_delta({}, b"ONE=1\0TWO=2\0")
    assert too_many.value.code == "environment_too_large"


def test_environment_name_and_diagnostic_filters_cover_rejections(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    assert backend._safe_environment_name("INVALID-NAME") is False
    assert backend._safe_environment_name("BASH_FUNC_demo") is False
    assert backend._safe_environment_name("ACCESS_TOKEN") is False
    assert backend._safe_environment_name("SPACK_ROOT") is True

    monkeypatch.setattr(backend, "_MAX_DIAGNOSTIC_BYTES", 4)
    assert backend._bounded_diagnostic("abcdef") == "[tail truncated]\ncdef"


class _Thread:
    def __init__(self, *, alive: bool) -> None:
        self.alive = alive

    def join(self, timeout: float) -> None:
        assert timeout > 0

    def is_alive(self) -> bool:
        return self.alive


def test_finish_captures_cleans_inherited_pipes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    process = SimpleNamespace(stdout=io.BytesIO(), stderr=io.BytesIO())
    thread = _Thread(alive=True)

    def terminate(_process: object, *, include_exited_group: bool = False) -> None:
        assert include_exited_group is True
        thread.alive = False

    monkeypatch.setattr(backend, "_terminate_process_tree", terminate)
    backend._finish_captures(process, [thread])  # type: ignore[arg-type]
    assert process.stdout.closed
    assert process.stderr.closed

    thread = _Thread(alive=True)
    monkeypatch.setattr(backend, "_terminate_process_tree", lambda *args, **kwargs: None)
    with pytest.raises(RuntimeError, match="pipes did not close"):
        backend._finish_captures(process, [thread])  # type: ignore[arg-type]


def test_terminate_process_tree_windows_fallbacks(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class Process:
        pid = 42
        returncode: int | None = None

        def __init__(self) -> None:
            self.waits = 0
            self.terminated = False
            self.killed = False

        def poll(self) -> int | None:
            return self.returncode

        def terminate(self) -> None:
            self.terminated = True

        def wait(self, timeout: int) -> int:
            self.waits += 1
            if self.waits == 1:
                raise subprocess.TimeoutExpired("task", timeout)
            self.returncode = -9
            return -9

        def kill(self) -> None:
            self.killed = True

    process = Process()
    monkeypatch.setattr(backend.os, "name", "nt")
    monkeypatch.setattr(
        backend.subprocess,
        "run",
        lambda *args, **kwargs: (_ for _ in ()).throw(OSError("no taskkill")),
    )
    backend._terminate_process_tree(process)  # type: ignore[arg-type]
    assert process.terminated is True
    assert process.killed is True


def test_terminate_process_tree_posix_escalates(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class Process:
        pid = 42

        def __init__(self) -> None:
            self.waits = 0

        def poll(self) -> None:
            return None

        def wait(self, timeout: int) -> int:
            self.waits += 1
            if self.waits == 1:
                raise subprocess.TimeoutExpired("task", timeout)
            return -9

    signals: list[int] = []
    monkeypatch.setattr(backend.os, "name", "posix")
    monkeypatch.setitem(backend.os.__dict__, "killpg", lambda _pid, sig: signals.append(sig))
    backend._terminate_process_tree(Process())  # type: ignore[arg-type]
    assert signals == [backend.signal.SIGTERM, getattr(backend.signal, "SIGKILL", 9)]
