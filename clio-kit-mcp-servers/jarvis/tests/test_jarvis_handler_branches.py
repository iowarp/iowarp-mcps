"""Focused production failure-path tests for the JARVIS handler boundary."""

from __future__ import annotations

import io
import os
import subprocess
import sys
from collections import deque
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from jarvis_mcp.capabilities import jarvis_handler as handler


def _process_result(
    stdout: bytes = b"",
    *,
    stderr: bytes = b"",
    returncode: int = 0,
    stdout_truncated: bool = False,
) -> handler._BoundedProcessResult:
    return handler._BoundedProcessResult(
        returncode=returncode,
        stdout=stdout,
        stderr=stderr,
        stdout_truncated=stdout_truncated,
    )


class _BrokenStream:
    def read(self, _size: int) -> bytes:
        raise OSError("read failed")


def test_bounded_capture_handles_errors_and_full_chunk_trimming(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    broken = handler._BoundedCapture(_BrokenStream())  # type: ignore[arg-type]
    broken.drain()
    assert isinstance(broken.error, OSError)

    monkeypatch.setattr(handler, "_MAX_SPACK_CAPTURE_BYTES", 3)
    capture = handler._BoundedCapture(io.BytesIO())
    capture.chunks = deque([b"ab", b"cdef"])
    capture.size = 6
    capture._trim()
    assert capture.raw() == b"def"

    capture = handler._BoundedCapture(io.BytesIO())
    capture.chunks = deque([b"abcdef"])
    capture.size = 6
    capture._trim()
    assert capture.raw() == b"def"


@pytest.mark.asyncio
async def test_pipeline_operation_uses_progress_execution(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    observed: dict[str, object] = {}

    class Execution:
        def __init__(self, binding: object, **kwargs: object) -> None:
            observed.update(binding=binding, **kwargs)

        async def run(self, operation: Any, reporter: Any) -> str:
            observed["reporter"] = reporter
            return operation()

    async def reporter(_current: float, _total: float | None, _message: str) -> None:
        return None

    binding = object()
    monkeypatch.setattr(handler, "PackageProgressExecution", Execution)
    result = await handler._run_pipeline_operation(
        lambda: "complete",
        progress_binding=binding,  # type: ignore[arg-type]
        progress_reporter=reporter,
        execution_id="execution",
        pipeline_id="pipeline",
    )
    assert result == "complete"
    assert observed == {
        "binding": binding,
        "execution_id": "execution",
        "pipeline_id": "pipeline",
        "reporter": reporter,
    }


def test_jsonable_recurses_through_nonserializable_lists() -> None:
    value = object()
    assert handler._jsonable([value]) == [repr(value)]


def test_spack_environment_rolls_back_failed_persistence(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    pipeline = SimpleNamespace(
        env={"OLD": "prior", "BAD": 42},
        env_path=tmp_path / "environment.yaml",
        last_loaded_file="pipeline.yaml",
    )
    monkeypatch.setattr(
        handler, "_capture_spack_environment", lambda _specs: {"BAD": "new"}
    )
    monkeypatch.setattr(handler, "_read_spack_environment_state", lambda _pipeline: {})
    with pytest.raises(RuntimeError, match="not a string"):
        handler._apply_spack_environment(pipeline, ["demo"])

    pipeline.env = {"OLD": "prior"}
    saves: list[dict[str, object]] = []
    monkeypatch.setattr(
        handler,
        "_capture_spack_environment",
        lambda _specs: {"NEW": "value"},
    )
    monkeypatch.setattr(
        handler, "_save_pipeline", lambda value: saves.append(dict(value.env))
    )
    monkeypatch.setattr(
        handler,
        "_write_spack_environment_state",
        lambda *args, **kwargs: (_ for _ in ()).throw(OSError("disk full")),
    )
    with pytest.raises(OSError, match="disk full"):
        handler._apply_spack_environment(pipeline, ["demo"])
    assert pipeline.env == {"OLD": "prior"}
    assert pipeline.last_loaded_file == "pipeline.yaml"
    assert saves[-1] == {"OLD": "prior"}


def test_read_spack_state_rejects_size_parse_schema_and_values(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    path = tmp_path / handler._SPACK_ENVIRONMENT_STATE_FILENAME
    pipeline = SimpleNamespace(env_path=tmp_path / "environment.yaml")
    path.write_text("{}", encoding="utf-8")
    monkeypatch.setattr(handler, "_MAX_SPACK_CAPTURE_BYTES", 1)
    with pytest.raises(RuntimeError, match="too large"):
        handler._read_spack_environment_state(pipeline)

    monkeypatch.setattr(handler, "_MAX_SPACK_CAPTURE_BYTES", 1024)
    path.write_text("{", encoding="utf-8")
    with pytest.raises(RuntimeError, match="could not read"):
        handler._read_spack_environment_state(pipeline)

    path.write_text('{"schema_version":"wrong"}', encoding="utf-8")
    with pytest.raises(RuntimeError, match="unsupported schema"):
        handler._read_spack_environment_state(pipeline)

    path.write_text(
        '{"schema_version":"jarvis.mcp.spack-environment.v1",'
        '"variable_names":["API_TOKEN"],"previous_values":{"API_TOKEN":null}}',
        encoding="utf-8",
    )
    with pytest.raises(RuntimeError, match="invalid variable names"):
        handler._read_spack_environment_state(pipeline)


def test_write_spack_state_and_path_require_bounded_persistent_storage(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    with pytest.raises(RuntimeError, match="persistent environment path"):
        handler._spack_environment_state_path(SimpleNamespace())

    pipeline = SimpleNamespace(env_path=tmp_path / "environment.yaml")
    monkeypatch.setattr(handler, "_MAX_SPACK_CAPTURE_BYTES", 1)
    with pytest.raises(RuntimeError, match="too large"):
        handler._write_spack_environment_state(
            pipeline,
            specs=["demo"],
            variable_names=["PATH"],
            previous_values={"PATH": None},
            environment_sha256="digest",
        )


@pytest.mark.parametrize(
    ("first", "message"),
    [
        (OSError("launch"), "could not resolve"),
        (_process_result(returncode=7, stderr=b"failed"), "spack load"),
        (_process_result(stdout_truncated=True), "exceeded"),
        (_process_result(stdout=b"\xff"), "not UTF-8"),
    ],
)
def test_capture_spack_environment_rejects_load_failures(
    monkeypatch: pytest.MonkeyPatch, first: object, message: str
) -> None:
    monkeypatch.setattr(handler, "_spack_executable", lambda: "spack")

    def run(*_args: object, **_kwargs: object) -> handler._BoundedProcessResult:
        if isinstance(first, BaseException):
            raise first
        return first  # type: ignore[return-value]

    monkeypatch.setattr(handler, "_run_bounded_process", run)
    with pytest.raises(RuntimeError, match=message):
        handler._capture_spack_environment(["demo"])


def _capture_with_second_result(
    monkeypatch: pytest.MonkeyPatch,
    second: object,
) -> dict[str, str]:
    for name in ("NEW", "ONE", "TWO"):
        monkeypatch.delenv(name, raising=False)
    results: list[object] = [_process_result(b"export NEW=value"), second]
    monkeypatch.setattr(handler, "_spack_executable", lambda: "spack")

    def run(*_args: object, **_kwargs: object) -> handler._BoundedProcessResult:
        value = results.pop(0)
        if isinstance(value, BaseException):
            raise value
        return value  # type: ignore[return-value]

    monkeypatch.setattr(handler, "_run_bounded_process", run)
    return handler._capture_spack_environment(["demo"])


@pytest.mark.parametrize(
    ("second", "message"),
    [
        (OSError("bash"), "could not materialize"),
        (_process_result(returncode=4, stderr=b"bad script"), "script failed"),
        (_process_result(stdout_truncated=True), "exceeded"),
        (_process_result(stdout=b"missing marker"), "integrity marker"),
        (
            _process_result(stdout=handler._SPACK_ENVIRONMENT_MARKER + b"NEW=\xff\0"),
            "not UTF-8",
        ),
    ],
)
def test_capture_spack_environment_rejects_materialization_failures(
    monkeypatch: pytest.MonkeyPatch, second: object, message: str
) -> None:
    with pytest.raises(RuntimeError, match=message):
        _capture_with_second_result(monkeypatch, second)


def test_capture_spack_environment_enforces_value_variable_and_total_limits(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(handler, "_MAX_ENVIRONMENT_VALUE_BYTES", 1)
    with pytest.raises(RuntimeError, match="value is too large"):
        _capture_with_second_result(
            monkeypatch,
            _process_result(stdout=handler._SPACK_ENVIRONMENT_MARKER + b"NEW=xx\0"),
        )

    monkeypatch.setattr(handler, "_MAX_ENVIRONMENT_VALUE_BYTES", 10)
    monkeypatch.setattr(handler, "_MAX_ENVIRONMENT_VARIABLES", 1)
    with pytest.raises(RuntimeError, match="too many variables"):
        _capture_with_second_result(
            monkeypatch,
            _process_result(
                stdout=handler._SPACK_ENVIRONMENT_MARKER + b"ONE=1\0TWO=2\0"
            ),
        )

    monkeypatch.setattr(handler, "_MAX_ENVIRONMENT_VARIABLES", 10)
    monkeypatch.setattr(handler, "_MAX_SPACK_CAPTURE_BYTES", 1)
    with pytest.raises(RuntimeError, match="serialized"):
        _capture_with_second_result(
            monkeypatch,
            _process_result(stdout=handler._SPACK_ENVIRONMENT_MARKER + b"NEW=value\0"),
        )


def test_bounded_process_accepts_stdin_and_rejects_large_input(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    result = handler._run_bounded_process(
        [
            sys.executable,
            "-c",
            "import sys; sys.stdout.buffer.write(sys.stdin.buffer.read())",
        ],
        env=os.environ.copy(),
        timeout_seconds=10,
        stdin_payload=b"payload",
    )
    assert result.stdout == b"payload"

    monkeypatch.setattr(handler, "_MAX_SPACK_CAPTURE_BYTES", 1)
    with pytest.raises(ValueError, match="input exceeded"):
        handler._run_bounded_process(
            ["unused"], env={}, timeout_seconds=1, stdin_payload=b"x" * 66
        )


def test_bounded_process_closes_input_when_launch_fails(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    stream = io.BytesIO()
    monkeypatch.setattr(handler.tempfile, "TemporaryFile", lambda **_kwargs: stream)
    monkeypatch.setattr(
        handler.subprocess,
        "Popen",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(OSError("launch")),
    )
    with pytest.raises(OSError, match="launch"):
        handler._run_bounded_process(
            ["spack"], env={}, timeout_seconds=1, stdin_payload=b"input"
        )
    assert stream.closed


def test_bounded_process_surfaces_stream_read_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    process = SimpleNamespace(
        stdout=_BrokenStream(),
        stderr=io.BytesIO(),
        returncode=0,
        wait=lambda timeout: 0,
    )
    monkeypatch.setattr(handler.subprocess, "Popen", lambda *args, **kwargs: process)
    with pytest.raises(RuntimeError, match="stream read failed"):
        handler._run_bounded_process(["spack"], env={}, timeout_seconds=1)


class _Thread:
    def __init__(self, *, alive: bool) -> None:
        self.alive = alive

    def join(self, timeout: float) -> None:
        assert timeout > 0

    def is_alive(self) -> bool:
        return self.alive


def test_finish_spack_captures_closes_inherited_pipes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    process = SimpleNamespace(stdout=io.BytesIO(), stderr=io.BytesIO())
    thread = _Thread(alive=True)

    def terminate(_process: object, *, include_exited_group: bool = False) -> None:
        assert include_exited_group is True
        thread.alive = False

    monkeypatch.setattr(handler, "_terminate_spack_process_tree", terminate)
    handler._finish_spack_captures(process, [thread])  # type: ignore[arg-type]
    assert process.stdout.closed and process.stderr.closed

    thread = _Thread(alive=True)
    monkeypatch.setattr(
        handler, "_terminate_spack_process_tree", lambda *args, **kwargs: None
    )
    with pytest.raises(RuntimeError, match="pipes did not close"):
        handler._finish_spack_captures(process, [thread])  # type: ignore[arg-type]


def test_spack_diagnostic_and_executable_resolution(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setattr(handler, "_MAX_SPACK_DIAGNOSTIC_BYTES", 4)
    assert handler._bounded_spack_diagnostic(b"abcdef") == "[tail truncated]\ncdef"

    command = tmp_path / "spack"
    command.write_text("", encoding="utf-8")
    monkeypatch.setenv("JARVIS_MCP_SPACK_COMMAND", str(command))
    assert handler._spack_executable() == str(command)
    monkeypatch.setenv("JARVIS_MCP_SPACK_COMMAND", str(tmp_path / "missing"))
    with pytest.raises(RuntimeError, match="does not exist"):
        handler._spack_executable()

    monkeypatch.delenv("JARVIS_MCP_SPACK_COMMAND")
    monkeypatch.setattr(handler.shutil, "which", lambda _name: "/usr/bin/spack")
    assert handler._spack_executable() == "/usr/bin/spack"

    monkeypatch.setattr(handler.shutil, "which", lambda _name: None)
    root = tmp_path / "root"
    rooted = root / "bin" / "spack"
    rooted.parent.mkdir(parents=True)
    rooted.write_text("", encoding="utf-8")
    monkeypatch.setenv("SPACK_ROOT", str(root))
    assert handler._spack_executable() == str(rooted)

    monkeypatch.delenv("SPACK_ROOT")
    monkeypatch.setattr(Path, "home", lambda: tmp_path / "home")
    monkeypatch.setattr(Path, "is_file", lambda _path: False)
    with pytest.raises(RuntimeError, match="was not found"):
        handler._spack_executable()


def test_terminate_spack_tree_windows_fallbacks(
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
    monkeypatch.setattr(handler.os, "name", "nt")
    monkeypatch.setattr(
        handler.subprocess,
        "run",
        lambda *args, **kwargs: (_ for _ in ()).throw(OSError("no taskkill")),
    )
    handler._terminate_spack_process_tree(process)  # type: ignore[arg-type]
    assert process.terminated is True
    assert process.killed is True


def test_terminate_spack_tree_posix_handles_exit_lookup_and_escalation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    exited = SimpleNamespace(poll=lambda: 0)
    monkeypatch.setattr(handler.os, "name", "posix")
    handler._terminate_spack_process_tree(exited)  # type: ignore[arg-type]

    monkeypatch.setitem(
        handler.os.__dict__,
        "killpg",
        lambda _pid, _signal: (_ for _ in ()).throw(ProcessLookupError()),
    )
    handler._terminate_spack_process_tree(SimpleNamespace(pid=42, poll=lambda: None))  # type: ignore[arg-type]

    signals: list[int] = []
    polls = iter([0, 0])
    monkeypatch.setitem(
        handler.os.__dict__, "killpg", lambda _pid, sig: signals.append(sig)
    )
    handler._terminate_spack_process_tree(
        SimpleNamespace(pid=42, poll=lambda: next(polls)),
        include_exited_group=True,
    )  # type: ignore[arg-type]
    assert signals == [handler.signal.SIGTERM, getattr(handler.signal, "SIGKILL", 9)]

    class RunningProcess:
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

    signals.clear()
    handler._terminate_spack_process_tree(RunningProcess())  # type: ignore[arg-type]
    assert signals == [handler.signal.SIGTERM, getattr(handler.signal, "SIGKILL", 9)]


@pytest.mark.parametrize("specs", [[], ["demo"] * 33])
def test_spack_spec_collection_size_is_bounded(specs: list[str]) -> None:
    with pytest.raises(ValueError, match="between 1 and"):
        handler._validate_spack_specs(specs)


@pytest.mark.parametrize("spec", ["", "x" * 1025, "demo\ninvalid"])
def test_each_spack_spec_is_strictly_validated(spec: str) -> None:
    with pytest.raises(ValueError):
        handler._validate_spack_specs([spec])


def test_runtime_environment_name_filters_invalid_and_transient_names() -> None:
    assert handler._safe_runtime_environment_name("INVALID-NAME") is False
    assert handler._safe_runtime_environment_name("BASH_FUNC_demo") is False
    assert handler._safe_runtime_environment_name("ACCESS_TOKEN") is False
    assert handler._safe_runtime_environment_name("SPACK_ROOT") is True


def _submission(**overrides: object) -> dict[str, object]:
    document: dict[str, object] = {
        "schema_version": "jarvis.scheduler.submission.v1",
        "provider": "slurm",
        "script_path": "/tmp/job.sh",
        "scheduler_job_id": "42",
        "submitted": True,
        "identity_source": "scheduler_submit_api",
        "state": "submitted",
        "wait": False,
        "terminal": False,
    }
    document.update(overrides)
    return document


@pytest.mark.parametrize(
    ("value", "message"),
    [
        ("invalid", "invalid scheduler submission"),
        (_submission(schema_version="wrong"), "schema is unsupported"),
        (_submission(provider="pbs"), "provider did not match"),
        (_submission(script_path="other"), "did not match this script"),
        (
            _submission(submitted=False),
            "provider-owned scheduler job identity",
        ),
        (_submission(scheduler_job_id="not-a-number"), "invalid SLURM job identity"),
    ],
)
def test_scheduler_submission_metadata_rejects_forged_records(
    value: object, message: str
) -> None:
    pipeline = SimpleNamespace(last_submission=value)
    with pytest.raises(RuntimeError, match=message):
        handler._scheduler_submission_metadata(
            pipeline,
            scheduler={"name": "slurm"},
            script_path="/tmp/job.sh",
            require_identity=True,
        )


def test_scheduler_submission_metadata_handles_script_only_contract() -> None:
    assert (
        handler._scheduler_submission_metadata(
            SimpleNamespace(last_submission=None),
            scheduler={"name": "slurm"},
            script_path="/tmp/job.sh",
            require_identity=False,
        )
        is None
    )
    script = _submission(
        scheduler_job_id=None,
        submitted=False,
        identity_source=None,
    )
    assert (
        handler._scheduler_submission_metadata(
            SimpleNamespace(last_submission=script),
            scheduler={"name": "slurm"},
            script_path="/tmp/job.sh",
            require_identity=False,
        )
        == script
    )
    with pytest.raises(RuntimeError, match="script-only"):
        handler._scheduler_submission_metadata(
            SimpleNamespace(last_submission=_submission()),
            scheduler={"name": "slurm"},
            script_path="/tmp/job.sh",
            require_identity=False,
        )
    with pytest.raises(RuntimeError, match="provider-owned"):
        handler._scheduler_submission_metadata(
            SimpleNamespace(last_submission=script),
            scheduler={"name": "slurm"},
            script_path="/tmp/job.sh",
            require_identity=True,
        )


def test_waited_failure_metadata_rejects_stale_or_nonworkload_records() -> None:
    pipeline = SimpleNamespace(last_submission=_submission())
    assert (
        handler._waited_workload_failure_metadata(
            pipeline,
            scheduler={"name": "slurm"},
            prior_submission={},
            submit=False,
            wait=True,
        )
        is None
    )
    assert (
        handler._waited_workload_failure_metadata(
            pipeline,
            scheduler={"name": "slurm"},
            prior_submission=handler._jsonable(pipeline.last_submission),
            submit=True,
            wait=True,
        )
        is None
    )
    pipeline.last_submission = _submission(script_path=None)
    assert (
        handler._waited_workload_failure_metadata(
            pipeline,
            scheduler={"name": "slurm"},
            prior_submission={},
            submit=True,
            wait=True,
        )
        is None
    )
    pipeline.last_submission = _submission(state="completed", terminal_returncode=0)
    assert (
        handler._waited_workload_failure_metadata(
            pipeline,
            scheduler={"name": "slurm"},
            prior_submission={},
            submit=True,
            wait=True,
        )
        is None
    )


def test_waited_failure_metadata_rejects_invalid_or_absent_provider_document(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    pipeline = SimpleNamespace(last_submission=_submission())
    monkeypatch.setattr(
        handler,
        "_scheduler_submission_metadata",
        lambda *args, **kwargs: (_ for _ in ()).throw(RuntimeError("invalid")),
    )
    assert (
        handler._waited_workload_failure_metadata(
            pipeline,
            scheduler={"name": "slurm"},
            prior_submission={},
            submit=True,
            wait=True,
        )
        is None
    )
    monkeypatch.setattr(
        handler, "_scheduler_submission_metadata", lambda *args, **kwargs: None
    )
    assert (
        handler._waited_workload_failure_metadata(
            pipeline,
            scheduler={"name": "slurm"},
            prior_submission={},
            submit=True,
            wait=True,
        )
        is None
    )
