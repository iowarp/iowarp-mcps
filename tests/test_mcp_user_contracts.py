"""Live wire and packaged-artifact tests for locked MCP user contracts."""

from __future__ import annotations

import hashlib
import json
import sys
import time
from pathlib import Path
from typing import Any, cast

import pytest
from click.testing import CliRunner

from clio_kit import main
from clio_kit.mcp_contracts import (
    ContractGenerationError,
    MAX_PROBE_LINES,
    MCP_USER_CONTRACT_CANONICALIZATION,
    MCP_USER_CONTRACT_PROJECTION,
    USER_CONTRACT_SPECS,
    canonical_contract_projection,
    canonical_json_bytes,
    exchange_mcp_tools_list,
    generate_user_contract_artifacts,
    load_mcp_user_contract,
    mcp_user_contract_digest,
)

JSON = dict[str, Any]
REPOSITORY_ROOT = Path(__file__).resolve().parents[1]


def test_committed_contracts_match_real_locked_stdio_tools_list() -> None:
    """Committed artifacts must exactly match live FastMCP stdio responses."""
    observed = generate_user_contract_artifacts(REPOSITORY_ROOT, check=True)

    assert [artifact["contract_id"] for artifact in observed] == [
        spec.contract_id for spec in USER_CONTRACT_SPECS
    ]


@pytest.mark.parametrize(
    ("contract_id", "expected_names"),
    [
        (
            "clio-kit-jarvis-user-v3",
            {
                "jarvis_create_pipeline",
                "jarvis_describe",
                "jarvis_add_step",
                "jarvis_edit_step",
                "jarvis_run",
                "jarvis_get_execution",
                "jarvis_get_execution_progress",
            },
        ),
        (
            "clio-kit-spack-user-v3",
            {"spack_find", "spack_install", "spack_locate"},
        ),
    ],
)
def test_shipped_contract_digest_covers_exact_user_surface(
    contract_id: str,
    expected_names: set[str],
) -> None:
    """The public digest is reproducible from the shipped wire Tool objects."""
    artifact = load_mcp_user_contract(contract_id)
    tools = [cast(JSON, tool) for tool in cast(list[object], artifact["tools"])]

    assert artifact["canonicalization"] == MCP_USER_CONTRACT_CANONICALIZATION
    assert artifact["projection"] == MCP_USER_CONTRACT_PROJECTION
    assert {tool["name"] for tool in tools} == expected_names
    assert artifact["contract_sha256"] == mcp_user_contract_digest(tools)
    assert (
        artifact["wire_sha256"]
        == hashlib.sha256(canonical_json_bytes({"tools": tools})).hexdigest()
    )


def test_spack_contract_requires_load_spec_without_exposing_load() -> None:
    """Spack locate returns JARVIS's reload input without a fake load operation."""
    artifact = load_mcp_user_contract("clio-kit-spack-user-v3")
    tools = {
        cast(str, tool["name"]): cast(JSON, tool)
        for tool in cast(list[JSON], artifact["tools"])
    }

    assert set(tools) == {"spack_find", "spack_install", "spack_locate"}
    assert "spack_load" not in tools
    output_schema = cast(JSON, tools["spack_locate"]["outputSchema"])
    properties = cast(JSON, output_schema["properties"])
    assert properties["load_spec"] == {"type": "string"}
    assert "load_spec" in cast(list[str], output_schema["required"])


def test_jarvis_contract_combines_edit_remove_and_exposes_execution_queries() -> None:
    """JARVIS keeps mutations compact while exposing native execution queries."""
    artifact = load_mcp_user_contract("clio-kit-jarvis-user-v3")
    tools = {
        cast(str, tool["name"]): cast(JSON, tool)
        for tool in cast(list[JSON], artifact["tools"])
    }

    assert "jarvis_remove_step" not in tools
    edit_input = cast(JSON, tools["jarvis_edit_step"]["inputSchema"])
    properties = cast(JSON, edit_input["properties"])
    operation = cast(JSON, properties["operation"])
    assert operation["enum"] == ["edit", "remove"]
    assert "jarvis_get_execution" in tools
    assert "jarvis_get_execution_progress" in tools
    run_input = cast(JSON, tools["jarvis_run"]["inputSchema"])
    run_properties = cast(JSON, run_input["properties"])
    execution_id = cast(JSON, run_properties["execution_id"])
    assert execution_id == {
        "anyOf": [{"type": "string"}, {"type": "null"}],
        "default": None,
    }
    for tool_name in ("jarvis_get_execution", "jarvis_get_execution_progress"):
        query_input = cast(JSON, tools[tool_name]["inputSchema"])
        assert query_input["required"] == ["pipeline_id", "execution_id"]
        assert set(cast(JSON, query_input["properties"])) == {
            "pipeline_id",
            "execution_id",
        }
    expected_result_schemas = {
        "jarvis_run": "clio-kit.jarvis-run.v1",
        "jarvis_get_execution": "clio-kit.jarvis-execution.v1",
        "jarvis_get_execution_progress": (
            "clio-kit.jarvis-execution-progress-query.v1"
        ),
    }
    for tool_name, schema_version in expected_result_schemas.items():
        output = cast(JSON, tools[tool_name]["outputSchema"])
        output_properties = cast(JSON, output["properties"])
        assert output_properties["schema_version"] == {
            "const": schema_version,
            "type": "string",
        }
    for tool_name in ("jarvis_run", "jarvis_get_execution"):
        output = cast(JSON, tools[tool_name]["outputSchema"])
        handle = cast(JSON, cast(JSON, output["properties"])["execution_handle"])
        handle_properties = cast(JSON, handle["properties"])
        assert handle_properties["schema_version"] == {
            "const": "jarvis.execution.handle.v1",
            "type": "string",
        }
        assert set(cast(list[str], handle["required"])) == {
            "schema_version",
            "execution_id",
            "pipeline_id",
            "mode",
            "scheduler_provider",
            "scheduler_native_id",
            "cluster",
        }
    run_output = cast(JSON, tools["jarvis_run"]["outputSchema"])
    run_output_properties = cast(JSON, run_output["properties"])
    run_progress = cast(JSON, run_output_properties["progress"])
    run_progress_properties = cast(JSON, run_progress["properties"])
    assert run_progress_properties["schema_version"] == {
        "const": "jarvis.execution.progress.v1",
        "type": "string",
    }
    assert "progress" in cast(list[str], run_output["required"])


