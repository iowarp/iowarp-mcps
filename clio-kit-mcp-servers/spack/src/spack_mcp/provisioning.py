"""Real Spack installs: full on-disk build logs and typed failure classes.

New owner module (clio-kit#370), split out of the ratcheted ``backend.py``
rather than grown inside it. This composes ``backend.py``'s generic bounded
subprocess primitives (``_run_bounded_command``, ``_spack_executable``, the
Windows Job Object containment behind them) and ``discovery.py``'s repo/
recipe catalog instead of re-implementing process management or package
discovery a second time.

Synchronous with a generous configurable timeout for now -- streaming/task
augmentation is explicitly deferred to the kit tasks-semantics slice
(SEP-2663); the door's task layer will wrap this call later without changing
its contract.

Typed failure vocabulary (the owner's law: every error names the failure AND
the recovery affordance):
  - ``recipe_not_found`` -- no registered repo declares this package, and
    every repo was actually readable; the repos searched are in ``detail``.
  - ``availability_unknown`` -- the catalog found no match, but at least one
    registered repo could not be scanned; refusing the install would risk a
    false veto of a recipe spack itself could have served, so this names
    which repos were unreadable instead of guessing (clio-kit#370 fix round,
    R2).
  - ``build_failure`` -- Spack ran and exited nonzero; ``detail`` carries the
    log path and tail.
  - ``timed_out`` -- exceeded ``timeout_seconds``; ``detail`` carries the log
    path so an operator/agent can inspect progress without re-running.
  - ``capture_failed`` -- the bounded subprocess capture itself failed after
    Spack was launched (mirrors ``backend._run_spack``'s handling of the
    same ``RuntimeError``); ``detail`` carries the log path.
  - ``log_unwritable`` -- the install log directory or file could not be
    created/opened; Spack is never invoked in this case.
  - ``install_not_observed`` / ``install_prefix_ambiguous`` -- Spack exited
    0 but the post-install locate composition could not resolve exactly one
    installed package (composes with ``backend.locate_installed``, the same
    mechanism ``spack_locate`` uses).
"""

from __future__ import annotations

import os
import re
import subprocess
import tempfile
import threading
import time
import uuid
from collections.abc import Callable
from pathlib import Path
from typing import BinaryIO, Literal

from pydantic import BaseModel, ConfigDict, Field

from spack_mcp import backend, discovery
from spack_mcp.backend import SPACK_RESULT_SCHEMA, SpackBackendError, SpackPackage

_MAX_INSTALL_TIMEOUT_SECONDS = 86_400
_LOG_TAIL_BYTES = 8_000
_SPEC_SLUG = re.compile(r"[^A-Za-z0-9_.@+-]+")


class SpackInstallResult(BaseModel):
    """Completed Spack install: full log on disk, tail inline, real prefix."""

    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["spack.mcp.result.v1"] = SPACK_RESULT_SCHEMA
    operation: Literal["install"] = "install"
    requested_spec: str
    reuse: bool
    status: Literal["installed"] = "installed"
    duration_seconds: float
    package: SpackPackage
    prefix: str
    load_spec: str = Field(
        description=(
            "Exact runtime identity for JARVIS. Copy this value unchanged from "
            "spack_install.output.load_spec into one element of "
            "jarvis_run.input.spack_specs."
        )
    )
    log_path: str = Field(description="Full build log on disk, unbounded by the MCP response.")
    log_tail: str = Field(description="Bounded tail of the build log for inline review.")


