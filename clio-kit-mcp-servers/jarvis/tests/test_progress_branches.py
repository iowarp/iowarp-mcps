"""Focused branch coverage for the package-progress production boundary."""

from __future__ import annotations

import io
import os
from dataclasses import dataclass, field
from pathlib import Path
from queue import Queue
from types import SimpleNamespace
from typing import Any

import pytest

import jarvis_mcp.progress as progress


@dataclass
class _Adapter:
    package_name: str = "test.package"
    package_version: str = "1.0"
    run_id: str = "run"
    adapter_name: str = "adapter"
    application_profile: str | None = None
    paths: list[Path] = field(default_factory=list)
    observed: list[str] = field(default_factory=list)
    resets: int = 0

    def observe_jarvis_stdout(self, text: str) -> list[dict[str, object]]:
        self.observed.append(text)
        return []

    def observe_stdout(self, text: str) -> list[dict[str, object]]:
        self.observed.append(text)
        return []

    def finalize_jarvis_stdout(self) -> list[dict[str, object]]:
        return []

    def finalize_stdout(self) -> list[dict[str, object]]:
        return []

    def reset_stdout(self) -> None:
        self.resets += 1

    def progress_log_paths(self) -> list[Path]:
        return self.paths

    def acceptance_progress_valid(self, metadata: dict[str, Any]) -> bool:
        return metadata.get("accepted") is True


def _binding(
    adapter: _Adapter,
    *,
    source: str = "jarvis_stdout_fallback",
    path: Path | None = None,
) -> progress.PackageProgressBinding:
    return progress.PackageProgressBinding(
        identity=progress.PackageProgressProviderIdentity(
            entry_point_name="adapter",
            entry_point_value="provider:factory",
            distribution_name="provider",
            distribution_version="1.0",
            adapter_name=adapter.adapter_name,
            package_name=adapter.package_name,
            package_version=adapter.package_version,
            application_profile=None,
        ),
        adapter=adapter,
        source_authority=source,
        log_path=path,
    )


def _record() -> dict[str, object]:
    return {
        "label": "iteration",
        "current": 1,
        "total": 2,
        "unit": "step",
        "message": "running",
        "metadata": {"accepted": True},
    }


def test_progress_output_delegates_text_stream_properties(tmp_path: Path) -> None:
    adapter = _Adapter()
    records: Queue[dict[str, object]] = Queue()
    path = tmp_path / "diagnostic.txt"
    with path.open("w", encoding="utf-8") as delegate:
        output = progress._ProgressOutput(delegate, _binding(adapter), records)
        assert output.isatty() is False
        assert output.fileno() == delegate.fileno()
        assert output.encoding == delegate.encoding


@pytest.mark.asyncio
async def test_execution_propagates_operation_failure_after_owned_wait() -> None:
    execution = progress.PackageProgressExecution(
        _binding(_Adapter()), execution_id="run", pipeline_id="pipeline"
    )

    def operation() -> None:
        raise ValueError("workload failed")

    async def reporter(_current: float, _total: float | None, _message: str) -> None:
        return None

    with pytest.raises(ValueError, match="workload failed"):
        await execution.run(operation, reporter)


@pytest.mark.asyncio
async def test_execution_reports_progress_error_even_when_operation_fails() -> None:
    class FinalizingAdapter(_Adapter):
        def finalize_jarvis_stdout(self) -> list[dict[str, object]]:
            raise RuntimeError("provider finalization failed")

    execution = progress.PackageProgressExecution(
        _binding(FinalizingAdapter()), execution_id="run", pipeline_id="pipeline"
    )

    def operation() -> None:
        raise ValueError("workload failed")

    async def reporter(_current: float, _total: float | None, _message: str) -> None:
        return None

    with pytest.raises(RuntimeError, match="provider finalization failed") as raised:
        await execution.run(operation, reporter)
    assert isinstance(raised.value.__cause__, ValueError)


