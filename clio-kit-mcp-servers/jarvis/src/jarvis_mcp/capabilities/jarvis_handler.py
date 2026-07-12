import asyncio
import errno
import hashlib
import inspect
import json
import os
import re
import shutil
import signal
import stat
import subprocess
import sys
import tempfile
import threading
import time
from collections import deque
from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager, redirect_stdout
from dataclasses import dataclass
from datetime import datetime, timezone
from functools import wraps
from pathlib import Path
from typing import Any, BinaryIO, Optional, cast
from uuid import uuid4

from fastapi import HTTPException
from fastmcp.exceptions import ToolError

from jarvis_mcp.progress import (
    PackageProgressBinding,
    PackageProgressExecution,
    ProgressReporter,
    bind_package_progress_provider,
)


RUNTIME_METADATA_SCHEMA = "jarvis.runtime.v1"
RUNTIME_ERROR_SCHEMA = "jarvis.error.v1"
_MAX_SPACK_SPECS = 32
_MAX_SPACK_SPEC_LENGTH = 1024
_MAX_ENVIRONMENT_VARIABLES = 512
_MAX_ENVIRONMENT_VALUE_BYTES = 256 * 1024
_MAX_SPACK_CAPTURE_BYTES = 8 * 1024 * 1024
_MAX_SPACK_DIAGNOSTIC_BYTES = 32 * 1024
_SPACK_STREAM_CHUNK_BYTES = 64 * 1024
_SPACK_STREAM_JOIN_TIMEOUT_SECONDS = 5.0
_SPACK_ENVIRONMENT_MARKER = b"\0__JARVIS_MCP_SPACK_ENVIRONMENT_V1__\0"
_SPACK_ENVIRONMENT_STATE_SCHEMA = "jarvis.mcp.spack-environment.v1"
_SPACK_ENVIRONMENT_STATE_FILENAME = ".jarvis-mcp-spack-environment.json"
_SPACK_ENVIRONMENT_TRANSACTION_SCHEMA = "jarvis.mcp.spack-environment-transaction.v1"
_SPACK_ENVIRONMENT_TRANSACTION_FILENAME = ".jarvis-mcp-spack-environment.pending.json"
_PIPELINE_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")
_WINDOWS_RESERVED_PIPELINE_NAMES = {
    "CON",
    "PRN",
    "AUX",
    "NUL",
    "CLOCK$",
    *(f"COM{index}" for index in range(1, 10)),
    *(f"LPT{index}" for index in range(1, 10)),
}
_HOST_ENTRY = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,252}$")
_PIPELINE_LOCK_TIMEOUT_SECONDS = 30.0
_ENVIRONMENT_NAME = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
_DEFAULT_RUNTIME_ENVIRONMENT_ALLOWLIST = {
    "ACLOCAL_PATH",
    "CMAKE_PREFIX_PATH",
    "CPATH",
    "CPLUS_INCLUDE_PATH",
    "C_INCLUDE_PATH",
    "INFOPATH",
    "LD_LIBRARY_PATH",
    "LIBRARY_PATH",
    "MANPATH",
    "MODULEPATH",
    "PATH",
    "PKG_CONFIG_PATH",
    "PYTHONPATH",
    "SPACK_ROOT",
}
_TRANSIENT_ENVIRONMENT_NAMES = {
    "BASHOPTS",
    "BASHPID",
    "EUID",
    "OLDPWD",
    "PPID",
    "PS1",
    "PS2",
    "PS4",
    "PWD",
    "SHELLOPTS",
    "SHLVL",
    "UID",
    "_",
}
_SENSITIVE_ENVIRONMENT_FRAGMENTS = {
    "AUTH",
    "COOKIE",
    "CREDENTIAL",
    "PASSWORD",
    "PRIVATE_KEY",
    "SECRET",
    "TOKEN",
}
_SENSITIVE_ENVIRONMENT_SUFFIXES = {
    "_ACCESS_KEY_ID",
    "_API_KEY",
    "_DATABASE_URL",
    "_PAT",
}
_SENSITIVE_ENVIRONMENT_EXACT_NAMES = {
    "ACCESS_KEY_ID",
    "API_KEY",
    "DATABASE_URL",
    "PAT",
}


class _SpackDocumentDurabilityError(RuntimeError):
    """A sidecar replacement was visible but its directory was not durable."""


@dataclass(frozen=True)
class _SecureDocument:
    """One bounded sidecar document pinned to its opened filesystem identity."""

    payload: dict[str, Any]
    device: int
    inode: int


@dataclass
class _PipelineFileLock:
    """An acquired cross-process advisory lock descriptor."""

    descriptor: int
    path: Path


@dataclass(frozen=True)
class _BoundedProcessResult:
    """Bounded result from one child process."""

    returncode: int
    stdout: bytes
    stderr: bytes
    stdout_truncated: bool = False
    stderr_truncated: bool = False


class _BoundedCapture:
    """Drain one child stream while retaining only a bounded tail."""

    def __init__(self, stream: BinaryIO) -> None:
        self.stream = stream
        self.chunks: deque[bytes] = deque()
        self.size = 0
        self.truncated = False
        self.error: OSError | None = None

    def drain(self) -> None:
        """Drain until EOF while keeping retained memory bounded."""
        try:
            while chunk := self.stream.read(_SPACK_STREAM_CHUNK_BYTES):
                self.chunks.append(chunk)
                self.size += len(chunk)
                self._trim()
        except OSError as exc:
            self.error = exc

    def _trim(self) -> None:
        overflow = self.size - _MAX_SPACK_CAPTURE_BYTES
        if overflow <= 0:
            return
        self.truncated = True
        while overflow > 0:
            first = self.chunks[0]
            if len(first) <= overflow:
                self.chunks.popleft()
                self.size -= len(first)
                overflow -= len(first)
                continue
            self.chunks[0] = first[overflow:]
            self.size -= overflow
            overflow = 0

    def raw(self) -> bytes:
        """Return the retained undecoded bytes."""
        return b"".join(self.chunks)


Pipeline: Any | None = None
_PIPELINE_IMPORT_ERROR: Exception | None = None

try:  # pragma: no cover - current JARVIS-CD environments.
    from jarvis_cd.core.pipeline import Pipeline as _Pipeline  # type: ignore[import-untyped]

    Pipeline = _Pipeline
except ModuleNotFoundError as core_error:  # pragma: no cover - legacy environments.
    try:
        from jarvis_cd.basic.pkg import Pipeline as _Pipeline  # type: ignore[import-untyped]

        Pipeline = _Pipeline
    except ModuleNotFoundError as legacy_error:
        _PIPELINE_IMPORT_ERROR = (
            legacy_error if "jarvis_cd" in str(legacy_error) else core_error
        )


def _validate_pipeline_id(pipeline_id: str) -> str:
    """Return a bounded path-safe named-pipeline identifier."""
    reserved_stem = (
        pipeline_id.split(".", 1)[0].upper() if isinstance(pipeline_id, str) else ""
    )
    if (
        not isinstance(pipeline_id, str)
        or _PIPELINE_ID.fullmatch(pipeline_id) is None
        or pipeline_id.endswith(".")
        or reserved_stem in _WINDOWS_RESERVED_PIPELINE_NAMES
    ):
        raise ValueError(
            "pipeline_id must be 1-128 ASCII letters, digits, dots, underscores, "
            "or hyphens, cannot begin with punctuation or end with a dot, and "
            "cannot be a reserved Windows path alias"
        )
    return pipeline_id


def _pipeline_lock_root() -> Path:
    """Return a private operator-configurable directory for pipeline locks."""
    configured = os.getenv("JARVIS_MCP_LOCK_DIR")
    root = (
        Path(configured).expanduser()
        if configured
        else Path.home() / ".cache" / "jarvis-mcp" / "locks"
    )
    root.mkdir(parents=True, exist_ok=True, mode=0o700)
    if os.name != "nt":
        root.chmod(0o700)
        status = root.stat()
        current_uid = getattr(os, "geteuid", lambda: status.st_uid)()
        if status.st_uid != current_uid or stat.S_IMODE(status.st_mode) & 0o077:
            raise RuntimeError("JARVIS MCP lock directory is not private to its owner")
    return root.resolve()


def _pipeline_lock_path(pipeline_id: str) -> Path:
    """Return the non-user-controlled lock path for one validated pipeline."""
    digest = hashlib.sha256(pipeline_id.casefold().encode("ascii")).hexdigest()
    return _pipeline_lock_root() / f"pipeline-{digest}.lock"


def _open_pipeline_lock(path: Path) -> _PipelineFileLock:
    """Open and validate one private regular lock file without following links."""
    flags = os.O_RDWR | os.O_CREAT | getattr(os, "O_CLOEXEC", 0)
    flags |= getattr(os, "O_NOFOLLOW", 0)
    descriptor = os.open(path, flags, 0o600)
    try:
        status = os.fstat(descriptor)
        path_status = path.lstat()
        if (
            not stat.S_ISREG(status.st_mode)
            or stat.S_ISLNK(path_status.st_mode)
            or (status.st_dev, status.st_ino)
            != (path_status.st_dev, path_status.st_ino)
            or status.st_nlink != 1
        ):
            raise RuntimeError("JARVIS MCP lock path is not a stable regular file")
        current_uid = getattr(os, "geteuid", lambda: status.st_uid)()
        if os.name != "nt" and (
            status.st_uid != current_uid or stat.S_IMODE(status.st_mode) & 0o077
        ):
            raise RuntimeError("JARVIS MCP lock file is not private to its owner")
        if status.st_size == 0:
            os.write(descriptor, b"\0")
            os.fsync(descriptor)
        return _PipelineFileLock(descriptor=descriptor, path=path)
    except Exception:
        os.close(descriptor)
        raise


