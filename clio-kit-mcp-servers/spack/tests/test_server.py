"""Tests for the compact Spack MCP tool surface."""

from __future__ import annotations

import importlib
import json
import os
import sys
from pathlib import Path

import pytest
from fastmcp.exceptions import ToolError

from spack_mcp import server
from spack_mcp.backend import SpackBackendError, SpackFindResult


@pytest.mark.asyncio
async def test_find_returns_typed_result(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        server,
        "find_installed",
        lambda query: SpackFindResult(query=query, packages=[], count=0),
    )

    result = await server.spack_find_tool("missing")

    assert result.operation == "find"
    assert result.count == 0


@pytest.mark.asyncio
async def test_install_forwards_explicit_reuse_false(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    observed: dict[str, object] = {}

    def install(spec: str, *, reuse: bool, timeout_seconds: int) -> object:
        observed.update(
            spec=spec,
            reuse=reuse,
            timeout_seconds=timeout_seconds,
        )
        return object()

    monkeypatch.setattr(server, "install_spec", install)

    result = await server.spack_install_tool(
        "lammps@20250722.1",
        reuse=False,
        timeout_seconds=30,
    )

    assert result is not None
    assert observed == {
        "spec": "lammps@20250722.1",
        "reuse": False,
        "timeout_seconds": 30,
    }


@pytest.mark.asyncio
async def test_backend_failures_become_is_error_tool_errors(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fail(spec: str) -> object:
        raise SpackBackendError(
            "not_installed",
            f"missing: {spec}",
            operation="locate",
        )

    monkeypatch.setattr(server, "locate_installed", fail)

    with pytest.raises(ToolError) as error:
        await server.spack_locate_tool("missing")

    assert json.loads(str(error.value))["error"]["code"] == "not_installed"


def test_user_surface_hides_environment_materialization() -> None:
    assert server.USER_TOOLS == {"spack_find", "spack_locate", "spack_install"}
    assert "spack_environment" not in server.USER_TOOLS
    assert "spack_load" not in server.USER_TOOLS | server.ADMIN_TOOLS


def test_capabilities_assign_runtime_environment_to_jarvis() -> None:
    capabilities = server.spack_capabilities()

    assert capabilities["stateful_load_exposed"] is False
    assert capabilities["runtime_owner"] == "jarvis_run"


@pytest.mark.asyncio
async def test_install_annotation_discloses_open_world_interaction() -> None:
    """Install may contact repositories and build caches outside the MCP server."""
    fresh_server = importlib.reload(server)
    try:
        tools = await fresh_server.mcp.list_tools(run_middleware=False)
        install = next(tool for tool in tools if tool.name == "spack_install")
        assert install.annotations is not None
        assert install.annotations.openWorldHint is True
    finally:
        importlib.reload(server)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("profile", "expected"),
    [
        ("user", {"spack_find", "spack_locate", "spack_install"}),
        ("admin", {"spack_environment"}),
        (
            "all",
            {"spack_find", "spack_locate", "spack_install", "spack_environment"},
        ),
    ],
)
async def test_profiles_enforce_real_fastmcp_tool_surface(
    profile: str,
    expected: set[str],
) -> None:
    fresh_server = importlib.reload(server)
    try:
        fresh_server.apply_tool_profile(profile)
        tools = await fresh_server.mcp.list_tools(run_middleware=False)
        assert {tool.name for tool in tools} == expected
    finally:
        importlib.reload(server)


def test_main_sets_validated_spack_command(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    command = tmp_path / "spack"
    command.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
    command.chmod(0o755)
    fresh_server = importlib.reload(server)
    try:
        monkeypatch.setattr(
            sys,
            "argv",
            ["spack-mcp", "--spack-command", str(command)],
        )
        monkeypatch.delenv("SPACK_MCP_COMMAND", raising=False)
        monkeypatch.setattr(fresh_server.mcp, "run", lambda **kwargs: None)

        fresh_server.main()

        assert Path(os.environ["SPACK_MCP_COMMAND"]) == command.resolve()
    finally:
        importlib.reload(server)


def test_main_rejects_missing_spack_command(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setattr(
        sys,
        "argv",
        ["spack-mcp", "--spack-command", str(tmp_path / "missing-spack")],
    )

    with pytest.raises(SystemExit) as error:
        server.main()

    assert error.value.code == 2
