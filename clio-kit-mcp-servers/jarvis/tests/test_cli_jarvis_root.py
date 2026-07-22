"""Focused tests for operator-selected JARVIS roots."""

from __future__ import annotations

import importlib
import os
import sys
from pathlib import Path
from unittest.mock import patch

import pytest


@pytest.mark.parametrize(
    ("module_name", "command"),
    [
        ("jarvis_mcp.server", "jarvis-mcp"),
        ("jarvis_mcp.user_server", "jarvis-user-mcp"),
        ("jarvis_mcp.admin_server", "jarvis-admin-mcp"),
    ],
)
def test_entrypoints_set_validated_jarvis_root_before_serving(
    tmp_path: Path,
    module_name: str,
    command: str,
) -> None:
    """Every entrypoint applies the resolved root before starting its server."""
    jarvis_root = tmp_path / "isolated root"
    jarvis_root.mkdir()
    observed_roots: list[str | None] = []

    def capture_run(**_kwargs: object) -> None:
        observed_roots.append(os.environ.get("JARVIS_ROOT"))

    if module_name != "jarvis_mcp.server":
        sys.modules.pop(module_name, None)
    with (
        patch("sys.argv", [command, "--jarvis-root", str(jarvis_root)]),
        patch.dict("os.environ", {}, clear=True),
        patch("jarvis_mcp.server.apply_tool_profile"),
        patch("jarvis_mcp.server.mcp.run", side_effect=capture_run),
    ):
        module = importlib.import_module(module_name)
        module.main()

    assert observed_roots == [str(jarvis_root.resolve())]


@pytest.mark.parametrize("invalid_kind", ["missing", "file"])
def test_main_rejects_non_directory_jarvis_root(
    tmp_path: Path,
    invalid_kind: str,
) -> None:
    """The operator option fails before serving unless its root is a directory."""
    invalid_root = tmp_path / invalid_kind
    if invalid_kind == "file":
        invalid_root.write_text("not a directory", encoding="utf-8")

    with (
        patch("sys.argv", ["jarvis-mcp", "--jarvis-root", str(invalid_root)]),
        patch("jarvis_mcp.server.mcp.run") as run_server,
        pytest.raises(SystemExit) as error,
    ):
        from jarvis_mcp.server import main

        main()

    assert error.value.code == 2
    run_server.assert_not_called()