def _try_acquire_pipeline_lock(lock: _PipelineFileLock) -> bool:
    """Attempt one non-blocking platform advisory lock acquisition."""
    if os.name == "nt":  # pragma: no cover - exercised by Windows integration.
        import msvcrt

        os.lseek(lock.descriptor, 0, os.SEEK_SET)
        try:
            msvcrt.locking(lock.descriptor, msvcrt.LK_NBLCK, 1)
            return True
        except OSError as exc:
            if exc.errno in {errno.EACCES, errno.EAGAIN, errno.EDEADLK, errno.EPERM}:
                return False
            raise
    fcntl = __import__("fcntl")  # pragma: no cover - POSIX only.

    try:
        fcntl.flock(lock.descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
        return True
    except BlockingIOError:
        return False


def _release_pipeline_lock(lock: _PipelineFileLock) -> None:
    """Release and close one platform advisory lock descriptor."""
    try:
        if os.name == "nt":  # pragma: no cover - exercised by Windows integration.
            import msvcrt

            os.lseek(lock.descriptor, 0, os.SEEK_SET)
            msvcrt.locking(lock.descriptor, msvcrt.LK_UNLCK, 1)
        else:
            fcntl = __import__("fcntl")  # pragma: no cover - POSIX only.

            fcntl.flock(lock.descriptor, fcntl.LOCK_UN)
    finally:
        os.close(lock.descriptor)


@asynccontextmanager
async def _pipeline_operation_lock(pipeline_id: str) -> AsyncIterator[None]:
    """Serialize a complete named-pipeline operation across processes."""
    lock = _open_pipeline_lock(_pipeline_lock_path(pipeline_id))
    acquired = False
    loop = asyncio.get_running_loop()
    deadline = loop.time() + _PIPELINE_LOCK_TIMEOUT_SECONDS
    try:
        while not acquired:
            acquired = _try_acquire_pipeline_lock(lock)
            if acquired:
                break
            if loop.time() >= deadline:
                raise RuntimeError(f"pipeline is busy: {pipeline_id}")
            await asyncio.sleep(0.05)
        yield
    finally:
        if acquired:
            _release_pipeline_lock(lock)
        else:
            os.close(lock.descriptor)


def _locked_pipeline_operation(
    function: Callable[..., Awaitable[dict[str, Any]]],
) -> Callable[..., Awaitable[dict[str, Any]]]:
    """Validate and lock the first pipeline-id argument for one async handler."""

    @wraps(function)
    async def guarded(pipeline_id: str, *args: Any, **kwargs: Any) -> dict[str, Any]:
        validated = _validate_pipeline_id(pipeline_id)
        async with _pipeline_operation_lock(validated):
            return await function(validated, *args, **kwargs)

    return guarded


@_locked_pipeline_operation
async def create_pipeline(
    pipeline_id: str,
    initial_config: dict[str, Any] | None = None,
) -> dict:
    try:
        with _protocol_stdout_to_stderr():
            pipeline = _require_pipeline_class()()
            _create_pipeline(pipeline, pipeline_id)
            if initial_config is not None:
                _apply_pipeline_config(pipeline, initial_config)
            _build_pipeline_env(pipeline)
            _save_pipeline(pipeline)
        return {"pipeline_id": pipeline_id, "status": "created"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Create failed: {e}")


@_locked_pipeline_operation
async def configure_pipeline(pipeline_id: str, config: dict[str, Any]) -> dict:
    """Configure pipeline-level JARVIS settings using native Pipeline fields."""
    try:
        with _protocol_stdout_to_stderr():
            pipeline = _load_pipeline(pipeline_id)
            _apply_pipeline_config(pipeline, config)
            _save_pipeline(pipeline)
        return {
            "pipeline_id": _pipeline_id(pipeline),
            "status": "configured",
            "config": _jsonable(_pipeline_config(pipeline)),
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Pipeline configure failed: {e}")


async def load_pipeline(pipeline_id: Optional[str] = None) -> dict:
    try:
        if pipeline_id is None:
            with _protocol_stdout_to_stderr():
                _load_pipeline(None)
        else:
            validated = _validate_pipeline_id(pipeline_id)
            async with _pipeline_operation_lock(validated):
                with _protocol_stdout_to_stderr():
                    _load_pipeline(validated)
        return {"pipeline_id": pipeline_id, "status": "loaded"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Load failed: {e}")


@_locked_pipeline_operation
async def export_pipeline(pipeline_id: str, include_yaml: bool = True) -> dict:
    """Return a structured snapshot of a JARVIS pipeline."""
    try:
        with _protocol_stdout_to_stderr():
            pipeline = _load_pipeline(pipeline_id)
            config = _pipeline_config(pipeline)
        yaml_path = _optional_str(config.get("JARVIS_YAML_PATH"))
        payload: dict[str, Any] = {
            "pipeline_id": _pipeline_id(pipeline),
            "config_path": _optional_str(_pipeline_config_path(pipeline)),
            "env_path": _optional_str(_pipeline_env_path(pipeline)),
            "yaml_path": yaml_path,
            "config": _jsonable(config),
            "env": _jsonable(getattr(pipeline, "env", {})),
            "packages": [
                _package_snapshot(pkg) for pkg in _pipeline_packages(pipeline)
            ],
        }
        if include_yaml and yaml_path is not None:
            yaml_file = Path(yaml_path)
            if yaml_file.exists():
                payload["pipeline_yaml"] = yaml_file.read_text(encoding="utf-8")
        return payload
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Export failed: {e}")


@_locked_pipeline_operation
async def append_pkg(
    pipeline_id: str,
    pkg_type: str,
    pkg_id: Optional[str] = None,
    do_configure: bool = True,
    **kwargs: Any,
) -> dict:
    try:
        raw_kwargs = dict(kwargs)
        config_flag = do_configure
        if "do_configure" in raw_kwargs:
            config_flag = raw_kwargs.pop("do_configure")

        with _protocol_stdout_to_stderr():
            pipeline = _load_pipeline(pipeline_id)
            if _is_legacy_pipeline(pipeline):
                pipeline.append(
                    pkg_type, pkg_id=pkg_id, do_configure=config_flag, **raw_kwargs
                ).save()
            else:
                config_args = _kwargs_to_config_args(raw_kwargs)
                if config_flag is not None:
                    config_args.append(f"do_configure={str(config_flag).lower()}")
                pipeline.append(pkg_type, package_alias=pkg_id, config_args=config_args)
                _save_pipeline(pipeline)
        return {"pipeline_id": pipeline_id, "appended": pkg_type}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Append failed: {e}")


@_locked_pipeline_operation
async def build_pipeline_env(pipeline_id: str) -> dict:
    """
    Load a Jarvis-CD pipeline, rebuild its environment cache,
    tracking only CMAKE_PREFIX_PATH and PATH from the current shell, then save.
    """
    try:
        with _protocol_stdout_to_stderr():
            pipeline = _load_pipeline(pipeline_id)
            _build_pipeline_env(pipeline)
            _save_pipeline(pipeline)
        return {"pipeline_id": pipeline_id, "status": "environment_built"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Build env failed: {e}")


@_locked_pipeline_operation
async def update_pipeline(pipeline_id: str) -> dict:
    """
    Re-apply the current environment & configuration to every pkg in the pipeline,
    then persist the updated pipeline.
    """
    try:
        with _protocol_stdout_to_stderr():
            pipeline = _load_pipeline(pipeline_id)
            pipeline.update()
            _save_pipeline(pipeline)
        return {"pipeline_id": pipeline_id, "status": "updated"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Update failed: {e}")


@_locked_pipeline_operation
async def configure_pkg(pipeline_id: str, pkg_id: str, **kwargs: Any) -> dict:
    try:
        with _protocol_stdout_to_stderr():
            pipeline = _load_pipeline(pipeline_id)
            if hasattr(pipeline, "configure"):
                pipeline.configure(pkg_id, **kwargs)
            else:
                pipeline.configure_package(pkg_id, _kwargs_to_config_args(kwargs))
            _save_pipeline(pipeline)
        return {"pipeline_id": pipeline_id, "configured": pkg_id}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Configure failed: {e}")


@_locked_pipeline_operation
async def get_pkg_config(pipeline_id: str, pkg_id: str) -> dict:
    try:
        with _protocol_stdout_to_stderr():
            pipeline = _load_pipeline(pipeline_id)
            pkg = _get_package(pipeline, pkg_id)
        if pkg is None:
            raise HTTPException(status_code=404, detail=f"Package '{pkg_id}' not found")
        return {
            "pipeline_id": _pipeline_id(pipeline),
            "pkg_id": pkg_id,
            "config": _jsonable(_package_config(pkg)),
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Get config failed: {e}")


@_locked_pipeline_operation
async def unlink_pkg(pipeline_id: str, pkg_id: str) -> dict:
    try:
        with _protocol_stdout_to_stderr():
            pipeline = _load_pipeline(pipeline_id)
            if _get_package(pipeline, pkg_id) is None:
                raise HTTPException(
                    status_code=404,
                    detail=f"Package '{pkg_id}' not found in pipeline '{pipeline_id}'",
                )
            if hasattr(pipeline, "unlink"):
                pipeline.unlink(pkg_id)
            else:
                pipeline.rm(pkg_id)
            _save_pipeline(pipeline)
        return {"pipeline_id": pipeline_id, "unlinked": pkg_id}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Unlink failed: {e}")


@_locked_pipeline_operation
async def remove_pkg(pipeline_id: str, pkg_id: str) -> dict:
    try:
        with _protocol_stdout_to_stderr():
            pipeline = _load_pipeline(pipeline_id)
            if _get_package(pipeline, pkg_id) is None:
                raise HTTPException(
                    status_code=404,
                    detail=f"Package '{pkg_id}' not found in pipeline '{pipeline_id}'",
                )
            if not hasattr(pipeline, "remove"):
                raise HTTPException(
                    status_code=501,
                    detail=(
                        "Installed JARVIS-CD does not provide destructive package "
                        "removal; use unlink_pkg to remove pipeline membership while "
                        "preserving package files"
                    ),
                )
            pipeline.remove(pkg_id)
            _save_pipeline(pipeline)
        return {"pipeline_id": pipeline_id, "removed": pkg_id}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Remove failed: {e}")


@_locked_pipeline_operation
async def run_pipeline(
    pipeline_id: str,
    mode: str = "auto",
    *,
    submit: bool = True,
    wait: bool = False,
    spack_specs: Optional[list[str]] = None,
    progress_reporter: ProgressReporter | None = None,
    pipeline_config: dict[str, Any] | None = None,
) -> dict:
    """Run a pipeline and return JARVIS-owned structured runtime metadata."""
    started_at = datetime.now(timezone.utc)
    execution_id = f"jarvis_{uuid4().hex}"
    try:
        with _protocol_stdout_to_stderr():
            pipeline = _load_pipeline(pipeline_id)
            if pipeline_config is not None:
                _apply_pipeline_config(pipeline, pipeline_config)
                _save_pipeline(pipeline)
            environment_metadata = _apply_spack_environment(
                pipeline,
                spack_specs or [],
            )
            normalized = mode.strip().lower()
            if normalized not in {"auto", "direct", "scheduler"}:
                raise ValueError("mode must be one of: auto, direct, scheduler")
            scheduler = getattr(pipeline, "scheduler", None)
            has_scheduler = isinstance(scheduler, dict) and bool(scheduler)
            if normalized == "scheduler" and not has_scheduler:
                raise ValueError(
                    "scheduler mode requires a configured pipeline scheduler"
                )
            progress_binding = (
                bind_package_progress_provider(
                    _pipeline_packages(pipeline),
                    execution_id=execution_id,
                    base_deploy_mode=getattr(pipeline, "base_deploy_mode", None),
                )
                if progress_reporter is not None
                else None
            )
        resolved_pipeline_id = _pipeline_id(pipeline) or pipeline_id
        if normalized == "scheduler" or (normalized == "auto" and has_scheduler):
            if submit and not hasattr(pipeline, "last_submission"):
                raise RuntimeError(
                    "installed JARVIS-CD does not expose the structured "
                    "scheduler submission API required by jarvis_run"
                )
            submit_parameters = inspect.signature(pipeline.submit).parameters
            if "execution_id" not in submit_parameters:
                raise RuntimeError(
                    "installed JARVIS-CD does not expose immutable execution "
                    "snapshots required by jarvis_run"
                )
            prior_submission = _jsonable(getattr(pipeline, "last_submission", None))
            try:
                script_path = await _run_pipeline_operation(
                    lambda: pipeline.submit(
                        submit=submit,
                        wait=wait,
                        execution_id=execution_id,
                    ),
                    progress_binding=progress_binding,
                    progress_reporter=progress_reporter,
                    execution_id=execution_id,
                    pipeline_id=resolved_pipeline_id,
                )
            except Exception as exc:
                failure = _waited_workload_failure_metadata(
                    pipeline,
                    scheduler=scheduler,
                    prior_submission=prior_submission,
                    submit=submit,
                    wait=wait,
                    execution_id=execution_id,
                )
                if failure is None:
                    raise
                (
                    failed_submission_metadata,
                    failed_script_path,
                    returncode,
                ) = failure
                failed_result = _runtime_result(
                    pipeline,
                    pipeline_id=pipeline_id,
                    execution_id=execution_id,
                    mode="scheduler",
                    status="failed",
                    terminal=True,
                    scheduler=scheduler,
                    scheduler_phase="workload_failed",
                    script_path=failed_script_path,
                    submit=True,
                    wait=True,
                    started_at=started_at,
                    environment_metadata=environment_metadata,
                    submission_metadata=failed_submission_metadata,
                    terminal_returncode=returncode,
                    terminal_reason=str(exc),
                )
                raise ToolError(
                    _structured_runtime_error(
                        code="jarvis_workload_failed",
                        message=f"Run failed: {exc}",
                        pipeline_id=pipeline_id,
                        execution_id=execution_id,
                        runtime_metadata=failed_result["runtime_metadata"],
                    )
                ) from exc
            submission_metadata = _scheduler_submission_metadata(
                pipeline,
                scheduler=scheduler,
                script_path=str(script_path),
                require_identity=submit,
                execution_id=execution_id,
            )
            status = (
                "completed"
                if submit and wait
                else "submitted"
                if submit
                else "scripted"
            )
            return _runtime_result(
                pipeline,
                pipeline_id=pipeline_id,
                execution_id=execution_id,
                mode="scheduler",
                status=status,
                terminal=submit and wait,
                scheduler=scheduler,
                scheduler_phase=status,
                script_path=str(script_path),
                submit=submit,
                wait=wait,
                started_at=started_at,
                environment_metadata=environment_metadata,
                submission_metadata=submission_metadata,
            )
        await _run_pipeline_operation(
            pipeline.run,
            progress_binding=progress_binding,
            progress_reporter=progress_reporter,
            execution_id=execution_id,
            pipeline_id=resolved_pipeline_id,
        )
        return _runtime_result(
            pipeline,
            pipeline_id=pipeline_id,
            execution_id=execution_id,
            mode="direct",
            status="completed",
            terminal=True,
            scheduler=None,
            scheduler_phase=None,
            script_path=None,
            submit=True,
            wait=True,
            started_at=started_at,
            environment_metadata=environment_metadata,
            submission_metadata=None,
        )
    except ToolError:
        raise
    except Exception as e:
        raise ToolError(
            _structured_runtime_error(
                code="jarvis_run_failed",
                message=f"Run failed: {e}",
                pipeline_id=pipeline_id,
                execution_id=execution_id,
            )
        ) from e


async def _run_pipeline_operation(
    operation: Any,
    *,
    progress_binding: PackageProgressBinding | None,
    progress_reporter: ProgressReporter | None,
    execution_id: str,
    pipeline_id: str,
) -> Any:
    """Run one JARVIS operation with optional package-provider observations."""
    if progress_binding is None or progress_reporter is None:
        with _protocol_stdout_to_stderr():
            return operation()
    return await PackageProgressExecution(
        progress_binding,
        execution_id=execution_id,
        pipeline_id=pipeline_id,
    ).run(operation, progress_reporter)


@_locked_pipeline_operation
async def destroy_pipeline(pipeline_id: str) -> dict:
    try:
        with _protocol_stdout_to_stderr():
            pipeline = _load_pipeline(pipeline_id)
            pipeline.destroy()
        return {"pipeline_id": pipeline_id, "status": "destroyed"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Destroy failed: {e}")


def _package_snapshot(pkg: Any) -> dict[str, Any]:
    if isinstance(pkg, dict):
        return {
            "pkg_id": _optional_str(pkg.get("pkg_id") or pkg.get("id")),
            "pkg_type": _optional_str(pkg.get("pkg_type") or pkg.get("type")),
            "global_id": _optional_str(pkg.get("global_id")),
            "config_path": _optional_str(pkg.get("config_path")),
            "config": _jsonable(pkg.get("config")),
        }
    return {
        "pkg_id": _optional_str(getattr(pkg, "pkg_id", None)),
        "pkg_type": _optional_str(getattr(pkg, "pkg_type", None)),
        "global_id": _optional_str(getattr(pkg, "global_id", None)),
        "config_path": _optional_str(getattr(pkg, "config_path", None)),
        "config": _jsonable(getattr(pkg, "config", None)),
    }


def _jsonable(value: Any) -> Any:
    try:
        json.dumps(value)
        return value
    except TypeError:
        if isinstance(value, dict):
            return {str(key): _jsonable(item) for key, item in value.items()}
        if isinstance(value, list):
            return [_jsonable(item) for item in value]
        if isinstance(value, tuple):
            return [_jsonable(item) for item in value]
        return repr(value)


def _apply_spack_environment(
    pipeline: Any,
    spack_specs: list[str],
) -> dict[str, Any]:
    """Capture, merge, and persist a filtered Spack runtime environment.

    The environment is materialized in this JARVIS invocation instead of relying
    on shell-local ``spack load`` state. Scheduler submission seals the resulting
    named state into an execution-scoped pipeline/environment snapshot.
    """
    recovered = _recover_spack_environment_transaction(pipeline)
    if not spack_specs:
        if recovered is not None:
            return recovered
        committed = _read_spack_environment_state_document(pipeline)
        if committed is None:
            return {
                "specs": [],
                "variable_names": [],
                "variable_count": 0,
                "environment_sha256": None,
                "persisted": False,
                "scheduler_reload": "execution_snapshot",
                "transaction_id": None,
                "disposition": "not_requested",
            }
        _spack_state_previous_values(committed.payload)
        if not _committed_spack_environment_matches(pipeline, committed.payload):
            raise RuntimeError(
                "persisted Spack environment state does not match pipeline YAML"
            )
        _assert_secure_document_unchanged(
            _spack_environment_state_path(pipeline), committed
        )
        return _spack_environment_metadata(committed.payload, disposition="reused")
    normalized = _validate_spack_specs(spack_specs)
    environment = _capture_spack_environment(normalized)
    prior_document = _read_spack_environment_state_document(pipeline)
    prior_payload = prior_document.payload if prior_document is not None else None
    prior_values = (
        _spack_state_previous_values(prior_payload) if prior_payload is not None else {}
    )
    prior_owned_names = set(prior_values)
    prior_environment = dict(pipeline.env)
    prior_source_value = getattr(pipeline, "last_loaded_file", None)
    prior_source = _optional_str(prior_source_value)
    serialized = json.dumps(
        environment,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    environment_sha256 = hashlib.sha256(serialized).hexdigest()
    transaction_id = uuid4().hex
    pending_written = False
    try:
        for name, previous_value in prior_values.items():
            if previous_value is None:
                pipeline.env.pop(name, None)
            else:
                pipeline.env[name] = previous_value
        previous_values: dict[str, str | None] = {}
        for name in environment:
            previous_value = pipeline.env.get(name)
            if previous_value is not None and not isinstance(previous_value, str):
                raise RuntimeError(
                    f"JARVIS pipeline environment value is not a string: {name}"
                )
            previous_values[name] = previous_value
        touched_names = prior_owned_names | environment.keys()
        rollback_values = {
            name: (
                cast(str, prior_environment[name])
                if name in prior_environment
                else None
            )
            for name in sorted(touched_names)
        }
        _write_spack_environment_transaction(
            pipeline,
            transaction_id=transaction_id,
            rollback_values=rollback_values,
            prior_source=prior_source,
            environment_sha256=environment_sha256,
            prior_state=prior_payload,
        )
        pending_written = True
        pipeline.env.update(environment)
        if hasattr(pipeline, "last_loaded_file"):
            pipeline.last_loaded_file = None
        _save_pipeline(pipeline)
        _write_spack_environment_state(
            pipeline,
            specs=normalized,
            variable_names=sorted(environment),
            previous_values=previous_values,
            environment_sha256=environment_sha256,
            transaction_id=transaction_id,
        )
        pending = _read_spack_environment_transaction_document(pipeline)
        if pending is None:
            raise RuntimeError(
                "Spack environment transaction disappeared before commit"
            )
        _clear_spack_environment_transaction(pipeline, expected=pending)
    except _SpackDocumentDurabilityError as exc:
        if pending_written:
            try:
                _recover_spack_environment_transaction(pipeline, force_rollback=True)
            except Exception as recovery_exc:
                raise RuntimeError(
                    "Spack environment durability failed and transaction recovery "
                    f"also failed: {recovery_exc}"
                ) from exc
        else:
            pipeline.env.clear()
            pipeline.env.update(prior_environment)
            if hasattr(pipeline, "last_loaded_file"):
                pipeline.last_loaded_file = prior_source_value
        raise
    except Exception as exc:
        if pending_written:
            try:
                _recover_spack_environment_transaction(pipeline)
            except Exception as recovery_exc:
                raise RuntimeError(
                    "Spack environment persistence failed and transaction recovery "
                    f"also failed: {recovery_exc}"
                ) from exc
        else:
            pipeline.env.clear()
            pipeline.env.update(prior_environment)
            if hasattr(pipeline, "last_loaded_file"):
                pipeline.last_loaded_file = prior_source_value
        raise
    return {
        "specs": normalized,
        "variable_names": sorted(environment),
        "variable_count": len(environment),
        "environment_sha256": environment_sha256,
        "removed_variable_names": sorted(prior_owned_names - environment.keys()),
        "persisted": True,
        "scheduler_reload": "execution_snapshot",
        "prior_source_yaml": prior_source,
        "transaction_id": transaction_id,
        "disposition": "applied",
    }


def _read_spack_environment_state(pipeline: Any) -> dict[str, str | None]:
    """Return prior values shadowed by the previous Spack materialization."""
    document = _read_spack_environment_state_document(pipeline)
    if document is None:
        return {}
    return _spack_state_previous_values(document.payload)


def _spack_state_previous_values(payload: dict[str, Any]) -> dict[str, str | None]:
    """Validate and return values shadowed by one committed Spack state."""
    raw_names = payload.get("variable_names")
    raw_previous_values = payload.get("previous_values")
    if (
        not isinstance(raw_names, list)
        or len(raw_names) > _MAX_ENVIRONMENT_VARIABLES
        or not all(
            isinstance(name, str) and _valid_persisted_environment_name(name)
            for name in raw_names
        )
        or not isinstance(raw_previous_values, dict)
        or set(raw_previous_values) != set(raw_names)
        or not all(
            value is None
            or (
                isinstance(value, str)
                and len(value.encode("utf-8")) <= _MAX_ENVIRONMENT_VALUE_BYTES
            )
            for value in raw_previous_values.values()
        )
    ):
        raise RuntimeError(
            "persisted Spack environment state has invalid variable names"
        )
    return {
        name: cast(dict[str, str | None], raw_previous_values)[name]
        for name in cast(list[str], raw_names)
    }


def _read_spack_environment_state_document(
    pipeline: Any,
) -> _SecureDocument | None:
    """Read the bounded committed Spack state document when it exists."""
    path = _spack_environment_state_path(pipeline)
    document = _secure_read_spack_document(
        path,
        description="persisted Spack environment state",
    )
    if document is None:
        return None
    payload = document.payload
    if not isinstance(payload, dict) or payload.get("schema_version") != (
        _SPACK_ENVIRONMENT_STATE_SCHEMA
    ):
        raise RuntimeError(
            "persisted Spack environment state has an unsupported schema"
        )
    transaction_id = payload.get("transaction_id")
    specs = payload.get("specs")
    environment_sha256 = payload.get("environment_sha256")
    if (
        not isinstance(specs, list)
        or not all(
            isinstance(spec, str)
            and 0 < len(spec) <= _MAX_SPACK_SPEC_LENGTH
            and not spec.startswith("-")
            and not any(
                ord(character) < 32 or ord(character) == 127 for character in spec
            )
            for spec in specs
        )
        or len(specs) > _MAX_SPACK_SPECS
        or not isinstance(environment_sha256, str)
        or re.fullmatch(r"[0-9a-f]{64}", environment_sha256) is None
    ):
        raise RuntimeError("persisted Spack environment state is invalid")
    if transaction_id is not None and (
        not isinstance(transaction_id, str)
        or re.fullmatch(r"[0-9a-f]{32}", transaction_id) is None
    ):
        raise RuntimeError("persisted Spack environment transaction id is invalid")
    return _SecureDocument(
        payload=payload,
        device=document.device,
        inode=document.inode,
    )


def _write_spack_environment_state(
    pipeline: Any,
    *,
    specs: list[str],
    variable_names: list[str],
    previous_values: dict[str, str | None],
    environment_sha256: str,
    transaction_id: str | None = None,
) -> None:
    """Atomically persist the variables owned by the current Spack materialization."""
    path = _spack_environment_state_path(pipeline)
    path.parent.mkdir(parents=True, exist_ok=True)
    document = {
        "schema_version": _SPACK_ENVIRONMENT_STATE_SCHEMA,
        "specs": specs,
        "variable_names": variable_names,
        "previous_values": previous_values,
        "environment_sha256": environment_sha256,
    }
    if transaction_id is not None:
        if re.fullmatch(r"[0-9a-f]{32}", transaction_id) is None:
            raise RuntimeError("Spack environment transaction id is invalid")
        document["transaction_id"] = transaction_id
    _atomic_write_spack_document(
        path,
        document,
        too_large_message="persisted Spack environment state is too large",
    )


def _write_spack_environment_transaction(
    pipeline: Any,
    *,
    transaction_id: str,
    rollback_values: dict[str, str | None],
    prior_source: str | None,
    environment_sha256: str,
    prior_state: dict[str, Any] | None = None,
) -> None:
    """Durably record how to recover an interrupted two-file pipeline update."""
    if re.fullmatch(r"[0-9a-f]{32}", transaction_id) is None:
        raise RuntimeError("Spack environment transaction id is invalid")
    if len(rollback_values) > _MAX_ENVIRONMENT_VARIABLES * 2 or not all(
        _valid_persisted_environment_name(name)
        and (
            value is None
            or (
                isinstance(value, str)
                and len(value.encode("utf-8")) <= _MAX_ENVIRONMENT_VALUE_BYTES
            )
        )
        for name, value in rollback_values.items()
    ):
        raise RuntimeError("Spack environment rollback values are invalid")
    if prior_source is not None and len(prior_source.encode("utf-8")) > 65_536:
        raise RuntimeError("Spack environment prior source path is too large")
    if re.fullmatch(r"[0-9a-f]{64}", environment_sha256) is None:
        raise RuntimeError("Spack environment digest is invalid")
    if prior_state is not None:
        _spack_state_previous_values(prior_state)
    path = _spack_environment_transaction_path(pipeline)
    _atomic_write_spack_document(
        path,
        {
            "schema_version": _SPACK_ENVIRONMENT_TRANSACTION_SCHEMA,
            "transaction_id": transaction_id,
            "rollback_values": rollback_values,
            "prior_source": prior_source,
            "environment_sha256": environment_sha256,
            "prior_state": prior_state,
        },
        too_large_message="Spack environment transaction is too large",
    )


def _read_spack_environment_transaction_document(
    pipeline: Any,
) -> _SecureDocument | None:
    """Securely read and validate one pending environment transaction."""
    document = _secure_read_spack_document(
        _spack_environment_transaction_path(pipeline),
        description="Spack environment transaction",
    )
    if document is None:
        return None
    payload = document.payload
    if set(payload) != {
        "schema_version",
        "transaction_id",
        "rollback_values",
        "prior_source",
        "environment_sha256",
        "prior_state",
    }:
        raise RuntimeError("Spack environment transaction has invalid fields")
    transaction_id = payload.get("transaction_id")
    rollback_values = payload.get("rollback_values")
    prior_source = payload.get("prior_source")
    environment_sha256 = payload.get("environment_sha256")
    prior_state = payload.get("prior_state")
    if (
        payload.get("schema_version") != _SPACK_ENVIRONMENT_TRANSACTION_SCHEMA
        or not isinstance(transaction_id, str)
        or re.fullmatch(r"[0-9a-f]{32}", transaction_id) is None
        or not isinstance(rollback_values, dict)
        or len(rollback_values) > _MAX_ENVIRONMENT_VARIABLES * 2
        or not all(
            isinstance(name, str)
            and _valid_persisted_environment_name(name)
            and (
                value is None
                or (
                    isinstance(value, str)
                    and len(value.encode("utf-8")) <= _MAX_ENVIRONMENT_VALUE_BYTES
                )
            )
            for name, value in rollback_values.items()
        )
        or (prior_source is not None and not isinstance(prior_source, str))
        or (
            isinstance(prior_source, str) and len(prior_source.encode("utf-8")) > 65_536
        )
        or not isinstance(environment_sha256, str)
        or re.fullmatch(r"[0-9a-f]{64}", environment_sha256) is None
        or (prior_state is not None and not isinstance(prior_state, dict))
    ):
        raise RuntimeError("Spack environment transaction is invalid")
    if isinstance(prior_state, dict):
        _spack_state_previous_values(prior_state)
        prior_specs = prior_state.get("specs")
        prior_digest = prior_state.get("environment_sha256")
        prior_transaction_id = prior_state.get("transaction_id")
        if (
            prior_state.get("schema_version") != _SPACK_ENVIRONMENT_STATE_SCHEMA
            or not isinstance(prior_specs, list)
            or not all(isinstance(spec, str) for spec in prior_specs)
            or len(prior_specs) > _MAX_SPACK_SPECS
            or not isinstance(prior_digest, str)
            or re.fullmatch(r"[0-9a-f]{64}", prior_digest) is None
            or (
                prior_transaction_id is not None
                and (
                    not isinstance(prior_transaction_id, str)
                    or re.fullmatch(r"[0-9a-f]{32}", prior_transaction_id) is None
                )
            )
        ):
            raise RuntimeError("Spack environment transaction prior state is invalid")
    return document


def _recover_spack_environment_transaction(
    pipeline: Any,
    *,
    force_rollback: bool = False,
) -> dict[str, Any] | None:
    """Finish or roll back a crash-interrupted Spack environment update."""
    pending = _read_spack_environment_transaction_document(pipeline)
    if pending is None:
        return None
    payload = pending.payload
    transaction_id = cast(str, payload["transaction_id"])
    rollback_values = cast(dict[str, str | None], payload["rollback_values"])
    prior_source = cast(str | None, payload["prior_source"])
    environment_sha256 = cast(str, payload["environment_sha256"])
    prior_state = cast(dict[str, Any] | None, payload["prior_state"])
    committed = _read_spack_environment_state_document(pipeline)
    transaction_committed = (
        not force_rollback
        and committed is not None
        and committed.payload.get("transaction_id") == transaction_id
        and committed.payload.get("environment_sha256") == environment_sha256
        and _committed_spack_environment_matches(pipeline, committed.payload)
    )
    if transaction_committed:
        if committed is None:
            raise AssertionError("committed transaction has no state document")
        _spack_state_previous_values(committed.payload)
        _assert_secure_document_unchanged(
            _spack_environment_state_path(pipeline), committed
        )
        _clear_spack_environment_transaction(pipeline, expected=pending)
        return _spack_environment_metadata(
            committed.payload,
            disposition="recovered_committed",
        )

    environment = getattr(pipeline, "env", None)
    if not isinstance(environment, dict):
        raise RuntimeError("JARVIS pipeline environment is not mutable")
    for name, value in rollback_values.items():
        if value is None:
            environment.pop(name, None)
        else:
            environment[name] = value
    if hasattr(pipeline, "last_loaded_file"):
        pipeline.last_loaded_file = prior_source
    _save_pipeline(pipeline)

    if prior_state is None:
        if committed is not None:
            _remove_pinned_spack_document(
                _spack_environment_state_path(pipeline), committed
            )
    else:
        _atomic_write_spack_document(
            _spack_environment_state_path(pipeline),
            prior_state,
            too_large_message="persisted Spack environment state is too large",
        )
    _clear_spack_environment_transaction(pipeline, expected=pending)
    if prior_state is not None:
        return _spack_environment_metadata(
            prior_state,
            disposition="recovered_rolled_back",
        )
    return {
        "specs": [],
        "variable_names": [],
        "variable_count": 0,
        "environment_sha256": None,
        "persisted": False,
        "scheduler_reload": "execution_snapshot",
        "transaction_id": transaction_id,
        "disposition": "recovered_rolled_back",
    }


def _committed_spack_environment_matches(
    pipeline: Any,
    payload: dict[str, Any],
) -> bool:
    """Return whether pipeline memory contains the exact committed Spack delta."""
    names = payload.get("variable_names")
    environment = getattr(pipeline, "env", None)
    if not isinstance(names, list) or not isinstance(environment, dict):
        return False
    materialized: dict[str, str] = {}
    for name in names:
        value = environment.get(name)
        if not isinstance(name, str) or not isinstance(value, str):
            return False
        materialized[name] = value
    serialized = json.dumps(
        dict(sorted(materialized.items())),
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    return hashlib.sha256(serialized).hexdigest() == payload.get("environment_sha256")


def _spack_environment_metadata(
    payload: dict[str, Any],
    *,
    disposition: str,
) -> dict[str, Any]:
    """Return bounded runtime provenance from a validated committed state."""
    previous_values = _spack_state_previous_values(payload)
    specs = cast(list[str], payload["specs"])
    names = sorted(previous_values)
    return {
        "specs": list(specs),
        "variable_names": names,
        "variable_count": len(names),
        "environment_sha256": cast(str, payload["environment_sha256"]),
        "persisted": True,
        "scheduler_reload": "execution_snapshot",
        "transaction_id": payload.get("transaction_id"),
        "disposition": disposition,
    }


def _clear_spack_environment_transaction(
    pipeline: Any,
    *,
    expected: _SecureDocument,
) -> None:
    """Remove only the exact recovered transaction and sync its directory."""
    _remove_pinned_spack_document(
        _spack_environment_transaction_path(pipeline), expected
    )


def _open_spack_path_descriptor(path: Path, *, nonblocking: bool = False) -> int:
    """Open a sidecar while permitting identity-pinned rename/delete on Windows."""
    if os.name != "nt":
        flags = os.O_RDONLY | getattr(os, "O_CLOEXEC", 0) | getattr(os, "O_NOFOLLOW", 0)
        if nonblocking:
            flags |= getattr(os, "O_NONBLOCK", 0)
        return os.open(path, flags)

    import ctypes
    import msvcrt
    from ctypes import wintypes

    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    create_file = kernel32.CreateFileW
    create_file.argtypes = [
        wintypes.LPCWSTR,
        wintypes.DWORD,
        wintypes.DWORD,
        wintypes.LPVOID,
        wintypes.DWORD,
        wintypes.DWORD,
        wintypes.HANDLE,
    ]
    create_file.restype = wintypes.HANDLE
    handle = create_file(
        str(path),
        0x80000000,  # GENERIC_READ
        0x00000001 | 0x00000002 | 0x00000004,  # SHARE_READ|WRITE|DELETE
        None,
        3,  # OPEN_EXISTING
        0x00000080 | 0x00200000,  # NORMAL | OPEN_REPARSE_POINT
        None,
    )
    invalid_handle = ctypes.c_void_p(-1).value
    if handle == invalid_handle:
        raise ctypes.WinError(ctypes.get_last_error())
    try:
        return msvcrt.open_osfhandle(
            int(handle),
            os.O_RDONLY | getattr(os, "O_BINARY", 0),
        )
    except BaseException:
        kernel32.CloseHandle(handle)
        raise


def _remove_pinned_spack_document(path: Path, expected: _SecureDocument) -> None:
    """Durably remove one exact sidecar through recoverable phase names."""
    _recover_spack_document_removal(path)
    clearing = path.with_name(f".{path.name}.clearing")
    cleared = path.with_name(f".{path.name}.cleared")
    try:
        descriptor = _open_spack_path_descriptor(path)
    except FileNotFoundError as exc:
        raise RuntimeError(
            f"Spack sidecar disappeared before removal: {path.name}"
        ) from exc
    clear_committed = False
    try:
        status = os.fstat(descriptor)
        if (
            not stat.S_ISREG(status.st_mode)
            or status.st_nlink != 1
            or (status.st_dev, status.st_ino) != (expected.device, expected.inode)
        ):
            raise RuntimeError(f"Spack sidecar changed before removal: {path.name}")

        os.replace(path, clearing)
        _assert_descriptor_path_identity(clearing, descriptor, expected)
        try:
            _fsync_spack_directory(path.parent)
        except OSError as exc:
            os.replace(clearing, path)
            _fsync_spack_directory(path.parent)
            raise _SpackDocumentDurabilityError(
                f"could not durably prepare Spack sidecar removal: {path.name}"
            ) from exc

        os.replace(clearing, cleared)
        _assert_descriptor_path_identity(cleared, descriptor, expected)
        try:
            _fsync_spack_directory(path.parent)
        except OSError as exc:
            os.replace(cleared, path)
            _fsync_spack_directory(path.parent)
            raise _SpackDocumentDurabilityError(
                f"could not durably commit Spack sidecar removal: {path.name}"
            ) from exc
        clear_committed = True
        _unlink_cleared_spack_document(cleared, expected)
    except BaseException:
        if not clear_committed:
            restored = False
            for phase in (clearing, cleared):
                try:
                    phase_descriptor = _open_expected_spack_descriptor(phase, expected)
                except (FileNotFoundError, RuntimeError):
                    continue
                os.close(phase_descriptor)
                os.replace(phase, path)
                _fsync_spack_directory(path.parent)
                restored = True
                break
            if not restored:
                try:
                    path.lstat()
                except FileNotFoundError:
                    _atomic_write_spack_document(
                        path,
                        expected.payload,
                        too_large_message="Spack recovery evidence is too large",
                    )
        raise
    finally:
        os.close(descriptor)


def _open_expected_spack_descriptor(
    path: Path,
    expected: _SecureDocument,
) -> int:
    """Open a phase path and bind it to the expected stable identity."""
    descriptor = _open_spack_path_descriptor(path)
    try:
        _assert_descriptor_path_identity(path, descriptor, expected)
    except BaseException:
        os.close(descriptor)
        raise
    return descriptor


def _assert_descriptor_path_identity(
    path: Path,
    descriptor: int,
    expected: _SecureDocument,
) -> None:
    """Bind a phase pathname to the still-open expected inode."""
    descriptor_status = os.fstat(descriptor)
    path_status = path.lstat()
    identity = (expected.device, expected.inode)
    if (
        stat.S_ISLNK(path_status.st_mode)
        or (descriptor_status.st_dev, descriptor_status.st_ino) != identity
        or (path_status.st_dev, path_status.st_ino) != identity
        or descriptor_status.st_nlink != 1
    ):
        raise RuntimeError(f"Spack sidecar changed during removal: {path.name}")


def _unlink_cleared_spack_document(
    path: Path,
    expected: _SecureDocument,
) -> None:
    """Unlink a committed clear phase and recreate evidence on fsync failure."""
    descriptor = _open_spack_path_descriptor(path)
    try:
        _assert_descriptor_path_identity(path, descriptor, expected)
        os.unlink(path)
        if os.name == "nt":
            try:
                path.lstat()
            except FileNotFoundError:
                unlinked_expected = True
            else:
                unlinked_expected = False
        else:
            unlinked_expected = os.fstat(descriptor).st_nlink == 0
        if not unlinked_expected:
            _atomic_write_spack_document(
                path,
                expected.payload,
                too_large_message="Spack removal evidence is too large",
            )
            raise RuntimeError(f"Spack sidecar changed during unlink: {path.name}")
        try:
            _fsync_spack_directory(path.parent)
        except OSError as exc:
            _atomic_write_spack_document(
                path,
                expected.payload,
                too_large_message="Spack removal evidence is too large",
            )
            raise _SpackDocumentDurabilityError(
                f"could not durably finish Spack sidecar removal: {path.name}"
            ) from exc
    finally:
        os.close(descriptor)


def _recover_spack_document_removal(path: Path) -> None:
    """Restore a prepared clear or finish a durably committed clear."""
    clearing = path.with_name(f".{path.name}.clearing")
    cleared = path.with_name(f".{path.name}.cleared")
    try:
        clearing.lstat()
        has_clearing = True
    except FileNotFoundError:
        has_clearing = False
    try:
        cleared.lstat()
        has_cleared = True
    except FileNotFoundError:
        has_cleared = False
    if has_clearing and has_cleared:
        raise RuntimeError(f"conflicting Spack removal phases: {path.name}")
    if has_clearing:
        try:
            path.lstat()
        except FileNotFoundError:
            os.replace(clearing, path)
            _fsync_spack_directory(path.parent)
        else:
            raise RuntimeError(f"conflicting Spack sidecar removal: {path.name}")
    if has_cleared:
        evidence = _secure_read_spack_document(
            cleared,
            description="committed Spack removal evidence",
            recover_removal=False,
        )
        if evidence is None:
            return
        _unlink_cleared_spack_document(cleared, evidence)


def _assert_secure_document_unchanged(
    path: Path,
    expected: _SecureDocument,
) -> None:
    """Reject a sidecar replaced after its secure bounded read."""
    try:
        status = path.lstat()
    except OSError as exc:
        raise RuntimeError(f"Spack sidecar changed after read: {path.name}") from exc
    if stat.S_ISLNK(status.st_mode) or (status.st_dev, status.st_ino) != (
        expected.device,
        expected.inode,
    ):
        raise RuntimeError(f"Spack sidecar changed after read: {path.name}")


def _secure_read_spack_document(
    path: Path,
    *,
    description: str,
    recover_removal: bool = True,
) -> _SecureDocument | None:
    """Read one private regular JSON sidecar through one bounded descriptor."""
    if recover_removal:
        _recover_spack_document_removal(path)
    try:
        descriptor = _open_spack_path_descriptor(path, nonblocking=True)
    except FileNotFoundError:
        return None
    except OSError as exc:
        raise RuntimeError(f"could not open {description}: {exc}") from exc
    try:
        status = os.fstat(descriptor)
        path_status = path.lstat()
        if (
            not stat.S_ISREG(status.st_mode)
            or stat.S_ISLNK(path_status.st_mode)
            or (status.st_dev, status.st_ino)
            != (path_status.st_dev, path_status.st_ino)
            or status.st_nlink != 1
        ):
            raise RuntimeError(f"{description} is not a stable regular file")
        current_uid = getattr(os, "geteuid", lambda: status.st_uid)()
        if os.name != "nt" and (
            status.st_uid != current_uid or stat.S_IMODE(status.st_mode) & 0o077
        ):
            raise RuntimeError(f"{description} is not private to its owner")
        if status.st_size > _MAX_SPACK_CAPTURE_BYTES:
            raise RuntimeError(f"{description} is too large")
        chunks: list[bytes] = []
        retained = 0
        while retained <= _MAX_SPACK_CAPTURE_BYTES:
            chunk = os.read(
                descriptor,
                min(65_536, _MAX_SPACK_CAPTURE_BYTES + 1 - retained),
            )
            if not chunk:
                break
            chunks.append(chunk)
            retained += len(chunk)
        if retained > _MAX_SPACK_CAPTURE_BYTES:
            raise RuntimeError(f"{description} is too large")
        final_status = os.fstat(descriptor)
        if (final_status.st_dev, final_status.st_ino) != (status.st_dev, status.st_ino):
            raise RuntimeError(f"{description} changed while being read")
        identity = _SecureDocument(
            payload={}, device=status.st_dev, inode=status.st_ino
        )
        _assert_secure_document_unchanged(path, identity)
        try:
            payload = json.loads(b"".join(chunks).decode("utf-8", errors="strict"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise RuntimeError(f"could not read {description}: {exc}") from exc
        if not isinstance(payload, dict):
            raise RuntimeError(f"{description} is not a JSON object")
        return _SecureDocument(
            payload=cast(dict[str, Any], payload),
            device=status.st_dev,
            inode=status.st_ino,
        )
    finally:
        os.close(descriptor)


def _atomic_write_spack_document(
    path: Path,
    document: dict[str, Any],
    *,
    too_large_message: str,
) -> None:
    """Write one bounded JSON sidecar with atomic replacement and durability."""
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(document, separators=(",", ":"), sort_keys=True) + "\n"
    if len(payload.encode("utf-8")) > _MAX_SPACK_CAPTURE_BYTES:
        raise RuntimeError(too_large_message)
    descriptor, temporary_name = tempfile.mkstemp(
        dir=path.parent,
        prefix=f".{path.name}.",
        suffix=".tmp",
        text=True,
    )
    temporary_path = Path(temporary_name)
    replaced = False
    descriptor_owned = True
    try:
        _set_private_descriptor_mode(descriptor)
        try:
            stream = os.fdopen(
                descriptor,
                "w",
                encoding="utf-8",
                newline="\n",
            )
        except BaseException:
            os.close(descriptor)
            descriptor_owned = False
            raise
        descriptor_owned = False
        with stream:
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary_path, path)
        replaced = True
        try:
            _fsync_spack_directory(path.parent)
        except OSError as exc:
            raise _SpackDocumentDurabilityError(
                f"could not make Spack sidecar durable: {path.name}"
            ) from exc
    finally:
        if descriptor_owned:
            os.close(descriptor)
        if not replaced:
            temporary_path.unlink(missing_ok=True)


def _atomic_write_hostfile(path: Path, hosts: list[str]) -> None:
    """Durably replace an MCP-managed hostfile without exposing partial bytes."""
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = "\n".join(hosts) + "\n"
    descriptor, temporary_name = tempfile.mkstemp(
        dir=path.parent,
        prefix=f".{path.name}.",
        suffix=".tmp",
        text=True,
    )
    temporary_path = Path(temporary_name)
    descriptor_owned = True
    replaced = False
    try:
        _set_private_descriptor_mode(descriptor)
        try:
            stream = os.fdopen(
                descriptor,
                "w",
                encoding="utf-8",
                newline="\n",
            )
        except BaseException:
            os.close(descriptor)
            descriptor_owned = False
            raise
        descriptor_owned = False
        with stream:
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary_path, path)
        replaced = True
        _fsync_spack_directory(path.parent)
    finally:
        if descriptor_owned:
            os.close(descriptor)
        if not replaced:
            temporary_path.unlink(missing_ok=True)


def _set_private_descriptor_mode(descriptor: int) -> None:
    """Restrict a newly-created sidecar descriptor where chmod is available."""
    fchmod = getattr(os, "fchmod", None)
    if os.name != "nt" and fchmod is not None:
        fchmod(descriptor, 0o600)


def _fsync_spack_directory(path: Path) -> None:
    """Sync sidecar directory entries where the platform exposes that primitive."""
    if os.name == "nt":
        return
    descriptor = os.open(path, os.O_RDONLY | getattr(os, "O_DIRECTORY", 0))
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def _spack_environment_state_path(pipeline: Any) -> Path:
    """Return the pipeline-local sidecar that tracks Spack-owned variables."""
    environment_path = _pipeline_env_path(pipeline)
    if not isinstance(environment_path, (str, os.PathLike)):
        raise RuntimeError(
            "JARVIS pipeline does not expose a persistent environment path"
        )
    return Path(environment_path).with_name(_SPACK_ENVIRONMENT_STATE_FILENAME)


def _spack_environment_transaction_path(pipeline: Any) -> Path:
    """Return the pipeline-local write-ahead transaction sidecar path."""
    environment_path = _pipeline_env_path(pipeline)
    if not isinstance(environment_path, (str, os.PathLike)):
        raise RuntimeError(
            "JARVIS pipeline does not expose a persistent environment path"
        )
    return Path(environment_path).with_name(_SPACK_ENVIRONMENT_TRANSACTION_FILENAME)


def _capture_spack_environment(spack_specs: list[str]) -> dict[str, str]:
    """Return a bounded, non-secret environment delta produced by Spack.

    User specs are passed to Spack as argv, never interpolated into shell text.
    Only the sourceable script emitted by ``spack load --sh`` is evaluated in an
    isolated Bash child. The result is compared with the caller environment so
    unchanged credentials are never copied into JARVIS pipeline state.
    """
    spack = _spack_executable()
    try:
        loaded = _run_bounded_process(
            [spack, "load", "--sh", *spack_specs],
            env=os.environ.copy(),
            timeout_seconds=120,
        )
    except (OSError, subprocess.TimeoutExpired, RuntimeError) as exc:
        raise RuntimeError(
            f"could not resolve Spack runtime environment: {exc}"
        ) from exc
    if loaded.returncode != 0:
        detail = (
            _bounded_spack_diagnostic(loaded.stderr)
            or _bounded_spack_diagnostic(loaded.stdout)
            or "unknown Spack error"
        )
        raise RuntimeError(f"spack load environment failed: {detail}")
    if loaded.stdout_truncated:
        raise RuntimeError("Spack runtime environment script exceeded the output limit")
    try:
        environment_script = loaded.stdout.decode("utf-8", errors="strict")
    except UnicodeDecodeError as exc:
        raise RuntimeError("Spack runtime environment script was not UTF-8") from exc

    baseline = dict(os.environ)
    script = (
        "set -e\n"
        + environment_script
        + "\nprintf '\\0__JARVIS_MCP_SPACK_ENVIRONMENT_V1__\\0'\nenv -0\n"
    )
    try:
        captured = _run_bounded_process(
            ["bash", "--noprofile", "--norc"],
            env=baseline,
            stdin_payload=script.encode("utf-8"),
            timeout_seconds=120,
        )
    except (OSError, subprocess.TimeoutExpired, RuntimeError) as exc:
        raise RuntimeError(
            f"could not materialize Spack runtime environment: {exc}"
        ) from exc
    if captured.returncode != 0:
        detail = _bounded_spack_diagnostic(captured.stderr)
        raise RuntimeError(f"Spack runtime environment script failed: {detail}")
    if captured.stdout_truncated:
        raise RuntimeError(
            "materialized Spack runtime environment exceeded the output limit"
        )
    _, marker, raw_environment = captured.stdout.partition(_SPACK_ENVIRONMENT_MARKER)
    if not marker:
        raise RuntimeError(
            "materialized Spack runtime environment omitted its integrity marker"
        )

    materialized: dict[str, str] = {}
    for item in raw_environment.split(b"\0"):
        if not item or b"=" not in item:
            continue
        raw_name, raw_value = item.split(b"=", 1)
        try:
            name = raw_name.decode("utf-8", errors="strict")
            value = raw_value.decode("utf-8", errors="strict")
        except UnicodeDecodeError as exc:
            raise RuntimeError("Spack runtime environment was not UTF-8") from exc
        if baseline.get(name) == value or not _safe_runtime_environment_name(name):
            continue
        if len(raw_value) > _MAX_ENVIRONMENT_VALUE_BYTES:
            raise RuntimeError(f"Spack environment value is too large: {name}")
        materialized[name] = value
    if len(materialized) > _MAX_ENVIRONMENT_VARIABLES:
        raise RuntimeError(
            "Spack environment changed too many variables: "
            f"{len(materialized)} > {_MAX_ENVIRONMENT_VARIABLES}"
        )
    ordered = dict(sorted(materialized.items()))
    serialized = json.dumps(ordered, separators=(",", ":"), sort_keys=True).encode(
        "utf-8"
    )
    if len(serialized) > _MAX_SPACK_CAPTURE_BYTES:
        raise RuntimeError(
            "serialized Spack runtime environment exceeded the output limit"
        )
    return ordered


def _run_bounded_process(
    argv: list[str],
    *,
    env: dict[str, str],
    timeout_seconds: int,
    stdin_payload: bytes | None = None,
) -> _BoundedProcessResult:
    """Run a child while retaining at most the configured tail per stream."""
    if stdin_payload is not None and len(stdin_payload) > _MAX_SPACK_CAPTURE_BYTES + 64:
        raise ValueError("subprocess input exceeded the configured limit")

    stdin_file: BinaryIO | int = subprocess.DEVNULL
    owned_stdin: BinaryIO | None = None
    if stdin_payload is not None and os.name != "nt":
        temporary_stdin = cast(BinaryIO, tempfile.TemporaryFile(mode="w+b"))
        temporary_stdin.write(stdin_payload)
        temporary_stdin.seek(0)
        owned_stdin = temporary_stdin
        stdin_file = temporary_stdin
    windows_job: Any | None = None
    try:
        if os.name == "nt":
            from jarvis_mcp.windows_job import (
                spawn_windows_job_process,
            )

            process, windows_job = spawn_windows_job_process(
                argv,
                shell=False,
                stdin_payload=stdin_payload,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                env=env,
            )
        else:
            process = subprocess.Popen(
                argv,
                stdin=stdin_file,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                env=env,
                start_new_session=True,
            )
    except OSError:
        if owned_stdin is not None:
            owned_stdin.close()
        raise

    if (
        process.stdout is None or process.stderr is None
    ):  # pragma: no cover - Popen contract.
        _terminate_spack_process_tree(process, windows_job=windows_job)
        if owned_stdin is not None:
            owned_stdin.close()
        if windows_job is not None:
            windows_job.close(process)
        raise RuntimeError("subprocess capture pipes were not created")

    stdout_capture = _BoundedCapture(cast(BinaryIO, process.stdout))
    stderr_capture = _BoundedCapture(cast(BinaryIO, process.stderr))
    threads = [
        threading.Thread(target=stdout_capture.drain, daemon=True),
        threading.Thread(target=stderr_capture.drain, daemon=True),
    ]
    for thread in threads:
        thread.start()

    timeout_error: subprocess.TimeoutExpired | None = None
    try:
        returncode = process.wait(timeout=timeout_seconds)
    except subprocess.TimeoutExpired as exc:
        timeout_error = exc
        _terminate_spack_process_tree(process, windows_job=windows_job)
        returncode = process.returncode if process.returncode is not None else -1
    finally:
        if owned_stdin is not None:
            owned_stdin.close()

    try:
        _finish_spack_captures(process, threads, windows_job=windows_job)
        if timeout_error is not None:
            raise timeout_error
        capture_error = stdout_capture.error or stderr_capture.error
        if capture_error is not None:
            raise RuntimeError(f"subprocess stream read failed: {capture_error}")
        if windows_job is not None:
            windows_job.ensure_empty(process)
        return _BoundedProcessResult(
            returncode=returncode,
            stdout=stdout_capture.raw(),
            stderr=stderr_capture.raw(),
            stdout_truncated=stdout_capture.truncated,
            stderr_truncated=stderr_capture.truncated,
        )
    finally:
        if windows_job is not None:
            windows_job.close(process)


def _finish_spack_captures(
    process: subprocess.Popen[bytes],
    threads: list[threading.Thread],
    *,
    windows_job: Any | None = None,
) -> None:
    """Finish pipe readers and clean descendants that inherited the pipes."""
    deadline = time.monotonic() + _SPACK_STREAM_JOIN_TIMEOUT_SECONDS
    for thread in threads:
        thread.join(timeout=max(0.0, deadline - time.monotonic()))
    if not any(thread.is_alive() for thread in threads):
        return
    _terminate_spack_process_tree(
        process,
        include_exited_group=True,
        windows_job=windows_job,
    )
    if process.stdout is not None:
        process.stdout.close()
    if process.stderr is not None:
        process.stderr.close()
    for thread in threads:
        thread.join(timeout=1)
    if any(thread.is_alive() for thread in threads):
        raise RuntimeError("subprocess output pipes did not close")


def _bounded_spack_diagnostic(payload: bytes) -> str:
    """Return a small decoded tail suitable for MCP error text."""
    if len(payload) > _MAX_SPACK_DIAGNOSTIC_BYTES:
        payload = payload[-_MAX_SPACK_DIAGNOSTIC_BYTES:]
        prefix = "[tail truncated]\n"
    else:
        prefix = ""
    return prefix + payload.decode("utf-8", errors="replace").strip()


def _terminate_spack_process_tree(
    process: subprocess.Popen[bytes],
    *,
    include_exited_group: bool = False,
    windows_job: Any | None = None,
) -> None:
    """Terminate a Spack/Bash child and descendants in its process group."""
    if os.name == "nt":
        if windows_job is None:
            raise RuntimeError("Windows subprocess has no identity-pinned Job Object")
        windows_job.terminate(process)
        return
    if process.poll() is not None and not include_exited_group:
        return
    try:
        kill_process_group = cast(Callable[[int, int], None], vars(os)["killpg"])
        kill_process_group(process.pid, signal.SIGTERM)
    except ProcessLookupError:
        return
    if process.poll() is not None:
        if include_exited_group:
            try:
                kill_process_group(process.pid, getattr(signal, "SIGKILL", 9))
            except ProcessLookupError:
                pass
        return
    try:
        process.wait(timeout=10)
    except subprocess.TimeoutExpired:
        try:
            kill_process_group(process.pid, getattr(signal, "SIGKILL", 9))
        except ProcessLookupError:
            pass
        process.wait(timeout=5)


def _spack_executable() -> str:
    configured = os.getenv("JARVIS_MCP_SPACK_COMMAND")
    if configured:
        candidate = Path(configured).expanduser()
        if candidate.is_file():
            return str(candidate)
        raise RuntimeError(f"configured Spack command does not exist: {candidate}")
    resolved = shutil.which("spack")
    if resolved is not None:
        return resolved
    candidates: list[Path] = []
    spack_root = os.getenv("SPACK_ROOT")
    if spack_root:
        candidates.append(Path(spack_root).expanduser() / "bin" / "spack")
    candidates.extend(
        [
            Path.home() / ".local" / "spack" / "bin" / "spack",
            Path("/opt/spack/bin/spack"),
        ]
    )
    for candidate in candidates:
        if candidate.is_file():
            return str(candidate)
    raise RuntimeError(
        "Spack executable was not found in PATH, SPACK_ROOT/bin, "
        "~/.local/spack, or /opt/spack"
    )


def _validate_spack_specs(spack_specs: list[str]) -> list[str]:
    if not spack_specs or len(spack_specs) > _MAX_SPACK_SPECS:
        raise ValueError(
            f"spack_specs must contain between 1 and {_MAX_SPACK_SPECS} specs"
        )
    normalized: list[str] = []
    for spec in spack_specs:
        value = spec.strip()
        if not value or len(value) > _MAX_SPACK_SPEC_LENGTH:
            raise ValueError(
                "each Spack spec must be non-empty and at most 1024 characters"
            )
        if value.startswith("-"):
            raise ValueError("Spack specs cannot begin with '-'")
        if any(ord(character) < 32 or ord(character) == 127 for character in value):
            raise ValueError("Spack specs cannot contain control characters")
        normalized.append(value)
    return normalized


def _valid_persisted_environment_name(name: str) -> bool:
    """Return whether a legacy sidecar name is syntactically non-sensitive."""
    if _ENVIRONMENT_NAME.fullmatch(name) is None:
        return False
    normalized = name.upper()
    if normalized in _TRANSIENT_ENVIRONMENT_NAMES or normalized.startswith(
        "BASH_FUNC_"
    ):
        return False
    return not (
        normalized in _SENSITIVE_ENVIRONMENT_EXACT_NAMES
        or any(
            normalized.endswith(suffix) for suffix in _SENSITIVE_ENVIRONMENT_SUFFIXES
        )
        or any(fragment in normalized for fragment in _SENSITIVE_ENVIRONMENT_FRAGMENTS)
    )


def _runtime_environment_allowlist() -> set[str]:
    """Return the default allowlist plus bounded operator-owned exact names."""
    allowed = set(_DEFAULT_RUNTIME_ENVIRONMENT_ALLOWLIST)
    configured_values = [
        os.getenv("CLIO_SPACK_ENV_ALLOWLIST", ""),
        os.getenv("JARVIS_MCP_SPACK_ENV_ALLOWLIST", ""),
    ]
    raw_names = [
        name.strip()
        for configured in configured_values
        for name in configured.split(",")
        if name.strip()
    ]
    if len(raw_names) > 128 or sum(len(name) for name in raw_names) > 8192:
        raise RuntimeError("Spack environment allowlist extension is too large")
    for name in raw_names:
        if not _valid_persisted_environment_name(name):
            raise RuntimeError(f"invalid Spack environment allowlist name: {name}")
        allowed.add(name.upper())
    return allowed


def _safe_runtime_environment_name(name: str) -> bool:
    """Return whether a captured variable is explicitly safe to persist."""
    return (
        _valid_persisted_environment_name(name)
        and name.upper() in _runtime_environment_allowlist()
    )


def _runtime_result(
    pipeline: Any,
    *,
    pipeline_id: str,
    execution_id: str,
    mode: str,
    status: str,
    terminal: bool,
    scheduler: Any,
    scheduler_phase: str | None,
    script_path: str | None,
    submit: bool,
    wait: bool,
    started_at: datetime,
    environment_metadata: dict[str, Any] | None,
    submission_metadata: dict[str, Any] | None,
    terminal_returncode: int | None = None,
    terminal_reason: str | None = None,
) -> dict[str, Any]:
    resolved_pipeline_id = _pipeline_id(pipeline) or pipeline_id
    scheduler_document = _jsonable(scheduler) if isinstance(scheduler, dict) else None
    scheduler_provider = (
        _optional_str(scheduler_document.get("name"))
        if isinstance(scheduler_document, dict)
        else None
    )
    scheduler_job_id = (
        _optional_str(submission_metadata.get("scheduler_job_id"))
        if submission_metadata is not None
        else None
    )
    finished_at = datetime.now(timezone.utc) if terminal else None
    runtime_metadata: dict[str, Any] = {
        "schema_version": RUNTIME_METADATA_SCHEMA,
        "source": "jarvis_mcp",
        "execution_id": execution_id,
        "pipeline_id": resolved_pipeline_id,
        "mode": mode,
        "scheduler_provider": scheduler_provider,
        "scheduler_type": scheduler_provider,
        "scheduler_job_id": scheduler_job_id,
        "scheduler_phase": scheduler_phase,
        "script_path": script_path,
        "hostfile_path": (
            _optional_str(submission_metadata.get("hostfile_path"))
            if submission_metadata is not None
            and submission_metadata.get("hostfile_path") is not None
            else _optional_str(scheduler_document.get("hostfile"))
            if isinstance(scheduler_document, dict)
            else None
        ),
        "output_path": (
            _optional_str(scheduler_document.get("output"))
            if isinstance(scheduler_document, dict)
            else None
        ),
        "error_path": (
            _optional_str(scheduler_document.get("error"))
            if isinstance(scheduler_document, dict)
            else None
        ),
        "package_provenance": _pipeline_package_provenance(pipeline),
        "terminal": {
            "state": status,
            "terminal": terminal,
            "returncode": (
                terminal_returncode
                if terminal_returncode is not None
                else 0
                if terminal
                else None
            ),
            "reason": terminal_reason,
            "started_at": started_at.isoformat(),
            "finished_at": finished_at.isoformat() if finished_at is not None else None,
        },
        "details": {
            "execution_owner": "jarvis_cd.pipeline",
            "submit": submit,
            "wait": wait,
            "environment": environment_metadata,
            "scheduler_submission": submission_metadata,
        },
    }
    return {
        "pipeline_id": resolved_pipeline_id,
        "status": status,
        "mode": mode,
        "scheduler": scheduler_document,
        "script_path": script_path,
        "wait": wait,
        "runtime_metadata": runtime_metadata,
    }


def _waited_workload_failure_metadata(
    pipeline: Any,
    *,
    scheduler: Any,
    prior_submission: Any,
    submit: bool,
    wait: bool,
    execution_id: str | None = None,
) -> tuple[dict[str, Any], str, int] | None:
    """Return a fresh, validated scheduler-owned waited-workload failure."""
    if not submit or not wait:
        return None
    current = getattr(pipeline, "last_submission", None)
    if not isinstance(current, dict) or _jsonable(current) == prior_submission:
        return None
    script_path = _optional_str(current.get("script_path"))
    if script_path is None:
        return None
    try:
        document = _scheduler_submission_metadata(
            pipeline,
            scheduler=scheduler,
            script_path=script_path,
            require_identity=True,
            execution_id=execution_id,
        )
    except RuntimeError:
        return None
    if document is None:
        return None
    returncode = document.get("terminal_returncode")
    if (
        document.get("state") != "workload_failed"
        or document.get("wait") is not True
        or document.get("terminal") is not True
        or isinstance(returncode, bool)
        or not isinstance(returncode, int)
        or returncode == 0
    ):
        return None
    return document, script_path, returncode


def _scheduler_submission_metadata(
    pipeline: Any,
    *,
    scheduler: Any,
    script_path: str,
    require_identity: bool,
    execution_id: str | None = None,
) -> dict[str, Any] | None:
    """Validate scheduler metadata produced by JARVIS-CD's provider boundary."""
    value = getattr(pipeline, "last_submission", None)
    if value is None:
        if not require_identity:
            return None
        raise RuntimeError(
            "JARVIS-CD did not return a provider-owned scheduler job identity"
        )
    if not isinstance(value, dict):
        raise RuntimeError("JARVIS-CD returned invalid scheduler submission metadata")
    document = {str(key): _jsonable(item) for key, item in value.items()}
    if document.get("schema_version") != "jarvis.scheduler.submission.v1":
        raise RuntimeError("JARVIS-CD scheduler submission schema is unsupported")
    configured_provider = (
        _optional_str(scheduler.get("name")) if isinstance(scheduler, dict) else None
    )
    if _optional_str(document.get("provider")) != configured_provider:
        raise RuntimeError("JARVIS-CD scheduler submission provider did not match")
    if _optional_str(document.get("script_path")) != script_path:
        raise RuntimeError("JARVIS-CD scheduler submission did not match this script")
    if execution_id is not None:
        if _optional_str(document.get("execution_id")) != execution_id:
            raise RuntimeError(
                "JARVIS-CD scheduler submission did not match this execution"
            )
        for key in (
            "hostfile_path",
            "pipeline_snapshot_path",
            "pipeline_input_path",
        ):
            value = document.get(key)
            if not isinstance(value, str) or not value.strip():
                raise RuntimeError(f"JARVIS-CD scheduler submission omitted {key}")
        snapshot_digest = document.get("pipeline_snapshot_sha256")
        if (
            not isinstance(snapshot_digest, str)
            or re.fullmatch(r"[0-9a-f]{64}", snapshot_digest) is None
        ):
            raise RuntimeError(
                "JARVIS-CD scheduler submission returned an invalid snapshot digest"
            )
    job_id = _optional_str(document.get("scheduler_job_id"))
    if job_id is not None and (
        document.get("submitted") is not True
        or document.get("identity_source") != "scheduler_submit_api"
    ):
        raise RuntimeError(
            "JARVIS-CD did not return a provider-owned scheduler job identity"
        )
    if not require_identity and job_id is not None:
        raise RuntimeError(
            "JARVIS-CD returned a scheduler identity for a script-only run"
        )
    if not require_identity and job_id is None:
        return document
    if job_id is None:
        raise RuntimeError(
            "JARVIS-CD did not return a provider-owned scheduler job identity"
        )
    if configured_provider == "slurm" and re.fullmatch(r"[0-9]+", job_id) is None:
        raise RuntimeError("JARVIS-CD returned an invalid SLURM job identity")
    return document


def _pipeline_package_provenance(pipeline: Any) -> list[dict[str, Any]]:
    provenance: list[dict[str, Any]] = []
    for package in _pipeline_packages(pipeline):
        snapshot = _package_snapshot(package)
        provenance.append(
            {
                key: snapshot.get(key)
                for key in ("pkg_id", "pkg_type", "global_id", "config_path")
                if snapshot.get(key) is not None
            }
        )
    return provenance


def _structured_runtime_error(
    *,
    code: str,
    message: str,
    pipeline_id: str,
    execution_id: str,
    runtime_metadata: dict[str, Any] | None = None,
) -> str:
    document: dict[str, Any] = {
        "schema_version": RUNTIME_ERROR_SCHEMA,
        "error": {
            "code": code,
            "message": message,
            "pipeline_id": pipeline_id,
            "execution_id": execution_id,
        },
    }
    if runtime_metadata is not None:
        document["runtime_metadata"] = runtime_metadata
    return json.dumps(document, separators=(",", ":"), sort_keys=True)


def _protocol_stdout_to_stderr() -> Any:
    """Keep JARVIS package prints off stdio MCP stdout."""
    return redirect_stdout(sys.stderr)


def _optional_str(value: Any) -> str | None:
    if value is None:
        return None
    return str(value)


def _load_pipeline(pipeline_id: str | None) -> Any:
    pipeline_cls = _require_pipeline_class()
    if pipeline_id is not None:
        pipeline_id = _validate_pipeline_id(pipeline_id)
    if _uses_current_pipeline_api():
        if pipeline_id is not None:
            return pipeline_cls(pipeline_id)
        pipeline = pipeline_cls()
        loaded = pipeline.load()
        return loaded if loaded is not None else pipeline
    pipeline = pipeline_cls()
    loaded = pipeline.load(pipeline_id)
    return loaded if loaded is not None else pipeline


def _create_pipeline(pipeline: Any, pipeline_id: str) -> Any:
    created = pipeline.create(_validate_pipeline_id(pipeline_id))
    return created if created is not None else pipeline


def _save_pipeline(pipeline: Any) -> None:
    if hasattr(pipeline, "save"):
        pipeline.save()


def _build_pipeline_env(pipeline: Any) -> None:
    if not hasattr(pipeline, "build_env"):
        return
    default_keys = ["CMAKE_PREFIX_PATH", "PATH"]
    env_track_dict = {key: True for key in default_keys}
    try:
        built = pipeline.build_env(env_track_dict)
    except TypeError:
        built = pipeline.build_env()
    if built is not None and built is not pipeline:
        _save_pipeline(built)


def _apply_pipeline_config(pipeline: Any, config: dict[str, Any]) -> None:
    """Apply top-level Pipeline configuration that JARVIS persists to YAML."""
    supported = {
        "scheduler",
        "hostfile",
        "hostfile_entries",
        "container_image",
        "container_uri",
        "container_engine",
        "container_base",
        "container_ssh_port",
        "container_extensions",
        "container_env",
        "container_host_path",
        "container_workspace",
        "container_caps",
        "container_binds",
        "container_gpu",
        "tmp_bind_root",
        "base_deploy_mode",
        "ssh_cmd",
        "pssh_cmd",
        "mpi_cmd",
        "env",
    }
    unknown = sorted(set(config) - supported)
    if unknown:
        raise ValueError(f"unsupported pipeline config keys: {', '.join(unknown)}")
    if "scheduler" in config:
        scheduler = config["scheduler"]
        if scheduler is not None and not isinstance(scheduler, dict):
            raise ValueError("scheduler must be an object or null")
        pipeline.scheduler = dict(scheduler) if scheduler is not None else None
        if pipeline.scheduler and hasattr(pipeline, "_apply_scheduler_hostfile"):
            pipeline._apply_scheduler_hostfile()
    if "hostfile" in config:
        hostfile_path = config["hostfile"]
        if hostfile_path in (None, ""):
            pipeline.hostfile = None
        else:
            try:
                hostfile_text = os.fspath(hostfile_path)
            except TypeError as exc:
                raise ValueError("hostfile must be one bounded printable path") from exc
            if not isinstance(hostfile_text, str) or (
                len(hostfile_text.encode("utf-8")) > 4096
                or any(
                    ord(character) < 32 or ord(character) == 127
                    for character in hostfile_text
                )
            ):
                raise ValueError("hostfile must be one bounded printable path")
            from jarvis_cd.util.hostfile import Hostfile  # type: ignore[import-untyped]

            pipeline.hostfile = Hostfile(path=hostfile_text)
    if "hostfile_entries" in config:
        hosts = config["hostfile_entries"]
        if not isinstance(hosts, list) or not all(
            isinstance(host, str) for host in hosts
        ):
            raise ValueError("hostfile_entries must be a list of host names")
        if len(hosts) > 4096 or any(
            _HOST_ENTRY.fullmatch(host) is None for host in hosts
        ):
            raise ValueError("hostfile_entries contains an invalid host name")
        shared_dir = pipeline.jarvis.get_pipeline_shared_dir(pipeline.name)
        shared_dir.mkdir(parents=True, exist_ok=True)
        hostfile_path = shared_dir / "mcp-hostfile.txt"
        _atomic_write_hostfile(hostfile_path, hosts)
        from jarvis_cd.util.hostfile import Hostfile  # type: ignore[import-untyped]

        pipeline.hostfile = Hostfile(path=str(hostfile_path))
    if "env" in config:
        env = config["env"]
        if env is None:
            pipeline.env = {}
        elif isinstance(env, dict):
            pipeline.env.update(env)
        else:
            raise ValueError("env must be an object or null")
    for key in supported - {"scheduler", "hostfile", "hostfile_entries", "env"}:
        if key in config:
            setattr(pipeline, key, config[key])
    if hasattr(pipeline, "_apply_launcher_overrides"):
        pipeline._apply_launcher_overrides()


def _is_legacy_pipeline(pipeline: Any) -> bool:
    return hasattr(pipeline, "sub_pkgs") or hasattr(pipeline, "configure")


def _pipeline_id(pipeline: Any) -> str | None:
    return _optional_str(
        getattr(pipeline, "global_id", None)
        or getattr(pipeline, "pipeline_id", None)
        or getattr(pipeline, "name", None)
    )


def _pipeline_config(pipeline: Any) -> dict[str, Any]:
    config = getattr(pipeline, "config", None)
    if isinstance(config, dict):
        return config
    data: dict[str, Any] = {
        "name": getattr(pipeline, "name", None),
        "packages": _pipeline_packages(pipeline),
        "interceptors": getattr(pipeline, "interceptors", None),
        "scheduler": getattr(pipeline, "scheduler", None),
        "hostfile": getattr(pipeline, "hostfile", None),
    }
    return {key: value for key, value in data.items() if value is not None}


def _pipeline_config_path(pipeline: Any) -> Any:
    if hasattr(pipeline, "config_path"):
        return getattr(pipeline, "config_path")
    jarvis = getattr(pipeline, "jarvis", None)
    name = getattr(pipeline, "name", None)
    if jarvis is not None and name and hasattr(jarvis, "get_pipeline_dir"):
        return jarvis.get_pipeline_dir(name) / "pipeline.yaml"
    return None


def _pipeline_env_path(pipeline: Any) -> Any:
    if hasattr(pipeline, "env_path"):
        return getattr(pipeline, "env_path")
    jarvis = getattr(pipeline, "jarvis", None)
    name = getattr(pipeline, "name", None)
    if jarvis is not None and name and hasattr(jarvis, "get_pipeline_dir"):
        directory = jarvis.get_pipeline_dir(name)
        if isinstance(directory, (str, os.PathLike)):
            return Path(directory) / "environment.yaml"
    return None


def _pipeline_packages(pipeline: Any) -> list[Any]:
    packages = getattr(pipeline, "sub_pkgs", None)
    if packages is None:
        packages = getattr(pipeline, "packages", [])
    return list(packages)


def _get_package(pipeline: Any, pkg_id: str) -> Any:
    if hasattr(pipeline, "get_pkg"):
        return pipeline.get_pkg(pkg_id)
    for pkg in _pipeline_packages(pipeline):
        if isinstance(pkg, dict):
            if pkg.get("pkg_id") == pkg_id or pkg.get("id") == pkg_id:
                return pkg
        elif getattr(pkg, "pkg_id", None) == pkg_id:
            return pkg
    return None


def _package_config(pkg: Any) -> Any:
    if isinstance(pkg, dict):
        return pkg.get("config", {})
    return getattr(pkg, "config", {})


def _kwargs_to_config_args(kwargs: dict[str, Any]) -> list[str]:
    args: list[str] = []
    for key, value in kwargs.items():
        if value is None:
            continue
        if isinstance(value, bool):
            args.append(f"{key}={str(value).lower()}")
        else:
            args.append(f"{key}={value}")
    return args


def _uses_current_pipeline_api() -> bool:
    pipeline_cls = _require_pipeline_class()
    parameters = inspect.signature(pipeline_cls.load).parameters
    return "load_type" in parameters


def _require_pipeline_class() -> Any:
    if Pipeline is not None:
        return Pipeline
    detail = f": {_PIPELINE_IMPORT_ERROR}" if _PIPELINE_IMPORT_ERROR is not None else ""
    raise RuntimeError(
        "JARVIS-CD Pipeline API is not available. Install a JARVIS-CD version "
        f"with jarvis_cd.core.pipeline or legacy jarvis_cd.basic.pkg{detail}"
    )
