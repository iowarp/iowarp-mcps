"""Contributor-facing plugin authoring: scaffold, check, submit.

The marketplace indexes outside plugins rather than vendoring them, so a
contributor's directory never passes through this repository's CI. These checks
are the only thing standing between a malformed plugin and a user's install.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from click.testing import CliRunner

from clio_kit.community import read_community_entries
from clio_kit.plugins import (
    PluginProblem,
    build_community_entry,
    plugin_group,
    validate_plugin,
)


def _scaffold(directory: Path, name: str | None = None) -> None:
    args = ["init", str(directory)]
    if name is not None:
        args += ["--name", name]
    result = CliRunner().invoke(plugin_group, args)
    assert result.exit_code == 0, result.output


def test_scaffold_is_valid_the_moment_it_is_created(tmp_path: Path) -> None:
    """A contributor's first `validate` must pass, or the tool taught nothing."""
    plugin_dir = tmp_path / "materials-lab"
    _scaffold(plugin_dir)

    manifest, problems = validate_plugin(plugin_dir)

    assert problems == []
    assert manifest["name"] == "materials-lab"
    # The conventional layout is picked up on its own. Emitting component path
    # fields would hand every contributor one more thing that can point
    # somewhere that does not survive installation.
    assert not {"skills", "agents", "commands", "hooks"} & set(manifest)
    assert (plugin_dir / "skills" / "example-workflow" / "SKILL.md").is_file()
    assert (plugin_dir / ".mcp.json").is_file()


def test_scaffolding_refuses_a_name_that_would_shadow_ours(tmp_path: Path) -> None:
    """clio- is generated from this repository's own plugins."""
    result = CliRunner().invoke(
        plugin_group, ["init", str(tmp_path / "x"), "--name", "clio-materials"]
    )
    assert result.exit_code != 0
    assert "reserved" in result.output


def test_validation_catches_what_breaks_only_after_install(tmp_path: Path) -> None:
    """A path out of the plugin root works locally and fails on a user's machine."""
    plugin_dir = tmp_path / "materials-lab"
    _scaffold(plugin_dir)
    manifest_path = plugin_dir / ".claude-plugin" / "plugin.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["skills"] = "../shared/skills"
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    _, problems = validate_plugin(plugin_dir)

    assert any("leaves the plugin directory" in problem for problem in problems)


def test_validation_catches_a_skill_that_resolves_nowhere(tmp_path: Path) -> None:
    """A skill is namespaced by its directory and referred to by its name."""
    plugin_dir = tmp_path / "materials-lab"
    _scaffold(plugin_dir)
    skill = plugin_dir / "skills" / "example-workflow" / "SKILL.md"
    skill.write_text(
        skill.read_text(encoding="utf-8").replace(
            "name: example-workflow", "name: example"
        ),
        encoding="utf-8",
    )

    _, problems = validate_plugin(plugin_dir)

    assert any("but lives in" in problem for problem in problems)


def test_validation_catches_a_plugin_that_would_install_nothing(
    tmp_path: Path,
) -> None:
    """An empty plugin installs successfully and does nothing, which reads as a bug."""
    plugin_dir = tmp_path / "hollow"
    (plugin_dir / ".claude-plugin").mkdir(parents=True)
    (plugin_dir / ".claude-plugin" / "plugin.json").write_text(
        json.dumps({"name": "hollow", "description": "Nothing at all."}),
        encoding="utf-8",
    )

    _, problems = validate_plugin(plugin_dir)

    assert any("installing it would do nothing" in problem for problem in problems)


def test_an_mcp_server_needs_somewhere_to_connect(tmp_path: Path) -> None:
    """A server entry with neither a command nor a url can never start."""
    plugin_dir = tmp_path / "materials-lab"
    _scaffold(plugin_dir)
    (plugin_dir / ".mcp.json").write_text(
        json.dumps({"broken": {"args": ["--serve"]}}), encoding="utf-8"
    )

    _, problems = validate_plugin(plugin_dir)

    assert any("needs a command or a url" in problem for problem in problems)


def test_validate_reports_a_directory_that_is_not_a_plugin(tmp_path: Path) -> None:
    with pytest.raises(PluginProblem, match="plugin init"):
        validate_plugin(tmp_path)


def test_submit_refuses_a_plugin_that_would_not_publish(tmp_path: Path) -> None:
    """Submission is the wrong place to discover a problem `validate` names."""
    plugin_dir = tmp_path / "materials-lab"
    _scaffold(plugin_dir)
    manifest_path = plugin_dir / ".claude-plugin" / "plugin.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    del manifest["description"]
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    result = CliRunner().invoke(
        plugin_group, ["submit", str(plugin_dir), "--repo", "some-lab/materials"]
    )

    assert result.exit_code != 0
    assert "no description" in result.output


def test_submit_round_trips_into_a_marketplace_entry(tmp_path: Path) -> None:
    """What `submit` writes must be what the generator reads back."""
    plugin_dir = tmp_path / "plugin" / "materials-lab"
    _scaffold(plugin_dir)
    manifest_path = plugin_dir / ".claude-plugin" / "plugin.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["description"] = "Crystal structure skills."
    manifest["author"] = {"name": "some-lab"}
    manifest["keywords"] = ["materials"]
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    checkout = tmp_path / "clio-kit"
    entry_path = checkout / "community" / "entries" / "materials-lab.toml"
    entry_path.parent.mkdir(parents=True)
    result = CliRunner().invoke(
        plugin_group,
        [
            "submit",
            str(plugin_dir),
            "--repo",
            "some-lab/materials-agent-skills",
            "--output",
            str(entry_path),
        ],
    )
    assert result.exit_code == 0, result.output

    entries = read_community_entries(checkout)

    assert len(entries) == 1
    assert entries[0]["source"] == {
        "source": "github",
        "repo": "some-lab/materials-agent-skills",
    }
    assert entries[0]["metadata"] == {"maintainer": "some-lab", "indexed": True}


def test_submit_rejects_a_repository_that_is_not_owner_slash_name(
    tmp_path: Path,
) -> None:
    plugin_dir = tmp_path / "materials-lab"
    _scaffold(plugin_dir)
    manifest_path = plugin_dir / ".claude-plugin" / "plugin.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["description"] = "Crystal structure skills."
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    result = CliRunner().invoke(
        plugin_group,
        ["submit", str(plugin_dir), "--repo", "https://github.com/some-lab/materials"],
    )

    assert result.exit_code != 0
    assert "owner/name" in result.output


def test_entry_falls_back_to_community_when_no_category_is_declared() -> None:
    entry = build_community_entry({"name": "x", "description": "d"}, "owner/repo")

    assert 'category    = "community"' in entry
    assert 'repo = "owner/repo"' in entry
