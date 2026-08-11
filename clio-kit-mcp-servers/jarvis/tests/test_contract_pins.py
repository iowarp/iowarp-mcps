"""Wire-contract pins for the jarvis MCP server (clio-kit campaign #362, Slice 1).

These pins capture the server's wire surface as it stood before the
``server.py`` / ``jarvis_handler.py`` owner-module split: the full
``tools/list`` (every tool's name, title, description, tags, annotations, and
input/output JSON schema) and the structured ``tools/call`` result of four
representative tools. They are the refactor's safety net -- committed BEFORE
any file was split, they must stay green, unmodified, across it. Any
wire-visible drift (a renamed tool, a reshaped schema, a changed result
envelope) fails here first, independent of every other test in this suite.

The four representative tools were chosen to cover the code this campaign
moves:

- ``jarvis_describe`` (target=package_search) exercises the package
  inventory/search path (moving to ``jarvis_mcp.package_discovery``).
- ``jarvis_create_pipeline`` exercises the thin pipeline-tool wrapping that
  stays in ``server.py``.
- ``jarvis_run`` exercises ``JarvisRunResult`` (moving to
  ``jarvis_mcp.models.execution``) as an MCP tool OUTPUT SCHEMA -- FastMCP
  validates the return value against it before it goes on the wire.
- ``jarvis_get_execution`` exercises ``JarvisExecutionResult.model_validate``
  (moving to ``jarvis_mcp.models.execution``), the one tool that re-validates
  its handler's raw dict through Pydantic before returning it.

Regenerate a pin only when the wire contract is DELIBERATELY changing (never
to make a refactor "pass"). To regenerate: reproduce the capture harness
described in the clio-kit campaign #362 wave-1 PR description, or hand-edit
the JSON fixture and confirm the diff is the intended, reviewed wire change.
"""

from __future__ import annotations

import importlib
import json
from pathlib import Path
from unittest.mock import Mock, patch

import pytest
from fastmcp import Client

from jarvis_mcp import server

FIXTURES_DIR = Path(__file__).parent / "fixtures"
TOOLS_LIST_PIN = FIXTURES_DIR / "jarvis_tools_list_pin.json"
TOOL_CALL_PINS = FIXTURES_DIR / "jarvis_tool_call_pins.json"


def _tool_contract(tool) -> dict:
    """Project one FastMCP Tool onto its wire-relevant contract fields."""
    return {
        "name": tool.name,
        "title": tool.title,
        "description": tool.description or "",
        "tags": sorted(tool.tags) if getattr(tool, "tags", None) else [],
        "annotations": tool.annotations.model_dump() if tool.annotations else {},
        "input_schema": tool.input_schema,
        "output_schema": getattr(tool, "output_schema", None),
    }


@pytest.mark.asyncio
async def test_tools_list_contract_pin() -> None:
    """The full 36-tool registry's wire-relevant shape matches the pin exactly.

    Reloads ``jarvis_mcp.server`` for a clean, unfiltered 36-tool registry
    regardless of test order (mirrors test_tool_titles.py's rationale:
    ``apply_tool_profile`` permanently mutates the shared ``mcp`` singleton).
    """
    fresh_server = importlib.reload(server)
    try:
        async with Client(fresh_server.mcp) as client:
            tools = await client.list_tools()
        actual = sorted((_tool_contract(t) for t in tools), key=lambda c: c["name"])
    finally:
        importlib.reload(server)

    expected = json.loads(TOOLS_LIST_PIN.read_text(encoding="utf-8"))

    actual_names = [t["name"] for t in actual]
    expected_names = [t["name"] for t in expected]
    assert actual_names == expected_names, (
        "jarvis tool registry drifted from the contract pin -- a tool was "
        "added, removed, or renamed. If this is deliberate, regenerate "
        f"{TOOLS_LIST_PIN.name}.\n"
        f"pinned:  {expected_names}\n"
        f"actual:  {actual_names}"
    )

    by_name_actual = {t["name"]: t for t in actual}
    by_name_expected = {t["name"]: t for t in expected}
    for name in expected_names:
        assert by_name_actual[name] == by_name_expected[name], (
            f"tool {name!r} wire contract drifted from the pin:\n"
            f"pinned:  {json.dumps(by_name_expected[name], indent=2, sort_keys=True)}\n"
            f"actual:  {json.dumps(by_name_actual[name], indent=2, sort_keys=True)}"
        )


