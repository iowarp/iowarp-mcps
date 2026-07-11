"""Bounded subprocess and result contracts for Spack operations."""

from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import signal
import subprocess
import tempfile
import threading
import time
from collections import deque
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any, BinaryIO, Final, Literal, cast

from pydantic import BaseModel, ConfigDict, Field

SPACK_RESULT_SCHEMA: Final = "spack.mcp.result.v1"
SPACK_ERROR_SCHEMA: Final = "spack.mcp.error.v1"
_MAX_CAPTURE_BYTES = 8 * 1024 * 1024
_MAX_DIAGNOSTIC_BYTES = 32 * 1024
_MAX_SPEC_LENGTH = 1024
_MAX_INSTALL_TIMEOUT_SECONDS = 86_400
_MAX_ENVIRONMENT_VARIABLES = 512
_MAX_ENVIRONMENT_VALUE_BYTES = 256 * 1024
_MAX_PACKAGE_RECORDS = 10_000
_STREAM_CHUNK_BYTES = 64 * 1024
_STREAM_JOIN_TIMEOUT_SECONDS = 5.0
_ENVIRONMENT_MARKER = b"\0__SPACK_MCP_ENVIRONMENT_V1__\0"
_ENVIRONMENT_NAME = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
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


class SpackPackage(BaseModel):
    """Stable summary of one concrete installed Spack package."""

    model_config = ConfigDict(extra="forbid")

    name: str
    version: str | None = None
    dag_hash: str | None = None
    compiler: str | None = None
    architecture: str | None = None


class SpackFindResult(BaseModel):
    """Machine-readable installed-package query result."""

    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["spack.mcp.result.v1"] = SPACK_RESULT_SCHEMA
    operation: Literal["find"] = "find"
    query: str | None = None
    packages: list[SpackPackage] = Field(default_factory=list)
    count: int


class SpackLocateResult(BaseModel):
    """Unique installed package and its exact prefix."""

    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["spack.mcp.result.v1"] = SPACK_RESULT_SCHEMA
    operation: Literal["locate"] = "locate"
    requested_spec: str
    package: SpackPackage
    prefix: str


class SpackInstallResult(BaseModel):
    """Completed Spack install operation and observed matching installs."""

    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["spack.mcp.result.v1"] = SPACK_RESULT_SCHEMA
    operation: Literal["install"] = "install"
    requested_spec: str
    reuse: bool
    status: Literal["installed"] = "installed"
    duration_seconds: float
    packages: list[SpackPackage]
    stdout_excerpt: str | None = None


class SpackEnvironmentResult(BaseModel):
    """Admin-only structured runtime environment for installed specs."""

    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["spack.mcp.result.v1"] = SPACK_RESULT_SCHEMA
    operation: Literal["environment"] = "environment"
    specs: list[str]
    environment: dict[str, str]
    variable_names: list[str]
    environment_sha256: str