def install_spec(
    spec: str,
    *,
    reuse: bool = True,
    timeout_seconds: int = 14_400,
) -> SpackInstallResult:
    """Install one Spack spec with a full build log and typed failure classes."""
    normalized = backend._validated_spec(spec)
    if timeout_seconds < 1 or timeout_seconds > _MAX_INSTALL_TIMEOUT_SECONDS:
        raise SpackBackendError(
            "invalid_timeout",
            f"timeout_seconds must be between 1 and {_MAX_INSTALL_TIMEOUT_SECONDS}",
            operation="install",
        )
    base_name = discovery.base_package_name(normalized)
    availability = discovery.classify_recipe_availability(base_name)
    if not availability.available:
        if availability.repos_unreadable:
            raise SpackBackendError(
                "availability_unknown",
                f"could not confirm whether a recipe named {base_name!r} is available",
                operation="install",
                detail=(
                    f"repos unreadable: {', '.join(availability.repos_unreadable)}; "
                    f"repos successfully searched: {', '.join(availability.repos_searched)}; "
                    "refusing to guess -- fix the unreadable repo(s) and retry, or confirm "
                    "availability with spack_search"
                ),
            )
        raise SpackBackendError(
            "recipe_not_found",
            f"no recipe named {base_name!r} in any registered repo",
            operation="install",
            detail=availability.message,
        )

    try:
        log_path = _new_log_path(normalized)
    except OSError as exc:
        raise SpackBackendError(
            "log_unwritable",
            "could not create the Spack install log directory",
            operation="install",
            detail=str(exc),
        ) from exc

    executable = backend._spack_executable()
    argv = [executable, "install", "--reuse" if reuse else "--fresh", normalized]
    started = time.monotonic()
    try:
        log_file = log_path.open("wb")
    except OSError as exc:
        raise SpackBackendError(
            "log_unwritable",
            "could not open the Spack install log file",
            operation="install",
            detail=f"log_path={log_path}; {exc}",
        ) from exc
    with log_file:
        sink = _locking_sink(log_file)
        try:
            result = backend._run_bounded_command(
                argv,
                env=os.environ.copy(),
                timeout_seconds=timeout_seconds,
                stdout_sink=sink,
                stderr_sink=sink,
            )
        except subprocess.TimeoutExpired as exc:
            raise SpackBackendError(
                "timed_out",
                f"Spack install exceeded {timeout_seconds} seconds",
                operation="install",
                detail=(
                    f"log_path={log_path}; inspect that file to check build progress, "
                    "or re-run spack_install with a larger timeout_seconds"
                ),
            ) from exc
        except OSError as exc:
            raise SpackBackendError(
                "launch_failed",
                "could not launch Spack",
                operation="install",
                detail=str(exc),
            ) from exc
        except RuntimeError as exc:
            raise SpackBackendError(
                "capture_failed",
                f"could not capture Spack install output for {normalized}",
                operation="install",
                detail=f"log_path={log_path}; {exc}",
            ) from exc
    duration = round(time.monotonic() - started, 3)
    tail = _read_tail(log_path)
    if result.returncode != 0:
        raise SpackBackendError(
            "build_failure",
            f"Spack install failed for {normalized}",
            operation="install",
            returncode=result.returncode,
            detail=f"log_path={log_path}\n{tail}",
        )
    return _observe_install(
        normalized, reuse=reuse, duration=duration, log_path=log_path, tail=tail
    )


def _observe_install(
    normalized: str,
    *,
    reuse: bool,
    duration: float,
    log_path: Path,
    tail: str,
) -> SpackInstallResult:
    """Resolve the freshly installed spec's identity via the locate composition."""
    try:
        located = backend.locate_installed(normalized)
    except SpackBackendError as exc:
        if exc.code == "not_installed":
            raise SpackBackendError(
                "install_not_observed",
                "Spack exited successfully but no matching installed package was observed",
                operation="install",
                detail=f"log_path={log_path}",
            ) from exc
        if exc.code == "ambiguous_spec":
            raise SpackBackendError(
                "install_prefix_ambiguous",
                "install succeeded but the spec resolves to multiple installed packages; "
                "use a fully qualified spec (e.g. include the dag hash) to determine one prefix",
                operation="install",
                detail=exc.detail,
            ) from exc
        raise
    return SpackInstallResult(
        requested_spec=normalized,
        reuse=reuse,
        duration_seconds=duration,
        package=located.package,
        prefix=located.prefix,
        load_spec=located.load_spec,
        log_path=str(log_path),
        log_tail=tail,
    )


def _install_log_dir() -> Path:
    configured = os.getenv("SPACK_MCP_INSTALL_LOG_DIR")
    directory = (
        Path(configured).expanduser()
        if configured
        else Path(tempfile.gettempdir()) / "spack-mcp" / "install-logs"
    )
    directory.mkdir(parents=True, exist_ok=True)
    return directory


def _new_log_path(spec: str) -> Path:
    slug = _SPEC_SLUG.sub("-", spec).strip("-") or "spec"
    timestamp = time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())
    return _install_log_dir() / f"{slug}-{timestamp}-{uuid.uuid4().hex[:8]}.log"


def _locking_sink(handle: BinaryIO) -> Callable[[bytes], None]:
    """Serialize concurrent stdout/stderr writers onto one open log file.

    Guards against a drain thread outliving the caller's ``with`` block over
    ``handle`` (clio-kit#370 fix round, S9): once ``handle`` is closed,
    further chunks are dropped instead of raising ``ValueError`` inside a
    daemon thread, where the traceback would be swallowed and the tail of
    the build log lost without a trace. In the normal path this is
    unreachable -- ``backend._finish_captures`` joins every drain thread (or
    this module's own ``RuntimeError`` -> ``capture_failed`` handling fires)
    before ``_run_bounded_command`` returns -- but the guard costs nothing
    and removes the failure mode entirely rather than merely narrowing it.
    """
    lock = threading.Lock()

    def sink(chunk: bytes) -> None:
        with lock:
            if handle.closed:
                return
            handle.write(chunk)
            handle.flush()

    return sink


def _read_tail(path: Path, *, max_bytes: int = _LOG_TAIL_BYTES) -> str:
    try:
        size = path.stat().st_size
        with path.open("rb") as handle:
            if size > max_bytes:
                handle.seek(size - max_bytes)
            data = handle.read()
    except OSError as exc:
        return f"[could not read log tail: {exc}]"
    text = data.decode("utf-8", errors="replace")
    return ("[log truncated]\n" + text) if size > max_bytes else text