def test_contract_projection_matches_downstream_schema_digest_shape() -> None:
    """The canonical projection uses explicit optional fields and sorted tools."""
    tools: list[JSON] = [
        {"name": "z", "description": "last", "inputSchema": {"type": "object"}},
        {
            "name": "a",
            "inputSchema": {"type": "object"},
            "annotations": {"readOnlyHint": True},
        },
    ]

    assert canonical_contract_projection(tools) == {
        "tools": [
            {
                "annotations": {"readOnlyHint": True},
                "description": None,
                "input_schema": {"type": "object"},
                "name": "a",
                "output_schema": None,
                "title": None,
            },
            {
                "annotations": None,
                "description": "last",
                "input_schema": {"type": "object"},
                "name": "z",
                "output_schema": None,
                "title": None,
            },
        ]
    }


def test_contract_cli_lists_and_prints_verified_artifacts() -> None:
    """Operators and downstream release gates can inspect the wheel contract."""
    runner = CliRunner()

    listed = runner.invoke(main, ["mcp-contracts"])
    shown = runner.invoke(main, ["mcp-contract", "clio-kit-spack-user-v3"])

    assert listed.exit_code == 0, listed.output
    assert "clio-kit-jarvis-user-v3" in listed.output
    assert "clio-kit-spack-user-v3" in listed.output
    assert shown.exit_code == 0, shown.output
    assert json.loads(shown.output)["contract_id"] == "clio-kit-spack-user-v3"


@pytest.mark.parametrize(
    ("stream_name", "max_output_bytes", "max_line_bytes", "expected_error"),
    [
        ("stdout", 512, 4_096, "stdout byte limit exceeded"),
        ("stdout", 4_096, 512, "stdout line limit exceeded"),
        ("stderr", 512, 4_096, "stderr byte limit exceeded"),
        ("stderr", 4_096, 512, "stderr line limit exceeded"),
    ],
)
def test_contract_probe_kills_hostile_stream_on_live_overflow(
    tmp_path: Path,
    stream_name: str,
    max_output_bytes: int,
    max_line_bytes: int,
    expected_error: str,
) -> None:
    """Probe pipes are fixed-chunk bounded and kill a producer before it continues."""
    sentinel = tmp_path / f"{stream_name}-{max_output_bytes}-continued"
    script = (
        "import pathlib,sys,time; "
        f"stream=sys.{stream_name}.buffer; "
        "stream.write(b'x'*2048); stream.flush(); "
        "time.sleep(10); pathlib.Path(sys.argv[1]).write_text('continued')"
    )
    started = time.monotonic()

    with pytest.raises(ContractGenerationError, match=expected_error):
        exchange_mcp_tools_list(
            [sys.executable, "-c", script, str(sentinel)],
            contract_id=f"hostile-{stream_name}",
            timeout_seconds=8,
            max_output_bytes=max_output_bytes,
            max_line_bytes=max_line_bytes,
        )

    assert time.monotonic() - started < 5
    time.sleep(0.1)
    assert not sentinel.exists()


@pytest.mark.parametrize("stream_name", ["stdout", "stderr"])
def test_contract_probe_reports_line_count_overflow_immediately(
    tmp_path: Path,
    stream_name: str,
) -> None:
    """A full stdout queue cannot hide stdout or stderr line-count failures."""
    sentinel = tmp_path / f"{stream_name}-line-count-continued"
    script = (
        "import pathlib,sys,time; "
        f"stream=sys.{stream_name}.buffer; "
        "stream.write(b'x\\n'*int(sys.argv[2])); stream.flush(); "
        "time.sleep(10); pathlib.Path(sys.argv[1]).write_text('continued')"
    )
    started = time.monotonic()

    with pytest.raises(
        ContractGenerationError,
        match=rf"{stream_name} line-count limit exceeded",
    ):
        exchange_mcp_tools_list(
            [
                sys.executable,
                "-c",
                script,
                str(sentinel),
                str(MAX_PROBE_LINES + 1),
            ],
            contract_id=f"hostile-{stream_name}-line-count",
            timeout_seconds=8,
        )

    assert time.monotonic() - started < 5
    time.sleep(0.1)
    assert not sentinel.exists()
