"""Agent-facing package lookup and bounded discovery contract tests."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import Mock, patch

import pytest
from fastmcp.exceptions import ToolError

from jarvis_mcp.server import (
    PACKAGE_SEARCH_MAX_RESULT_BYTES,
    _PackageAgentMetadata,
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

    def metadata(package_name: str) -> _PackageAgentMetadata:
        settings_calls.append(package_name)
        return _PackageAgentMetadata(
            settings=[{"name": "mode", "default": "service"}],
            deployment=None,
        )

    with (
        patch("jarvis_mcp.server.get_manager", return_value=_manager_for(repo)),
        patch("jarvis_mcp.server._package_agent_metadata", side_effect=metadata),
    ):
        short = await jarvis_describe_tool("package", package_name="PARAVIEW")
        canonical = await jarvis_describe_tool(
            "package", package_name="builtin.paraview"
        )

    assert short["package"] == canonical["package"]
    assert short["package"]["name"] == "builtin.paraview"
    assert settings_calls == ["builtin.paraview", "builtin.paraview"]


@pytest.mark.asyncio
async def test_named_package_projects_package_owned_deployment_contract(
    tmp_path: Path,
) -> None:
    """Describe returns the package contract unchanged and without source paths."""

    repo = tmp_path / "repo"
    _write_package(repo, "site.simulator", "Generic simulation package.")
    deployment = {
        "schema_version": "jarvis.package-deployment.v1",
        "package": "site.simulator",
        "execution_profiles": [
            {
                "name": "distributed_batch",
                "execution_kind": "batch",
                "description": "Run the selected distributed simulation workload.",
                "when": [
                    {
                        "parameter": "mode",
                        "operator": "equals",
                        "value": "batch",
                    }
                ],
                "runtime_requirements": ["simulation_runtime"],
                "readiness": {
                    "mechanism": "process_exit",
                    "condition": "exit_code_zero",
                },
            }
        ],
        "runtime_requirements": [
            {
                "id": "simulation_runtime",
                "description": "Runtime capable of distributed simulation.",
                "required_capabilities": ["mpi"],
                "available_capabilities": ["mpi"],
                "status": {
                    "state": "ready",
                    "usable": True,
                    "reason_code": "provider_resolved",
                },
                "provider_resolutions": [
                    {
                        "provider": "spack",
                        "query": {"kind": "spec", "value": "simulator"},
                    }
                ],
            }
        ],
        "configuration_rules": [
            {
                "when": [
                    {
                        "parameter": "mode",
                        "operator": "equals",
                        "value": "batch",
                    }
                ],
                "requires": [
                    {
                        "parameter": "tasks",
                        "operator": "greater_than",
                        "value": 0,
                    }
                ],
                "description": "Batch execution requires at least one task.",
            }
        ],
    }
    package = Mock()
    package.configure_menu.return_value = [
        {"name": "mode", "type": str, "default": "batch"},
        {"name": "tasks", "type": int, "default": 1},
        {
            "name": "input_deck",
            "type": str,
            "default": "",
            "input_binding": {
                "schema_version": "jarvis.configuration-input-binding.v1",
                "kind": "local_file",
                "structure": "regular_file",
            },
        },
        {
            "name": "install_query",
            "type": str,
            "default": "",
            "agent_visible": False,
        },
    ]
    package.describe_deployment.return_value = deployment

    with (
        patch("jarvis_mcp.server.get_manager", return_value=_manager_for(repo)),
        patch(
            "jarvis_cd.core.pkg.Pkg.load_standalone",
            return_value=package,
        ) as load_standalone,
    ):
        result = await jarvis_describe_tool("package", package_name="site.simulator")

    description = result["package"]
    assert description["schema_version"] == "jarvis.package-description.v1"
    assert description["deployment"] == deployment
    assert description["settings"] == [
        {
            "name": "mode",
            "type": "str",
            "default": "batch",
            "required": False,
            "nullable": False,
        },
        {
            "name": "tasks",
            "type": "int",
            "default": 1,
            "required": False,
            "nullable": False,
        },
        {
            "name": "input_deck",
            "type": "str",
            "default": "",
            "required": False,
            "nullable": False,
            "input_binding": {
                "schema_version": "jarvis.configuration-input-binding.v1",
                "kind": "local_file",
                "structure": "regular_file",
            },
        },
    ]
    assert "path" not in description
    assert "install_query" not in {
        setting["name"] for setting in description["settings"]
    }
    assert "executable" not in json.dumps(description, sort_keys=True).casefold()
    load_standalone.assert_called_once_with("site.simulator")


def test_setting_projection_rejects_unversioned_or_open_input_bindings() -> None:
    """File staging authority comes only from the exact closed descriptor."""
    with pytest.raises(ValueError, match="invalid package configuration input binding"):
        _setting_from_menu_item(
            {
                "name": "input_deck",
                "type": str,
                "input_binding": {
                    "kind": "local_file",
                    "structure": "regular_file",
                    "untrusted": True,
                },
            }
        )


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
    assert package["schema_version"] == "jarvis.package-description.v1"
    deployment = package["deployment"]
    assert deployment["schema_version"] == "jarvis.package-deployment.v1"
    assert deployment["package"] == "builtin.paraview"
    assert {
        (profile["name"], profile["execution_kind"])
        for profile in deployment["execution_profiles"]
    } == {
        ("batch_script", "batch"),
        ("client_server", "service"),
        ("live_dataset_service", "service"),
    }
    assert {
        requirement["id"] for requirement in deployment["runtime_requirements"]
    } == {"paraview.batch", "paraview.server", "paraview.service"}
    for requirement in deployment["runtime_requirements"]:
        assert requirement["provider_resolutions"] == [
            {
                "provider": "spack",
                "query": {"kind": "spec", "value": "paraview"},
            }
        ]
    deployment_text = json.dumps(deployment, sort_keys=True).lower()
    assert "pvpython" not in deployment_text
    assert "pvbatch" not in deployment_text
    assert "--mesa" not in deployment_text
    assert "path" not in package
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

    def metadata(package_name: str) -> _PackageAgentMetadata:
        settings_calls.append(package_name)
        return _PackageAgentMetadata(
            settings=[{"name": "package", "default": package_name}],
            deployment=None,
        )

    with (
        patch("jarvis_mcp.server.get_manager", return_value=_manager_for(repo)),
        patch("jarvis_mcp.server._package_agent_metadata", side_effect=metadata),
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
    """Search ranks deterministically and never loads full agent metadata.

    Discovery may read a package's declared configuration menu (see
    ``test_package_search_finds_packages_by_declared_input_binding``) but must
    never take the ``_package_agent_metadata`` path, whose deployment-contract
    validation raises ``ToolError`` -- one package's bad contract must not be
    able to fail an unrelated search.
    """

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
            "jarvis_mcp.server._package_agent_metadata",
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
            "jarvis_mcp.server._package_agent_metadata",
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
async def test_package_search_finds_packages_by_declared_input_binding(
    tmp_path: Path,
) -> None:
    """A staged-input package is discoverable through its declared contract.

    Live regression (p5run2): an agent that had authored a local script
    searched ``shell`` and ``script``, and the only package it could reach
    declared no ``input_binding`` at all, so its file was never staged and the
    job ran ``bash marker.sh`` in a directory that never received the file.
    The package that DOES declare the binding was unreachable because search
    ranked over module docstrings only.
    """

    repo = tmp_path / "repo"
    _write_package(repo, "builtin.my_shell", "Launch the MyShell application.")
    _write_package(repo, "site.bounded_command", "Package for bounded commands.")
    _write_package(repo, "site.unrelated", "Unrelated application.")

    declared = {
        "builtin.my_shell": [{"name": "script", "msg": "The path of shell script."}],
        "site.bounded_command": [
            {
                "name": "command",
                "msg": "Argument vector to execute. No shell is interposed.",
            },
            {
                "name": "script",
                "msg": "Caller-local script staged onto the cluster.",
                "input_binding": {
                    "schema_version": "jarvis.configuration-input-binding.v1",
                    "kind": "local_file",
                    "structure": "regular_file",
                },
            },
        ],
    }

    def configuration_text(package_name: str) -> str:
        menu = declared.get(package_name)
        if menu is None:
            return ""
        return " ".join(
            part
            for item in menu
            for part in (
                item["name"],
                item["msg"],
                *(
                    ("input_binding", "local_file", "regular_file")
                    if "input_binding" in item
                    else ()
                ),
            )
        )

    with (
        patch("jarvis_mcp.server.get_manager", return_value=_manager_for(repo)),
        patch(
            "jarvis_mcp.server._package_configuration_search_text",
            side_effect=configuration_text,
        ),
    ):
        shell = await jarvis_describe_tool("package_search", query="shell")
        binding = await jarvis_describe_tool("package_search", query="local_file")

    # The identity match still ranks first; the declared contract adds the
    # candidate the agent could not otherwise reach.
    assert [package["name"] for package in shell["packages"]] == [
        "builtin.my_shell",
        "site.bounded_command",
    ]
    # The binding's own declared vocabulary is a capability query.
    assert [package["name"] for package in binding["packages"]] == [
        "site.bounded_command"
    ]
    # The wire projection is unchanged: identity only, never settings.
    for package in shell["packages"] + binding["packages"]:
        assert set(package) <= {"name", "short_name", "repository", "description"}


@pytest.mark.asyncio
async def test_package_search_survives_a_package_that_cannot_be_loaded(
    tmp_path: Path,
) -> None:
    """One unloadable package must not fail a whole discovery request."""

    repo = tmp_path / "repo"
    _write_package(repo, "builtin.broken", "Broken package.")
    _write_package(repo, "builtin.echo", "Echo package.")

    def explode(package_name: str) -> str:
        raise RuntimeError(f"cannot import {package_name}")

    with (
        patch("jarvis_mcp.server.get_manager", return_value=_manager_for(repo)),
        patch("jarvis_cd.core.pkg.Pkg.load_standalone", side_effect=explode),
    ):
        result = await jarvis_describe_tool("package_search", query="echo")

    assert [package["name"] for package in result["packages"]] == ["builtin.echo"]


@pytest.mark.asyncio
async def test_legacy_packages_target_remains_exhaustive_with_settings(
    tmp_path: Path,
) -> None:
    """The released exhaustive response retains its shape and full settings."""

    repo = tmp_path / "repo"
    _write_package(repo, "builtin.echo", "Echo package.")
    _write_package(repo, "builtin.paraview", "ParaView package.")

    def metadata(package_name: str) -> _PackageAgentMetadata:
        return _PackageAgentMetadata(
            settings=[{"name": "package", "default": package_name}],
            deployment=None,
        )

    with (
        patch("jarvis_mcp.server.get_manager", return_value=_manager_for(repo)),
        patch("jarvis_mcp.server._package_agent_metadata", side_effect=metadata),
    ):
        result = await jarvis_describe_tool("packages")

    assert result == {
        "target": "packages",
        "packages": [
            {
                "schema_version": "jarvis.package-description.v1",
                "name": "builtin.echo",
                "short_name": "echo",
                "description": "Echo package.",
                "deployment": None,
                "settings": [{"name": "package", "default": "builtin.echo"}],
            },
            {
                "schema_version": "jarvis.package-description.v1",
                "name": "builtin.paraview",
                "short_name": "paraview",
                "description": "ParaView package.",
                "deployment": None,
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
    assert "versioned deployment contract" in describe.description
    assert "runtime requirements" in describe.description
    assert "readiness" in describe.description
    assert "agent-visible" in describe.description
    assert "input_binding" in describe.description
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

    output_schema = describe.output_schema
    assert output_schema is not None
    result_schema = output_schema["properties"]["result"]
    package_branch = next(
        branch
        for branch in result_schema["oneOf"]
        if branch["properties"]["target"].get("const") == "package"
    )
    package_schema = package_branch["properties"]["package"]
    assert package_schema["additionalProperties"] is False
    settings_schema = next(
        option
        for option in package_schema["properties"]["settings"]["anyOf"]
        if option.get("type") == "array"
    )["items"]
    assert settings_schema["additionalProperties"] is False
    assert "default" in settings_schema["properties"]
    assert "default" not in settings_schema["required"]
    assert {"name", "required", "nullable"}.issubset(settings_schema["required"])
    deployment_schema = next(
        option
        for option in package_schema["properties"]["deployment"]["anyOf"]
        if option.get("type") == "object"
    )
    assert deployment_schema["additionalProperties"] is False
    assert deployment_schema["properties"]["schema_version"]["const"] == (
        "jarvis.package-deployment.v1"
    )
    assert set(deployment_schema["properties"]) == {
        "schema_version",
        "package",
        "execution_profiles",
        "runtime_requirements",
        "configuration_rules",
    }
    encoded_deployment_schema = json.dumps(deployment_schema, sort_keys=True)
    for required_term in (
        "execution_kind",
        "readiness",
        "provider_resolutions",
        "required_capabilities",
        "configuration_rules",
    ):
        assert required_term in encoded_deployment_schema


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
        "nullable": False,
        "aliases": ["execution_mode"],
    }


def test_null_default_is_explicitly_advertised_as_nullable() -> None:
    """Agents can distinguish an omitted default from an invalid null value."""

    assert _setting_from_menu_item(
        {
            "name": "optional_label",
            "msg": "Optional label",
            "type": str,
            "default": None,
        }
    ) == {
        "name": "optional_label",
        "description": "Optional label",
        "type": "str",
        "default": None,
        "required": False,
        "nullable": True,
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
    assert "agent-visible" in add_step.description
    config_description = properties["config"]["description"]
    assert "must not be renamed" in config_description
    assert "objects or lists" in config_description
    assert "serializes them canonically" in config_description
    assert "nullable=true" in config_description


@pytest.mark.asyncio
async def test_jarvis_run_schema_teaches_exact_spack_handoff() -> None:
    """The run tool names both ends of the cross-server runtime handoff."""

    tools = await mcp.list_tools()
    run = next(tool for tool in tools if tool.name == "jarvis_run")
    properties = run.parameters["properties"]

    assert isinstance(run.description, str)
    assert "spack_locate.output.load_spec" in run.description
    assert "jarvis_run.input.spack_specs" in run.description
    assert "executable path" in run.description
    spack_specs = properties["spack_specs"]
    assert "spack_locate.output.load_spec" in spack_specs["description"]
    assert "spack_locate.output.prefix" in spack_specs["description"]
