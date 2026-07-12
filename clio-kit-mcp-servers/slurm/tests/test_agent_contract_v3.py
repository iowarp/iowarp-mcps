"""Locked tests for the compact Slurm user contract."""

from __future__ import annotations

import stat
import subprocess
import sys
from types import SimpleNamespace
from typing import Any
from unittest.mock import MagicMock, Mock, patch

import pytest
from fastmcp import Client
from fastmcp.exceptions import ToolError

from slurm_mcp import agent_contract
from slurm_mcp.agent_contract import (
    SlurmCancellation,
    SlurmClusterSnapshot,
    SlurmJobDescription,
    SlurmJobList,
    SlurmSubmission,
    cluster_snapshot,
    contract_schemas,
    describe_job,
    list_jobs,
    request_cancellation,
    submit,
)
from slurm_mcp import server
from slurm_mcp.implementation.job_output import _read_output
from slurm_mcp.implementation.job_submission import _create_sbatch_script
from slurm_mcp.implementation.array_jobs import submit_array_job
from slurm_mcp.implementation.utils import (
    SLURM_FIELD_SEPARATOR,
    SlurmCommandResult,
    read_regular_job_script,
    run_slurm_command,
)
from slurm_mcp.implementation.node_info import get_node_info


EXPECTED_USER_TOOLS = (
    "slurm_submit",
    "slurm_list",
    "slurm_describe",
    "slurm_cluster",
    "slurm_cancel",
)
EXPECTED_LEGACY_TOOLS = (
    "submit_slurm_job",
    "check_job_status",
    "cancel_slurm_job",
    "list_slurm_jobs",
    "get_slurm_info",
    "get_job_details",
    "get_job_output",
    "get_queue_info",
    "submit_array_job",
    "get_node_info",
    "allocate_slurm_nodes",
    "deallocate_slurm_nodes",
    "get_allocation_status",
)


def _assert_every_object_schema_is_closed(schema: Any) -> None:
    if isinstance(schema, dict):
        if schema.get("type") == "object":
            assert schema.get("additionalProperties") is False, schema
        for value in schema.values():
            _assert_every_object_schema_is_closed(value)
    elif isinstance(schema, list):
        for value in schema:
            _assert_every_object_schema_is_closed(value)


def test_user_contract_locks_exact_names_and_closed_schemas() -> None:
    """The default user-v3 catalog and its schemas are deterministic and closed."""
    assert server.MCP_METADATA_PROFILE == "user"
    assert server.USER_TOOL_NAMES == EXPECTED_USER_TOOLS
    assert server.LEGACY_TOOL_NAMES == EXPECTED_LEGACY_TOOLS
    tools = {tool.name: tool for tool in server._registered_tools()}
    assert set(EXPECTED_USER_TOOLS) <= tools.keys()
    for name in EXPECTED_USER_TOOLS:
        tool = tools[name]
        assert tool.parameters["additionalProperties"] is False
        assert tool.output_schema["additionalProperties"] is False
        _assert_every_object_schema_is_closed(tool.parameters)
        _assert_every_object_schema_is_closed(tool.output_schema)

    cancel = tools["slurm_cancel"]
    assert cancel.annotations.destructiveHint is True
    assert cancel.annotations.readOnlyHint is False
    assert set(cancel.parameters["required"]) == {"job_id", "confirm_job_id"}


