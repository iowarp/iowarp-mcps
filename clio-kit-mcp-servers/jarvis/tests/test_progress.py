"""Production invariants for JARVIS package progress notifications."""

from __future__ import annotations

import asyncio
import json
import subprocess
import sys
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path
from queue import Empty, Queue
from typing import Any

import pytest

from jarvis_mcp.progress import (
    PACKAGE_PROGRESS_MAX_NOTIFICATIONS,
    PackageProgressBinding,
    PackageProgressExecution,
    PackageProgressProviderIdentity,
    _enqueue_records,
    bind_package_progress_provider,
)


@dataclass
class _FakeAdapter:
    package_name: str
    marker: str
    package_version: str = "2.0.0"
    run_id: str = "execution-a"
    adapter_name: str = "test-progress"
    application_profile: str | None = "test.profile"
    seen: list[str] = field(default_factory=list)

    def observe_jarvis_stdout(self, text: str) -> list[dict[str, object]]:
        self.seen.append(text)
        if self.marker not in text:
            return []
        return [self._record()]

    def observe_stdout(self, text: str) -> list[dict[str, object]]:
        return self.observe_jarvis_stdout(text)

    def finalize_jarvis_stdout(self) -> list[dict[str, object]]:
        return []

    def finalize_stdout(self) -> list[dict[str, object]]:
        return []

    def reset_stdout(self) -> None:
        return None

    def progress_log_paths(self) -> list[Path]:
        return []

    def acceptance_progress_valid(self, metadata: dict[str, Any]) -> bool:
        return metadata.get("prediction_status") == "accepted"

    def _record(self) -> dict[str, object]:
        return {
            "label": "iteration",
            "current": 1.0,
            "total": 2.0,
            "unit": "step",
            "message": self.marker,
            "metadata": {
                "adapter": self.adapter_name,
                "package_name": self.package_name,
                "package_version": self.package_version,
                "run_id": self.run_id,
                "execution_id": self.run_id,
                "prediction_status": "accepted",
            },
        }


def _binding(adapter: _FakeAdapter) -> PackageProgressBinding:
    return PackageProgressBinding(
        identity=PackageProgressProviderIdentity(
            entry_point_name="test-progress",
            entry_point_value="test_progress:factory",
            distribution_name="test-progress-provider",
            distribution_version="2.0.0",
            adapter_name=adapter.adapter_name,
            package_name=adapter.package_name,
            package_version=adapter.package_version,
            application_profile=adapter.application_profile,
        ),
        adapter=adapter,
        source_authority="jarvis_stdout_fallback",
        log_path=None,
    )


@pytest.mark.asyncio
async def test_reporter_failure_waits_for_owned_operation_to_finish() -> None:
    adapter = _FakeAdapter(package_name="test.package", marker="PROGRESS-A")
    execution = PackageProgressExecution(
        _binding(adapter),
        execution_id=adapter.run_id,
        pipeline_id="pipeline-a",
    )
    finished = threading.Event()

    def operation() -> str:
        print("PROGRESS-A", flush=True)
        time.sleep(0.25)
        finished.set()
        return "complete"

    async def broken_reporter(
        _current: float, _total: float | None, _message: str
    ) -> None:
        raise RuntimeError("notification transport failed")

    started = time.monotonic()
    with pytest.raises(RuntimeError, match="notification transport failed"):
        await execution.run(operation, broken_reporter)

    assert finished.is_set()
    assert time.monotonic() - started >= 0.2


def test_provider_burst_is_rejected_before_queue_growth() -> None:
    records: Queue[dict[str, object]] = Queue(
        maxsize=PACKAGE_PROGRESS_MAX_NOTIFICATIONS
    )
    burst = [{} for _ in range(PACKAGE_PROGRESS_MAX_NOTIFICATIONS + 1)]

    with pytest.raises(RuntimeError, match="too many records"):
        _enqueue_records(burst, records)

    assert records.qsize() == 0


