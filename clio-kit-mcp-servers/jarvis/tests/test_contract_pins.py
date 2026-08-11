"""Wire-contract pins for the jarvis MCP server (clio-kit campaign #362, Slice 1).

These pins capture the server's wire surface as it stood before the
``server.py`` / ``jarvis_handler.py`` owner-module split: the full
``tools/list`` registration -- every tool's LITERAL wire record
(``Tool.model_dump(mode="json", by_alias=True)``: name, title, description,
inputSchema, outputSchema, annotations, icons, execution, and ``_meta``
including ``_meta.fastmcp.tags``) in actual registration order -- and the
full ``tools/call`` result envelope (``content``, ``structured_content``,
``meta``, ``is_error``) of four representative tools. They are the
refactor's safety net -- committed BEFORE any file was split, they must stay
green, unmodified, across it. Any wire-visible drift (a renamed tool, a
reshaped schema, a reordered registration, a changed result envelope) fails
here first, independent of every other test in this suite.

Pinning the literal ``model_dump`` output (rather than a hand-picked field
subset) is deliberate: an earlier version of this pin reconstructed
``tags`` as a top-level field and dropped ``execution``/``icons``/``_meta``
entirely, silently blessing a lossy projection of the wire contract (PR #364
review finding 1). Pinning ``result.data`` alone made the same mistake for
tools/call (finding 2) -- ``data`` is a client-side convenience view derived
from ``structured_content``, not what the server puts on the wire.

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

Both fixtures were verified byte-for-byte identical when captured against
the pre-split commit (ea232ac, before server.py's owner-module split) and
the post-split tree -- see the PR #364 wave-1 description for the
verification method (a throwaway git worktree at the pre-split commit,
diffed against the same capture run post-split).

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


@pytest.mark.asyncio
async def test_tools_list_contract_pin() -> None:
    """The full 36-tool registry -- every field, in registration order -- matches the pin.

    Reloads ``jarvis_mcp.server`` for a clean, unfiltered 36-tool registry
    regardless of test order (mirrors test_tool_titles.py's rationale:
    ``apply_tool_profile`` permanently mutates the shared ``mcp`` singleton).
    """
    fresh_server = importlib.reload(server)
    try:
        async with Client(fresh_server.mcp) as client:
            tools = await client.list_tools()
        actual_order = [tool.name for tool in tools]
        actual_by_name = {
            tool.name: tool.model_dump(mode="json", by_alias=True) for tool in tools
        }
    finally:
        importlib.reload(server)

    pinned = json.loads(TOOLS_LIST_PIN.read_text(encoding="utf-8"))
    pinned_order: list[str] = pinned["order"]
    pinned_by_name: dict[str, dict] = pinned["tools"]

    assert actual_order == pinned_order, (
        "jarvis tool REGISTRATION ORDER drifted from the contract pin -- a "
        "tool was added, removed, renamed, or reordered. If this is "
        f"deliberate, regenerate {TOOLS_LIST_PIN.name}.\n"
        f"pinned:  {pinned_order}\n"
        f"actual:  {actual_order}"
    )
    assert set(actual_by_name) == set(pinned_by_name)
    for name in pinned_order:
        assert actual_by_name[name] == pinned_by_name[name], (
            f"tool {name!r} FULL wire record drifted from the pin:\n"
            f"pinned:  {json.dumps(pinned_by_name[name], indent=2, sort_keys=True)}\n"
            f"actual:  {json.dumps(actual_by_name[name], indent=2, sort_keys=True)}"
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


def _envelope(result) -> dict:
    """Project a CallToolResult onto the full wire envelope this pin covers."""
    return {
        "content": [item.model_dump(mode="json") for item in result.content],
        "structured_content": result.structured_content,
        "meta": result.meta,
        "is_error": result.is_error,
    }


@pytest.mark.asyncio
async def test_jarvis_describe_package_search_call_pin(tool_call_pins) -> None:
    """Package-search discovery result envelope (the code moving to package_discovery.py)."""
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

    assert _envelope(result) == pin["result"]


@pytest.mark.asyncio
async def test_jarvis_create_pipeline_call_pin(tool_call_pins) -> None:
    """The thin pipeline-tool wrapping that stays in server.py."""
    pin = tool_call_pins["jarvis_create_pipeline"]
    with patch("jarvis_mcp.server.create_pipeline") as mock_create:
        mock_create.return_value = {"pipeline_id": "pin_pipeline", "status": "created"}
        async with Client(server.mcp) as client:
            result = await client.call_tool("jarvis_create_pipeline", pin["args"])

    assert _envelope(result) == pin["result"]


@pytest.mark.asyncio
async def test_jarvis_run_call_pin(tool_call_pins) -> None:
    """JarvisRunResult as a validated MCP tool OUTPUT SCHEMA, full envelope."""
    pin = tool_call_pins["jarvis_run"]
    with patch("jarvis_mcp.server.run_pipeline") as mock_run:
        mock_run.return_value = dict(_RUN_RESULT)
        async with Client(server.mcp) as client:
            result = await client.call_tool("jarvis_run", pin["args"])

    assert _envelope(result) == pin["result"]


@pytest.mark.asyncio
async def test_jarvis_get_execution_call_pin(tool_call_pins) -> None:
    """JarvisExecutionResult.model_validate re-validation, full envelope."""
    pin = tool_call_pins["jarvis_get_execution"]
    with patch("jarvis_mcp.server.get_execution") as mock_get:
        mock_get.return_value = dict(_EXECUTION_RESULT)
        async with Client(server.mcp) as client:
            result = await client.call_tool("jarvis_get_execution", pin["args"])

    assert _envelope(result) == pin["result"]