@pytest.mark.parametrize(
    ("profile", "expected"),
    [
        ("user", set(EXPECTED_USER_TOOLS)),
        ("legacy", set(EXPECTED_LEGACY_TOOLS)),
        ("admin", set(EXPECTED_USER_TOOLS) | set(EXPECTED_LEGACY_TOOLS)),
        ("all", set(EXPECTED_USER_TOOLS) | set(EXPECTED_LEGACY_TOOLS)),
    ],
)
def test_profile_separation(profile: str, expected: set[str]) -> None:
    """Profiles remove every tool outside their exact declared surface."""
    every_name = set(EXPECTED_USER_TOOLS) | set(EXPECTED_LEGACY_TOOLS) | {"other"}
    tools = [SimpleNamespace(name=name) for name in every_name]
    remove_tool = Mock()
    with (
        patch.object(server, "_registered_tools", return_value=tools),
        patch.object(server.mcp.local_provider, "remove_tool", remove_tool),
    ):
        server.apply_tool_profile(profile)
    assert {
        call.args[0] for call in remove_tool.call_args_list
    } == every_name - expected


def test_unknown_profile_fails_closed() -> None:
    """An unknown profile never silently exposes the full tool surface."""
    with pytest.raises(ValueError, match="profile must be one of"):
        server.apply_tool_profile("operator")


def test_main_selects_user_profile_by_default() -> None:
    """The installed command applies the compact profile without operator flags."""
    with (
        patch("sys.argv", ["slurm-mcp"]),
        patch.dict("os.environ", {}, clear=True),
        patch.object(server, "apply_tool_profile") as apply_profile,
        patch.object(server.mcp, "run") as run,
    ):
        server.main()
    apply_profile.assert_called_once_with("user")
    run.assert_called_once_with(transport="stdio")


@pytest.mark.parametrize(
    ("tool_name", "backend_name", "arguments"),
    [
        ("slurm_submit_tool", "submit", {"script_path": "job.sh"}),
        ("slurm_list_tool", "list_jobs", {}),
        ("slurm_describe_tool", "describe_job", {"job_id": "123"}),
        ("slurm_cluster_tool", "cluster_snapshot", {}),
        (
            "slurm_cancel_tool",
            "request_cancellation",
            {"job_id": "123", "confirm_job_id": "123"},
        ),
    ],
)
async def test_user_tool_wrappers_return_backend_results_and_preserve_tool_errors(
    tool_name: str,
    backend_name: str,
    arguments: dict[str, object],
) -> None:
    """The thin MCP layer returns typed backends and preserves their ToolErrors."""
    expected = MagicMock()
    with patch.object(server, backend_name, return_value=expected):
        assert await getattr(server, tool_name)(**arguments) is expected

    denied = ToolError("scheduler denied the request")
    with patch.object(server, backend_name, side_effect=denied):
        with pytest.raises(ToolError) as captured:
            await getattr(server, tool_name)(**arguments)
    assert captured.value is denied


@pytest.mark.parametrize(
    ("tool_name", "backend_name", "arguments", "message"),
    [
        (
            "slurm_submit_tool",
            "submit",
            {"script_path": "job.sh"},
            "Slurm submission failed",
        ),
        ("slurm_list_tool", "list_jobs", {}, "Slurm job listing failed"),
        (
            "slurm_describe_tool",
            "describe_job",
            {"job_id": "123"},
            "Slurm job description failed",
        ),
        ("slurm_cluster_tool", "cluster_snapshot", {}, "Slurm cluster query failed"),
        (
            "slurm_cancel_tool",
            "request_cancellation",
            {"job_id": "123", "confirm_job_id": "123"},
            "Slurm cancellation failed",
        ),
    ],
)
async def test_user_tool_wrappers_translate_unexpected_backend_errors(
    tool_name: str,
    backend_name: str,
    arguments: dict[str, object],
    message: str,
) -> None:
    """Unexpected backend failures become bounded agent-facing ToolErrors."""
    with patch.object(server, backend_name, side_effect=RuntimeError("boom")):
        with pytest.raises(ToolError, match=message):
            await getattr(server, tool_name)(**arguments)


def test_result_contracts_are_closed() -> None:
    """Every public result model rejects additional fields recursively."""
    assert contract_schemas() == (
        SlurmSubmission,
        SlurmJobList,
        SlurmJobDescription,
        SlurmClusterSnapshot,
        SlurmCancellation,
    )
    for model in contract_schemas():
        _assert_every_object_schema_is_closed(model.model_json_schema())


