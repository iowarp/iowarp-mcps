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
    discover_skills,
    find_skills_root,
    format_skill_listing,
    parse_frontmatter,
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
    shipped = _shipped_tools_by_server()
    for reference in sorted(declared):
        server, delimiter, tool = reference.partition(":")
        assert delimiter, (
            f"{name} cites '{reference}' unqualified; MCP references must be "
            "server:tool or an agent with several servers mounted cannot resolve them"
        )
        assert server in shipped, f"{name} cites unknown server '{server}'"
        assert tool in shipped[server], (
            f"{name} cites '{tool}' which {server} does not expose"
        )


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


@pytest.mark.parametrize("name,manifest", SKILLS, ids=[n for n, _ in SKILLS])
def test_body_cites_nothing_the_frontmatter_did_not_declare(
    name: str, manifest: Path
) -> None:
    """The declared list is what the drift guard checks, so it must be complete.

    A tool used in the steps but missing from `tools:` is invisible to the
    existence check above, which is exactly how a skill would survive a rename
    it should have failed.
    """
    body = manifest.read_text(encoding="utf-8")
    declared = {t.strip() for t in parse_frontmatter(body).get("tools", "").split(",")}
    steps = body.split("---", 2)[-1]
    cited = {
        f"{server}:{tool}"
        for server, tools in _shipped_tools_by_server().items()
        for tool in tools
        if f"`{server}:{tool}`" in steps
    }

    undeclared = sorted(cited - declared)
    assert not undeclared, f"{name} uses tools it never declared: {undeclared}"


@pytest.mark.parametrize("name,manifest", SKILLS, ids=[n for n, _ in SKILLS])
def test_body_never_cites_a_tool_unqualified(name: str, manifest: Path) -> None:
    """`identify_io_bottlenecks` exists on two servers; bare names are ambiguous."""
    shipped = _shipped_tools_by_server()
    every_tool = {tool for tools in shipped.values() for tool in tools}
    body = manifest.read_text(encoding="utf-8").split("---", 2)[-1]

    bare = sorted(
        tool for tool in every_tool if f"`{tool}`" in body and f":{tool}`" not in body
    )
    assert not bare, f"{name} cites tools without a server prefix: {bare}"


@pytest.mark.parametrize("name,manifest", SKILLS, ids=[n for n, _ in SKILLS])
def test_description_says_when_to_use_the_skill(name: str, manifest: Path) -> None:
    """The description is the only thing loaded until a skill triggers.

    Anthropic's authoring guidance is explicit: it must carry both what the
    skill does and when to reach for it, in third person, within 1024
    characters. Without the trigger half an agent cannot select it.
    """
    description = parse_frontmatter(manifest.read_text(encoding="utf-8"))["description"]

    assert "Use when" in description, f"{name} never says when to use it"
    assert len(description) <= 1024, f"{name} description exceeds 1024 characters"
    assert not description.startswith(("I ", "You ")), "write in third person"


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
