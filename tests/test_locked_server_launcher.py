"""Tests for reproducible embedded MCP server launches."""

from pathlib import Path

import click
import pytest

from clio_kit import (
    LOCKED_SERVER_LAUNCH_SCHEMA,
    locked_server_command,
    locked_server_environment,
    locked_server_project_identity,
)


def test_locked_server_command_uses_immutable_frozen_project(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The launcher must resolve child dependencies only from the shipped lock."""
    server_path = tmp_path / "jarvis"
    server_path.mkdir()
    (server_path / "uv.lock").write_text("version = 1\n", encoding="utf-8")
    monkeypatch.setattr("clio_kit.uv_command", lambda: "/opt/uv/bin/uv")

    command = locked_server_command(server_path, "jarvis-mcp")

    assert command == [
        "/opt/uv/bin/uv",
        "run",
        "--no-editable",
        "--frozen",
        "--project",
        str(server_path),
        "jarvis-mcp",
    ]


def test_locked_server_command_rejects_missing_lock(tmp_path: Path) -> None:
    """An embedded server without a lock must fail closed."""
    server_path = tmp_path / "spack"
    server_path.mkdir()

    with pytest.raises(click.ClickException, match="refusing an unpinned"):
        locked_server_command(server_path, "spack-mcp")


def test_locked_server_environment_is_source_and_lock_addressed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Changing server code or its lock must select a different cached environment."""
    server_path = tmp_path / "jarvis"
    source_path = server_path / "src" / "jarvis_mcp"
    source_path.mkdir(parents=True)
    (server_path / "pyproject.toml").write_text(
        "[project]\nname = 'jarvis-mcp'\nversion = '1.0.0'\n",
        encoding="utf-8",
    )
    (server_path / "uv.lock").write_text("version = 1\n", encoding="utf-8")
    module_path = source_path / "server.py"
    module_path.write_text("VALUE = 1\n", encoding="utf-8")
    monkeypatch.setenv("CLIO_KIT_CACHE_DIR", str(tmp_path / "cache"))

    first = locked_server_environment(server_path)
    first_identity = locked_server_project_identity(server_path)
    module_path.write_text("VALUE = 2\n", encoding="utf-8")
    second = locked_server_environment(server_path)
    second_identity = locked_server_project_identity(server_path)

    assert first.parent == (tmp_path / "cache" / "mcp-environments").resolve()
    assert first.name.startswith("jarvis-")
    assert first != second
    assert first_identity["schema_version"] == LOCKED_SERVER_LAUNCH_SCHEMA
    assert first_identity["server_name"] == "jarvis"
    assert len(first_identity["project_sha256"]) == 64
    assert len(first_identity["lock_sha256"]) == 64
    assert first_identity["project_sha256"] != second_identity["project_sha256"]
    assert first_identity["lock_sha256"] == second_identity["lock_sha256"]