def test_submit_unifies_single_and_array_jobs(tmp_path: Any) -> None:
    """One operation exposes the common submission intent and native ID."""
    script = tmp_path / "job.sh"
    script.write_text("#!/bin/sh\necho ok\n", encoding="utf-8")
    with patch.object(
        agent_contract,
        "submit_slurm_job",
        return_value={"job_id": "81234", "status": "SUBMITTED"},
    ) as single_submit:
        result = submit(str(script), cores=4, memory="8G", job_name="science")
    assert result.model_dump() == {
        "schema_version": "clio-kit.slurm-submission.v1",
        "scheduler": "slurm",
        "scheduler_native_id": "81234",
        "kind": "job",
        "state": "submitted",
        "script_path": str(script),
        "array": None,
        "resources": {
            "cores": 4,
            "memory": "8G",
            "time_limit": "01:00:00",
            "partition": None,
            "job_name": "science",
        },
    }
    single_submit.assert_called_once()

    with patch.object(
        agent_contract,
        "submit_array_job",
        return_value={"array_job_id": "81235", "real_slurm": True},
    ) as array_submit:
        array_result = submit(str(script), array="0-31%4")
    assert array_result.scheduler_native_id == "81235"
    assert array_result.kind == "array"
    assert array_result.array == "0-31%4"
    array_submit.assert_called_once()


def test_submit_rejects_directive_injection_before_backend() -> None:
    """Array and resource values cannot inject additional SBATCH directives."""
    with patch.object(agent_contract, "submit_array_job") as backend:
        with pytest.raises(ToolError, match="array must be"):
            submit("job.sh", array="0-1\n#SBATCH --account=other")
    backend.assert_not_called()

    with patch.object(agent_contract, "submit_slurm_job") as backend:
        with pytest.raises(ToolError, match="partition contains unsupported"):
            submit("job.sh", partition="gpu; touch /tmp/bad")
    backend.assert_not_called()


def test_list_jobs_normalizes_native_ids_and_filters() -> None:
    """List results use stable names instead of leaking legacy response keys."""
    with patch.object(
        agent_contract,
        "list_slurm_jobs",
        return_value={
            "jobs": [
                {
                    "job_id": "9001_7",
                    "state": "RUNNING",
                    "name": "sim",
                    "user": "alice",
                    "time": "00:03",
                    "time_limit": "01:00:00",
                    "nodes": "1",
                    "cpus": "8",
                }
            ]
        },
    ):
        result = list_jobs(user="alice", state="RUNNING", partition="compute")
    assert result.count == 1
    assert result.jobs[0].scheduler_native_id == "9001_7"
    assert result.jobs[0].elapsed == "00:03"
    assert result.filters.partition == "compute"
    assert result.limit == 100
    assert result.truncated is False


def test_list_jobs_caps_returned_records_and_reports_truncation() -> None:
    """Large queues cannot create unbounded user-contract results."""
    jobs = [
        {
            "job_id": str(index + 1),
            "state": "RUNNING",
            "name": f"job-{index}",
            "user": "alice",
            "time": "00:01",
            "time_limit": "01:00:00",
            "nodes": "1",
            "cpus": "1",
        }
        for index in range(3)
    ]
    with patch.object(
        agent_contract,
        "list_slurm_jobs",
        return_value={"jobs": jobs, "truncated": False},
    ) as backend:
        result = list_jobs(limit=2)
    assert [job.scheduler_native_id for job in result.jobs] == ["1", "2"]
    assert result.limit == 2
    assert result.truncated is True
    backend.assert_called_once_with(None, None, None, max_records=2)