@pytest.mark.asyncio
async def test_concurrent_progress_executions_are_serialized_without_cross_capture() -> (
    None
):
    active = 0
    max_active = 0
    active_lock = threading.Lock()
    adapters = [
        _FakeAdapter(package_name="test.a", marker="PROGRESS-A", run_id="execution-a"),
        _FakeAdapter(package_name="test.b", marker="PROGRESS-B", run_id="execution-b"),
    ]
    reports: dict[str, list[dict[str, object]]] = {"execution-a": [], "execution-b": []}

    def operation(marker: str) -> str:
        nonlocal active, max_active
        with active_lock:
            active += 1
            max_active = max(max_active, active)
        try:
            print(marker, flush=True)
            time.sleep(0.15)
            return marker
        finally:
            with active_lock:
                active -= 1

    async def run(adapter: _FakeAdapter) -> str:
        async def reporter(_current: float, _total: float | None, message: str) -> None:
            reports[adapter.run_id].append(json.loads(message))

        return await PackageProgressExecution(
            _binding(adapter),
            execution_id=adapter.run_id,
            pipeline_id=f"pipeline-{adapter.run_id}",
        ).run(lambda: operation(adapter.marker), reporter)

    results = await asyncio.gather(*(run(adapter) for adapter in adapters))

    assert results == ["PROGRESS-A", "PROGRESS-B"]
    assert max_active == 1
    assert [item["execution_id"] for item in reports["execution-a"]] == ["execution-a"]
    assert [item["execution_id"] for item in reports["execution-b"]] == ["execution-b"]
    assert "PROGRESS-B" not in "".join(adapters[0].seen)
    assert "PROGRESS-A" not in "".join(adapters[1].seen)


@pytest.mark.asyncio
async def test_released_jarvis_provider_emits_observed_progress_before_completion() -> (
    None
):
    """Exercise the installed JARVIS package entry point as a live provider."""
    execution_id = "execution-provider-live"
    binding = bind_package_progress_provider(
        [
            {
                "pkg_type": "builtin.lammps",
                "config": {
                    "progress": {"adapter": "lammps", "total_steps": 100},
                },
            }
        ],
        execution_id=execution_id,
    )
    assert binding is not None
    assert binding.identity.entry_point_name == "lammps"
    assert binding.identity.entry_point_value == (
        "jarvis_cd.progress.lammps:adapter_from_package"
    )
    assert binding.identity.distribution_name.replace("_", "-") == "jarvis-cd"
    assert binding.identity.distribution_version
    assert binding.identity.package_name == "builtin.lammps"
    assert binding.source_authority == "jarvis_stdout_fallback"

    finished = threading.Event()
    envelopes: list[tuple[dict[str, Any], bool]] = []

    def operation() -> str:
        print("[builtin.lammps] [START] BEGIN", flush=True)
        print("run 100", flush=True)
        print("Step Temp CPU", flush=True)
        for step, elapsed in ((0, 0.0), (25, 0.1), (50, 0.2), (75, 0.3)):
            print(f"{step} 300 {elapsed}", flush=True)
            time.sleep(0.03)
        print("[builtin.lammps] [START] END", flush=True)
        time.sleep(0.15)
        finished.set()
        return "complete"

    async def reporter(_current: float, _total: float | None, message: str) -> None:
        envelopes.append((json.loads(message), finished.is_set()))

    result = await PackageProgressExecution(
        binding,
        execution_id=execution_id,
        pipeline_id="pipeline-provider-live",
    ).run(operation, reporter)

    assert result == "complete"
    assert envelopes
    assert any(not was_finished for _, was_finished in envelopes)
    assert any(
        envelope["provider_acceptance_validated"] is True for envelope, _ in envelopes
    )
    assert all(
        envelope["execution_id"] == execution_id
        and envelope["source_authority"] == "jarvis_stdout_fallback"
        and envelope["provider"]["entry_point"] == "lammps"
        for envelope, _ in envelopes
    )


