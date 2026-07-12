"""Real cross-platform tests for the Windows Job Object boundary."""

from __future__ import annotations

import os
import subprocess
import sys
import threading
from pathlib import Path
from types import SimpleNamespace
from typing import Any, cast

import pytest

from spack_mcp import windows_job


def _as_process(process: object) -> subprocess.Popen[Any]:
    """Cast a deliberately minimal process test double to the runtime protocol."""
    return cast(subprocess.Popen[Any], process)


def _as_writer(writer: object) -> threading.Thread:
    """Cast a deliberately minimal writer test double to the runtime protocol."""
    return cast(threading.Thread, writer)


class _FinishedWriter:
    """Thread-like writer that has already completed."""

    def join(self, timeout: float | None = None) -> None:
        """Accept a bounded join without blocking."""
        del timeout

    def is_alive(self) -> bool:
        """Report that the writer has completed."""
        return False


class _StuckWriter:
    """Thread-like writer that remains alive after every join."""

    def __init__(self) -> None:
        self.join_count = 0

    def join(self, timeout: float | None = None) -> None:
        """Record each bounded join attempt."""
        del timeout
        self.join_count += 1

    def is_alive(self) -> bool:
        """Report that the writer is still blocked."""
        return True


class _RaisingStdin:
    """Pipe-like object whose close operation reports an OS error."""

    def __init__(self) -> None:
        self.close_count = 0

    def close(self) -> None:
        """Record the close and emulate an already-broken pipe."""
        self.close_count += 1
        raise OSError("pipe already closed")


class _TimeoutProcess:
    """Process-like object that requires the terminate timeout fallback."""

    stdin = None

    def __init__(self) -> None:
        self.killed = False
        self.wait_count = 0

    def poll(self) -> None:
        """Report that the process has not exited."""
        return None

    def wait(self, timeout: float | None = None) -> int:
        """Time out once, then report a successful forced exit."""
        self.wait_count += 1
        if self.wait_count == 1:
            raise subprocess.TimeoutExpired("test-process", timeout or 0.0)
        return 0

    def kill(self) -> None:
        """Record the forced process kill."""
        self.killed = True


class _SpawnedProcess:
    """Process-like object used to prove spawn-failure cleanup."""

    stdin = None

    def __init__(self) -> None:
        self.killed = False
        self.wait_timeouts: list[float | None] = []

    def kill(self) -> None:
        """Record the forced process kill."""
        self.killed = True

    def wait(self, timeout: float | None = None) -> int:
        """Record the bounded reap and report success."""
        self.wait_timeouts.append(timeout)
        return 0


def _stop_process(process: subprocess.Popen[bytes]) -> None:
    """Stop a test child without leaving a background process behind."""
    if process.poll() is not None:
        return
    process.terminate()
    try:
        process.wait(timeout=5)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait(timeout=5)


