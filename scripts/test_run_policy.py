"""Owned test storage with live leases, crash recovery, and mandatory cleanup."""

from __future__ import annotations

import errno
import hashlib
import json
import os
import shutil
import sys
import tempfile
import uuid
from pathlib import Path
from typing import BinaryIO

import psutil

SCHEMA = "clio.test-run.v1"
ROOT_ENV = "CLIO_TEST_RUN_ROOT"


def _reap_run_children(root: Path) -> None:
    """Stop only processes carrying this run's inherited ownership marker."""
    owned: dict[int, psutil.Process] = {}
    for process in psutil.process_iter():
        if process.pid == os.getpid():
            continue
        try:
            if process.environ().get(ROOT_ENV) == str(root):
                owned[process.pid] = process
                owned.update(
                    {child.pid: child for child in process.children(recursive=True)}
                )
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue
    for process in owned.values():
        try:
            process.terminate()
        except psutil.NoSuchProcess:
            pass
    _, alive = psutil.wait_procs(list(owned.values()), timeout=3)
    for process in alive:
        try:
            process.kill()
        except psutil.NoSuchProcess:
            pass
    _, alive = psutil.wait_procs(alive, timeout=3)
    if alive:
        raise RuntimeError(
            f"TEST CLEANUP FAILED: live processes remain in {root}: {[p.pid for p in alive]}"
        )


def _lock(path: Path, *, wait: bool = False) -> BinaryIO | None:
    handle = path.open("a+b")
    if handle.tell() == 0:
        handle.write(b"0")
        handle.flush()
    handle.seek(0)
    try:
        if os.name == "nt":
            import msvcrt

            msvcrt.locking(
                handle.fileno(), msvcrt.LK_LOCK if wait else msvcrt.LK_NBLCK, 1
            )
        else:
            import fcntl

            fcntl.flock(handle.fileno(), fcntl.LOCK_EX | (0 if wait else fcntl.LOCK_NB))
    except OSError as exc:
        handle.close()
        if not wait and exc.errno in {errno.EACCES, errno.EAGAIN, errno.EDEADLK}:
            return None
        raise
    return handle


def _owner(root: Path) -> dict[str, str]:
    value = json.loads((root / "owner.json").read_text(encoding="utf-8"))
    if not isinstance(value, dict) or value.get("schema") != SCHEMA:
        raise RuntimeError(f"Invalid test-run ownership marker: {root}")
    return value


def _validated_run(root: Path, base: Path, checkout: Path) -> Path:
    """Resolve ownership before either locking or deleting a candidate directory."""
    resolved = root.resolve(strict=True)
    if resolved.parent != base.resolve() or resolved != root.absolute():
        raise RuntimeError(f"Refusing test cleanup outside the owned run root: {root}")
    if _owner(root).get("checkout") != str(checkout):
        raise RuntimeError(f"Refusing cleanup of another checkout's test run: {root}")
    return resolved


def _remove(root: Path, base: Path, checkout: Path) -> None:
    """Delete only an owned, resolved immediate child; never follow a root junction."""
    resolved = _validated_run(root, base, checkout)
    _reap_run_children(root)
    shutil.rmtree(resolved)


def run_base(checkout: Path) -> Path:
    """Choose a short root on the checkout drive, never the Windows system temp."""
    checkout = checkout.resolve()
    identity = hashlib.sha256(str(checkout).encode()).hexdigest()[:12]
    default = (
        Path(checkout.anchor) / ".clio-test-runs" / identity
        if os.name == "nt"
        else checkout / ".test-runs"
    )
    configured = os.environ.get("CLIO_TEST_RUNS_DIR", "").strip()
    base = (Path(configured) / identity if configured else default).resolve()
    if os.name == "nt" and base.drive.lower() != checkout.drive.lower():
        raise RuntimeError("Test storage must be on the checkout drive")
    return base


