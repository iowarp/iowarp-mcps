"""Focused production failure-path tests for the JARVIS handler boundary."""

from __future__ import annotations

import asyncio
import builtins
import io
import json
import multiprocessing
import os
import subprocess
import sys
import time
from collections import deque
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from jarvis_mcp.capabilities import jarvis_handler as handler


def _hold_pipeline_lock_process(
    lock_dir: str,
    ready: Any,
    release: Any,
) -> None:
    """Hold one real cross-process pipeline lock until the parent releases it."""
    os.environ["JARVIS_MCP_LOCK_DIR"] = lock_dir

    async def hold() -> None:
        async with handler._pipeline_operation_lock("Shared-Pipeline"):
            ready.set()
            while not release.is_set():
                await asyncio.sleep(0.02)

    asyncio.run(hold())


def _os_exit_during_two_yaml_save(root: str) -> None:
    """Create a real pending transaction and die before environment.yaml replace."""
    from types import SimpleNamespace
    from unittest.mock import patch

    from jarvis_cd.core import pipeline as pipeline_module
    from jarvis_cd.core.pipeline import Pipeline

    root_path = Path(root)
    jarvis = SimpleNamespace(
        hostfile=None,
        get_pipeline_dir=lambda name: root_path / "config" / "pipelines" / name,
        get_pipeline_shared_dir=lambda name: root_path / "shared" / name,
        get_pipeline_private_dir=lambda name: root_path / "private" / name,
        set_current_pipeline=lambda _name: None,
    )
    with patch("jarvis_cd.core.pipeline.Jarvis.get_instance", return_value=jarvis):
        pipeline = Pipeline()
    pipeline.create("os-exit-transaction")
    pipeline.env = {"PATH": "/site/bin", "SITE": "kept"}
    pipeline.last_loaded_file = "source.yaml"
    pipeline.save()

    atomic_dump = getattr(pipeline_module, "_atomic_yaml_dump", None)
    if callable(atomic_dump):

        def crash_before_atomic_environment(path: Path, value: object) -> None:
            pending = handler._spack_environment_transaction_path(pipeline)
            if path.name == "environment.yaml" and pending.exists():
                os._exit(97)
            atomic_dump(path, value)

        setattr(
            pipeline_module,
            "_atomic_yaml_dump",
            crash_before_atomic_environment,
        )
    else:
        real_open = builtins.open

        def crash_before_legacy_environment(
            path: object, mode: str = "r", *args: Any, **kwargs: Any
        ) -> Any:
            pending = handler._spack_environment_transaction_path(pipeline)
            if (
                str(path).endswith("environment.yaml")
                and "w" in mode
                and pending.exists()
            ):
                os._exit(97)
            return real_open(path, mode, *args, **kwargs)

        builtins.open = crash_before_legacy_environment
    handler._capture_spack_environment = lambda _specs: {
        "PATH": "/spack/new/bin",
        "SPACK_ROOT": "/opt/spack",
    }
    handler._apply_spack_environment(pipeline, ["demo@1"])