def test_process_start_identity_tracks_a_real_live_process() -> None:
    """A live Windows PID has a stable creation identity until it exits."""
    if os.name != "nt":
        with pytest.raises(RuntimeError, match="unavailable"):
            windows_job.process_start_identity(os.getpid())
        return

    process = subprocess.Popen(
        [sys.executable, "-c", "import time; time.sleep(60)"],
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    try:
        identity = windows_job.process_start_identity(process.pid)
        assert identity is not None
        assert identity.startswith("windows-filetime:")
        assert identity == windows_job.process_start_identity(process.pid)
    finally:
        _stop_process(process)

    assert windows_job.process_start_identity(process.pid) is None


def test_job_rejects_and_kills_a_real_retained_descendant(tmp_path: Path) -> None:
    """A completed broker cannot silently leave a descendant running."""
    if os.name != "nt":
        with pytest.raises(RuntimeError, match="unavailable"):
            windows_job.spawn_windows_job_process(["unused"], shell=False, stdin_payload=None)
        return

    pid_path = tmp_path / "descendant.pid"
    descendant_code = "import time; time.sleep(60)"
    parent_code = (
        "import pathlib,subprocess,sys;"
        f"child=subprocess.Popen([sys.executable,'-c',{descendant_code!r}],"
        "stdin=subprocess.DEVNULL,stdout=subprocess.DEVNULL,"
        "stderr=subprocess.DEVNULL);"
        f"pathlib.Path({str(pid_path)!r}).write_text(str(child.pid),encoding='ascii')"
    )
    process, job = windows_job.spawn_windows_job_process(
        [sys.executable, "-c", parent_code],
        shell=False,
        stdin_payload=None,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    try:
        assert process.wait(timeout=15) == 0
        descendant_pid = int(pid_path.read_text(encoding="ascii"))
        assert windows_job.process_start_identity(descendant_pid) is not None
        with pytest.raises(
            RuntimeError,
            match=r"left [1-9][0-9]* Windows Job Object descendants",
        ):
            job.ensure_empty(process, timeout_seconds=5)
        assert job.terminated_for_capture is True
        assert windows_job.process_start_identity(descendant_pid) is None
    finally:
        job.close(process, timeout_seconds=5)
        if process.stdout is not None:
            process.stdout.close()
        if process.stderr is not None:
            process.stderr.close()


def test_platform_specific_argument_validation(monkeypatch: pytest.MonkeyPatch) -> None:
    """Platform wrappers fail explicitly before unsafe process creation."""
    if os.name != "nt":
        with pytest.raises(RuntimeError, match="ctypes APIs"):
            windows_job._load_kernel32()
        with pytest.raises(RuntimeError, match="error APIs"):
            windows_job._last_error()
        return

    with pytest.raises(ValueError, match="positive"):
        windows_job.process_start_identity(0)
    with pytest.raises(ValueError, match="owns broker stdin"):
        windows_job.spawn_windows_job_process(
            ["unused"],
            shell=False,
            stdin_payload=None,
            stdin=subprocess.DEVNULL,
        )
    monkeypatch.setattr(windows_job, "_MAX_BROKER_MESSAGE_BYTES", 1)
    with pytest.raises(ValueError, match="message bound"):
        windows_job.spawn_windows_job_process(
            ["message-is-too-long"], shell=False, stdin_payload=None
        )
    with pytest.raises(RuntimeError, match="process handle"):
        windows_job._assign_process(1, _as_process(SimpleNamespace()))


def test_spawn_assignment_failure_reaps_process_and_closes_job(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Assignment failure cannot leak either the broker or Job handle."""
    if os.name != "nt":
        with pytest.raises(RuntimeError, match="unavailable"):
            windows_job.spawn_windows_job_process(["unused"], shell=False, stdin_payload=None)
        return

    process = _SpawnedProcess()
    closed_handles: list[int] = []
    popen_kwargs: list[dict[str, Any]] = []

    def fake_popen(*args: Any, **kwargs: Any) -> _SpawnedProcess:
        del args
        popen_kwargs.append(kwargs)
        return process

    def fail_assignment(handle: int, assigned: object) -> None:
        assert handle == 41
        assert assigned is process
        raise RuntimeError("assignment failed")

    monkeypatch.setattr(windows_job, "_create_job", lambda: 41)
    monkeypatch.setattr(subprocess, "Popen", fake_popen)
    monkeypatch.setattr(windows_job, "_assign_process", fail_assignment)
    monkeypatch.setattr(windows_job, "_close_handle", closed_handles.append)

    with pytest.raises(RuntimeError, match="assignment failed"):
        windows_job.spawn_windows_job_process(
            ["unused"],
            shell=False,
            stdin_payload="payload",
            creationflags=4,
        )

    assert process.killed is True
    assert process.wait_timeouts == [5]
    assert closed_handles == [41]
    assert popen_kwargs[0]["creationflags"] & 4


def test_writer_failure_and_stall_are_explicit(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Writer exceptions and an unresponsive writer both fail loudly."""
    writer_error = ValueError("frame write failed")
    failed_job = windows_job.WindowsJob(
        handle=1,
        writer=_as_writer(_FinishedWriter()),
        writer_errors=[writer_error],
    )
    with pytest.raises(RuntimeError, match="broker input failed") as failure:
        failed_job._finish_writer(
            _as_process(SimpleNamespace(stdin=None)),
            timeout_seconds=1,
        )
    assert failure.value.__cause__ is writer_error

    stuck_writer = _StuckWriter()
    stdin = _RaisingStdin()
    terminated_handles: list[int] = []
    monkeypatch.setattr(windows_job, "_active_processes", lambda handle: 1)
    monkeypatch.setattr(windows_job, "_terminate_job", terminated_handles.append)
    stuck_job = windows_job.WindowsJob(
        handle=7,
        writer=_as_writer(stuck_writer),
        writer_errors=[],
    )
    with pytest.raises(RuntimeError, match="writer did not stop"):
        stuck_job._finish_writer(
            _as_process(SimpleNamespace(stdin=stdin)),
            timeout_seconds=1,
        )
    assert stuck_writer.join_count == 2
    assert stdin.close_count == 1
    assert terminated_handles == [7]


def test_terminate_uses_bounded_process_kill_fallback(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A root process that misses its deadline is killed and reaped."""
    process = _TimeoutProcess()
    empty_waits: list[tuple[int, float]] = []

    def record_empty_wait(handle: int, *, timeout_seconds: float) -> None:
        empty_waits.append((handle, timeout_seconds))

    monkeypatch.setattr(windows_job, "_active_processes", lambda handle: 0)
    monkeypatch.setattr(windows_job, "_wait_until_empty", record_empty_wait)
    job = windows_job.WindowsJob(
        handle=11,
        writer=_as_writer(_FinishedWriter()),
        writer_errors=[],
    )
    job.terminate(_as_process(process), timeout_seconds=0.01)

    assert process.killed is True
    assert process.wait_count == 2
    assert empty_waits == [(11, 0.01)]


def test_empty_and_closed_job_lifecycle_is_idempotent(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Empty completion succeeds and repeated cleanup is a no-op."""
    process = _as_process(SimpleNamespace(stdin=None))
    monkeypatch.setattr(windows_job, "_active_after_wait", lambda *args, **kwargs: 0)
    job = windows_job.WindowsJob(
        handle=13,
        writer=_as_writer(_FinishedWriter()),
        writer_errors=[],
    )
    job.ensure_empty(process, timeout_seconds=1)

    closed_job = windows_job.WindowsJob(
        handle=17,
        writer=_as_writer(_FinishedWriter()),
        writer_errors=[],
        closed=True,
    )
    closed_job.terminate(process, timeout_seconds=1)
    closed_job.close(process, timeout_seconds=1)

    monkeypatch.setattr(windows_job, "_active_after_wait", lambda *args, **kwargs: 2)
    with pytest.raises(RuntimeError, match="remained populated: 2"):
        windows_job._wait_until_empty(17, timeout_seconds=0)
