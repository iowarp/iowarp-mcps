"""Bounded live progress bridge from JARVIS package providers to MCP."""

from __future__ import annotations

import asyncio
import json
import math
import os
import stat
import sys
from collections.abc import Awaitable, Callable
from contextlib import redirect_stdout
from dataclasses import dataclass
from importlib.metadata import entry_points
from pathlib import Path
from queue import Empty, Full, Queue
from threading import Lock as ThreadLock
from typing import Any, Protocol, TextIO, TypeVar, cast


PACKAGE_PROGRESS_SCHEMA = "clio-kit.jarvis-package-progress.v1"
PACKAGE_PROGRESS_ENTRYPOINT_GROUP = "clio_relay.package_progress_adapters"
PACKAGE_PROGRESS_MAX_NOTIFICATION_BYTES = 64 * 1024
PACKAGE_PROGRESS_MAX_NOTIFICATIONS = 10_000
PACKAGE_PROGRESS_MAX_TOTAL_BYTES = 4 * 1024 * 1024
PACKAGE_PROGRESS_LOG_READ_BYTES = 1024 * 1024
PACKAGE_PROGRESS_POLL_SECONDS = 0.05

_ResultT = TypeVar("_ResultT")
_PROGRESS_STDOUT_LOCK = asyncio.Lock()


class PackageProgressAdapter(Protocol):
    """Runtime contract implemented by a released JARVIS package provider."""

    package_name: str
    package_version: str
    run_id: str
    adapter_name: str
    application_profile: str | None

    def observe_jarvis_stdout(self, text: str) -> list[dict[str, object]]: ...

    def observe_stdout(self, text: str) -> list[dict[str, object]]: ...

    def finalize_jarvis_stdout(self) -> list[dict[str, object]]: ...

    def finalize_stdout(self) -> list[dict[str, object]]: ...

    def reset_stdout(self) -> None: ...

    def progress_log_paths(self) -> list[Path]: ...

    def acceptance_progress_valid(self, metadata: dict[str, Any]) -> bool: ...


ProgressReporter = Callable[[float, float | None, str], Awaitable[None]]


@dataclass(frozen=True)
class PackageProgressProviderIdentity:
    """Immutable provider identity attached to every MCP notification."""

    entry_point_name: str
    entry_point_value: str
    distribution_name: str
    distribution_version: str
    adapter_name: str
    package_name: str
    package_version: str
    application_profile: str | None

    def as_dict(self) -> dict[str, object]:
        """Return the bounded wire representation of this provider identity."""
        rendered: dict[str, object] = {
            "entry_point": self.entry_point_name,
            "entry_point_value": self.entry_point_value,
            "distribution": self.distribution_name,
            "distribution_version": self.distribution_version,
            "adapter": self.adapter_name,
            "package_name": self.package_name,
            "package_version": self.package_version,
        }
        if self.application_profile is not None:
            rendered["application_profile"] = self.application_profile
        return rendered


@dataclass
class PackageProgressBinding:
    """One released package provider bound to a concrete JARVIS execution."""

    identity: PackageProgressProviderIdentity
    adapter: PackageProgressAdapter
    source_authority: str
    log_path: Path | None


@dataclass
class _LogState:
    path: Path
    offset: int = 0
    identity: tuple[int, int] | None = None


class _ProgressOutput:
    """Forward JARVIS stdout to stderr while feeding the selected provider."""

    def __init__(
        self,
        delegate: TextIO,
        binding: PackageProgressBinding,
        records: Queue[dict[str, object]],
    ) -> None:
        self._delegate = delegate
        self._binding = binding
        self._records = records
        self._lock = ThreadLock()

    def write(self, value: str) -> int:
        """Forward a fragment and enqueue any complete provider observations."""
        with self._lock:
            written = self._delegate.write(value)
            self._delegate.flush()
            if self._binding.source_authority == "jarvis_stdout_fallback":
                _enqueue_records(
                    self._binding.adapter.observe_jarvis_stdout(value),
                    self._records,
                )
            return written

    def flush(self) -> None:
        """Flush the protocol-safe diagnostic stream."""
        self._delegate.flush()

    def isatty(self) -> bool:
        """Delegate terminal detection used by JARVIS logging."""
        return self._delegate.isatty()

    def fileno(self) -> int:
        """Delegate the underlying diagnostic file descriptor."""
        return self._delegate.fileno()

    @property
    def encoding(self) -> str | None:
        """Expose the delegate encoding expected by text writers."""
        return self._delegate.encoding


