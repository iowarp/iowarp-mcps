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

from clio_kit import get_skills_path, main
from clio_kit.skills import (
    REQUIRED_FRONTMATTER,
    describe_skill,
    discover_skills,
    find_skills_root,
    format_skill_listing,
    parse_frontmatter,
)

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
TOOL_REFERENCE = re.compile(r"`([a-z][a-z0-9_]*)`")


def _shipped_tool_names() -> set[str]:
    servers = REPOSITORY_ROOT / "clio-kit-mcp-servers"
    return {
        tool["name"]
        for manifest in servers.glob("*/server.json")
        for tool in json.loads(manifest.read_text(encoding="utf-8")).get("tools", [])
    }


def _shipped_server_names() -> set[str]:
    servers = REPOSITORY_ROOT / "clio-kit-mcp-servers"
    return {path.parent.name for path in servers.glob("*/pyproject.toml")}


SKILLS = sorted(discover_skills(REPOSITORY_ROOT / "skills").items())


def test_the_repository_ships_at_least_one_skill() -> None:
    assert SKILLS, (
        "skills/ is empty; the launcher's skill commands have nothing to serve"
    )


@pytest.mark.parametrize("name,manifest", SKILLS, ids=[n for n, _ in SKILLS])
def test_skill_declares_the_required_frontmatter(name: str, manifest: Path) -> None:
    fields = parse_frontmatter(manifest.read_text(encoding="utf-8"))

    for key in REQUIRED_FRONTMATTER:
        assert fields.get(key), f"{name} is missing frontmatter '{key}'"
    assert fields["name"] == name, "frontmatter name must match the directory"


@pytest.mark.parametrize("name,manifest", SKILLS, ids=[n for n, _ in SKILLS])
def test_skill_names_only_servers_that_ship(name: str, manifest: Path) -> None:
    """A skill pointing at a removed or renamed server sends an agent nowhere."""
    fields = parse_frontmatter(manifest.read_text(encoding="utf-8"))
    declared = {s.strip() for s in fields.get("servers", "").split(",") if s.strip()}

    assert declared, f"{name} must declare which servers it spans"
    assert declared <= _shipped_server_names(), (
        f"{name} names servers that do not ship: {sorted(declared - _shipped_server_names())}"
    )


@pytest.mark.parametrize("name,manifest", SKILLS, ids=[n for n, _ in SKILLS])
def test_every_tool_a_skill_declares_still_exists(name: str, manifest: Path) -> None:
    """The check that makes skills survive #357's merges and renames.

    A skill declares its tools in frontmatter rather than having them inferred
    from prose: a body legitimately mentions parameter names, and this one
    deliberately names a tool that does not exist ("do not look for spack_load")
    to stop an agent hunting for it.
    """
    fields = parse_frontmatter(manifest.read_text(encoding="utf-8"))
    declared = {t.strip() for t in fields.get("tools", "").split(",") if t.strip()}

    assert declared, f"{name} declares no tools; it is not describing a workflow"
    missing = sorted(declared - _shipped_tool_names())
    assert not missing, f"{name} declares tools that no longer exist: {missing}"


@pytest.mark.parametrize("name,manifest", SKILLS, ids=[n for n, _ in SKILLS])
def test_declared_tools_are_actually_used_in_the_body(
    name: str, manifest: Path
) -> None:
    """The declaration and the prose must not drift apart."""
    body = manifest.read_text(encoding="utf-8")
    fields = parse_frontmatter(body)
    declared = {t.strip() for t in fields.get("tools", "").split(",") if t.strip()}
    steps = body.split("---", 2)[-1]

    unused = sorted(tool for tool in declared if f"`{tool}`" not in steps)
    assert not unused, f"{name} declares tools its steps never mention: {unused}"


def test_a_skill_spans_more_than_one_server() -> None:
    """Single-server sequencing belongs in that server's MCP prompt instead.

    Prompts ship and version with the server's contract; a skill that duplicates
    one just gives the agent two sources that can disagree.
    """
    for name, manifest in SKILLS:
        fields = parse_frontmatter(manifest.read_text(encoding="utf-8"))
        declared = {
            s.strip() for s in fields.get("servers", "").split(",") if s.strip()
        }
        assert len(declared) > 1, (
            f"{name} spans one server; make it an MCP prompt on that server"
        )


def test_listing_reports_each_skill_with_its_description() -> None:
    lines = format_skill_listing(REPOSITORY_ROOT / "skills")

    assert lines[0] == "Available skills:"
    for name, manifest in SKILLS:
        assert any(name in line and describe_skill(manifest) in line for line in lines)


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
    assert get_skills_path().is_dir()


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
