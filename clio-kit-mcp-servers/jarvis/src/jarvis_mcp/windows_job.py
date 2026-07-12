"""Identity-pinned Windows Job Object ownership for bounded subprocesses."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import threading
import time
from dataclasses import dataclass, field
from typing import Any


_JOB_EMPTY_TIMEOUT_SECONDS = 10.0
_NATURAL_EXIT_GRACE_SECONDS = 1.0
_WRITER_TIMEOUT_SECONDS = 5.0
_POLL_SECONDS = 0.02
_MAX_BROKER_MESSAGE_BYTES = 1024 * 1024

_BROKER_SCRIPT = r"""
import json
import os
import subprocess
import sys


def read_exact(descriptor, size):
    chunks = []
    remaining = size
    while remaining:
        chunk = os.read(descriptor, remaining)
        if not chunk:
            raise SystemExit(125)
        chunks.append(chunk)
        remaining -= len(chunk)
    return b"".join(chunks)


descriptor = sys.stdin.fileno()
message_size = int.from_bytes(read_exact(descriptor, 4), "big")
if message_size < 1 or message_size > 1024 * 1024:
    raise SystemExit(125)
try:
    message = json.loads(read_exact(descriptor, message_size))
except (UnicodeDecodeError, json.JSONDecodeError):
    raise SystemExit(125)
if not isinstance(message, dict) or not isinstance(message.get("shell"), bool):
    raise SystemExit(125)
command = message.get("command")
if not isinstance(command, (str, list)):
    raise SystemExit(125)
if isinstance(command, list) and not all(isinstance(item, str) for item in command):
    raise SystemExit(125)