@pytest.mark.asyncio
async def test_fastmcp_returns_the_structured_closed_envelope() -> None:
    """The contract survives a real in-memory MCP call, not only direct Python calls."""
    expected = SlurmJobList(
        filters=agent_contract.JobListFilter(user=None, state=None, partition=None),
        jobs=[],
        count=0,
        limit=100,
        truncated=False,
    )
    with patch.object(server, "list_jobs", return_value=expected):
        async with Client(server.mcp) as client:
            result = await client.call_tool("slurm_list", {})
    assert result.is_error is False
    assert result.structured_content == expected.model_dump(mode="json")


def test_describe_combines_status_details_and_bounded_output() -> None:
    """Describe replaces three separate reads and bounds returned log content."""
    with (
        patch.object(
            agent_contract,
            "get_job_status",
            return_value={"job_id": "42", "status": "RUNNING", "reason": "node01"},
        ),
        patch.object(
            agent_contract,
            "get_job_details",
            return_value={"job_id": "42", "details": {"JobName": "demo", "NumCPUs": 4}},
        ),
        patch.object(
            agent_contract,
            "get_job_output",
            side_effect=[
                {"file_path": "/logs/42.out", "content": "abcdefgh"},
                {"error": "stderr file not created"},
            ],
        ),
    ):
        result = describe_job("42", output="both", max_output_chars=5)
    assert result.scheduler_native_id == "42"
    assert result.state == "RUNNING"
    assert result.terminal is False
    assert [item.name for item in result.properties] == ["JobName", "NumCPUs"]
    assert result.outputs[0].content == "defgh"
    assert result.outputs[0].truncated is True
    assert result.diagnostics == ["stderr unavailable: stderr file not created"]


def test_output_reader_uses_a_bounded_tail(tmp_path: Any) -> None:
    """The v3 output path does not load an unbounded scheduler log into memory."""
    output = tmp_path / "job.out"
    output.write_text("prefix-" + ("x" * 100) + "-tail", encoding="utf-8")
    content, truncated = _read_output(str(output), max_chars=10)
    assert content == "xxxxx-tail"
    assert truncated is True


def test_output_reader_remains_bounded_if_the_log_grows() -> None:
    """Descriptor growth cannot turn a bounded tail read into ``read()``."""

    class GrowingStream:
        def __init__(self) -> None:
            self.read_sizes: list[int] = []

        def __enter__(self) -> "GrowingStream":
            return self

        def __exit__(self, *_args: object) -> None:
            return None

        def fileno(self) -> int:
            return 1

        def seek(self, _offset: int, _whence: int) -> int:
            return 0

        def read(self, size: int) -> bytes:
            self.read_sizes.append(size)
            return b"x" * size

    stream = GrowingStream()
    metadata = SimpleNamespace(st_mode=stat.S_IFREG, st_size=1)
    with (
        patch("builtins.open", return_value=stream),
        patch("slurm_mcp.implementation.job_output.os.fstat", return_value=metadata),
    ):
        content, truncated = _read_output("growing.out", max_chars=10)
    assert stream.read_sizes == [40]
    assert content == "x" * 10
    assert truncated is True


def test_output_reader_rejects_non_regular_scheduler_paths() -> None:
    """A scheduler stdout path cannot make the MCP block on a FIFO or device."""

    stream = MagicMock()
    stream.__enter__ = Mock(return_value=stream)
    stream.__exit__ = Mock(return_value=None)
    stream.fileno.return_value = 1
    metadata = SimpleNamespace(st_mode=stat.S_IFIFO, st_size=0)
    with (
        patch("builtins.open", return_value=stream),
        patch("slurm_mcp.implementation.job_output.os.fstat", return_value=metadata),
        pytest.raises(ValueError, match="not a regular file"),
    ):
        _read_output("job.pipe", max_chars=10)
    stream.read.assert_not_called()