def _real_pipeline(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Any:
    """Create a real JARVIS Pipeline with every durable path under tmp_path."""
    from jarvis_cd.core.pipeline import Pipeline

    jarvis = SimpleNamespace(
        hostfile=None,
        get_pipeline_dir=lambda name: tmp_path / "config" / "pipelines" / name,
        get_pipeline_shared_dir=lambda name: tmp_path / "shared" / name,
        get_pipeline_private_dir=lambda name: tmp_path / "private" / name,
        set_current_pipeline=lambda _name: None,
    )
    monkeypatch.setattr("jarvis_cd.core.pipeline.Jarvis.get_instance", lambda: jarvis)
    pipeline = Pipeline()
    pipeline.create("transaction-test")
    pipeline.env = {"PATH": "/site/bin", "SITE": "kept"}
    pipeline.last_loaded_file = "/operator/source.yaml"
    pipeline.save()
    return pipeline


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


@pytest.mark.parametrize(
    "pipeline_id",
    [
        "",
        ".",
        "..",
        "name.",
        "CON",
        "con.txt",
        "LPT9.pipeline",
        "../escape",
        "/absolute",
        "name/child",
        "a" * 129,
    ],
)
def test_pipeline_identifiers_are_bounded_and_root_safe(pipeline_id: str) -> None:
    """Agent-controlled names cannot escape JARVIS pipeline roots."""
    with pytest.raises(ValueError, match="pipeline_id"):
        handler._validate_pipeline_id(pipeline_id)
    assert handler._validate_pipeline_id("valid-pipeline_1.0") == "valid-pipeline_1.0"


def test_pipeline_lock_keys_serialize_case_aliases(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Case aliases map to one lock even on a case-sensitive filesystem."""
    monkeypatch.setenv("JARVIS_MCP_LOCK_DIR", str(tmp_path / "locks"))
    assert handler._pipeline_lock_path("Pipeline") == handler._pipeline_lock_path(
        "pipeline"
    )


def test_runtime_environment_requires_explicit_nonsecret_allowlist(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Credential-shaped and arbitrary variables are never persisted by default."""
    for name in ("AWS_ACCESS_KEY_ID", "GITHUB_PAT", "DATABASE_URL", "API_TOKEN"):
        assert handler._safe_runtime_environment_name(name) is False
    monkeypatch.setenv(
        "JARVIS_MCP_SPACK_ENV_ALLOWLIST",
        "AWS_ACCESS_KEY_ID,GITHUB_PAT,DATABASE_URL,API_TOKEN",
    )
    with pytest.raises(RuntimeError, match="invalid Spack environment allowlist"):
        handler._runtime_environment_allowlist()
    monkeypatch.delenv("JARVIS_MCP_SPACK_ENV_ALLOWLIST")
    assert handler._safe_runtime_environment_name("PATH") is True
    monkeypatch.setenv("JARVIS_MCP_SPACK_ENV_ALLOWLIST", "HDF5_ROOT")
    assert handler._safe_runtime_environment_name("HDF5_ROOT") is True


def test_no_spack_request_returns_explicit_provenance(tmp_path: Path) -> None:
    """Absence of a request and sidecar is machine-readable, never null."""
    pipeline = SimpleNamespace(
        env={},
        env_path=tmp_path / "environment.yaml",
        last_loaded_file=None,
    )

    metadata = handler._apply_spack_environment(pipeline, [])

    assert metadata == {
        "specs": [],
        "variable_names": [],
        "variable_count": 0,
        "environment_sha256": None,
        "persisted": False,
        "scheduler_reload": "execution_snapshot",
        "transaction_id": None,
        "disposition": "not_requested",
    }


def test_no_spec_reuse_rejects_stale_pipeline_yaml_environment(tmp_path: Path) -> None:
    """A committed sidecar cannot bless YAML state with a different digest."""
    pipeline = SimpleNamespace(
        env={"PATH": "/stale/bin"},
        env_path=tmp_path / "environment.yaml",
        last_loaded_file=None,
    )
    serialized = json.dumps(
        {"PATH": "/committed/bin"}, separators=(",", ":"), sort_keys=True
    ).encode("utf-8")
    handler._write_spack_environment_state(
        pipeline,
        specs=["demo"],
        variable_names=["PATH"],
        previous_values={"PATH": None},
        environment_sha256=handler.hashlib.sha256(serialized).hexdigest(),
        transaction_id="a" * 32,
    )

    with pytest.raises(RuntimeError, match="does not match pipeline YAML"):
        handler._apply_spack_environment(pipeline, [])


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


def test_spack_environment_transaction_rolls_back_interrupted_pipeline_save(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    pipeline = SimpleNamespace(
        env={"PATH": "/spack/new/bin", "NEW_SPEC_ONLY": "new", "SITE": "kept"},
        env_path=tmp_path / "environment.yaml",
        last_loaded_file=None,
    )
    transaction_id = "a" * 32
    digest = "b" * 64
    handler._write_spack_environment_transaction(
        pipeline,
        transaction_id=transaction_id,
        rollback_values={"PATH": "/spack/old/bin", "NEW_SPEC_ONLY": None},
        prior_source="source.yaml",
        environment_sha256=digest,
    )
    saves: list[dict[str, object]] = []
    monkeypatch.setattr(
        handler,
        "_save_pipeline",
        lambda value: saves.append(
            {
                "env": dict(value.env),
                "last_loaded_file": value.last_loaded_file,
            }
        ),
    )

    metadata = handler._apply_spack_environment(pipeline, [])
    assert metadata is not None
    assert metadata["disposition"] == "recovered_rolled_back"

    assert pipeline.env == {"PATH": "/spack/old/bin", "SITE": "kept"}
    assert pipeline.last_loaded_file == "source.yaml"
    assert saves == [
        {
            "env": {"PATH": "/spack/old/bin", "SITE": "kept"},
            "last_loaded_file": "source.yaml",
        }
    ]
    assert not handler._spack_environment_transaction_path(pipeline).exists()


def test_spack_environment_transaction_keeps_durably_committed_update(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    pipeline = SimpleNamespace(
        env={"PATH": "/spack/new/bin", "SITE": "kept"},
        env_path=tmp_path / "environment.yaml",
        last_loaded_file=None,
    )
    transaction_id = "c" * 32
    digest = handler.hashlib.sha256(b'{"PATH":"/spack/new/bin"}').hexdigest()
    handler._write_spack_environment_transaction(
        pipeline,
        transaction_id=transaction_id,
        rollback_values={"PATH": "/spack/old/bin"},
        prior_source="source.yaml",
        environment_sha256=digest,
    )
    handler._write_spack_environment_state(
        pipeline,
        specs=["lammps"],
        variable_names=["PATH"],
        previous_values={"PATH": "/spack/old/bin"},
        environment_sha256=digest,
        transaction_id=transaction_id,
    )
    monkeypatch.setattr(
        handler,
        "_save_pipeline",
        lambda _pipeline: pytest.fail("committed transaction must not roll back"),
    )

    handler._recover_spack_environment_transaction(pipeline)

    assert pipeline.env == {"PATH": "/spack/new/bin", "SITE": "kept"}
    assert pipeline.last_loaded_file is None
    assert not handler._spack_environment_transaction_path(pipeline).exists()


def test_real_two_yaml_transaction_recovers_every_pipeline_save_boundary(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """A crash between pipeline.yaml and environment.yaml restores both files."""
    import jarvis_cd.core.pipeline as pipeline_module
    from jarvis_cd.core.pipeline import Pipeline

    pipeline = _real_pipeline(monkeypatch, tmp_path)
    failed = False
    atomic_dump = getattr(pipeline_module, "_atomic_yaml_dump", None)
    if callable(atomic_dump):

        def interrupt_atomic_environment(path: Path, value: Any) -> None:
            nonlocal failed
            if path.name == "environment.yaml" and not failed:
                failed = True
                raise OSError("simulated environment.yaml crash")
            atomic_dump(path, value)

        monkeypatch.setattr(
            pipeline_module,
            "_atomic_yaml_dump",
            interrupt_atomic_environment,
        )
    else:
        real_open = builtins.open

        def interrupt_environment(
            path: object, mode: str = "r", *args: Any, **kwargs: Any
        ) -> Any:
            nonlocal failed
            if str(path).endswith("environment.yaml") and "w" in mode and not failed:
                failed = True
                raise OSError("simulated environment.yaml crash")
            return real_open(path, mode, *args, **kwargs)

        monkeypatch.setattr(builtins, "open", interrupt_environment)
    monkeypatch.setattr(
        handler,
        "_capture_spack_environment",
        lambda _specs: {"PATH": "/spack/new/bin", "SPACK_ROOT": "/opt/spack"},
    )

    with pytest.raises(OSError, match="environment.yaml crash"):
        handler._apply_spack_environment(pipeline, ["demo"])
    assert failed is True

    reloaded = Pipeline("transaction-test")
    assert reloaded.env == {"PATH": "/site/bin", "SITE": "kept"}
    assert reloaded.last_loaded_file == "/operator/source.yaml"
    assert not handler._spack_environment_transaction_path(reloaded).exists()
    assert not handler._spack_environment_state_path(reloaded).exists()


def test_os_exit_between_two_yaml_documents_recovers_after_restart(
    tmp_path: Path,
) -> None:
    """A real process death between YAML replacements is recovered on restart."""
    from unittest.mock import patch

    from jarvis_cd.core.pipeline import Pipeline

    context = multiprocessing.get_context("spawn")
    process = context.Process(
        target=_os_exit_during_two_yaml_save,
        args=(str(tmp_path),),
    )
    process.start()
    process.join(20)
    if process.is_alive():
        process.terminate()
        process.join(5)
        pytest.fail("crash-injection child did not terminate")
    assert process.exitcode == 97

    jarvis = SimpleNamespace(
        hostfile=None,
        get_pipeline_dir=lambda name: tmp_path / "config" / "pipelines" / name,
        get_pipeline_shared_dir=lambda name: tmp_path / "shared" / name,
        get_pipeline_private_dir=lambda name: tmp_path / "private" / name,
        set_current_pipeline=lambda _name: None,
    )
    with patch("jarvis_cd.core.pipeline.Jarvis.get_instance", return_value=jarvis):
        reloaded = Pipeline("os-exit-transaction")

    metadata = handler._apply_spack_environment(reloaded, [])

    assert metadata["disposition"] == "recovered_rolled_back"
    assert reloaded.env == {"PATH": "/site/bin", "SITE": "kept"}
    assert reloaded.last_loaded_file == "source.yaml"
    assert not handler._spack_environment_transaction_path(reloaded).exists()


def test_state_directory_fsync_failure_forces_durable_rollback(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """A visible but non-durable state replacement never clears the WAL as committed."""
    from jarvis_cd.core.pipeline import Pipeline

    pipeline = _real_pipeline(monkeypatch, tmp_path)
    monkeypatch.setattr(
        handler,
        "_capture_spack_environment",
        lambda _specs: {"PATH": "/spack/new/bin", "SPACK_ROOT": "/opt/spack"},
    )
    real_fsync = handler._fsync_spack_directory
    calls = 0

    def fail_state_fsync(path: Path) -> None:
        nonlocal calls
        calls += 1
        if calls == 2:
            raise OSError("simulated state directory fsync failure")
        real_fsync(path)

    monkeypatch.setattr(handler, "_fsync_spack_directory", fail_state_fsync)
    with pytest.raises(handler._SpackDocumentDurabilityError):
        handler._apply_spack_environment(pipeline, ["demo"])

    reloaded = Pipeline("transaction-test")
    assert reloaded.env == {"PATH": "/site/bin", "SITE": "kept"}
    assert reloaded.last_loaded_file == "/operator/source.yaml"
    assert not handler._spack_environment_transaction_path(reloaded).exists()


@pytest.mark.parametrize("failure_boundary", [1, 2, 3])
def test_wal_clear_fsync_boundaries_preserve_recoverable_evidence(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    failure_boundary: int,
) -> None:
    """Every clear-phase fsync fault restores or leaves deterministic evidence."""
    pipeline = SimpleNamespace(env_path=tmp_path / "environment.yaml")
    handler._write_spack_environment_transaction(
        pipeline,
        transaction_id="d" * 32,
        rollback_values={"PATH": "/site/bin"},
        prior_source="source.yaml",
        environment_sha256="e" * 64,
    )
    pending = handler._read_spack_environment_transaction_document(pipeline)
    assert pending is not None
    real_fsync = handler._fsync_spack_directory
    calls = 0

    def fail_one_boundary(path: Path) -> None:
        nonlocal calls
        calls += 1
        if calls == failure_boundary:
            raise OSError(f"simulated clear fsync failure {failure_boundary}")
        real_fsync(path)

    monkeypatch.setattr(handler, "_fsync_spack_directory", fail_one_boundary)
    with pytest.raises(handler._SpackDocumentDurabilityError):
        handler._clear_spack_environment_transaction(pipeline, expected=pending)

    transaction_path = handler._spack_environment_transaction_path(pipeline)
    cleared_path = transaction_path.with_name(f".{transaction_path.name}.cleared")
    if failure_boundary < 3:
        assert transaction_path.is_file()
    else:
        assert not transaction_path.exists()
        assert cleared_path.is_file()

    monkeypatch.setattr(handler, "_fsync_spack_directory", real_fsync)
    recovered = handler._read_spack_environment_transaction_document(pipeline)
    if failure_boundary < 3:
        assert recovered is not None
    else:
        assert recovered is None
        assert not cleared_path.exists()


def test_retry_without_specs_finishes_committed_transaction_with_provenance(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """A crash after commit is reconciled without recapture and reports exact state."""
    from jarvis_cd.core.pipeline import Pipeline

    pipeline = _real_pipeline(monkeypatch, tmp_path)
    monkeypatch.setattr(
        handler,
        "_capture_spack_environment",
        lambda _specs: {"PATH": "/spack/new/bin", "SPACK_ROOT": "/opt/spack"},
    )
    real_clear = handler._clear_spack_environment_transaction
    calls = 0

    def crash_before_clear(*args: object, **kwargs: object) -> None:
        nonlocal calls
        calls += 1
        if calls == 1:
            raise KeyboardInterrupt("simulated process death")
        real_clear(*args, **kwargs)

    monkeypatch.setattr(
        handler, "_clear_spack_environment_transaction", crash_before_clear
    )
    with pytest.raises(KeyboardInterrupt, match="process death"):
        handler._apply_spack_environment(pipeline, ["demo@1"])

    reloaded = Pipeline("transaction-test")
    metadata = handler._apply_spack_environment(reloaded, [])
    assert metadata is not None
    assert metadata["disposition"] == "recovered_committed"
    assert metadata["specs"] == ["demo@1"]
    assert metadata["variable_names"] == ["PATH", "SPACK_ROOT"]
    assert isinstance(metadata["environment_sha256"], str)
    assert not handler._spack_environment_transaction_path(reloaded).exists()


def test_secure_sidecars_reject_links_fifos_and_replacement(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Sidecar readers never follow links or block on non-regular files."""
    pipeline = SimpleNamespace(env_path=tmp_path / "environment.yaml")
    target = tmp_path / "target.json"
    target.write_text("{}", encoding="utf-8")
    if os.name != "nt":
        target.chmod(0o600)
    state_path = handler._spack_environment_state_path(pipeline)
    try:
        state_path.symlink_to(target)
    except OSError:
        assert os.name == "nt"
    else:
        with pytest.raises(RuntimeError, match="could not open|regular file"):
            handler._read_spack_environment_state_document(pipeline)
        state_path.unlink()

    if hasattr(os, "mkfifo"):
        os.mkfifo(state_path)
        with pytest.raises(RuntimeError, match="regular file"):
            handler._read_spack_environment_state_document(pipeline)
        state_path.unlink()
    else:
        assert os.name == "nt"

    transaction_id = "e" * 32
    handler._write_spack_environment_transaction(
        pipeline,
        transaction_id=transaction_id,
        rollback_values={"PATH": "/site/bin"},
        prior_source=None,
        environment_sha256="f" * 64,
    )
    pinned = handler._read_spack_environment_transaction_document(pipeline)
    assert pinned is not None
    replacement = tmp_path / "replacement.json"
    replacement.write_text(json.dumps(pinned.payload), encoding="utf-8")
    if os.name != "nt":
        replacement.chmod(0o600)
    os.replace(replacement, handler._spack_environment_transaction_path(pipeline))
    with pytest.raises(RuntimeError, match="changed before removal"):
        handler._clear_spack_environment_transaction(pipeline, expected=pinned)
    assert handler._spack_environment_transaction_path(pipeline).is_file()


@pytest.mark.asyncio
async def test_pipeline_lock_serializes_across_processes(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """A second process cannot enter even through a case alias."""
    lock_dir = tmp_path / "locks"
    monkeypatch.setenv("JARVIS_MCP_LOCK_DIR", str(lock_dir))
    context = multiprocessing.get_context("spawn")
    ready = context.Event()
    release = context.Event()
    process = context.Process(
        target=_hold_pipeline_lock_process,
        args=(str(lock_dir), ready, release),
    )
    process.start()
    try:
        assert await asyncio.to_thread(ready.wait, 10)
        monkeypatch.setattr(handler, "_PIPELINE_LOCK_TIMEOUT_SECONDS", 0.2)
        with pytest.raises(RuntimeError, match="pipeline is busy"):
            async with handler._pipeline_operation_lock("shared-pipeline"):
                pytest.fail("second process acquired a held pipeline lock")
    finally:
        release.set()
        await asyncio.to_thread(process.join, 10)
        if process.is_alive():
            process.terminate()
            process.join(5)
    assert process.exitcode == 0


def test_read_spack_state_rejects_size_parse_schema_and_values(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    path = tmp_path / handler._SPACK_ENVIRONMENT_STATE_FILENAME
    pipeline = SimpleNamespace(env_path=tmp_path / "environment.yaml")
    path.write_text("{}", encoding="utf-8")
    path.chmod(0o600)
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
        '"specs":["demo"],"environment_sha256":"'
        + "a"
        * 64
        + '","variable_names":["API_TOKEN"],'
        '"previous_values":{"API_TOKEN":null}}',
        encoding="utf-8",
    )
    with pytest.raises(RuntimeError, match="invalid variable names"):
        handler._read_spack_environment_state(pipeline)


def test_write_spack_state_and_path_require_bounded_persistent_storage(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    with pytest.raises(RuntimeError, match="persistent environment path"):
        handler._spack_environment_state_path(SimpleNamespace())


@pytest.mark.parametrize("failure", ["fchmod", "fdopen"])
def test_atomic_sidecar_write_closes_mkstemp_descriptor_on_setup_failure(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    failure: str,
) -> None:
    """Failures before fd ownership transfer never leak the mkstemp handle."""
    descriptors: list[int] = []
    real_mkstemp = handler.tempfile.mkstemp

    def capture_mkstemp(*args: object, **kwargs: object) -> tuple[int, str]:
        descriptor, name = real_mkstemp(*args, **kwargs)
        descriptors.append(descriptor)
        return descriptor, name

    monkeypatch.setattr(handler.tempfile, "mkstemp", capture_mkstemp)
    if failure == "fchmod":
        monkeypatch.setattr(
            handler,
            "_set_private_descriptor_mode",
            lambda _descriptor: (_ for _ in ()).throw(OSError("fchmod failed")),
        )
    else:
        monkeypatch.setattr(
            handler.os,
            "fdopen",
            lambda *_args, **_kwargs: (_ for _ in ()).throw(OSError("fdopen failed")),
        )

    with pytest.raises(OSError, match=f"{failure} failed"):
        handler._atomic_write_spack_document(
            tmp_path / "state.json",
            {"value": 1},
            too_large_message="too large",
        )

    assert len(descriptors) == 1
    with pytest.raises(OSError):
        os.fstat(descriptors[0])
    assert list(tmp_path.glob(".state.json.*.tmp")) == []

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


def test_hostfile_fsync_failure_preserves_previous_bytes(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """A failed durable hostfile write never exposes a partial replacement."""
    hostfile = tmp_path / "mcp-hostfile.txt"
    hostfile.write_bytes(b"old-node\n")
    pipeline = SimpleNamespace(
        name="configured",
        jarvis=SimpleNamespace(
            get_pipeline_shared_dir=lambda _name: tmp_path,
        ),
    )

    monkeypatch.setattr(
        handler.os,
        "fsync",
        lambda _descriptor: (_ for _ in ()).throw(
            OSError("simulated hostfile fsync failure")
        ),
    )

    with pytest.raises(OSError, match="simulated hostfile fsync failure"):
        handler._apply_pipeline_config(
            pipeline,
            {"hostfile_entries": ["new-node-a", "new-node-b"]},
        )

    assert hostfile.read_bytes() == b"old-node\n"
    assert list(tmp_path.glob(".mcp-hostfile.txt.*.tmp")) == []


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
    monkeypatch.setenv("JARVIS_MCP_SPACK_ENV_ALLOWLIST", "NEW,ONE,TWO")
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


def test_windows_job_cleans_pipe_holder_after_parent_exit(tmp_path: Path) -> None:
    """A child retaining capture pipes is owned after its parent exits."""
    pid_path = tmp_path / "pipe-holder.pid"
    child_code = "import time; time.sleep(60)"
    parent_code = (
        "import os,subprocess,sys; "
        "kwargs=({'creationflags':subprocess.CREATE_NEW_PROCESS_GROUP} "
        "if os.name=='nt' else {}); "
        f"child=subprocess.Popen([sys.executable,'-c',{child_code!r}],**kwargs); "
        f"open({str(pid_path)!r},'w',encoding='ascii').write(str(child.pid))"
    )
    started = time.monotonic()

    result = handler._run_bounded_process(
        [sys.executable, "-c", parent_code],
        env=os.environ.copy(),
        timeout_seconds=20,
    )

    assert result.returncode == 0
    assert time.monotonic() - started < 12
    child_pid = int(pid_path.read_text(encoding="ascii"))
    if os.name == "nt":
        from jarvis_mcp.windows_job import (
            process_start_identity,
        )

        assert process_start_identity(child_pid) is None
        assert "taskkill" not in handler.inspect.getsource(
            handler._terminate_spack_process_tree
        )
    else:
        with pytest.raises(OSError):
            os.kill(child_pid, 0)


def test_bounded_process_closes_input_when_launch_fails(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(handler.os, "name", "posix")
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
    monkeypatch.setattr(handler.os, "name", "posix")
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

    def terminate(
        _process: object,
        *,
        include_exited_group: bool = False,
        windows_job: object | None = None,
    ) -> None:
        assert include_exited_group is True
        assert windows_job is None
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


def test_terminate_spack_tree_windows_requires_pinned_job(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class Process:
        pid = 42
        returncode: int | None = None

        def poll(self) -> int | None:
            return self.returncode

    process = Process()
    monkeypatch.setattr(handler.os, "name", "nt")
    with pytest.raises(RuntimeError, match="identity-pinned Job Object"):
        handler._terminate_spack_process_tree(process)  # type: ignore[arg-type]

    job = SimpleNamespace(
        terminate=lambda candidate: setattr(candidate, "returncode", -9)
    )
    handler._terminate_spack_process_tree(  # type: ignore[arg-type]
        process,
        windows_job=job,
    )
    assert process.returncode == -9


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


def test_scheduler_submission_metadata_binds_execution_snapshot() -> None:
    """Relay metadata is accepted only for the invocation's exact snapshot."""
    document = _submission(
        execution_id="jarvis_expected",
        hostfile_path="/tmp/execution/hostfile.txt",
        pipeline_snapshot_path="/tmp/execution/runtime",
        pipeline_input_path="/tmp/execution/input",
        pipeline_snapshot_sha256="a" * 64,
    )
    accepted = handler._scheduler_submission_metadata(
        SimpleNamespace(last_submission=document),
        scheduler={"name": "slurm"},
        script_path="/tmp/job.sh",
        require_identity=True,
        execution_id="jarvis_expected",
    )
    assert accepted == document

    with pytest.raises(RuntimeError, match="match this execution"):
        handler._scheduler_submission_metadata(
            SimpleNamespace(last_submission=document),
            scheduler={"name": "slurm"},
            script_path="/tmp/job.sh",
            require_identity=True,
            execution_id="jarvis_other",
        )
    with pytest.raises(RuntimeError, match="snapshot digest"):
        handler._scheduler_submission_metadata(
            SimpleNamespace(
                last_submission={**document, "pipeline_snapshot_sha256": "invalid"}
            ),
            scheduler={"name": "slurm"},
            script_path="/tmp/job.sh",
            require_identity=True,
            execution_id="jarvis_expected",
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