@pytest.mark.asyncio
async def test_report_limits_fail_closed(monkeypatch: pytest.MonkeyPatch) -> None:
    execution = progress.PackageProgressExecution(
        _binding(_Adapter()), execution_id="run", pipeline_id="pipeline"
    )

    async def reporter(_current: float, _total: float | None, _message: str) -> None:
        return None

    monkeypatch.setattr(progress, "PACKAGE_PROGRESS_MAX_NOTIFICATIONS", 0)
    with pytest.raises(RuntimeError, match="maximum notification count"):
        await execution._report_record(_record(), reporter)

    execution = progress.PackageProgressExecution(
        _binding(_Adapter()), execution_id="run", pipeline_id="pipeline"
    )
    monkeypatch.setattr(progress, "PACKAGE_PROGRESS_MAX_NOTIFICATIONS", 10)
    monkeypatch.setattr(progress, "PACKAGE_PROGRESS_MAX_NOTIFICATION_BYTES", 1)
    with pytest.raises(RuntimeError, match="notification exceeded its byte limit"):
        await execution._report_record(_record(), reporter)

    execution = progress.PackageProgressExecution(
        _binding(_Adapter()), execution_id="run", pipeline_id="pipeline"
    )
    monkeypatch.setattr(progress, "PACKAGE_PROGRESS_MAX_NOTIFICATION_BYTES", 65_536)
    monkeypatch.setattr(progress, "PACKAGE_PROGRESS_MAX_TOTAL_BYTES", 1)
    with pytest.raises(RuntimeError, match="total byte limit"):
        await execution._report_record(_record(), reporter)


class _EntryPoints(list[Any]):
    def select(self, *, group: str) -> _EntryPoints:
        assert group == progress.PACKAGE_PROGRESS_ENTRYPOINT_GROUP
        return self


@dataclass
class _EntryPoint:
    name: str = "adapter"
    value: str = "provider:factory"
    factory: Any = None
    dist: Any = field(
        default_factory=lambda: SimpleNamespace(name="provider", version="1.0")
    )

    def load(self) -> Any:
        return self.factory


def _bind(monkeypatch: pytest.MonkeyPatch, entries: list[_EntryPoint]) -> Any:
    monkeypatch.setattr(progress, "entry_points", lambda: _EntryPoints(entries))
    return progress.bind_package_progress_provider(
        [{"pkg_type": "test.package", "config": {}}], execution_id="run"
    )


def test_provider_binding_handles_disabled_and_ambiguous_pipelines() -> None:
    assert (
        progress.bind_package_progress_provider(
            [
                {
                    "pkg_type": "one",
                    "config": {"progress": {"adapter": "none"}},
                }
            ],
            execution_id="run",
        )
        is None
    )
    with pytest.raises(RuntimeError, match="exactly one"):
        progress.bind_package_progress_provider(
            [
                {"pkg_type": "one", "config": {}},
                {
                    "pkg_type": "two",
                    "config": {"progress": {"adapter": "adapter"}},
                },
            ],
            execution_id="run",
        )