def test_real_command_runner_caps_output_and_times_out() -> None:
    """Production Popen execution bounds noisy and unresponsive Slurm commands."""
    result = run_slurm_command(
        [sys.executable, "-c", "import sys; sys.stdout.write('x' * 100000)"],
        max_stdout_bytes=128,
        max_stderr_bytes=128,
    )
    assert len(result.stdout.encode("utf-8")) == 128
    assert result.stdout_truncated is True

    with pytest.raises(subprocess.TimeoutExpired):
        run_slurm_command(
            [sys.executable, "-c", "import time; time.sleep(5)"],
            timeout=0.05,
            max_stdout_bytes=128,
            max_stderr_bytes=128,
        )


def test_scheduler_delimiter_preserves_commas_in_node_fields() -> None:
    """Features, GRES, and node lists are not split on their embedded commas."""
    delimiter = SLURM_FIELD_SEPARATOR
    stdout = delimiter.join(
        ["node[01-02]", "idle", "0/128/0/128", "512000", "zen4,avx", "gpu:a100:4,ssd:1"]
    )
    response = SlurmCommandResult(
        args=["sinfo"],
        returncode=0,
        stdout=stdout + "\n",
        stderr="",
    )
    with (
        patch(
            "slurm_mcp.implementation.node_info.check_slurm_available",
            return_value=True,
        ),
        patch(
            "slurm_mcp.implementation.node_info.run_slurm_command",
            return_value=response,
        ),
    ):
        result = get_node_info()
    assert result["nodes"] == [
        {
            "node_name": "node[01-02]",
            "state": "idle",
            "cpus": "0/128/0/128",
            "memory": "512000",
            "features": "zen4,avx",
            "gres": "gpu:a100:4,ssd:1",
        }
    ]


def test_job_scripts_are_regular_bounded_utf8_files(tmp_path: Any) -> None:
    """Submission reads through validated descriptors with an explicit byte cap."""
    script = tmp_path / "job.sh"
    script.write_bytes(b"echo ok\n")
    assert read_regular_job_script(str(script), max_bytes=64) == "echo ok\n"
    with pytest.raises(ValueError, match="exceeds"):
        read_regular_job_script(str(script), max_bytes=4)
    with pytest.raises(ValueError, match="not a regular file"):
        read_regular_job_script(str(tmp_path), max_bytes=64)


def test_legacy_submission_rejects_sbatch_directive_injection(tmp_path: Any) -> None:
    """Admin and legacy names enforce injection checks at the backend boundary."""
    script = tmp_path / "job.sh"
    script.write_text("echo ok\n", encoding="utf-8")
    with pytest.raises(ValueError, match="job_name contains unsupported"):
        _create_sbatch_script(
            str(script),
            1,
            job_name="safe\nid > /tmp/injected",
        )
    with pytest.raises(ValueError, match="array_range must be"):
        submit_array_job(
            str(script),
            "0-1\n#SBATCH --account=other",
        )


def test_describe_rejects_non_native_job_id_without_queries() -> None:
    """Job lookups accept Slurm native IDs, not shell text or relay IDs."""
    with patch.object(agent_contract, "get_job_status") as backend:
        with pytest.raises(ToolError, match="scheduler-native Slurm ID"):
            describe_job("execution-abc; scancel 1")
    backend.assert_not_called()


def test_describe_does_not_invent_completion_when_accounting_is_unavailable() -> None:
    """Disappearance from squeue alone is not proof that a job completed."""
    with (
        patch.object(
            agent_contract,
            "get_job_status",
            return_value={
                "job_id": "42",
                "status": "COMPLETED",
                "reason": "Job not found (may have completed)",
            },
        ),
        patch.object(
            agent_contract,
            "get_job_details",
            return_value={"job_id": "42", "error": "Job not found"},
        ),
    ):
        result = describe_job("42")
    assert result.state == "UNKNOWN"
    assert result.terminal is False
    assert result.diagnostics == [
        "details unavailable: Job not found",
        "lifecycle unavailable: job is absent from the live queue and no accounting "
        "record was found",
    ]


