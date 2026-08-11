"""Discovery for the shipped skill collection.

A skill is a markdown file describing a workflow that spans more than one MCP
server. Anything one server can express on its own belongs in that server's MCP
prompt, which ships and versions with its contract; a skill exists for the
sequences no single server owns -- resolve a Spack install, then hand its exact
spec to JARVIS to run, for instance.

Layout, one directory per skill so a skill can carry supporting files later::

    skills/<name>/SKILL.md

Each SKILL.md opens with YAML-style frontmatter carrying at least ``name`` and
``description``, matching the convention agents already read.
"""

import sys
from pathlib import Path

import click

SKILL_FILENAME = "SKILL.md"
REQUIRED_FRONTMATTER = ("name", "description", "category", "servers", "tools")


def find_skills_root(module_dir: Path) -> Path:
    """Locate the shipped skills directory in a checkout or an installed wheel.

    Mirrors how the launcher already resolves its other shared data: the
    repository copy wins in a source checkout, then the locations a wheel's
    shared data can land in.
    """
    candidates = [
        module_dir.parent.parent / "skills",
        module_dir.parent / "skills",
        module_dir / "skills",
        Path(sys.prefix) / "share" / "clio-kit" / "skills",
        Path(sys.executable).parent.parent / "skills",
        Path(sys.executable).parent.parent / "share" / "skills",
    ]
    for candidate in candidates:
        if candidate.is_dir():
            return candidate
    return candidates[0]


def parse_frontmatter(text: str) -> dict[str, str]:
    """Return the leading ``---`` delimited key/value block, empty if absent.

    Deliberately not a YAML parser: the frontmatter this project ships is flat
    ``key: value`` lines, and depending on a YAML library to read a shipped
    asset would put a parser in the launcher's runtime for no gain.
    """
    if not text.startswith("---"):
        return {}
    _, _, rest = text.partition("\n")
    block, sep, _ = rest.partition("\n---")
    if not sep:
        return {}
    fields: dict[str, str] = {}
    for line in block.splitlines():
        key, delimiter, value = line.partition(":")
        if delimiter and key.strip() and not key.startswith((" ", "\t", "#")):
            fields[key.strip()] = value.strip().strip("\"'")
    return fields


def discover_skills(skills_root: Path) -> dict[str, Path]:
    """Map skill name to its SKILL.md, keyed by directory name."""
    if not skills_root.is_dir():
        return {}
    found: dict[str, Path] = {}
    for child in sorted(skills_root.iterdir()):
        if child.name.startswith(".") or not child.is_dir():
            continue
        manifest = child / SKILL_FILENAME
        if manifest.is_file():
            found[child.name] = manifest
    return found


def describe_skill(manifest: Path) -> str:
    """Return one skill's one-line description, or an empty string."""
    try:
        text = manifest.read_text(encoding="utf-8")
    except OSError:
        return ""
    return parse_frontmatter(text).get("description", "")


def skill_field(manifest: Path, field: str) -> str:
    """Return one frontmatter field, or an empty string."""
    try:
        text = manifest.read_text(encoding="utf-8")
    except OSError:
        return ""
    return parse_frontmatter(text).get(field, "")


def format_skill_listing(skills_root: Path) -> list[str]:
    """Render `clio-kit skills` grouped by category."""
    skills = discover_skills(skills_root)
    if not skills:
        return ["No skills found."]
    by_category: dict[str, list[tuple[str, Path]]] = {}
    for name, manifest in skills.items():
        category = skill_field(manifest, "category") or "Uncategorized"
        by_category.setdefault(category, []).append((name, manifest))

    lines: list[str] = []
    for category in sorted(by_category):
        if lines:
            lines.append("")
        lines.append(f"{category}:")
        for name, manifest in sorted(by_category[category]):
            lines.append(f"  {name}")
            summary = describe_skill(manifest).split(". Use when")[0].rstrip(".")
            if summary:
                lines.append(f"      {summary}.")
    lines.append("")
    lines.append("Usage: clio-kit skill <skill-name>")
    return lines


SKILL_INSTALL_SCOPES = {
    "user": Path.home() / ".claude" / "skills",
    "project": Path(".claude") / "skills",
}


def format_install_result(skills_root: Path, scope: str) -> list[str]:
    """Install for one scope and render the outcome as output lines."""
    destination = SKILL_INSTALL_SCOPES[scope].expanduser().resolve()
    installed = install_skills(skills_root, destination)
    if not installed:
        return ["No skills found to install."]
    return [f"Installed {len(installed)} skills to {destination}:"] + [
        f"  - {name}" for name in installed
    ]


def install_skills(skills_root: Path, destination: Path) -> list[str]:
    """Copy the shipped skills to where an agent discovers them.

    Claude Code reads skills from ~/.claude/skills or ./.claude/skills; the kit
    ships them inside its wheel, so they are invisible there until copied. Each
    skill is replaced wholesale rather than merged, so a stale file from an
    older release cannot survive an upgrade.
    """
    import shutil

    skills = discover_skills(skills_root)
    if not skills:
        return []
    destination.mkdir(parents=True, exist_ok=True)
    installed: list[str] = []
    for name, manifest in skills.items():
        target = destination / name
        if target.exists():
            shutil.rmtree(target)
        shutil.copytree(manifest.parent, target)
        installed.append(name)
    return installed