def test_provider_binding_rejects_invalid_entry_points(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    with pytest.raises(RuntimeError, match="not callable"):
        _bind(monkeypatch, [_EntryPoint(factory=object())])

    assert _bind(monkeypatch, [_EntryPoint(factory=lambda _package: None)]) is None

    with pytest.raises(RuntimeError, match="multiple"):
        _bind(
            monkeypatch,
            [
                _EntryPoint(name="a", factory=lambda _package: _Adapter()),
                _EntryPoint(name="b", factory=lambda _package: _Adapter()),
            ],
        )


def test_provider_binding_rejects_missing_declared_provider(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(progress, "entry_points", lambda: _EntryPoints())
    with pytest.raises(RuntimeError, match="is unavailable"):
        progress.bind_package_progress_provider(
            [
                {
                    "pkg_type": "test.package",
                    "config": {"progress": {"adapter": "missing"}},
                }
            ],
            execution_id="run",
        )


def test_provider_binding_validates_distribution_and_log_contract(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    missing_dist = _EntryPoint(factory=lambda _package: _Adapter(), dist=None)
    with pytest.raises(RuntimeError, match="no distribution identity"):
        _bind(monkeypatch, [missing_dist])

    with pytest.raises(RuntimeError, match="at most one log path"):
        _bind(
            monkeypatch,
            [
                _EntryPoint(
                    factory=lambda _package: _Adapter(
                        paths=[tmp_path / "one", tmp_path / "two"]
                    )
                )
            ],
        )


def test_package_declarations_and_adapter_names_are_strict() -> None:
    package = SimpleNamespace(pkg_type="test.package", config={"deploy_mode": "local"})
    assert progress._package_declaration(package, "cluster") == {
        "pkg_type": "test.package",
        "deploy_mode": "local",
        "effective_deploy_mode": "local",
    }
    assert (
        progress._package_declaration(
            SimpleNamespace(pkg_type="test.package", config={}), "cluster"
        )["effective_deploy_mode"]
        == "cluster"
    )
    assert progress._declared_adapter({"progress": "invalid"}) is None
    assert progress._declared_adapter({"progress": {}}) is None
    for invalid in ("", 42):
        with pytest.raises(RuntimeError, match="non-empty string"):
            progress._declared_adapter({"progress": {"adapter": invalid}})


def test_adapter_validation_rejects_identity_and_protocol_errors() -> None:
    with pytest.raises(RuntimeError, match="non-empty pkg_type"):
        progress._validate_adapter(_Adapter(), {})
    with pytest.raises(RuntimeError, match="identity mismatch"):
        progress._validate_adapter(_Adapter(), {"pkg_type": "different"})
    with pytest.raises(RuntimeError, match="adapter_name is invalid"):
        progress._validate_adapter(
            _Adapter(adapter_name=""), {"pkg_type": "test.package"}
        )
    broken = _Adapter()
    broken.observe_stdout = None  # type: ignore[method-assign]
    with pytest.raises(RuntimeError, match="lacks observe_stdout"):
        progress._validate_adapter(broken, {"pkg_type": "test.package"})


@pytest.mark.parametrize(
    ("record", "message"),
    [
        ({"extra": True}, "unsupported fields"),
        ({"current": True, "metadata": {}}, "current must be finite"),
        ({"current": 1, "total": "two", "metadata": {}}, "total must be finite"),
        ({"current": 1, "metadata": []}, "metadata must be an object"),
        (
            {"current": 1, "metadata": {"unsafe": object()}},
            "not JSON-safe",
        ),
        ({"current": 1, "label": "", "metadata": {}}, "label is invalid"),
        (
            {"current": 1, "message": "x" * 4097, "metadata": {}},
            "message is invalid",
        ),
    ],
)
def test_progress_records_reject_unbounded_or_unsafe_values(
    record: dict[str, object], message: str
) -> None:
    with pytest.raises(RuntimeError, match=message):
        progress._validated_record(record)


def test_log_polling_tracks_identity_rotation_and_bounded_reads(
    tmp_path: Path,
) -> None:
    path = tmp_path / "progress.log"
    path.write_text("old", encoding="utf-8")
    state = progress._baseline_log(path)
    assert state is not None
    assert state.offset == 3

    with path.open("a", encoding="utf-8") as stream:
        stream.write("-new")
    adapter = _Adapter(paths=[path])
    records: Queue[dict[str, object]] = Queue()
    assert (
        progress._poll_log(
            _binding(adapter, source="package_log", path=path), state, records
        )
        is False
    )
    assert adapter.observed == ["-new"]

    state.identity = (-1, -1)
    state.offset = 0
    assert (
        progress._poll_log(
            _binding(adapter, source="package_log", path=path), state, records
        )
        is False
    )
    assert adapter.resets == 1


def test_log_opening_rejects_nonregular_and_changed_files(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    assert progress._open_regular_log(tmp_path / "missing") is None
    with pytest.raises(RuntimeError, match="regular nonsymlink"):
        progress._open_regular_log(tmp_path)

    first = tmp_path / "first.log"
    second = tmp_path / "second.log"
    first.write_text("first", encoding="utf-8")
    second.write_text("second", encoding="utf-8")
    real_open = os.open
    monkeypatch.setattr(
        progress.os,
        "open",
        lambda _path, flags: real_open(second, flags),
    )
    with pytest.raises(RuntimeError, match="changed while opening"):
        progress._open_regular_log(first)


def test_queue_overflow_is_explicit() -> None:
    records: Queue[dict[str, object]] = Queue(maxsize=1)
    records.put_nowait({})
    with pytest.raises(RuntimeError, match="fixed limit"):
        progress._enqueue_records([{}], records)


def test_relative_log_paths_are_normalized(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(Path.cwd())
    normalized = progress._normalized_log_path(Path("logs/progress.txt"))
    assert normalized.is_absolute()
    assert normalized.name == "progress.txt"


def test_progress_output_uses_adapter_observer() -> None:
    adapter = _Adapter()
    delegate = io.StringIO()
    records: Queue[dict[str, object]] = Queue()
    output = progress._ProgressOutput(delegate, _binding(adapter), records)
    assert output.write("progress") == len("progress")
    output.flush()
    assert adapter.observed == ["progress"]