class SpackBackendError(RuntimeError):
    """Structured backend failure suitable for an MCP error result."""

    def __init__(
        self,
        code: str,
        message: str,
        *,
        operation: str,
        returncode: int | None = None,
        detail: str | None = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.operation = operation
        self.returncode = returncode
        self.detail = detail

    def as_json(self) -> str:
        """Return a stable machine-readable MCP error message."""
        return json.dumps(
            {
                "schema_version": SPACK_ERROR_SCHEMA,
                "error": {
                    "code": self.code,
                    "message": self.message,
                    "operation": self.operation,
                    "returncode": self.returncode,
                    "detail": self.detail,
                },
            },
            separators=(",", ":"),
            sort_keys=True,
        )


@dataclass(frozen=True)
class _CommandResult:
    argv: tuple[str, ...]
    returncode: int
    stdout: str
    stderr: str
    duration_seconds: float
    stdout_truncated: bool = False
    stderr_truncated: bool = False
    stdout_bytes: bytes | None = None
    stderr_bytes: bytes | None = None


class _BoundedCapture:
    """Drain one child stream while retaining only a bounded tail."""

    def __init__(self, stream: BinaryIO) -> None:
        self.stream = stream
        self.chunks: deque[bytes] = deque()
        self.size = 0
        self.truncated = False
        self.error: OSError | None = None

    def drain(self) -> None:
        """Drain until EOF without allowing retained data to grow unbounded."""
        try:
            while chunk := self.stream.read(_STREAM_CHUNK_BYTES):
                self.chunks.append(chunk)
                self.size += len(chunk)
                self._trim()
        except OSError as exc:
            self.error = exc

    def _trim(self) -> None:
        overflow = self.size - _MAX_CAPTURE_BYTES
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

    def text(self) -> str:
        """Decode the retained tail and mark it when earlier bytes were dropped."""
        value = self.raw().decode("utf-8", errors="replace")
        if self.truncated:
            return "[tail truncated]\n" + value
        return value

    def raw(self) -> bytes:
        """Return the retained undecoded bytes."""
        return b"".join(self.chunks)


def find_installed(query: str | None = None) -> SpackFindResult:
    """List installed packages matching an optional Spack constraint."""
    normalized = None if query is None else _validated_spec(query)
    args = ["find", "--json"]
    if normalized is not None:
        args.append(normalized)
    result = _run_spack(args, operation="find", timeout_seconds=120)
    records = _decode_find_records(result)
    packages = sorted(
        (_package_summary(record) for record in records),
        key=lambda package: (
            package.name,
            package.version or "",
            package.dag_hash or "",
            package.compiler or "",
            package.architecture or "",
        ),
    )
    return SpackFindResult(query=normalized, packages=packages, count=len(packages))


def locate_installed(spec: str) -> SpackLocateResult:
    """Resolve exactly one installed spec and return its prefix."""
    normalized = _validated_spec(spec)
    found = find_installed(normalized)
    if not found.packages:
        raise SpackBackendError(
            "not_installed",
            f"no installed Spack package matches: {normalized}",
            operation="locate",
        )
    if len(found.packages) != 1:
        choices = [package.model_dump(mode="json") for package in found.packages[:20]]
        raise SpackBackendError(
            "ambiguous_spec",
            f"Spack spec matches {len(found.packages)} installed packages",
            operation="locate",
            detail=json.dumps(choices, separators=(",", ":"), sort_keys=True),
        )
    package = found.packages[0]
    exact = f"/{package.dag_hash}" if package.dag_hash else normalized
    result = _run_spack(
        ["location", "-i", exact],
        operation="locate",
        timeout_seconds=120,
    )
    prefix = result.stdout.strip()
    if not prefix or len(prefix.splitlines()) != 1 or not Path(prefix).is_absolute():
        raise SpackBackendError(
            "invalid_prefix",
            "Spack returned an invalid or non-absolute installation prefix",
            operation="locate",
        )
    return SpackLocateResult(
        requested_spec=normalized,
        package=package,
        prefix=prefix,
    )


def install_spec(
    spec: str,
    *,
    reuse: bool = True,
    timeout_seconds: int = 14_400,
) -> SpackInstallResult:
    """Install one Spack spec without invoking a shell."""
    normalized = _validated_spec(spec)
    if timeout_seconds < 1 or timeout_seconds > _MAX_INSTALL_TIMEOUT_SECONDS:
        raise SpackBackendError(
            "invalid_timeout",
            f"timeout_seconds must be between 1 and {_MAX_INSTALL_TIMEOUT_SECONDS}",
            operation="install",
        )
    args = ["install"]
    if reuse:
        args.append("--reuse")
    args.append(normalized)
    result = _run_spack(args, operation="install", timeout_seconds=timeout_seconds)
    found = find_installed(normalized)
    if not found.packages:
        raise SpackBackendError(
            "install_not_observed",
            "Spack exited successfully but no matching installed package was observed",
            operation="install",
        )
    excerpt = result.stdout.strip()
    if len(excerpt) > 4000:
        excerpt = "[tail truncated]\n" + excerpt[-4000:]
    return SpackInstallResult(
        requested_spec=normalized,
        reuse=reuse,
        duration_seconds=round(result.duration_seconds, 3),
        packages=found.packages,
        stdout_excerpt=excerpt or None,
    )


def resolve_environment(specs: list[str]) -> SpackEnvironmentResult:
    """Resolve an admin-only structured environment without mutating the server."""
    if not specs or len(specs) > 32:
        raise SpackBackendError(
            "invalid_specs",
            "specs must contain between 1 and 32 entries",
            operation="environment",
        )
    normalized = [_validated_spec(spec) for spec in specs]
    loaded = _run_spack(
        ["load", "--sh", *normalized],
        operation="environment",
        timeout_seconds=120,
    )
    if loaded.stdout_truncated:
        raise SpackBackendError(
            "response_too_large",
            "Spack environment script exceeded the response limit",
            operation="environment",
        )
    loaded_bytes = (
        loaded.stdout_bytes if loaded.stdout_bytes is not None else loaded.stdout.encode("utf-8")
    )
    try:
        environment_script = loaded_bytes.decode("utf-8", errors="strict")
    except UnicodeDecodeError as exc:
        raise SpackBackendError(
            "invalid_environment",
            "Spack environment script was not UTF-8",
            operation="environment",
        ) from exc
    baseline = dict(os.environ)
    script = (
        "set -e\n" + environment_script + "\nprintf '\\0__SPACK_MCP_ENVIRONMENT_V1__\\0'\nenv -0\n"
    )
    try:
        captured = _run_bounded_command(
            ["bash", "--noprofile", "--norc"],
            env=baseline,
            stdin_payload=script.encode("utf-8"),
            timeout_seconds=120,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise SpackBackendError(
            "environment_capture_failed",
            "could not materialize the Spack environment",
            operation="environment",
            detail=str(exc),
        ) from exc
    except RuntimeError as exc:
        raise SpackBackendError(
            "environment_capture_failed",
            "could not capture the materialized Spack environment",
            operation="environment",
            detail=str(exc),
        ) from exc
    if captured.returncode != 0:
        raise SpackBackendError(
            "environment_capture_failed",
            "the Spack environment script failed",
            operation="environment",
            returncode=captured.returncode,
            detail=_bounded_diagnostic(captured.stderr),
        )
    if captured.stdout_truncated:
        raise SpackBackendError(
            "environment_too_large",
            "the materialized Spack environment exceeded the response limit",
            operation="environment",
        )
    raw_environment = (
        captured.stdout_bytes
        if captured.stdout_bytes is not None
        else captured.stdout.encode("utf-8")
    )
    _, marker, raw_environment = raw_environment.partition(_ENVIRONMENT_MARKER)
    if not marker:
        raise SpackBackendError(
            "invalid_environment",
            "the Spack environment output omitted its integrity marker",
            operation="environment",
        )
    environment = dict(sorted(_filtered_environment_delta(baseline, raw_environment).items()))
    serialized = json.dumps(environment, separators=(",", ":"), sort_keys=True).encode("utf-8")
    if len(serialized) > _MAX_CAPTURE_BYTES:
        raise SpackBackendError(
            "environment_too_large",
            "the serialized Spack environment exceeded the response limit",
            operation="environment",
        )
    return SpackEnvironmentResult(
        specs=normalized,
        environment=environment,
        variable_names=sorted(environment),
        environment_sha256=hashlib.sha256(serialized).hexdigest(),
    )


def _run_spack(
    args: list[str],
    *,
    operation: str,
    timeout_seconds: int,
) -> _CommandResult:
    executable = _spack_executable()
    argv = [executable, *args]
    try:
        result = _run_bounded_command(
            argv,
            env=os.environ.copy(),
            timeout_seconds=timeout_seconds,
        )
    except OSError as exc:
        raise SpackBackendError(
            "launch_failed",
            "could not launch Spack",
            operation=operation,
            detail=str(exc),
        ) from exc
    except subprocess.TimeoutExpired as exc:
        raise SpackBackendError(
            "timed_out",
            f"Spack {operation} exceeded {timeout_seconds} seconds",
            operation=operation,
        ) from exc
    except RuntimeError as exc:
        raise SpackBackendError(
            "capture_failed",
            f"could not capture Spack {operation} output",
            operation=operation,
            detail=str(exc),
        ) from exc
    if result.returncode != 0:
        detail = (
            _bounded_diagnostic(result.stderr)
            or _bounded_diagnostic(result.stdout)
            or "Spack returned no diagnostic output"
        )
        raise SpackBackendError(
            "command_failed",
            f"Spack {operation} failed",
            operation=operation,
            returncode=result.returncode,
            detail=detail,
        )
    return result


def _run_bounded_command(
    argv: list[str],
    *,
    env: dict[str, str],
    timeout_seconds: int,
    stdin_payload: bytes | None = None,
) -> _CommandResult:
    """Run argv with bounded retained output and a bounded optional stdin file."""
    if stdin_payload is not None and len(stdin_payload) > _MAX_CAPTURE_BYTES + 64:
        raise ValueError("subprocess input exceeded the configured limit")

    started = time.monotonic()
    stdin_file: BinaryIO | int = subprocess.DEVNULL
    owned_stdin: BinaryIO | None = None
    if stdin_payload is not None:
        temporary_stdin = cast(BinaryIO, tempfile.TemporaryFile(mode="w+b"))
        temporary_stdin.write(stdin_payload)
        temporary_stdin.seek(0)
        owned_stdin = temporary_stdin
        stdin_file = temporary_stdin

    try:
        process = subprocess.Popen(
            argv,
            stdin=stdin_file,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env=env,
            start_new_session=os.name != "nt",
            creationflags=(
                int(getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)) if os.name == "nt" else 0
            ),
        )
    except OSError:
        if owned_stdin is not None:
            owned_stdin.close()
        raise

    if process.stdout is None or process.stderr is None:  # pragma: no cover - Popen contract.
        _terminate_process_tree(process)
        if owned_stdin is not None:
            owned_stdin.close()
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
        _terminate_process_tree(process)
        returncode = process.returncode if process.returncode is not None else -1
    finally:
        if owned_stdin is not None:
            owned_stdin.close()

    _finish_captures(process, threads)
    if timeout_error is not None:
        raise timeout_error
    capture_error = stdout_capture.error or stderr_capture.error
    if capture_error is not None:
        raise RuntimeError(f"subprocess stream read failed: {capture_error}")
    return _CommandResult(
        argv=tuple(argv),
        returncode=returncode,
        stdout=stdout_capture.text(),
        stderr=stderr_capture.text(),
        duration_seconds=time.monotonic() - started,
        stdout_truncated=stdout_capture.truncated,
        stderr_truncated=stderr_capture.truncated,
        stdout_bytes=stdout_capture.raw(),
        stderr_bytes=stderr_capture.raw(),
    )


def _finish_captures(
    process: subprocess.Popen[bytes],
    threads: list[threading.Thread],
) -> None:
    """Finish stream readers, cleaning inherited child pipes if necessary."""
    for thread in threads:
        thread.join(timeout=_STREAM_JOIN_TIMEOUT_SECONDS)
    if not any(thread.is_alive() for thread in threads):
        return
    _terminate_process_tree(process, include_exited_group=True)
    if process.stdout is not None:
        process.stdout.close()
    if process.stderr is not None:
        process.stderr.close()
    for thread in threads:
        thread.join(timeout=1)
    if any(thread.is_alive() for thread in threads):
        raise RuntimeError("subprocess output pipes did not close")


def _decode_find_records(result: _CommandResult) -> list[dict[str, Any]]:
    if result.stdout_truncated:
        raise SpackBackendError(
            "response_too_large",
            "Spack find JSON exceeded the response limit",
            operation="find",
        )
    try:
        payload = cast(object, json.loads(result.stdout))
    except json.JSONDecodeError as exc:
        raise SpackBackendError(
            "invalid_json",
            "Spack find did not return valid JSON",
            operation="find",
            detail=str(exc),
        ) from exc
    if isinstance(payload, dict):
        payload = cast(dict[str, object], payload).get("specs")
    if not isinstance(payload, list) or not all(isinstance(item, dict) for item in payload):
        raise SpackBackendError(
            "invalid_json_shape",
            "Spack find JSON was not an array of package objects",
            operation="find",
        )
    if len(payload) > _MAX_PACKAGE_RECORDS:
        raise SpackBackendError(
            "response_too_large",
            f"Spack find returned more than {_MAX_PACKAGE_RECORDS} package records",
            operation="find",
        )
    return [cast(dict[str, Any], item) for item in payload]


def _package_summary(record: dict[str, Any]) -> SpackPackage:
    name = record.get("name")
    if not isinstance(name, str) or not name:
        raise SpackBackendError(
            "invalid_package_record",
            "Spack package record omitted its name",
            operation="find",
        )
    compiler_value = record.get("compiler")
    compiler: str | None = None
    if isinstance(compiler_value, dict):
        compiler_name = compiler_value.get("name")
        compiler_version = compiler_value.get("version")
        if compiler_name is not None:
            compiler = str(compiler_name)
            if compiler_version is not None:
                compiler += f"@{compiler_version}"
    elif compiler_value is not None:
        compiler = str(compiler_value)
    architecture_value = record.get("arch") or record.get("architecture")
    architecture = (
        json.dumps(architecture_value, separators=(",", ":"), sort_keys=True)
        if isinstance(architecture_value, dict)
        else str(architecture_value)
        if architecture_value is not None
        else None
    )
    dag_hash = record.get("hash") or record.get("full_hash") or record.get("dag_hash")
    return SpackPackage(
        name=name,
        version=str(record["version"]) if record.get("version") is not None else None,
        dag_hash=str(dag_hash) if dag_hash is not None else None,
        compiler=compiler,
        architecture=architecture,
    )


def _spack_executable() -> str:
    configured = os.getenv("SPACK_MCP_COMMAND")
    if configured:
        candidate = Path(configured).expanduser()
        if candidate.is_file():
            return str(candidate)
        raise SpackBackendError(
            "command_not_found",
            "configured Spack executable does not exist",
            operation="startup",
            detail=str(candidate),
        )
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
    raise SpackBackendError(
        "command_not_found",
        "Spack executable was not found in PATH, SPACK_ROOT/bin, ~/.local/spack, or /opt/spack",
        operation="startup",
    )


def _validated_spec(spec: str) -> str:
    value = spec.strip()
    if not value or len(value) > _MAX_SPEC_LENGTH:
        raise SpackBackendError(
            "invalid_spec",
            "Spack spec must be non-empty and at most 1024 characters",
            operation="validation",
        )
    if value.startswith("-"):
        raise SpackBackendError(
            "invalid_spec",
            "Spack specs cannot begin with '-'",
            operation="validation",
        )
    if any(ord(character) < 32 or ord(character) == 127 for character in value):
        raise SpackBackendError(
            "invalid_spec",
            "Spack spec cannot contain control characters",
            operation="validation",
        )
    return value


def _filtered_environment_delta(baseline: dict[str, str], raw: bytes) -> dict[str, str]:
    environment: dict[str, str] = {}
    for item in raw.split(b"\0"):
        if not item or b"=" not in item:
            continue
        raw_name, raw_value = item.split(b"=", 1)
        try:
            name = raw_name.decode("utf-8", errors="strict")
            value = raw_value.decode("utf-8", errors="strict")
        except UnicodeDecodeError as exc:
            raise SpackBackendError(
                "invalid_environment",
                "Spack environment was not UTF-8",
                operation="environment",
            ) from exc
        if baseline.get(name) == value or not _safe_environment_name(name):
            continue
        if len(raw_value) > _MAX_ENVIRONMENT_VALUE_BYTES:
            raise SpackBackendError(
                "environment_value_too_large",
                f"Spack environment value is too large: {name}",
                operation="environment",
            )
        environment[name] = value
    if len(environment) > _MAX_ENVIRONMENT_VARIABLES:
        raise SpackBackendError(
            "environment_too_large",
            "Spack environment changed too many variables",
            operation="environment",
            detail=f"{len(environment)} > {_MAX_ENVIRONMENT_VARIABLES}",
        )
    return environment


def _safe_environment_name(name: str) -> bool:
    if _ENVIRONMENT_NAME.fullmatch(name) is None:
        return False
    normalized = name.upper()
    if normalized in _TRANSIENT_ENVIRONMENT_NAMES or normalized.startswith("BASH_FUNC_"):
        return False
    return not any(fragment in normalized for fragment in _SENSITIVE_ENVIRONMENT_FRAGMENTS)


def _bounded_diagnostic(value: str) -> str:
    payload = value.encode("utf-8", errors="replace")
    if len(payload) > _MAX_DIAGNOSTIC_BYTES:
        payload = payload[-_MAX_DIAGNOSTIC_BYTES:]
        prefix = "[tail truncated]\n"
    else:
        prefix = ""
    return prefix + payload.decode("utf-8", errors="replace").strip()


def _terminate_process_tree(
    process: subprocess.Popen[bytes],
    *,
    include_exited_group: bool = False,
) -> None:
    """Terminate the child and descendants started in its process group."""
    if os.name == "nt":
        if process.poll() is None:
            try:
                subprocess.run(
                    ["taskkill.exe", "/PID", str(process.pid), "/T", "/F"],
                    stdin=subprocess.DEVNULL,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    check=False,
                    timeout=10,
                )
            except (OSError, subprocess.TimeoutExpired):
                process.terminate()
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=5)
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
