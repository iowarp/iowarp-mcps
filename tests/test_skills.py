"""The shipped skills must stay true to the contracts they describe.

A skill hard-codes tool names and the servers they live on. Nothing else in the
build notices when a tool is renamed, merged into another server, or removed, so
a skill is the one asset here that can quietly become wrong while every other
check stays green. These tests are that notice.
"""

import json
import re
from pathlib import Path

import pytest
from click.testing import CliRunner

from clio_kit import main
from clio_kit.skills import (
    _shipped_root,
    discover_skills,
    find_skills_root,
    format_skill_listing,
    install_skills,
    parse_frontmatter,
    validate_skill,
)

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
TOOL_REFERENCE = re.compile(r"`([a-z][a-z0-9_]*)`")


def _shipped_tools_by_server() -> dict[str, set[str]]:
    """Map the client-facing server name to the tools it exposes.

    Clients register these servers as ``clio-<name>`` -- that is what the
    generated Claude Desktop, Claude Code and Gemini configs all use -- so a
    skill's fully qualified references are checked against the same names an
    agent would actually see.
    """
    servers = REPOSITORY_ROOT / "clio-kit-mcp-servers"
    return {
        f"clio-{manifest.parent.name}": {
            tool["name"]
            for tool in json.loads(manifest.read_text(encoding="utf-8")).get(
                "tools", []
            )
        }
        for manifest in servers.glob("*/server.json")
    }


def _shipped_server_names() -> set[str]:
    return set(_shipped_tools_by_server())


SKILLS = sorted(discover_skills(REPOSITORY_ROOT / "skills").items())


def test_the_repository_ships_at_least_one_skill() -> None:
    assert SKILLS, (
        "skills/ is empty; the launcher's skill commands have nothing to serve"
    )


@pytest.mark.parametrize("name,manifest", SKILLS, ids=[n for n, _ in SKILLS])
def test_shipped_skill_satisfies_every_rule(name: str, manifest: Path) -> None:
    """The suite and `clio-kit skills-validate` enforce one implementation.

    validate_skill covers the frontmatter, the more-than-one-server rule, and
    the tool declarations in both directions -- declared tools must exist on the
    server named and be used in the steps, and tools used in the steps must be
    declared. Sharing it means an externally authored skill is held to exactly
    the rules the shipped collection is.
    """
    problems = validate_skill(manifest, _shipped_tools_by_server())

    assert not problems, f"{name}: " + "; ".join(problems)


def test_validation_reports_every_problem_at_once(tmp_path: Path) -> None:
    """Fixing one problem per build is the slow way to write a skill."""
    skill = tmp_path / "broken-skill"
    skill.mkdir()
    (skill / "SKILL.md").write_text(
        "---\n"
        "name: wrong-name\n"
        "description: Does a thing.\n"
        "category: Custom\n"
        "servers: clio-hdf5\n"
        "tools: clio-hdf5:get_shape, clio-hdf5:no_such_tool\n"
        "---\n"
        "Call `get_shape`.\n",
        encoding="utf-8",
    )

    problems = validate_skill(skill / "SKILL.md", _shipped_tools_by_server())

    assert any("does not match" in p for p in problems)
    assert any("when to use" in p for p in problems)
    assert any("more than one server" in p for p in problems)
    assert any("does not expose 'no_such_tool'" in p for p in problems)
    assert any("without a server prefix" in p for p in problems)


def test_an_external_skill_can_be_validated_against_this_kit(tmp_path: Path) -> None:
    """Third parties writing skills for these servers get the same guard."""
    skill = tmp_path / "checking-node-health-before-a-run"
    skill.mkdir()
    (skill / "SKILL.md").write_text(
        "---\n"
        "name: checking-node-health-before-a-run\n"
        "description: Checks a node before submitting. Use when a job must not "
        "land on an unhealthy node.\n"
        "category: Custom\n"
        "servers: clio-node-hardware, clio-slurm\n"
        "tools: clio-node-hardware:health_check, clio-slurm:slurm_cluster\n"
        "---\n"
        "Run `clio-node-hardware:health_check`, then `clio-slurm:slurm_cluster`.\n",
        encoding="utf-8",
    )

    assert validate_skill(skill / "SKILL.md", _shipped_tools_by_server()) == []