def test_empty_details_do_not_turn_queue_absence_into_completion() -> None:
    """An empty detail object is not authoritative scheduler accounting."""
    with (
        patch.object(
            agent_contract,
            "get_job_status",
            return_value={
                "job_id": "42",
                "status": "COMPLETED",
                "reason": "Job not found (may have completed)",
            },
        ),
        patch.object(
            agent_contract,
            "get_job_details",
            return_value={"job_id": "42", "details": {}},
        ),
    ):
        result = describe_job("42")
    assert result.state == "UNKNOWN"
    assert result.terminal is False


def test_cluster_snapshot_unifies_cluster_queue_and_opt_in_nodes() -> None:
    """Cluster inspection composes the three useful reads into one snapshot."""
    with (
        patch.object(
            agent_contract,
            "get_slurm_info",
            return_value={
                "cluster_name": "ares",
                "version": "slurm 24.05",
                "partitions": [
                    {
                        "partition": "compute",
                        "avail_idle": "up",
                        "timelimit": "1-00:00:00",
                        "nodes": "32",
                        "state": "idle",
                        "nodelist": "node[01-32]",
                    }
                ],
            },
        ),
        patch.object(
            agent_contract,
            "get_queue_info",
            return_value={
                "jobs": [
                    {
                        "job_id": "77",
                        "state": "PENDING",
                        "name": "demo",
                        "user": "alice",
                        "partition": "compute",
                        "time": "0:00",
                        "time_limit": "1:00:00",
                        "nodes": "1",
                        "cpus": "2",
                        "priority": "100",
                    }
                ],
                "state_summary": {"PENDING": 1, "RUNNING": 0},
            },
        ),
        patch.object(
            agent_contract,
            "get_node_info",
            return_value={
                "nodes": [
                    {
                        "node_name": "node01",
                        "state": "idle",
                        "cpus": "0/64/0/64",
                        "memory": "256000",
                        "features": "zen4",
                        "gres": "gpu:4",
                    }
                ]
            },
        ),
    ):
        result = cluster_snapshot(partition="compute", include_nodes=True)
    assert result.cluster_name == "ares"
    assert result.queue_count == 1
    assert result.queue[0].scheduler_native_id == "77"
    assert result.nodes_included is True
    assert result.nodes[0].name == "node01"
    assert result.partition_limit == 256
    assert result.queue_limit == 100
    assert result.node_limit == 100
    assert result.partitions_truncated is False
    assert result.queue_truncated is False
    assert result.nodes_truncated is False
    assert result.state_counts_complete is True


def test_cancellation_requires_exact_confirmation_before_scancel() -> None:
    """A mismatch never reaches the destructive scheduler operation."""
    with patch.object(agent_contract, "cancel_slurm_job") as backend:
        with pytest.raises(ToolError, match="confirm_job_id must exactly match"):
            request_cancellation("123", confirm_job_id="124")
    backend.assert_not_called()

    with patch.object(
        agent_contract,
        "cancel_slurm_job",
        return_value={"job_id": "123", "status": "cancelled"},
    ) as backend:
        result = request_cancellation(
            "123", confirm_job_id="123", reason="user requested stop"
        )
    assert result.model_dump() == {
        "schema_version": "clio-kit.slurm-cancellation.v1",
        "scheduler": "slurm",
        "scheduler_native_id": "123",
        "result": "cancellation_requested",
        "confirmation_matched": True,
        "reason": "user requested stop",
    }
    backend.assert_called_once_with("123")


def test_cancellation_backend_failure_is_not_reported_as_success() -> None:
    """A failed scancel remains an MCP error, never a cancellation acknowledgement."""
    with patch.object(
        agent_contract,
        "cancel_slurm_job",
        return_value={"job_id": "123", "status": "error", "message": "denied"},
    ):
        with pytest.raises(ToolError, match="Slurm cancellation failed: denied"):
            request_cancellation("123", confirm_job_id="123")