def _shipped_root() -> Path:
    """Resolve the collection relative to this module's own install location."""
    return find_skills_root(Path(__file__).resolve().parent)


@click.command("skills")
def list_skills_command() -> None:
    """List the shipped cross-server skills, grouped by category."""
    click.echo("\n".join(format_skill_listing(_shipped_root())))


@click.command("skill")
@click.argument("skill_name")
def show_skill_command(skill_name: str) -> None:
    """Print one skill's SKILL.md to stdout."""
    skills = discover_skills(_shipped_root())
    manifest = skills.get(skill_name.lower())
    if manifest is None:
        click.echo(f"Error: Unknown skill '{skill_name}'")
        click.echo(f"Available skills: {', '.join(skills) or 'none'}")
        sys.exit(1)
    click.echo(manifest.read_text(encoding="utf-8"))


@click.command("skills-install")
@click.option(
    "--scope",
    type=click.Choice(sorted(SKILL_INSTALL_SCOPES)),
    default="user",
    help="Install for this user (~/.claude/skills) or this project (.claude/skills).",
)
def install_skills_command(scope: str) -> None:
    """Copy the shipped skills to where an agent discovers them."""
    click.echo("\n".join(format_install_result(_shipped_root(), scope)))


def read_server_inventory(servers_root: Path) -> dict[str, set[str]]:
    """Map each client-facing server name to the tools it exposes.

    Clients register these servers as ``clio-<name>``, which is what the
    generated Claude Desktop, Claude Code and Gemini configs all use, so skills
    are validated against the names an agent actually sees.
    """
    import json

    inventory: dict[str, set[str]] = {}
    for manifest in sorted(servers_root.glob("*/server.json")):
        try:
            document = json.loads(manifest.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        inventory[f"clio-{manifest.parent.name}"] = {
            tool["name"] for tool in document.get("tools", []) if "name" in tool
        }
    return inventory


def validate_skill(manifest: Path, tools_by_server: dict[str, set[str]]) -> list[str]:
    """Return every problem with one skill, empty when it is sound.

    Shared by the repository's own test suite and the `skills validate` command,
    so a skill written outside this repository is held to exactly the same rules
    as the shipped collection. Reports all problems at once rather than the
    first, because fixing them one build at a time is the slow way.
    """
    problems: list[str] = []
    text = manifest.read_text(encoding="utf-8")
    fields = parse_frontmatter(text)
    body = text.split("---", 2)[-1]

    for key in REQUIRED_FRONTMATTER:
        if not fields.get(key):
            problems.append(f"missing frontmatter '{key}'")
    if not problems and fields["name"] != manifest.parent.name:
        problems.append(
            f"frontmatter name {fields['name']!r} does not match "
            f"directory {manifest.parent.name!r}"
        )
    if "Use when" not in fields.get("description", ""):
        problems.append("description does not say when to use the skill")
    if len(fields.get("description", "")) > 1024:
        problems.append("description exceeds 1024 characters")

    servers = {s.strip() for s in fields.get("servers", "").split(",") if s.strip()}
    if len(servers) < 2:
        problems.append(
            "a skill must span more than one server; single-server sequencing "
            "belongs in that server's MCP prompt"
        )

    declared = {t.strip() for t in fields.get("tools", "").split(",") if t.strip()}
    for reference in sorted(declared):
        server, delimiter, tool = reference.partition(":")
        if not delimiter:
            problems.append(f"'{reference}' is unqualified; use server:tool")
            continue
        if server not in tools_by_server:
            problems.append(f"'{reference}' names unknown server '{server}'")
        elif tool not in tools_by_server[server]:
            problems.append(f"'{server}' does not expose '{tool}'")
        elif f"`{reference}`" not in body:
            problems.append(f"'{reference}' is declared but never used in the steps")

    for server, tools in tools_by_server.items():
        for tool in tools:
            if f"`{server}:{tool}`" in body and f"{server}:{tool}" not in declared:
                problems.append(f"'{server}:{tool}' is used but never declared")
            elif f"`{tool}`" in body and f":{tool}`" not in body:
                problems.append(f"'{tool}' is cited without a server prefix")
    return problems


@click.command("skills-validate")
@click.argument(
    "path",
    type=click.Path(exists=True, file_okay=False, path_type=Path),
    required=False,
)
def validate_skills_command(path: Path | None) -> None:
    """Check a skill collection against the servers this kit ships.

    Defaults to the shipped collection. Point it at your own directory to hold
    an external skill to the same rules.
    """
    from clio_kit import get_servers_path

    root = path or _shipped_root()
    skills = discover_skills(root)
    if not skills:
        click.echo(f"No skills found in {root}")
        sys.exit(1)
    inventory = read_server_inventory(get_servers_path())
    failures = 0
    for name, manifest in skills.items():
        problems = validate_skill(manifest, inventory)
        if problems:
            failures += 1
            click.echo(f"FAIL: {name}")
            for problem in problems:
                click.echo(f"  - {problem}")
        else:
            click.echo(f"OK:   {name}")
    if failures:
        click.echo(f"\n{failures} of {len(skills)} skills have problems.")
        sys.exit(1)
    click.echo(f"\nAll {len(skills)} skills validate against this kit's servers.")


SKILL_COMMANDS: tuple[click.Command, ...] = (
    list_skills_command,
    show_skill_command,
    install_skills_command,
    validate_skills_command,
)