class PackageProgressExecution:
    """Run one synchronous JARVIS operation while reporting provider progress."""

    def __init__(
        self,
        binding: PackageProgressBinding,
        *,
        execution_id: str,
        pipeline_id: str,
    ) -> None:
        self.binding = binding
        self.execution_id = execution_id
        self.pipeline_id = pipeline_id
        self._notification_count = 0
        self._notification_bytes = 0

    async def run(
        self,
        operation: Callable[[], _ResultT],
        reporter: ProgressReporter,
    ) -> _ResultT:
        """Execute in a worker thread and emit observations before completion."""
        records: Queue[dict[str, object]] = Queue(
            maxsize=PACKAGE_PROGRESS_MAX_NOTIFICATIONS
        )
        log_state = _baseline_log(self.binding.log_path)
        output = _ProgressOutput(sys.stderr, self.binding, records)

        def execute() -> _ResultT:
            # FastMCP's stdio transport captures ``sys.stdout.buffer`` before tool
            # dispatch. The real-stdio regression test proves protocol writes stay
            # on that captured stream while this serialized JARVIS-only redirect is
            # active.
            with redirect_stdout(output):
                return operation()

        async with _PROGRESS_STDOUT_LOCK:
            task = asyncio.create_task(asyncio.to_thread(execute))
            operation_error: BaseException | None = None
            progress_error: BaseException | None = None
            result: _ResultT | None = None
            while not task.done():
                if progress_error is None:
                    try:
                        if log_state is not None:
                            _poll_log(self.binding, log_state, records)
                        await self._drain_records(records, reporter)
                    except BaseException as exc:
                        progress_error = exc
                else:
                    _discard_records(records)
                try:
                    await asyncio.sleep(PACKAGE_PROGRESS_POLL_SECONDS)
                except BaseException as exc:
                    if progress_error is None:
                        progress_error = exc
            try:
                result = await asyncio.shield(task)
            except BaseException as exc:
                operation_error = exc
            if progress_error is None:
                try:
                    if log_state is not None:
                        while _poll_log(self.binding, log_state, records):
                            await self._drain_records(records, reporter)
                        _enqueue_records(
                            self.binding.adapter.finalize_stdout(), records
                        )
                    else:
                        _enqueue_records(
                            self.binding.adapter.finalize_jarvis_stdout(),
                            records,
                        )
                    await self._drain_records(records, reporter)
                except BaseException as exc:
                    progress_error = exc
            else:
                _discard_records(records)
            if progress_error is not None:
                if operation_error is not None:
                    raise progress_error from operation_error
                raise progress_error
            if operation_error is not None:
                raise operation_error
            return cast(_ResultT, result)

    async def _drain_records(
        self,
        records: Queue[dict[str, object]],
        reporter: ProgressReporter,
    ) -> None:
        while True:
            try:
                record = records.get_nowait()
            except Empty:
                return
            await self._report_record(record, reporter)

    async def _report_record(
        self,
        record: dict[str, object],
        reporter: ProgressReporter,
    ) -> None:
        self._notification_count += 1
        if self._notification_count > PACKAGE_PROGRESS_MAX_NOTIFICATIONS:
            raise RuntimeError(
                "JARVIS package progress exceeded the maximum notification count"
            )
        normalized = _validated_record(record)
        metadata = cast(dict[str, Any], normalized["metadata"])
        provider_acceptance_validated = (
            self.binding.adapter.acceptance_progress_valid(metadata) is True
        )
        envelope = {
            "schema_version": PACKAGE_PROGRESS_SCHEMA,
            "execution_id": self.execution_id,
            "pipeline_id": self.pipeline_id,
            "notification_sequence": self._notification_count,
            "source_authority": self.binding.source_authority,
            "provider": self.binding.identity.as_dict(),
            "provider_acceptance_validated": provider_acceptance_validated,
            "record": normalized,
        }
        message = json.dumps(envelope, separators=(",", ":"), sort_keys=True)
        encoded_size = len(message.encode("utf-8"))
        if encoded_size > PACKAGE_PROGRESS_MAX_NOTIFICATION_BYTES:
            raise RuntimeError(
                "JARVIS package progress notification exceeded its byte limit"
            )
        self._notification_bytes += encoded_size
        if self._notification_bytes > PACKAGE_PROGRESS_MAX_TOTAL_BYTES:
            raise RuntimeError("JARVIS package progress exceeded its total byte limit")
        await reporter(
            cast(float, normalized["current"]),
            cast(float | None, normalized.get("total")),
            message,
        )


