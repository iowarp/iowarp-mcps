"""Cross-platform ownership markers for cached MCP environments.

Each launcher holds a per-process advisory lock outside the environment it is
using. Cache maintenance can therefore distinguish a live environment from a
stale marker without touching the environment's contents or modification time.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Final

ENVIRONMENTS_DIRNAME: Final = "mcp-environments"
LOCKS_DIRNAME: Final = ".locks"


class EnvironmentInUseMarker:
    """Hold a per-process lock proving a live launcher uses one environment."""

    def __init__(self, cache_root: Path, env_dir_name: str) -> None:
        self._lock_dir = locks_dir(cache_root, env_dir_name)
        self._handle: _FileLock | None = None

    def __enter__(self) -> "EnvironmentInUseMarker":
        try:
            self._lock_dir.mkdir(parents=True, exist_ok=True)
            lock_path = self._lock_dir / f"{os.getpid()}.lock"
            handle = _FileLock(lock_path)
            handle.acquire()
            self._handle = handle
        except OSError:
            # Best-effort: an unwritable registry must not block a launch. The
            # current environment is never a deletion candidate regardless.
            self._handle = None
        return self

    def __exit__(self, *_exc: object) -> None:
        if self._handle is not None:
            self._handle.release()
            self._handle = None


def environment_in_use(cache_root: Path, env_dir_name: str) -> bool:
    """Return whether any live launcher currently holds this environment."""

    lock_dir = locks_dir(cache_root, env_dir_name)
    if not lock_dir.is_dir():
        return False
    in_use = False
    for lock_path in lock_dir.glob("*.lock"):
        probe = _FileLock(lock_path)
        if probe.try_acquire():
            probe.release()
            _remove_stale_marker(lock_path)
        else:
            in_use = True
    return in_use


def other_environment_in_use(cache_root: Path) -> bool:
    """Return whether another live launcher may hold the shared uv cache."""

    locks_root = cache_root / ENVIRONMENTS_DIRNAME / LOCKS_DIRNAME
    if not locks_root.is_dir():
        return False
    own_marker = f"{os.getpid()}.lock"
    for lock_path in locks_root.glob("*/*.lock"):
        if lock_path.name == own_marker:
            continue
        probe = _FileLock(lock_path)
        if not probe.try_acquire():
            return True
        probe.release()
        _remove_stale_marker(lock_path)
    return False


def locks_dir(cache_root: Path, env_dir_name: str) -> Path:
    """Return the lock-registry directory for one cached environment."""

    return cache_root / ENVIRONMENTS_DIRNAME / LOCKS_DIRNAME / env_dir_name


def _remove_stale_marker(lock_path: Path) -> None:
    try:
        lock_path.unlink()
    except OSError:
        pass


class _FileLock:
    """A cross-platform advisory lock on a single sentinel file."""

    def __init__(self, path: Path) -> None:
        self._path = path
        self._fd: int | None = None

    def acquire(self) -> None:
        """Acquire the lock or raise when another process holds it."""

        if not self.try_acquire():
            raise OSError(f"could not acquire lock: {self._path}")

    def try_acquire(self) -> bool:
        """Try to acquire the lock without blocking."""

        fd = os.open(self._path, os.O_RDWR | os.O_CREAT, 0o644)
        try:
            os.write(fd, b"\0")
            os.lseek(fd, 0, os.SEEK_SET)
            _lock_region(fd)
        except OSError:
            os.close(fd)
            return False
        self._fd = fd
        return True

    def release(self) -> None:
        """Release the lock when held."""

        if self._fd is None:
            return
        try:
            _unlock_region(self._fd)
        except OSError:
            pass
        finally:
            os.close(self._fd)
            self._fd = None


if sys.platform == "win32":
    import msvcrt

    def _lock_region(fd: int) -> None:
        msvcrt.locking(fd, msvcrt.LK_NBLCK, 1)

    def _unlock_region(fd: int) -> None:
        os.lseek(fd, 0, os.SEEK_SET)
        msvcrt.locking(fd, msvcrt.LK_UNLCK, 1)
else:
    import fcntl

    def _lock_region(fd: int) -> None:
        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)

    def _unlock_region(fd: int) -> None:
        fcntl.flock(fd, fcntl.LOCK_UN)