child = subprocess.Popen(command, shell=message["shell"], stdin=descriptor)
raise SystemExit(child.wait())
"""


@dataclass(slots=True)
class WindowsJob:
    """Own one process tree through a retained kernel Job Object handle."""

    handle: int
    writer: threading.Thread
    writer_errors: list[BaseException]
    closed: bool = False
    terminated_for_capture: bool = False
    _lock: threading.Lock = field(default_factory=threading.Lock)

    def terminate(
        self,
        process: subprocess.Popen[Any],
        *,
        timeout_seconds: float = _JOB_EMPTY_TIMEOUT_SECONDS,
    ) -> None:
        """Terminate the pinned job and prove that it became empty."""
        with self._lock:
            if self.closed:
                return
            if _active_processes(self.handle):
                _terminate_job(self.handle)
        if process.poll() is None:
            try:
                process.wait(timeout=timeout_seconds)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=timeout_seconds)
        self._finish_writer(process, timeout_seconds=timeout_seconds)
        _wait_until_empty(self.handle, timeout_seconds=timeout_seconds)

    def ensure_empty(
        self,
        process: subprocess.Popen[Any],
        *,
        timeout_seconds: float = _JOB_EMPTY_TIMEOUT_SECONDS,
    ) -> None:
        """Reject and clean descendants left behind by a completed root."""
        self._finish_writer(process, timeout_seconds=timeout_seconds)
        residual = _active_after_wait(
            self.handle,
            timeout_seconds=_NATURAL_EXIT_GRACE_SECONDS,
        )
        if residual == 0:
            return
        self.terminated_for_capture = True
        self.terminate(process, timeout_seconds=timeout_seconds)
        raise RuntimeError(
            f"completed subprocess left {residual} Windows Job Object descendants"
        )

    def close(
        self,
        process: subprocess.Popen[Any],
        *,
        timeout_seconds: float = _JOB_EMPTY_TIMEOUT_SECONDS,
    ) -> None:
        """Close the retained handle only after bounded tree cleanup."""
        with self._lock:
            if self.closed:
                return
        try:
            if _active_processes(self.handle):
                self.terminate(process, timeout_seconds=timeout_seconds)
        finally:
            with self._lock:
                if not self.closed:
                    _close_handle(self.handle)
                    self.closed = True

    def _finish_writer(
        self,
        process: subprocess.Popen[Any],
        *,
        timeout_seconds: float,
    ) -> None:
        self.writer.join(timeout=min(timeout_seconds, _WRITER_TIMEOUT_SECONDS))
        if self.writer.is_alive():
            with self._lock:
                if not self.closed and _active_processes(self.handle):
                    _terminate_job(self.handle)
            if process.stdin is not None:
                try:
                    process.stdin.close()
                except (OSError, ValueError):
                    pass
            self.writer.join(timeout=1)
            if self.writer.is_alive():
                raise RuntimeError("Windows broker stdin writer did not stop")
        if self.writer_errors:
            raise RuntimeError(
                f"Windows broker input failed: {self.writer_errors[0]}"
            ) from self.writer_errors[0]


def spawn_windows_job_process(
    command: str | list[str],
    *,
    shell: bool,
    stdin_payload: bytes | str | None,
    **popen_kwargs: Any,
) -> tuple[subprocess.Popen[Any], WindowsJob]:
    """Spawn only after pinning a blocked broker to a kill-on-close job."""
    if os.name != "nt":
        raise RuntimeError("Windows Job Objects are unavailable on this platform")
    if "stdin" in popen_kwargs:
        raise ValueError("spawn_windows_job_process owns broker stdin")
    message = json.dumps(
        {"command": command, "shell": shell},
        separators=(",", ":"),
    ).encode("utf-8")
    if not message or len(message) > _MAX_BROKER_MESSAGE_BYTES:
        raise ValueError("Windows broker command exceeded its message bound")
    payload = (
        b""
        if stdin_payload is None
        else stdin_payload.encode("utf-8")
        if isinstance(stdin_payload, str)
        else stdin_payload
    )
    frame = len(message).to_bytes(4, "big") + message + payload

    handle = _create_job()
    creationflags = int(popen_kwargs.pop("creationflags", 0))
    creationflags |= int(getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0))
    process: subprocess.Popen[Any] | None = None
    try:
        process = subprocess.Popen(
            [sys.executable, "-I", "-S", "-c", _BROKER_SCRIPT],
            stdin=subprocess.PIPE,
            creationflags=creationflags,
            **popen_kwargs,
        )
        _assign_process(handle, process)
    except BaseException:
        if process is not None:
            process.kill()
            process.wait(timeout=5)
        _close_handle(handle)
        raise

    writer_errors: list[BaseException] = []

    def write_frame() -> None:
        try:
            if process.stdin is None:
                raise RuntimeError("Windows broker stdin pipe was not created")
            stream = getattr(process.stdin, "buffer", process.stdin)
            stream.write(frame)
            stream.flush()
        except BaseException as exc:
            writer_errors.append(exc)
        finally:
            if process.stdin is not None:
                try:
                    process.stdin.close()
                except (OSError, ValueError):
                    pass

    writer = threading.Thread(target=write_frame, daemon=True)
    writer.start()
    return process, WindowsJob(
        handle=handle,
        writer=writer,
        writer_errors=writer_errors,
    )


def process_start_identity(process_id: int) -> str | None:
    """Return a Windows process creation identity without invoking tasklist."""
    if os.name != "nt":
        raise RuntimeError("Windows process identities are unavailable")
    if process_id <= 0:
        raise ValueError("process_id must be positive")
    import ctypes
    from ctypes import wintypes

    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel32.OpenProcess.restype = wintypes.HANDLE
    process_handle = kernel32.OpenProcess(0x1000, False, process_id)
    if not process_handle:
        error = ctypes.get_last_error()
        if error in {87, 1168}:
            return None
        raise RuntimeError(f"OpenProcess failed for {process_id}: {error}")
    creation = wintypes.FILETIME()
    exit_time = wintypes.FILETIME()
    kernel = wintypes.FILETIME()
    user = wintypes.FILETIME()
    try:
        exit_code = wintypes.DWORD()
        if not kernel32.GetExitCodeProcess(process_handle, ctypes.byref(exit_code)):
            raise RuntimeError(
                f"GetExitCodeProcess failed for {process_id}: {ctypes.get_last_error()}"
            )
        if exit_code.value != 259:
            return None
        if not kernel32.GetProcessTimes(
            process_handle,
            ctypes.byref(creation),
            ctypes.byref(exit_time),
            ctypes.byref(kernel),
            ctypes.byref(user),
        ):
            raise RuntimeError(
                f"GetProcessTimes failed for {process_id}: {ctypes.get_last_error()}"
            )
        value = (int(creation.dwHighDateTime) << 32) | int(creation.dwLowDateTime)
        return f"windows-filetime:{value}"
    finally:
        kernel32.CloseHandle(process_handle)


def _create_job() -> int:
    import ctypes
    from ctypes import wintypes

    class BasicLimitInformation(ctypes.Structure):
        _fields_ = [
            ("PerProcessUserTimeLimit", ctypes.c_longlong),
            ("PerJobUserTimeLimit", ctypes.c_longlong),
            ("LimitFlags", wintypes.DWORD),
            ("MinimumWorkingSetSize", ctypes.c_size_t),
            ("MaximumWorkingSetSize", ctypes.c_size_t),
            ("ActiveProcessLimit", wintypes.DWORD),
            ("Affinity", ctypes.c_size_t),
            ("PriorityClass", wintypes.DWORD),
            ("SchedulingClass", wintypes.DWORD),
        ]

    class IoCounters(ctypes.Structure):
        _fields_ = [
            (name, ctypes.c_ulonglong)
            for name in (
                "ReadOperationCount",
                "WriteOperationCount",
                "OtherOperationCount",
                "ReadTransferCount",
                "WriteTransferCount",
                "OtherTransferCount",
            )
        ]

    class ExtendedLimitInformation(ctypes.Structure):
        _fields_ = [
            ("BasicLimitInformation", BasicLimitInformation),
            ("IoInfo", IoCounters),
            ("ProcessMemoryLimit", ctypes.c_size_t),
            ("JobMemoryLimit", ctypes.c_size_t),
            ("PeakProcessMemoryUsed", ctypes.c_size_t),
            ("PeakJobMemoryUsed", ctypes.c_size_t),
        ]

    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel32.CreateJobObjectW.restype = wintypes.HANDLE
    handle = kernel32.CreateJobObjectW(None, None)
    if not handle:
        raise RuntimeError(f"CreateJobObjectW failed: {ctypes.get_last_error()}")
    information = ExtendedLimitInformation()
    information.BasicLimitInformation.LimitFlags = 0x00002000
    if not kernel32.SetInformationJobObject(
        handle,
        9,
        ctypes.byref(information),
        ctypes.sizeof(information),
    ):
        error = ctypes.get_last_error()
        kernel32.CloseHandle(handle)
        raise RuntimeError(f"SetInformationJobObject failed: {error}")
    return int(handle)


def _assign_process(handle: int, process: subprocess.Popen[Any]) -> None:
    import ctypes
    from ctypes import wintypes

    process_handle = getattr(process, "_handle", None)
    if process_handle is None:
        raise RuntimeError("Popen did not expose a Windows process handle")
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel32.AssignProcessToJobObject.argtypes = [wintypes.HANDLE, wintypes.HANDLE]
    if not kernel32.AssignProcessToJobObject(handle, int(process_handle)):
        raise RuntimeError(
            f"AssignProcessToJobObject failed: {ctypes.get_last_error()}"
        )


def _terminate_job(handle: int) -> None:
    import ctypes
    from ctypes import wintypes

    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel32.TerminateJobObject.argtypes = [wintypes.HANDLE, wintypes.UINT]
    if not kernel32.TerminateJobObject(handle, 1):
        raise RuntimeError(f"TerminateJobObject failed: {ctypes.get_last_error()}")


def _active_processes(handle: int) -> int:
    import ctypes
    from ctypes import wintypes

    class AccountingInformation(ctypes.Structure):
        _fields_ = [
            ("TotalUserTime", ctypes.c_longlong),
            ("TotalKernelTime", ctypes.c_longlong),
            ("ThisPeriodTotalUserTime", ctypes.c_longlong),
            ("ThisPeriodTotalKernelTime", ctypes.c_longlong),
            ("TotalPageFaultCount", wintypes.DWORD),
            ("TotalProcesses", wintypes.DWORD),
            ("ActiveProcesses", wintypes.DWORD),
            ("TotalTerminatedProcesses", wintypes.DWORD),
        ]

    information = AccountingInformation()
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    if not kernel32.QueryInformationJobObject(
        handle,
        1,
        ctypes.byref(information),
        ctypes.sizeof(information),
        None,
    ):
        raise RuntimeError(
            f"QueryInformationJobObject failed: {ctypes.get_last_error()}"
        )
    return int(information.ActiveProcesses)


def _wait_until_empty(handle: int, *, timeout_seconds: float) -> None:
    active = _active_after_wait(handle, timeout_seconds=timeout_seconds)
    if active:
        raise RuntimeError(f"Windows Job Object remained populated: {active}")


def _active_after_wait(handle: int, *, timeout_seconds: float) -> int:
    """Return the residual count after a bounded natural-exit grace period."""
    deadline = time.monotonic() + timeout_seconds
    active = _active_processes(handle)
    while active and time.monotonic() < deadline:
        time.sleep(_POLL_SECONDS)
        active = _active_processes(handle)
    return active


def _close_handle(handle: int) -> None:
    import ctypes

    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    if not kernel32.CloseHandle(handle):
        raise RuntimeError(f"CloseHandle failed: {ctypes.get_last_error()}")