def bind_package_progress_provider(
    packages: list[Any],
    *,
    execution_id: str,
    base_deploy_mode: object = None,
) -> PackageProgressBinding | None:
    """Bind one pipeline package to a released progress-provider entry point."""
    declarations = [
        _package_declaration(package, base_deploy_mode) for package in packages
    ]
    if len(declarations) != 1:
        if any(
            _declared_adapter(declaration) not in (None, "none")
            for declaration in declarations
        ):
            raise RuntimeError(
                "package progress requires exactly one JARVIS pipeline package"
            )
        return None
    package = declarations[0]
    declared_adapter = _declared_adapter(package)
    if declared_adapter == "none":
        return None
    matches: list[tuple[Any, PackageProgressAdapter]] = []
    available: list[str] = []
    for entry_point in sorted(
        entry_points().select(group=PACKAGE_PROGRESS_ENTRYPOINT_GROUP),
        key=lambda item: item.name,
    ):
        factory = entry_point.load()
        if not callable(factory):
            raise RuntimeError(
                f"package progress entry point is not callable: {entry_point.name}"
            )
        adapter = factory(dict(package))
        if adapter is None:
            continue
        typed_adapter = cast(PackageProgressAdapter, adapter)
        _validate_adapter(typed_adapter, package)
        available.append(typed_adapter.adapter_name)
        if declared_adapter is None or typed_adapter.adapter_name == declared_adapter:
            matches.append((entry_point, typed_adapter))
    if len(matches) > 1:
        raise RuntimeError(
            "multiple JARVIS package progress providers matched the pipeline"
        )
    if not matches:
        if declared_adapter is not None:
            raise RuntimeError(
                f"declared JARVIS package progress provider {declared_adapter!r} "
                f"is unavailable; available={sorted(available)}"
            )
        return None
    entry_point, adapter = matches[0]
    distribution = entry_point.dist
    if distribution is None or not distribution.name or not distribution.version:
        raise RuntimeError(
            "JARVIS package progress provider has no distribution identity"
        )
    adapter.run_id = execution_id
    paths = adapter.progress_log_paths()
    if len(paths) > 1:
        raise RuntimeError(
            "JARVIS package progress providers may expose at most one log path"
        )
    log_path = _normalized_log_path(paths[0]) if paths else None
    return PackageProgressBinding(
        identity=PackageProgressProviderIdentity(
            entry_point_name=entry_point.name,
            entry_point_value=entry_point.value,
            distribution_name=distribution.name,
            distribution_version=distribution.version,
            adapter_name=adapter.adapter_name,
            package_name=adapter.package_name,
            package_version=adapter.package_version,
            application_profile=adapter.application_profile,
        ),
        adapter=adapter,
        source_authority=(
            "package_log" if log_path is not None else "jarvis_stdout_fallback"
        ),
        log_path=log_path,
    )