_RUN_RESULT = {
    "schema_version": "clio-kit.jarvis-run.v1",
    "pipeline_id": "pin_pipeline",
    "execution_id": "pin-exec-0001",
    "status": "running",
    "mode": "direct",
    "scheduler": None,
    "script_path": None,
    "wait": False,
    "execution_handle": {
        "schema_version": "jarvis.execution.handle.v1",
        "execution_id": "pin-exec-0001",
        "pipeline_id": "pin_pipeline",
        "mode": "direct",
        "scheduler_provider": None,
        "scheduler_native_id": None,
        "cluster": None,
    },
    "execution_record": {
        "schema_version": "jarvis.execution.record.v1",
        "execution_id": "pin-exec-0001",
        "pipeline_id": "pin_pipeline",
        "pipeline_name": "pin_pipeline",
        "mode": "direct",
        "scheduler_provider": None,
        "scheduler_native_id": None,
        "cluster": None,
        "state": "running",
        "submitted": False,
        "terminal": False,
        "created_at": "2026-08-01T00:00:00Z",
        "updated_at": "2026-08-01T00:00:01Z",
        "return_code": None,
        "error": None,
        "metadata": {},
    },
    "progress": {
        "schema_version": "jarvis.execution.progress.v1",
        "execution_id": "pin-exec-0001",
        "pipeline_id": "pin_pipeline",
        "execution_state": "running",
        "terminal": False,
        "packages": [],
    },
    "runtime_metadata": {"source": "jarvis_mcp", "schema_version": "jarvis.runtime.v1"},
}

_EXECUTION_RESULT = {
    "schema_version": "clio-kit.jarvis-execution.v2",
    "pipeline_id": "pin_pipeline",
    "execution_id": "pin-exec-0001",
    "execution_handle": _RUN_RESULT["execution_handle"],
    "execution_record": _RUN_RESULT["execution_record"],
    "runtime_metadata": _RUN_RESULT["runtime_metadata"],
    "progress": _RUN_RESULT["progress"],
    "artifact_page": None,
    "service_runtimes": None,
}


@pytest.fixture
def tool_call_pins() -> dict:
    return json.loads(TOOL_CALL_PINS.read_text(encoding="utf-8"))


@pytest.mark.asyncio
async def test_jarvis_describe_package_search_call_pin(tool_call_pins) -> None:
    """Package-search discovery result shape (the code moving to package_discovery.py)."""
    pin = tool_call_pins["jarvis_describe_package_search"]
    with (
        patch("jarvis_mcp.server.JarvisManager") as mock_manager_class,
        patch("jarvis_mcp.server._manager", None),
        patch("jarvis_mcp.server.manager", None),
    ):
        mock_manager = Mock()
        mock_manager.list_repos.return_value = ["repo1", "repo2"]
        mock_manager_class.get_instance.return_value = mock_manager

        async with Client(server.mcp) as client:
            result = await client.call_tool("jarvis_describe", pin["args"])

    assert result.data == pin["result"]


@pytest.mark.asyncio
async def test_jarvis_create_pipeline_call_pin(tool_call_pins) -> None:
    """The thin pipeline-tool wrapping that stays in server.py."""
    pin = tool_call_pins["jarvis_create_pipeline"]
    with patch("jarvis_mcp.server.create_pipeline") as mock_create:
        mock_create.return_value = {"pipeline_id": "pin_pipeline", "status": "created"}
        async with Client(server.mcp) as client:
            result = await client.call_tool("jarvis_create_pipeline", pin["args"])

    assert result.data == pin["result"]


@pytest.mark.asyncio
async def test_jarvis_run_call_pin(tool_call_pins) -> None:
    """JarvisRunResult as a validated MCP tool OUTPUT SCHEMA."""
    pin = tool_call_pins["jarvis_run"]
    with patch("jarvis_mcp.server.run_pipeline") as mock_run:
        mock_run.return_value = dict(_RUN_RESULT)
        async with Client(server.mcp) as client:
            result = await client.call_tool("jarvis_run", pin["args"])

    assert result.data == pin["result"]


@pytest.mark.asyncio
async def test_jarvis_get_execution_call_pin(tool_call_pins) -> None:
    """JarvisExecutionResult.model_validate re-validation of the handler's raw dict."""
    pin = tool_call_pins["jarvis_get_execution"]
    with patch("jarvis_mcp.server.get_execution") as mock_get:
        mock_get.return_value = dict(_EXECUTION_RESULT)
        async with Client(server.mcp) as client:
            result = await client.call_tool("jarvis_get_execution", pin["args"])

    assert result.data == pin["result"]
