"""Author, check and submit a plugin for the CLIO Kit marketplace.

These commands are for contributors working in *their own* repository. The
marketplace indexes outside plugins rather than vendoring them (see
:mod:`clio_kit.community`), so the only thing that reaches this repository is a
one-file entry -- which means a malformed plugin is not caught by our CI at all.
``clio-kit plugin validate`` is where it gets caught instead, before a pull
request exists.

The skill frontmatter reader lives here because both this validator and the
manifest generator need the same answer to "is this SKILL.md loadable", and a
second implementation would drift from the first.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import click

# A plugin name is used to namespace its components (``plugin-name:skill-name``)
# and appears in install commands, so it has to survive being typed.
NAME_PATTERN = "abcdefghijklmnopqrstuvwxyz0123456789-"

# Generated from this repository's own servers, bundles and skills. An outside
# plugin claiming the prefix would shadow one of ours in the same catalogue.
RESERVED_PREFIX = "clio-"


class PluginProblem(Exception):
    """One reason a plugin directory would not publish correctly."""


def read_skill_frontmatter(skill_dir: Path) -> dict[str, str]:
    """Return one SKILL.md's frontmatter fields, or raise if it is unloadable.

    Only top-level keys are collected: an indented line continues the value
    above it, and a description long enough to wrap is the normal case rather
    than the exception.
    """
    skill_md = skill_dir / "SKILL.md"
    if not skill_md.is_file():
        raise PluginProblem(f"{skill_dir} has no SKILL.md")
    text = skill_md.read_text(encoding="utf-8")
    if not text.startswith("---\n"):
        raise PluginProblem(f"{skill_md} must open with YAML frontmatter")
    _, _, rest = text.partition("---\n")
    frontmatter, separator, _ = rest.partition("\n---\n")
    if not separator:
        raise PluginProblem(f"{skill_md} has unterminated frontmatter")

    fields: dict[str, str] = {}
    for line in frontmatter.splitlines():
        if not line or line.startswith((" ", "\t")):
            continue
        key, colon, value = line.partition(":")
        if colon:
            fields[key.strip()] = value.strip()

    for required in ("name", "description"):
        if not fields.get(required):
            raise PluginProblem(f"{skill_md} frontmatter needs a {required}")
    if fields["name"] != skill_dir.name:
        raise PluginProblem(
            f"{skill_md} declares name {fields['name']!r} "
            f"but lives in {skill_dir.name!r}"
        )
    return fields


def _check_name(name: Any, problems: list[str]) -> None:
    """Collect every reason a plugin name would not work as an identifier."""
    if not isinstance(name, str) or not name:
        problems.append("plugin.json needs a name")
        return
    if name.startswith(RESERVED_PREFIX):
        problems.append(
            f"name {name!r} claims the reserved {RESERVED_PREFIX!r} prefix, which is "
            "generated from CLIO Kit's own servers, bundles and skills"
        )
    if any(character not in NAME_PATTERN for character in name):
        problems.append(
            f"name {name!r} must be lower-case kebab-case; it namespaces this "
            "plugin's components and appears in install commands"
        )


def _check_component_paths(manifest: dict[str, Any], problems: list[str]) -> None:
    """Reject paths that will not survive installation.

    A plugin is copied into a cache directory on install, and nothing outside
    its own root is copied with it. A path that escapes resolves to nothing on
    the user's machine while working perfectly in the author's checkout, which
    is the worst shape a bug can take.
    """
    path_fields = (
        "skills",
        "commands",
        "agents",
        "workflows",
        "hooks",
        "mcpServers",
        "outputStyles",
        "lspServers",
    )
    for field in path_fields:
        value = manifest.get(field)
        if value is None or isinstance(value, dict):
            continue
        for entry in [value] if isinstance(value, str) else value:
            if not isinstance(entry, str):
                continue
            if entry.startswith("/") or ".." in Path(entry).parts:
                problems.append(
                    f"{field} path {entry!r} leaves the plugin directory; nothing "
                    "outside the plugin root is copied to the cache on install"
                )
            elif entry != "." and not entry.startswith("./"):
                problems.append(f"{field} path {entry!r} must start with './'")


def _check_mcp_servers(plugin_dir: Path, problems: list[str]) -> None:
    """Check the default MCP config, when there is one."""
    mcp_json = plugin_dir / ".mcp.json"
    if not mcp_json.is_file():
        return
    try:
        config = json.loads(mcp_json.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        problems.append(f".mcp.json is not valid JSON: {exc}")
        return
    servers = config.get("mcpServers", config)
    if not isinstance(servers, dict) or not servers:
        problems.append(".mcp.json declares no servers")
        return
    for name, entry in servers.items():
        if not isinstance(entry, dict):
            problems.append(f".mcp.json server {name!r} must be an object")
        elif not entry.get("command") and not entry.get("url"):
            problems.append(f".mcp.json server {name!r} needs a command or a url")


def validate_plugin(plugin_dir: Path) -> tuple[dict[str, Any], list[str]]:
    """Return a plugin's manifest and every problem found in its directory."""
    problems: list[str] = []
    manifest_path = plugin_dir / ".claude-plugin" / "plugin.json"
    if not manifest_path.is_file():
        raise PluginProblem(
            f"{plugin_dir} has no .claude-plugin/plugin.json; "
            "run `clio-kit plugin init` to scaffold one"
        )
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise PluginProblem(f"{manifest_path} is not valid JSON: {exc}") from exc
    if not isinstance(manifest, dict):
        raise PluginProblem(f"{manifest_path} must contain an object")

    _check_name(manifest.get("name"), problems)
    if not manifest.get("description"):
        problems.append(
            "plugin.json has no description; it is what a user reads before "
            "installing something you wrote"
        )
    _check_component_paths(manifest, problems)
    _check_mcp_servers(plugin_dir, problems)

    skills_root = plugin_dir / "skills"
    if skills_root.is_dir():
        for skill_dir in sorted(
            path for path in skills_root.iterdir() if path.is_dir()
        ):
            try:
                read_skill_frontmatter(skill_dir)
            except PluginProblem as exc:
                problems.append(str(exc))

    has_components = (
        any(
            (plugin_dir / directory).is_dir()
            for directory in ("skills", "commands", "agents", "hooks")
        )
        or (plugin_dir / ".mcp.json").is_file()
    )
    if not has_components and not manifest.get("dependencies"):
        problems.append(
            "plugin ships no skills, commands, agents, hooks or MCP servers, and "
            "declares no dependencies -- installing it would do nothing"
        )
    return manifest, problems