def _package_declaration(package: Any, base_deploy_mode: object) -> dict[str, Any]:
    if isinstance(package, dict):
        raw = cast(dict[str, Any], package)
        config = raw.get("config")
        declaration = (
            dict(cast(dict[str, Any], config)) if isinstance(config, dict) else {}
        )
        package_type = raw.get("pkg_type") or raw.get("type")
    else:
        config = getattr(package, "config", None)
        declaration = (
            dict(cast(dict[str, Any], config)) if isinstance(config, dict) else {}
        )
        package_type = getattr(package, "pkg_type", None) or getattr(
            package, "type", None
        )
    if isinstance(package_type, str) and package_type:
        declaration["pkg_type"] = package_type
    package_mode = declaration.get("deploy_mode")
    if package_mode is None and isinstance(base_deploy_mode, str) and base_deploy_mode:
        declaration["deploy_mode"] = base_deploy_mode
        declaration["effective_deploy_mode"] = base_deploy_mode
    elif isinstance(package_mode, str) and package_mode:
        declaration["effective_deploy_mode"] = package_mode
    return declaration


def _declared_adapter(package: dict[str, Any]) -> str | None:
    progress = package.get("progress")
    if not isinstance(progress, dict):
        return None
    value = cast(dict[str, object], progress).get("adapter")
    if value is None:
        return None
    if not isinstance(value, str) or not value:
        raise RuntimeError("JARVIS package progress.adapter must be a non-empty string")
    return value


def _validate_adapter(adapter: PackageProgressAdapter, package: dict[str, Any]) -> None:
    package_type = package.get("pkg_type")
    if not isinstance(package_type, str) or not package_type:
        raise RuntimeError("JARVIS package progress requires a non-empty pkg_type")
    if adapter.package_name != package_type:
        raise RuntimeError("JARVIS package progress provider package identity mismatch")
    for field_name in ("adapter_name", "package_version"):
        if not isinstance(getattr(adapter, field_name, None), str) or not getattr(
            adapter, field_name
        ):
            raise RuntimeError(
                f"JARVIS package progress provider {field_name} is invalid"
            )
    for method_name in (
        "observe_jarvis_stdout",
        "observe_stdout",
        "finalize_jarvis_stdout",
        "finalize_stdout",
        "reset_stdout",
        "progress_log_paths",
        "acceptance_progress_valid",
    ):
        if not callable(getattr(adapter, method_name, None)):
            raise RuntimeError(f"JARVIS package progress provider lacks {method_name}")


def _validated_record(record: dict[str, object]) -> dict[str, object]:
    allowed = {"label", "current", "total", "unit", "message", "metadata"}
    if not set(record).issubset(allowed):
        raise RuntimeError("JARVIS package progress record contains unsupported fields")
    current = _finite_number(record.get("current"))
    if current is None:
        raise RuntimeError("JARVIS package progress current must be finite")
    total_value = record.get("total")
    total = None if total_value is None else _finite_number(total_value)
    if total_value is not None and total is None:
        raise RuntimeError("JARVIS package progress total must be finite")
    metadata = record.get("metadata")
    if not isinstance(metadata, dict):
        raise RuntimeError("JARVIS package progress metadata must be an object")
    normalized: dict[str, object] = {
        "label": _bounded_text(record.get("label"), "label", default="progress"),
        "current": current,
        "metadata": {
            str(key): value
            for key, value in cast(dict[object, object], metadata).items()
        },
    }
    if total is not None:
        normalized["total"] = total
    for field_name in ("unit", "message"):
        value = record.get(field_name)
        if value is not None:
            normalized[field_name] = _bounded_text(value, field_name)
    try:
        json.dumps(normalized, allow_nan=False, separators=(",", ":"), sort_keys=True)
    except (TypeError, ValueError) as exc:
        raise RuntimeError(
            f"JARVIS package progress record is not JSON-safe: {exc}"
        ) from exc
    return normalized


