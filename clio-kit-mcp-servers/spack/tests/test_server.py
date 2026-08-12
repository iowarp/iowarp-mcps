"""Tests for the compact Spack MCP tool surface."""

from __future__ import annotations

import argparse
import importlib
import json
import os
import runpy
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest
from fastmcp.exceptions import ToolError

from spack_mcp import server
from spack_mcp.backend import (
    SpackBackendError,
    SpackEnvironmentResult,
    SpackFindResult,
)


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
async def test_locate_tools_list_teaches_exact_jarvis_handoff() -> None:
    """Agents can discover the cross-server handoff before calling locate."""

    tools = await server.mcp.list_tools(run_middleware=False)
    locate = next(tool for tool in tools if tool.name == "spack_locate")

    assert isinstance(locate.description, str)
    assert "spack_locate.output.load_spec" in locate.description
    assert "jarvis_run.input.spack_specs" in locate.description
    assert "executable path" in locate.description
    assert locate.output_schema is not None
    load_spec = locate.output_schema["properties"]["load_spec"]
    assert "spack_locate.output.load_spec" in load_spec["description"]
    assert "jarvis_run.input.spack_specs" in load_spec["description"]


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
    monkeypatch.setattr(server, "enrich_not_installed", lambda error, spec: error)

    with pytest.raises(ToolError) as error:
        await server.spack_locate_tool("missing")

    assert json.loads(str(error.value))["error"]["code"] == "not_installed"