def build_community_entry(manifest: dict[str, Any], repo: str) -> str:
    """Render the marketplace entry that indexes a plugin we do not own."""
    name = manifest.get("name", "")
    description = manifest.get("description", "")
    keywords = manifest.get("keywords") or []
    author = manifest.get("author") or {}
    maintainer = author.get("name") if isinstance(author, dict) else author
    lines = [
        f'name        = "{name}"',
        f'description = "{description}"',
        f'category    = "{manifest.get("category", "community")}"',
    ]
    if maintainer:
        lines.append(f'maintainer  = "{maintainer}"')
    if keywords:
        rendered = ", ".join(f'"{keyword}"' for keyword in keywords)
        lines.append(f"keywords    = [{rendered}]")
    lines += ["", "[source]", 'type = "github"', f'repo = "{repo}"']
    return "\n".join(lines) + "\n"


@click.group("plugin")
def plugin_group() -> None:
    """Author, check and submit a plugin for the CLIO Kit marketplace."""


@plugin_group.command("init")
@click.argument("directory", type=click.Path(path_type=Path))
@click.option("--name", default=None, help="Plugin name (defaults to the directory).")
def plugin_init(directory: Path, name: str | None) -> None:
    """Scaffold a plugin with a skill, an MCP config, and a manifest."""
    plugin_name = name or directory.name
    problems: list[str] = []
    _check_name(plugin_name, problems)
    if problems:
        raise click.ClickException("\n".join(problems))
    if (directory / ".claude-plugin" / "plugin.json").exists():
        raise click.ClickException(f"{directory} already contains a plugin manifest")

    skill_dir = directory / "skills" / "example-workflow"
    skill_dir.mkdir(parents=True, exist_ok=True)
    (directory / ".claude-plugin").mkdir(parents=True, exist_ok=True)

    # No component path fields: the conventional layout is picked up on its own,
    # and every path field is one more thing that can point somewhere that does
    # not survive installation.
    manifest = {
        "name": plugin_name,
        "description": "One sentence on what this plugin is for.",
        "version": "0.1.0",
        "author": {"name": "Your name", "url": "https://example.org"},
        "keywords": [],
    }
    (directory / ".claude-plugin" / "plugin.json").write_text(
        json.dumps(manifest, indent=2) + "\n", encoding="utf-8"
    )
    (directory / ".mcp.json").write_text(
        json.dumps(
            {"example-server": {"command": "npx", "args": ["-y", "@you/your-mcp"]}},
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    (skill_dir / "SKILL.md").write_text(
        "---\n"
        "name: example-workflow\n"
        "description: One sentence on what this does, then when to use it. "
        "The description is the whole trigger -- it is read in every session, "
        "and the body is only loaded when it fires.\n"
        "---\n"
        "\n"
        "# Example workflow\n"
        "\n"
        "Replace this with the sequence an agent gets wrong without it.\n",
        encoding="utf-8",
    )
    click.echo(f"Scaffolded {plugin_name} in {directory}")
    click.echo("Next: edit the manifest and the skill, then `clio-kit plugin validate`")


@plugin_group.command("validate")
@click.argument("directory", type=click.Path(exists=True, path_type=Path))
def plugin_validate(directory: Path) -> None:
    """Check a plugin directory against the rules the marketplace enforces."""
    try:
        manifest, problems = validate_plugin(directory)
    except PluginProblem as exc:
        raise click.ClickException(str(exc)) from exc
    if problems:
        for problem in problems:
            click.echo(f"  - {problem}")
        raise click.ClickException(f"{len(problems)} problem(s) in {directory}")
    click.echo(f"OK: {manifest['name']} would publish correctly")
    click.echo(
        "Note: this checks the shape the marketplace requires. Run "
        "`claude plugin validate --strict` as well for the client's own rules."
    )


@plugin_group.command("submit")
@click.argument("directory", type=click.Path(exists=True, path_type=Path))
@click.option("--repo", required=True, help="Your plugin's repository, as owner/name.")
@click.option(
    "--output",
    type=click.Path(path_type=Path),
    default=None,
    help="Write the entry here instead of printing it.",
)
def plugin_submit(directory: Path, repo: str, output: Path | None) -> None:
    """Render the marketplace entry that would index this plugin."""
    try:
        manifest, problems = validate_plugin(directory)
    except PluginProblem as exc:
        raise click.ClickException(str(exc)) from exc
    if problems:
        raise click.ClickException(
            "Fix these before submitting -- run `clio-kit plugin validate`:\n  - "
            + "\n  - ".join(problems)
        )
    if repo.count("/") != 1 or repo.startswith("/") or repo.endswith("/"):
        raise click.ClickException(f"--repo {repo!r} must be in owner/name form")

    entry = build_community_entry(manifest, repo)
    if output is not None:
        output.write_text(entry, encoding="utf-8")
        click.echo(f"Wrote {output}")
    else:
        click.echo(entry, nl=False)
    click.echo(
        f"\nAdd this as community/entries/{manifest['name']}.toml in a pull "
        "request against iowarp/clio-kit. Your code stays in your repository; "
        "the entry is the only thing we merge."
    )


PLUGIN_COMMANDS = (plugin_group,)
