"""Agent-facing package lookup and bounded discovery contract tests."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import Mock, patch

import pytest
from fastmcp.exceptions import ToolError

from jarvis_mcp.server import (
    PACKAGE_SEARCH_MAX_RESULT_BYTES,
    _setting_from_menu_item,
    jarvis_describe_tool,
    mcp,
)


def _write_package(repo: Path, canonical_name: str, description: str) -> Path:
    """Create one repository package using the current ``pkg.py`` layout."""

    package_dir = repo.joinpath(*canonical_name.split("."))
    package_dir.mkdir(parents=True, exist_ok=True)
    package_file = package_dir / "pkg.py"
    package_file.write_text(f'"""{description}"""\n', encoding="utf-8")
    return package_file


def _manager_for(repo: Path) -> Mock:
    """Return a manager exposing exactly one registered test repository."""

    manager = Mock()
    manager.list_repos.return_value = [repo]
    return manager


@pytest.mark.asyncio
async def test_named_package_loads_settings_for_only_the_selected_package(
    tmp_path: Path,
) -> None:
    """Exact short/full lookup must not instantiate the entire repository."""

    repo = tmp_path / "repo"
    _write_package(repo, "builtin.echo", "Echo package.")
    _write_package(repo, "builtin.paraview", "ParaView package.")
    _write_package(repo, "site.solver", "Solver package.")
    settings_calls: list[str] = []

    def settings(package_name: str) -> list[dict[str, object]]:
        settings_calls.append(package_name)
        return [{"name": "mode", "default": "service"}]

    with (
        patch("jarvis_mcp.server.get_manager", return_value=_manager_for(repo)),
        patch("jarvis_mcp.server._package_settings", side_effect=settings),
    ):
        short = await jarvis_describe_tool("package", package_name="PARAVIEW")
        canonical = await jarvis_describe_tool(
            "package", package_name="builtin.paraview"
        )

    assert short["package"] == canonical["package"]
    assert short["package"]["name"] == "builtin.paraview"
    assert settings_calls == ["builtin.paraview", "builtin.paraview"]


@pytest.mark.asyncio
async def test_paraview_description_is_semantic_not_site_runtime_configuration(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """The exact released JARVIS package gives agents no launcher escape hatch."""
    from jarvis_cd.core.config import Jarvis  # type: ignore[import-untyped]

    monkeypatch.setattr(Jarvis, "_instance", None)
    jarvis = Jarvis(jarvis_root=str(tmp_path / "jarvis"))
    jarvis.initialize(
        str(tmp_path / "config"),
        str(tmp_path / "private"),
        str(tmp_path / "shared"),
    )
    repositories = [Path(value) for value in jarvis.repos["repos"]]

    with patch(
        "jarvis_mcp.server.get_manager",
        return_value=Mock(list_repos=Mock(return_value=repositories)),
    ):
        result = await jarvis_describe_tool("package", package_name="paraview")

    package = result["package"]
    assert package["name"] == "builtin.paraview"
    settings = {setting["name"]: setting for setting in package["settings"]}
    assert settings["mode"]["default"] == "server"
    assert "service for a live dataset view" in settings["mode"]["description"]
    assert settings["dataset_descriptor"]["default"] == ""
    assert "requires mode=service" in settings["dataset_descriptor"]["description"]
    assert settings["force_offscreen_rendering"]["default"] is False
    assert (
        "service mode is always headless"
        in settings["force_offscreen_rendering"]["description"]
    )
    assert {
        "pvpython_bin",
        "pvpython_options",
        "pvbatch_bin",
        "pvbatch_options",
    }.isdisjoint(settings)


@pytest.mark.asyncio
async def test_ambiguous_short_name_fails_with_canonical_candidates(
    tmp_path: Path,
) -> None:
    """A short name shared by repositories cannot silently select one package."""

    repo = tmp_path / "repo"
    _write_package(repo, "builtin.solver", "Builtin solver.")
    _write_package(repo, "site.solver", "Site solver.")
    settings_calls: list[str] = []

    def settings(package_name: str) -> list[dict[str, object]]:
        settings_calls.append(package_name)
        return [{"name": "package", "default": package_name}]

    with (
        patch("jarvis_mcp.server.get_manager", return_value=_manager_for(repo)),
        patch("jarvis_mcp.server._package_settings", side_effect=settings),
    ):
        with pytest.raises(
            ToolError,
            match=(
                r"package short name is ambiguous: solver; use one of: "
                r"builtin\.solver, site\.solver"
            ),
        ):
            await jarvis_describe_tool("package", package_name="solver")
        selected = await jarvis_describe_tool("package", package_name="site.solver")

    assert selected["package"]["name"] == "site.solver"
    assert settings_calls == ["site.solver"]


@pytest.mark.asyncio
async def test_package_search_is_ranked_summary_only_and_cursor_bound(
    tmp_path: Path,
) -> None:
    """Search ranks deterministically without importing package settings."""

    repo = tmp_path / "repo"
    _write_package(repo, "builtin.paraview", "Generic visualization runtime.")
    _write_package(repo, "site.paraview_helper", "Site helper.")
    visual_file = _write_package(
        repo,
        "site.visual",
        "Scientific ParaView server for remote rendering.",
    )
    _write_package(repo, "site.unrelated", "Unrelated application.")

    with (
        patch("jarvis_mcp.server.get_manager", return_value=_manager_for(repo)),
        patch(
            "jarvis_mcp.server._package_settings",
            side_effect=AssertionError("search must not load settings"),
        ),
    ):
        first = await jarvis_describe_tool(
            "package_search", query="ParaView", page_size=2
        )
        cursor = first["next_cursor"]
        assert isinstance(cursor, str)
        second = await jarvis_describe_tool(
            "package_search",
            query="ParaView",
            page_size=2,
            cursor=cursor,
        )
        with pytest.raises(ToolError, match="does not match the requested query"):
            await jarvis_describe_tool(
                "package_search",
                query="solver",
                page_size=2,
                cursor=cursor,
            )

        visual_file.write_text(
            '"""Changed Scientific ParaView server description."""\n',
            encoding="utf-8",
        )
        with pytest.raises(ToolError, match="package inventory changed"):
            await jarvis_describe_tool(
                "package_search",
                query="ParaView",
                page_size=2,
                cursor=cursor,
            )

    assert first["schema_version"] == "jarvis.package-search.v1"
    assert first["target"] == "package_search"
    assert first["total_matches"] == 3
    assert [package["name"] for package in first["packages"]] == [
        "builtin.paraview",
        "site.paraview_helper",
    ]
    assert [package["name"] for package in second["packages"]] == ["site.visual"]
    assert second["next_cursor"] is None
    assert all("settings" not in package for package in first["packages"])
    assert all("path" not in package for package in first["packages"])
    assert "paraview" not in cursor.casefold()


@pytest.mark.asyncio
async def test_package_search_enforces_response_byte_ceiling(tmp_path: Path) -> None:
    """Large repositories are shortened into safe pages with continuations."""

    repo = tmp_path / "repo"
    description = "Searchable package. " + ("\u6e2c" * 20_000)
    for index in range(60):
        _write_package(repo, f"site.package_{index:03d}", description)

    with (
        patch("jarvis_mcp.server.get_manager", return_value=_manager_for(repo)),
        patch(
            "jarvis_mcp.server._package_settings",
            side_effect=AssertionError("search must not load settings"),
        ),
    ):
        result = await jarvis_describe_tool(
            "package_search", query="package", page_size=25
        )

    encoded = json.dumps(
        result,
        allow_nan=False,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    assert len(encoded) <= PACKAGE_SEARCH_MAX_RESULT_BYTES
    assert 0 < result["returned_count"] < 25
    assert result["total_matches"] == 60
    assert isinstance(result["next_cursor"], str)


@pytest.mark.asyncio
async def test_legacy_packages_target_remains_exhaustive_with_settings(
    tmp_path: Path,
) -> None:
    """The released exhaustive response retains its shape and full settings."""

    repo = tmp_path / "repo"
    echo_file = _write_package(repo, "builtin.echo", "Echo package.")
    paraview_file = _write_package(repo, "builtin.paraview", "ParaView package.")

    def settings(package_name: str) -> list[dict[str, object]]:
        return [{"name": "package", "default": package_name}]

    with (
        patch("jarvis_mcp.server.get_manager", return_value=_manager_for(repo)),
        patch("jarvis_mcp.server._package_settings", side_effect=settings),
    ):
        result = await jarvis_describe_tool("packages")

    assert result == {
        "target": "packages",
        "packages": [
            {
                "name": "builtin.echo",
                "short_name": "echo",
                "description": "Echo package.",
                "path": str(echo_file),
                "settings": [{"name": "package", "default": "builtin.echo"}],
            },
            {
                "name": "builtin.paraview",
                "short_name": "paraview",
                "description": "ParaView package.",
                "path": str(paraview_file),
                "settings": [{"name": "package", "default": "builtin.paraview"}],
            },
        ],
    }


@pytest.mark.asyncio
async def test_jarvis_describe_schema_teaches_exact_then_bounded_discovery() -> None:
    """The generated MCP schema steers agents away from exhaustive discovery."""

    tools = await mcp.list_tools()
    describe = next(tool for tool in tools if tool.name == "jarvis_describe")
    properties = describe.parameters["properties"]

    assert properties["target"]["enum"] == [
        "packages",
        "package_search",
        "package",
        "pipeline",
        "step",
    ]
    assert isinstance(describe.description, str)
    assert "named application" in describe.description
    assert (
        "unique short name or fully qualified"
        in properties["package_name"]["description"]
    )
    assert "Ambiguous short names fail" in properties["package_name"]["description"]
    query_text = next(
        option
        for option in properties["query"]["anyOf"]
        if option.get("type") == "string"
    )
    assert query_text["maxLength"] == 256
    assert properties["page_size"] == {
        "default": 10,
        "description": (
            "Maximum summary matches returned by target='package_search'; bounded to 25."
        ),
        "maximum": 25,
        "minimum": 1,
        "type": "integer",
    }
    assert "only for target='pipeline'" in properties["include_yaml"]["description"]


def test_package_setting_preserves_agent_relevant_parser_metadata() -> None:
    """Package-owned choices, requirements, and aliases survive discovery."""

    assert _setting_from_menu_item(
        {
            "name": "mode",
            "msg": "Execution mode",
            "type": str,
            "default": "service",
            "choices": ("service", "batch"),
            "required": True,
            "aliases": ("execution_mode",),
        }
    ) == {
        "name": "mode",
        "description": "Execution mode",
        "type": "str",
        "default": "service",
        "choices": ["service", "batch"],
        "required": True,
        "aliases": ["execution_mode"],
    }


@pytest.mark.asyncio
async def test_jarvis_add_step_schema_is_exact_and_has_no_user_bypass() -> None:
    """The compact user mutation teaches exact keys and always configures."""

    tools = await mcp.list_tools()
    add_step = next(tool for tool in tools if tool.name == "jarvis_add_step")
    legacy_append = next(tool for tool in tools if tool.name == "append_pkg")
    properties = add_step.parameters["properties"]

    assert "do_configure" not in properties
    assert "do_configure" in legacy_append.parameters["properties"]
    assert isinstance(add_step.description, str)
    assert "canonical setting names exactly" in add_step.description
    config_description = properties["config"]["description"]
    assert "must not be renamed" in config_description
    assert "objects or lists" in config_description
    assert "serializes them canonically" in config_description