@pytest.mark.asyncio
async def test_locate_not_installed_error_is_enriched_with_recipe_availability(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """spack_locate composes with recipe-availability so an agent learns whether
    to call spack_install or give up, instead of a bare not_installed."""

    def fail(spec: str) -> object:
        raise SpackBackendError("not_installed", f"missing: {spec}", operation="locate")

    observed: dict[str, object] = {}

    def enrich(error: SpackBackendError, spec: str) -> SpackBackendError:
        observed.update(code=error.code, spec=spec)
        return SpackBackendError(
            error.code,
            error.message,
            operation=error.operation,
            detail="recipe available in repo 'builtin' via spack_install",
        )

    monkeypatch.setattr(server, "locate_installed", fail)
    monkeypatch.setattr(server, "enrich_not_installed", enrich)

    with pytest.raises(ToolError) as error:
        await server.spack_locate_tool("lammps")

    payload = json.loads(str(error.value))
    assert observed == {"code": "not_installed", "spec": "lammps"}
    assert payload["error"]["detail"] == "recipe available in repo 'builtin' via spack_install"


@pytest.mark.asyncio
async def test_search_tool_forwards_query(monkeypatch: pytest.MonkeyPatch) -> None:
    observed: dict[str, object] = {}

    def search(query: str) -> object:
        observed["query"] = query
        return object()

    monkeypatch.setattr(server, "search_packages", search)

    result = await server.spack_search_tool("lammps")

    assert result is not None
    assert observed == {"query": "lammps"}


@pytest.mark.asyncio
async def test_info_tool_forwards_package(monkeypatch: pytest.MonkeyPatch) -> None:
    observed: dict[str, object] = {}

    def describe(package: str) -> object:
        observed["package"] = package
        return object()

    monkeypatch.setattr(server, "describe_package", describe)

    result = await server.spack_info_tool("hdf5")

    assert result is not None
    assert observed == {"package": "hdf5"}


def test_user_surface_hides_environment_materialization() -> None:
    assert server.USER_TOOLS == {
        "spack_find",
        "spack_locate",
        "spack_search",
        "spack_info",
        "spack_install",
    }
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
async def test_environment_admin_tool_returns_structured_delta(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    expected = SpackEnvironmentResult(
        specs=["demo"],
        environment={"PATH": "/spack/bin"},
        variable_names=["PATH"],
        environment_sha256="digest",
    )
    monkeypatch.setattr(server, "resolve_environment", lambda _specs: expected)

    assert await server.spack_environment_tool(["demo"]) is expected


def test_prepare_prompt_and_invalid_profile_are_explicit() -> None:
    prompt = server.prepare_spack_package("demo@1")
    assert len(prompt) == 1
    assert "spack_find" in prompt[0].content.text
    with pytest.raises(ValueError, match="profile must be one of"):
        server.apply_tool_profile("operator")


def test_spack_command_path_rejects_a_directory(tmp_path: Path) -> None:
    with pytest.raises(argparse.ArgumentTypeError, match="not a file"):
        server._spack_command_path(str(tmp_path))


def test_spack_command_path_rejects_nonexecutable_posix_file(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    command = tmp_path / "spack"
    command.write_text("", encoding="utf-8")
    monkeypatch.setattr(
        server,
        "os",
        SimpleNamespace(name="posix", access=lambda *_args: False, X_OK=1),
    )
    with pytest.raises(argparse.ArgumentTypeError, match="not executable"):
        server._spack_command_path(str(command))


def test_main_runs_http_and_admin_main_selects_admin_profile(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fresh_server = importlib.reload(server)
    observed: list[dict[str, object]] = []
    profiles: list[str] = []
    try:
        monkeypatch.setattr(
            sys,
            "argv",
            ["spack-mcp", "--transport", "http", "--host", "127.0.0.1"],
        )
        monkeypatch.setattr(fresh_server.mcp, "run", lambda **kwargs: observed.append(kwargs))
        monkeypatch.setattr(
            fresh_server, "apply_tool_profile", lambda profile: profiles.append(profile)
        )
        fresh_server.main()
        assert observed == [{"transport": "http", "host": "127.0.0.1", "port": 8000}]
        assert profiles == ["user"]

        called: list[bool] = []
        monkeypatch.setattr(fresh_server, "main", lambda: called.append(True))
        monkeypatch.delenv("SPACK_MCP_PROFILE", raising=False)
        fresh_server.admin_main()
        assert called == [True]
        assert os.environ["SPACK_MCP_PROFILE"] == "admin"
    finally:
        importlib.reload(server)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("profile", "expected"),
    [
        (
            "user",
            {"spack_find", "spack_locate", "spack_search", "spack_info", "spack_install"},
        ),
        ("admin", {"spack_environment"}),
        (
            "all",
            {
                "spack_find",
                "spack_locate",
                "spack_search",
                "spack_info",
                "spack_install",
                "spack_environment",
            },
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


@pytest.mark.parametrize(
    ("module_name", "arguments", "environment_transport", "expected_run"),
    [
        (
            "spack_mcp.user_server",
            ["--transport", "stdio"],
            "http",
            {"transport": "stdio"},
        ),
        (
            "spack_mcp.admin_server",
            ["--transport", "http", "--host", "127.0.0.1", "--port", "9012"],
            "stdio",
            {"transport": "http", "host": "127.0.0.1", "port": 9012},
        ),
        (
            "spack_mcp.admin_server",
            ["--transport", "stdio"],
            "http",
            {"transport": "stdio"},
        ),
    ],
)
def test_profile_entrypoints_execute_selected_transport(
    monkeypatch: pytest.MonkeyPatch,
    module_name: str,
    arguments: list[str],
    environment_transport: str,
    expected_run: dict[str, object],
) -> None:
    fresh_server = importlib.reload(server)
    observed: list[dict[str, object]] = []
    try:
        monkeypatch.setattr(sys, "argv", [module_name, *arguments])
        monkeypatch.setenv("MCP_TRANSPORT", environment_transport)
        monkeypatch.setattr(
            fresh_server.mcp,
            "run",
            lambda **kwargs: observed.append(kwargs),
        )

        runpy.run_module(module_name, run_name="__main__")

        assert observed == [expected_run]
    finally:
        importlib.reload(server)


def test_admin_entrypoint_sets_validated_spack_command_from_environment_transport(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    command = tmp_path / "spack"
    command.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
    command.chmod(0o755)
    fresh_server = importlib.reload(server)
    observed: list[dict[str, object]] = []
    try:
        monkeypatch.setattr(
            sys,
            "argv",
            ["spack-admin-mcp", "--spack-command", str(command)],
        )
        monkeypatch.setenv("MCP_TRANSPORT", "http")
        monkeypatch.delenv("SPACK_MCP_COMMAND", raising=False)
        monkeypatch.setattr(
            fresh_server.mcp,
            "run",
            lambda **kwargs: observed.append(kwargs),
        )

        runpy.run_module("spack_mcp.admin_server", run_name="__main__")

        assert Path(os.environ["SPACK_MCP_COMMAND"]) == command.resolve()
        assert observed == [{"transport": "http", "host": "0.0.0.0", "port": 8000}]
    finally:
        importlib.reload(server)


def test_user_entrypoint_sets_command_and_runs_http(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    command = tmp_path / "spack"
    command.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
    command.chmod(0o755)
    fresh_server = importlib.reload(server)
    observed: list[dict[str, object]] = []
    try:
        monkeypatch.setattr(
            sys,
            "argv",
            ["spack-mcp", "--transport", "http", "--spack-command", str(command)],
        )
        monkeypatch.delenv("SPACK_MCP_COMMAND", raising=False)
        monkeypatch.setattr(
            fresh_server.mcp,
            "run",
            lambda **kwargs: observed.append(kwargs),
        )

        runpy.run_module("spack_mcp.user_server", run_name="__main__")

        assert Path(os.environ["SPACK_MCP_COMMAND"]) == command.resolve()
        assert observed == [{"transport": "http", "host": "0.0.0.0", "port": 8000}]
    finally:
        importlib.reload(server)