def test_skill_names_follow_one_convention() -> None:
    """A mixed collection is harder to search and reference."""
    for name, _ in SKILLS:
        assert name.islower() and " " not in name and "_" not in name, name
        assert len(name) <= 64, name
        assert name.split("-")[0].endswith("ing"), (
            f"{name} should use the gerund form the collection settled on"
        )


def test_listing_reports_each_skill_with_its_description() -> None:
    lines = format_skill_listing(REPOSITORY_ROOT / "skills")

    categories = {
        parse_frontmatter(m.read_text(encoding="utf-8"))["category"] for _, m in SKILLS
    }
    for category in categories:
        assert f"{category}:" in lines
    for name, _ in SKILLS:
        assert any(name in line for line in lines)


def test_missing_skills_directory_reports_rather_than_raises(tmp_path: Path) -> None:
    assert discover_skills(tmp_path / "absent") == {}
    assert format_skill_listing(tmp_path / "absent") == ["No skills found."]


def test_frontmatter_parsing_ignores_a_body_without_one() -> None:
    assert parse_frontmatter("# Just a heading\n") == {}
    assert parse_frontmatter("---\nname: x\n") == {}, (
        "unterminated block is not frontmatter"
    )


def test_skills_root_resolves_inside_the_source_checkout() -> None:
    assert find_skills_root(REPOSITORY_ROOT / "src" / "clio_kit") == (
        REPOSITORY_ROOT / "skills"
    )
    assert _shipped_root().is_dir()


def test_cli_prints_a_skill_and_rejects_an_unknown_one() -> None:
    runner = CliRunner()
    name = SKILLS[0][0]

    shown = runner.invoke(main, ["skill", name])
    assert shown.exit_code == 0
    assert f"name: {name}" in shown.output

    missing = runner.invoke(main, ["skill", "no-such-skill"])
    assert missing.exit_code == 1
    assert "Unknown skill" in missing.output
    assert name in missing.output


def test_the_skills_plugin_manifest_matches_what_ships() -> None:
    """The plugin is generated, so it cannot drift from the collection."""
    manifest = json.loads(
        (REPOSITORY_ROOT / ".claude-plugin" / "plugin.json").read_text(encoding="utf-8")
    )

    assert manifest["name"] == "clio-skills"
    assert manifest["skills"] == "./skills/", (
        "must point at the repository's skills directory, the documented layout"
    )
    for name, _ in SKILLS:
        assert name in manifest["description"]


def test_the_marketplace_offers_the_skills_plugin() -> None:
    """`/plugin install` has to be able to reach the workflows, not just servers."""
    marketplace = json.loads(
        (REPOSITORY_ROOT / ".claude-plugin" / "marketplace.json").read_text(
            encoding="utf-8"
        )
    )
    entry = next(p for p in marketplace["plugins"] if p["name"] == "clio-skills")

    assert entry["source"] == "./"
    assert entry["category"] == "workflows"


def test_installing_replaces_a_stale_copy_rather_than_merging(tmp_path: Path) -> None:
    """An upgrade must not leave a file from the previous release behind."""
    destination = tmp_path / "skills"
    first = install_skills(REPOSITORY_ROOT / "skills", destination)
    stale = destination / first[0] / "LEFTOVER.md"
    stale.write_text("from an older release", encoding="utf-8")

    second = install_skills(REPOSITORY_ROOT / "skills", destination)

    assert sorted(second) == sorted(first)
    assert not stale.exists()
    assert (destination / first[0] / "SKILL.md").is_file()


def test_installing_into_an_empty_collection_reports_nothing(tmp_path: Path) -> None:
    assert install_skills(tmp_path / "absent", tmp_path / "dest") == []


def test_installing_leaves_skills_from_other_sources_alone(tmp_path: Path) -> None:
    """An install must not own the directory, only the skills it ships.

    Claude Code merges skills from the user directory, the project directory and
    every installed plugin, so a user's own skill lives beside these. Clearing
    the destination would delete it.
    """
    destination = tmp_path / "skills"
    foreign = destination / "someone-elses-skill"
    foreign.mkdir(parents=True)
    (foreign / "SKILL.md").write_text("---\nname: x\n---\n", encoding="utf-8")

    install_skills(REPOSITORY_ROOT / "skills", destination)

    assert (foreign / "SKILL.md").is_file(), "installing clobbered a foreign skill"
    assert len(list(destination.iterdir())) == len(SKILLS) + 1
