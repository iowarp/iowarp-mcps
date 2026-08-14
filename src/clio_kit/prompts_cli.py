"""The `clio-kit prompt` and `clio-kit prompts` commands.

Split out of the launcher module, which the size ratchet holds at a fixed line
count because it had become the place every new command landed. Prompts share
nothing with server launching beyond looking in the same shared-data locations,
so they move as a unit.
"""

from __future__ import annotations

import sys
from pathlib import Path

import click

MODULE_DIR = Path(__file__).parent.resolve()


def get_prompts_path():
    """Get the path to prompts directory (dev or installed)"""
    # First try development path (../../prompts from module)
    dev_path = MODULE_DIR.parent.parent / "prompts"
    if dev_path.exists():
        return dev_path

    # Try to find shared data in the installed package
    possible_paths = [
        # Standard site-packages installation
        MODULE_DIR.parent / "prompts",  # ../prompts from module
        # Alternative installation paths
        MODULE_DIR / "prompts",  # ./prompts from module
        # System-wide data directory
        Path(sys.prefix) / "share" / "clio-kit" / "prompts",
        # Local data directory
        Path.home() / ".local" / "share" / "clio-kit" / "prompts",
    ]

    # Try each possible path
    for path in possible_paths:
        if path.exists() and path.is_dir():
            return path

    # If none found, check if we're in an isolated environment (like uvx)
    python_path = Path(sys.executable)
    isolated_paths = [
        # uvx style isolated environment
        python_path.parent.parent / "prompts",
        python_path.parent.parent / "share" / "prompts",
        python_path.parent.parent / "purelib" / "prompts",
        python_path.parent.parent / "data" / "prompts",
    ]

    for path in isolated_paths:
        if path.exists() and path.is_dir():
            return path

    # Last resort: return the dev path
    return dev_path


def auto_discover_prompts():
    """Auto-discover prompts from the prompts directory (recursively)"""
    prompts_path = get_prompts_path()
    if not prompts_path.exists():
        return {}

    prompt_map = {}

    # Recursively scan for .md files
    for md_file in prompts_path.rglob("*.md"):
        # Get relative path from prompts directory
        relative_path = md_file.relative_to(prompts_path)

        # Create prompt name from relative path without extension
        # e.g., "code-coverage-prompt.md" -> "code-coverage-prompt"
        # e.g., "testing/foo.md" -> "testing/foo"
        prompt_name = str(relative_path.with_suffix(""))

        # Also support underscore version
        # "code-coverage-prompt" -> also accessible as "code_coverage_prompt"
        prompt_map[prompt_name] = md_file
        prompt_map[prompt_name.replace("-", "_")] = md_file

    return prompt_map


def list_available_prompts():
    """List all available prompts"""
    prompt_map = auto_discover_prompts()
    # Remove duplicates (dash vs underscore versions)
    unique_prompts = set()
    for name in prompt_map.keys():
        # Normalize to dash version for display
        unique_prompts.add(name.replace("_", "-"))
    return sorted(unique_prompts)


@click.command("prompt")
@click.argument("prompt_name", required=False)
def prompt(prompt_name):
    """Print a prompt to stdout. List all if no name specified."""

    prompt_map = auto_discover_prompts()

    if not prompt_name:
        # List all prompts
        prompts = list_available_prompts()
        if prompts:
            click.echo("Available prompts:")
            for p in prompts:
                click.echo(f"  - {p}")
        else:
            click.echo("No prompts found.")
        click.echo("\nUsage: clio-kit prompt <prompt-name>")
        return

    # Normalize prompt name (support both dash and underscore)
    prompt_lower = prompt_name.lower()

    if prompt_lower not in prompt_map:
        click.echo(f"Error: Unknown prompt '{prompt_name}'")
        click.echo(f"Available prompts: {', '.join(list_available_prompts())}")
        sys.exit(1)

    # Read and print the prompt file
    prompt_file = prompt_map[prompt_lower]
    try:
        with open(prompt_file, "r") as f:
            content = f.read()
        click.echo(content)
    except Exception as e:
        click.echo(f"Error reading prompt file: {e}")
        sys.exit(1)


@click.command("prompts")
def list_prompts_cmd():
    """List all available prompts"""
    prompts = list_available_prompts()
    if prompts:
        click.echo("Available prompts:")
        for p in prompts:
            click.echo(f"  - {p}")
    else:
        click.echo("No prompts found.")


PROMPT_COMMANDS = (prompt, list_prompts_cmd)