def test_fastmcp_stdio_progress_bypasses_serialized_jarvis_stdout_capture(
    tmp_path: Path,
) -> None:
    """Exercise the real FastMCP stdio writer while JARVIS stdout is redirected."""
    server = tmp_path / "real_fastmcp_progress_server.py"
    server.write_text(
        """import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from fastmcp import Context, FastMCP
from jarvis_mcp.progress import (
    PackageProgressBinding,
    PackageProgressExecution,
    PackageProgressProviderIdentity,
)

@dataclass
class Adapter:
    package_name: str = "test.package"
    package_version: str = "2.0.0"
    run_id: str = "execution-live"
    adapter_name: str = "test-progress"
    application_profile: str | None = "test.profile"

    def observe_jarvis_stdout(self, text: str):
        if "THERMO-LIVE" not in text:
            return []
        return [{
            "label": "iteration",
            "current": 1.0,
            "total": 2.0,
            "metadata": {
                "adapter": self.adapter_name,
                "package_name": self.package_name,
                "package_version": self.package_version,
                "run_id": self.run_id,
                "execution_id": self.run_id,
                "prediction_status": "accepted",
            },
        }]

    def observe_stdout(self, text: str):
        return self.observe_jarvis_stdout(text)

    def finalize_jarvis_stdout(self): return []
    def finalize_stdout(self): return []
    def reset_stdout(self): return None
    def progress_log_paths(self): return []
    def acceptance_progress_valid(self, metadata: dict[str, Any]):
        return metadata.get("prediction_status") == "accepted"

mcp = FastMCP("stdio-progress-proof")

@mcp.tool
async def run(ctx: Context) -> dict[str, bool]:
    adapter = Adapter()
    binding = PackageProgressBinding(
        identity=PackageProgressProviderIdentity(
            entry_point_name="test-progress",
            entry_point_value="test_progress:factory",
            distribution_name="test-progress-provider",
            distribution_version="2.0.0",
            adapter_name=adapter.adapter_name,
            package_name=adapter.package_name,
            package_version=adapter.package_version,
            application_profile=adapter.application_profile,
        ),
        adapter=adapter,
        source_authority="jarvis_stdout_fallback",
        log_path=None,
    )
    def operation():
        print("THERMO-LIVE", flush=True)
        time.sleep(0.3)
    await PackageProgressExecution(
        binding,
        execution_id=adapter.run_id,
        pipeline_id="pipeline-live",
    ).run(operation, ctx.report_progress)
    return {"completed": True}

mcp.run(transport="stdio", show_banner=False)
""",
        encoding="utf-8",
    )
    process = subprocess.Popen(
        [sys.executable, str(server)],
        text=True,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    assert process.stdin is not None
    assert process.stdout is not None
    output: Queue[str | None] = Queue()

    def read_stdout() -> None:
        assert process.stdout is not None
        for line in process.stdout:
            output.put(line)
        output.put(None)

    reader = threading.Thread(target=read_stdout, daemon=True)
    reader.start()
    requests = [
        {
            "jsonrpc": "2.0",
            "id": "init",
            "method": "initialize",
            "params": {
                "protocolVersion": "2024-11-05",
                "capabilities": {},
                "clientInfo": {"name": "test", "version": "1"},
            },
        },
        {"jsonrpc": "2.0", "method": "notifications/initialized", "params": {}},
        {
            "jsonrpc": "2.0",
            "id": "call",
            "method": "tools/call",
            "params": {
                "name": "run",
                "arguments": {},
                "_meta": {"progressToken": "live-token"},
            },
        },
    ]
    for request in requests:
        process.stdin.write(json.dumps(request, separators=(",", ":")) + "\n")
    process.stdin.flush()
    observed: list[dict[str, Any]] = []
    # A fresh FastMCP interpreter can take longer to import under concurrent CI
    # coverage load even though the protocol exchange itself is healthy.
    deadline = time.monotonic() + 30
    try:
        while time.monotonic() < deadline:
            try:
                line = output.get(timeout=0.2)
            except Empty:
                continue
            if line is None:
                break
            message = json.loads(line)
            observed.append(message)
            if message.get("id") == "call":
                break
    finally:
        process.stdin.close()
        process.terminate()
        process.wait(timeout=5)
        reader.join(timeout=1)

    methods = [message.get("method") for message in observed]
    call_index = next(
        index for index, message in enumerate(observed) if message.get("id") == "call"
    )
    progress_index = methods.index("notifications/progress")
    progress = observed[progress_index]
    assert progress_index < call_index
    assert progress["params"]["progressToken"] == "live-token"
    envelope = json.loads(progress["params"]["message"])
    assert envelope["schema_version"] == "clio-kit.jarvis-package-progress.v1"