def _bounded_text(value: object, field_name: str, *, default: str | None = None) -> str:
    if value is None and default is not None:
        return default
    if not isinstance(value, str) or not value or len(value.encode("utf-8")) > 4096:
        raise RuntimeError(f"JARVIS package progress {field_name} is invalid")
    return value


def _finite_number(value: object) -> float | None:
    if isinstance(value, bool) or not isinstance(value, int | float):
        return None
    parsed = float(value)
    return parsed if math.isfinite(parsed) else None


def _normalized_log_path(path: Path) -> Path:
    expanded = path.expanduser()
    candidate = expanded if expanded.is_absolute() else Path.cwd().absolute() / expanded
    return Path(os.path.abspath(candidate))


def _baseline_log(path: Path | None) -> _LogState | None:
    if path is None:
        return None
    handle = _open_regular_log(path)
    if handle is None:
        return _LogState(path=path)
    with handle:
        observed = os.fstat(handle.fileno())
        return _LogState(
            path=path,
            offset=observed.st_size,
            identity=(observed.st_dev, observed.st_ino),
        )


def _poll_log(
    binding: PackageProgressBinding,
    state: _LogState,
    records: Queue[dict[str, object]],
) -> bool:
    handle = _open_regular_log(state.path)
    if handle is None:
        return False
    with handle:
        observed = os.fstat(handle.fileno())
        identity = (observed.st_dev, observed.st_ino)
        if (
            state.identity is not None
            and identity != state.identity
            or observed.st_size < state.offset
        ):
            binding.adapter.reset_stdout()
            state.offset = 0
        state.identity = identity
        handle.seek(state.offset)
        payload = handle.read(PACKAGE_PROGRESS_LOG_READ_BYTES)
        state.offset = handle.tell()
        at_eof = state.offset >= os.fstat(handle.fileno()).st_size
    _enqueue_records(
        binding.adapter.observe_stdout(payload.decode("utf-8", errors="replace")),
        records,
    )
    return bool(payload) and not at_eof


def _enqueue_records(
    values: list[dict[str, object]],
    records: Queue[dict[str, object]],
) -> None:
    """Reject provider bursts before they can grow the cross-thread queue."""
    if len(values) > PACKAGE_PROGRESS_MAX_NOTIFICATIONS:
        raise RuntimeError("JARVIS package provider returned too many records at once")
    for record in values:
        try:
            records.put_nowait(record)
        except Full as exc:
            raise RuntimeError(
                "JARVIS package progress queue reached its fixed limit"
            ) from exc


def _discard_records(records: Queue[dict[str, object]]) -> None:
    """Keep a failed reporter from back-pressuring a still-owned operation."""
    while True:
        try:
            records.get_nowait()
        except Empty:
            return


def _open_regular_log(path: Path) -> Any:
    try:
        path_stat = os.stat(path, follow_symlinks=False)
    except FileNotFoundError:
        return None
    if stat.S_ISLNK(path_stat.st_mode) or not stat.S_ISREG(path_stat.st_mode):
        raise RuntimeError(
            "JARVIS package progress log must be a regular nonsymlink file"
        )
    flags = (
        os.O_RDONLY
        | int(getattr(os, "O_BINARY", 0))
        | int(getattr(os, "O_NOFOLLOW", 0))
        | int(getattr(os, "O_NONBLOCK", 0))
    )
    descriptor = os.open(path, flags)
    try:
        opened_stat = os.fstat(descriptor)
        if not stat.S_ISREG(opened_stat.st_mode) or (
            opened_stat.st_dev,
            opened_stat.st_ino,
        ) != (path_stat.st_dev, path_stat.st_ino):
            raise RuntimeError("JARVIS package progress log changed while opening")
        return os.fdopen(descriptor, "rb")
    except Exception:
        os.close(descriptor)
        raise