class TestRun:
    """A test run owns temporary state until all subprocesses and tests finish."""

    __test__ = False

    def __init__(self, checkout: Path, *, borrow: bool = True) -> None:
        self.checkout = checkout.resolve()
        self.base = run_base(self.checkout)
        self.base.mkdir(parents=True, exist_ok=True)
        self.lease: BinaryIO | None = None
        self.closed = False
        self.previous: dict[str, str | None] = {}
        self.old_temp = tempfile.tempdir
        self.old_bytecode = sys.pycache_prefix
        inherited = os.environ.get(ROOT_ENV)
        guard = _lock(self.base / ".guard", wait=True)
        assert guard is not None
        try:
            if borrow and inherited:
                candidate = Path(inherited).resolve()
                if (
                    candidate.parent == self.base
                    and candidate.is_dir()
                    and _owner(candidate).get("checkout") == str(self.checkout)
                ):
                    probe = _lock(candidate / ".lease")
                    if probe is None:
                        self.root = candidate
                        self._activate()
                        return
                    probe.close()
            for abandoned in self.base.glob("run-*"):
                if not abandoned.is_dir() or not (abandoned / "owner.json").is_file():
                    continue
                _validated_run(abandoned, self.base, self.checkout)
                probe = _lock(abandoned / ".lease")
                if probe is not None:
                    probe.close()
                    _remove(abandoned, self.base, self.checkout)
            self.root = self.base / f"run-{uuid.uuid4().hex[:12]}"
            self.root.mkdir()
            (self.root / "owner.json").write_text(
                json.dumps(
                    {
                        "schema": SCHEMA,
                        "checkout": str(self.checkout),
                        "pid": os.getpid(),
                    }
                ),
                encoding="utf-8",
            )
            self.lease = _lock(self.root / ".lease")
            assert self.lease is not None
            self._activate()
        finally:
            guard.close()

    def _activate(self) -> None:
        groups = {
            "temp": ("TEMP", "TMP", "TMPDIR"),
            "uv-cache": ("UV_CACHE_DIR",),
            "uv-python": ("UV_PYTHON_INSTALL_DIR",),
            "uv-tools": ("UV_TOOL_DIR",),
            "uv-bin": ("UV_TOOL_BIN_DIR",),
            "pip-cache": ("PIP_CACHE_DIR",),
            "bytecode": ("PYTHONPYCACHEPREFIX",),
            "cache": ("XDG_CACHE_HOME",),
            "data": ("XDG_DATA_HOME",),
            "config": ("XDG_CONFIG_HOME",),
            "local": ("LOCALAPPDATA",),
            "roaming": ("APPDATA",),
            "home": ("HOME", "USERPROFILE"),
            "clio-user": ("CLIO_USER_DIR",),
            "clio-runtime": ("CLIO_RUNTIME_STATE_DIR",),
            "clio-kit": ("CLIO_KIT_CACHE_DIR",),
            "matplotlib": ("MPLCONFIGDIR",),
        }
        values = {
            ROOT_ENV: str(self.root),
            "CLIO_TEST_HOST_PROFILE": os.environ.get(
                "CLIO_TEST_HOST_PROFILE",
                os.environ.get("USERPROFILE", str(Path.home())),
            ),
        }
        for directory, keys in groups.items():
            path = self.root / directory
            path.mkdir(exist_ok=True)
            values.update({key: str(path) for key in keys})
        for key, value in values.items():
            self.previous[key] = os.environ.get(key)
            os.environ[key] = value
        tempfile.tempdir = str(self.root / "temp")
        sys.pycache_prefix = str(self.root / "bytecode")

    def close(self) -> None:
        """Clean on success or failure; leave recoverable evidence if cleanup fails."""
        if self.closed:
            return
        self.closed = True
        try:
            if self.lease is not None:
                guard = _lock(self.base / ".guard", wait=True)
                assert guard is not None
                try:
                    self.lease.close()
                    _remove(self.root, self.base, self.checkout)
                finally:
                    guard.close()
        except OSError as exc:
            raise RuntimeError(
                f"TEST CLEANUP FAILED; retained owned run {self.root}: {exc}"
            ) from exc
        finally:
            tempfile.tempdir = self.old_temp
            sys.pycache_prefix = self.old_bytecode
            for key, value in self.previous.items():
                if value is None:
                    os.environ.pop(key, None)
                else:
                    os.environ[key] = value
