#!/usr/bin/env python3
import hashlib
import os
import shutil
import sys
import subprocess
from pathlib import Path
import click

# Determine if we're running from development or installed package
MODULE_DIR = Path(__file__).parent
LOCKED_SERVER_LAUNCH_SCHEMA = "clio-kit.locked-server.v1"
LOCKED_SERVER_SCHEMA_ENV = "CLIO_KIT_LOCKED_SERVER_SCHEMA"
LOCKED_SERVER_PROJECT_SHA_ENV = "CLIO_KIT_LOCKED_SERVER_PROJECT_SHA256"
LOCKED_SERVER_LOCK_SHA_ENV = "CLIO_KIT_LOCKED_SERVER_LOCK_SHA256"


def get_servers_path():
    """Get the path to servers directory (dev or installed)"""
    # First try development path (../../clio-kit-mcp-servers from module)
    dev_path = MODULE_DIR.parent.parent / "clio-kit-mcp-servers"
    if dev_path.exists():
        return dev_path

    # Try to find shared data in the installed package
    # When installed via wheel, shared data goes to site-packages/
    # Look for clio-kit-mcp-servers directory in various possible locations
    possible_paths = [
        # Standard site-packages installation
        MODULE_DIR.parent
        / "clio-kit-mcp-servers",  # ../clio-kit-mcp-servers from module
        # Alternative installation paths
        MODULE_DIR
        / "clio-kit-mcp-servers",  # ./clio-kit-mcp-servers from module (if included directly)
        # System-wide data directory
        Path(sys.prefix) / "share" / "clio-kit" / "clio-kit-mcp-servers",
        # Local data directory
        Path.home() / ".local" / "share" / "clio-kit" / "clio-kit-mcp-servers",
    ]

    # Try each possible path
    for path in possible_paths:
        if path.exists() and path.is_dir():
            return path

    # If none found, check if we're in an isolated environment (like uvx)
    # and try to find the data directory relative to the Python executable
    python_path = Path(sys.executable)
    isolated_paths = [
        # uvx style isolated environment - clio-kit-mcp-servers is at the root level
        python_path.parent.parent / "clio-kit-mcp-servers",
        python_path.parent.parent / "share" / "clio-kit-mcp-servers",
        python_path.parent.parent / "purelib" / "clio-kit-mcp-servers",
        python_path.parent.parent / "data" / "clio-kit-mcp-servers",
    ]

    for path in isolated_paths:
        if path.exists() and path.is_dir():
            return path

    # Last resort: return the dev path even if it doesn't exist
    # so the caller can handle the missing directory appropriately
    return dev_path


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


def get_search_path():
    """Get the path to the clio-agentic-search directory (dev or installed)"""
    dev_path = MODULE_DIR.parent.parent / "clio-agentic-search"
    if dev_path.exists():
        return dev_path

    possible_paths = [
        MODULE_DIR.parent / "clio-agentic-search",
        MODULE_DIR / "clio-agentic-search",
        Path(sys.prefix) / "share" / "clio-kit" / "clio-agentic-search",
        Path.home() / ".local" / "share" / "clio-kit" / "clio-agentic-search",
    ]

    for path in possible_paths:
        if path.exists() and path.is_dir():
            return path

    python_path = Path(sys.executable)
    isolated_paths = [
        python_path.parent.parent / "clio-agentic-search",
        python_path.parent.parent / "share" / "clio-agentic-search",
        python_path.parent.parent / "purelib" / "clio-agentic-search",
        python_path.parent.parent / "data" / "clio-agentic-search",
    ]

    for path in isolated_paths:
        if path.exists() and path.is_dir():
            return path

    return dev_path


def auto_discover_mcps():
    """Auto-discover MCP servers from the clio-kit-mcp-servers directory"""
    servers_path = get_servers_path()
    if not servers_path.exists():
        return {}, {}

    server_command_map = {}
    dir_name_map = {}

    # Scan for directories containing pyproject.toml
    for item in servers_path.iterdir():
        if item.is_dir() and not item.name.startswith("."):
            pyproject_file = item / "pyproject.toml"
            if pyproject_file.exists():
                # Read pyproject.toml to extract entry point
                try:
                    with open(pyproject_file, "r") as f:
                        content = f.read()

                    # Simple parsing to find the entry point
                    # Look for lines like: server-name-mcp = "module:main"
                    entry_point = None
                    for line in content.split("\n"):
                        line = line.strip()
                        if "-mcp =" in line and "=" in line:
                            entry_point = line.split("=")[0].strip().strip("\"'")
                            break

                    if entry_point:
                        # Create server name by removing -mcp suffix
                        server_name = entry_point.replace("-mcp", "").lower()
                        # Handle special cases for naming
                        if server_name == "node-hardware":
                            server_name = "node-hardware"
                        elif server_name == "parallel-sort":
                            server_name = "parallel-sort"

                        server_command_map[server_name] = entry_point
                        dir_name_map[server_name] = item.name

                except Exception:
                    # Skip directories that can't be processed
                    continue

    return server_command_map, dir_name_map


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


def list_available_servers():
    """List all available servers"""
    server_command_map, _ = auto_discover_mcps()
    return sorted(server_command_map.keys())


def list_available_prompts():
    """List all available prompts"""
    prompt_map = auto_discover_prompts()
    # Remove duplicates (dash vs underscore versions)
    unique_prompts = set()
    for name in prompt_map.keys():
        # Normalize to dash version for display
        unique_prompts.add(name.replace("_", "-"))
    return sorted(unique_prompts)


def subprocess_env_with_github_https_rewrite() -> dict[str, str]:
    """Return an environment that lets uv install GitHub deps without SSH keys."""
    env = os.environ.copy()
    if "GIT_CONFIG_COUNT" in env:
        return env
    env["GIT_CONFIG_COUNT"] = "1"
    env["GIT_CONFIG_KEY_0"] = "url.https://github.com/.insteadOf"
    env["GIT_CONFIG_VALUE_0"] = "git@github.com:"
    return env


def uvx_command() -> str:
    """Return a usable uvx executable path for interactive and batch shells."""
    found = shutil.which("uvx")
    if found is not None:
        return found
    local_uvx = Path.home() / ".local" / "bin" / "uvx"
    if local_uvx.exists():
        return str(local_uvx)
    return "uvx"


def uv_command() -> str:
    """Return a usable uv executable path for locked embedded projects."""
    found = shutil.which("uv")
    if found is not None:
        return found
    local_uv = Path.home() / ".local" / "bin" / "uv"
    if local_uv.exists():
        return str(local_uv)
    return "uv"


def locked_server_command(server_path: Path, entry_command: str) -> list[str]:
    """Build a command that executes an embedded server from its exact lock."""
    lock_path = server_path / "uv.lock"
    if not lock_path.is_file():
        raise click.ClickException(
            f"Embedded MCP server '{server_path.name}' has no uv.lock; "
            "refusing an unpinned runtime dependency resolution."
        )
    return [
        uv_command(),
        "run",
        "--no-editable",
        "--frozen",
        "--project",
        str(server_path),
        entry_command,
    ]


def locked_server_environment(server_path: Path) -> Path:
    """Return a reusable environment path keyed by locked server source bytes."""
    identity = locked_server_project_identity(server_path)
    return _locked_server_environment_path(
        server_path,
        project_sha256=identity["project_sha256"],
    )


def locked_server_project_identity(server_path: Path) -> dict[str, str]:
    """Hash the embedded server source and lock that define its child runtime."""
    digest = hashlib.sha256()
    inputs = [server_path / "pyproject.toml", server_path / "uv.lock"]
    source_path = server_path / "src"
    if source_path.is_dir():
        inputs.extend(path for path in source_path.rglob("*") if path.is_file())
    for path in sorted(inputs, key=lambda item: item.as_posix()):
        if not path.is_file():
            raise click.ClickException(
                f"Embedded MCP server '{server_path.name}' is incomplete: "
                f"missing {path.name}."
            )
        relative_path = path.relative_to(server_path).as_posix().encode("utf-8")
        digest.update(len(relative_path).to_bytes(8, "big"))
        digest.update(relative_path)
        with path.open("rb") as stream:
            while chunk := stream.read(1024 * 1024):
                digest.update(chunk)
    lock_sha256 = hashlib.sha256((server_path / "uv.lock").read_bytes()).hexdigest()
    return {
        "schema_version": LOCKED_SERVER_LAUNCH_SCHEMA,
        "server_name": server_path.name,
        "project_sha256": digest.hexdigest(),
        "lock_sha256": lock_sha256,
    }


def _locked_server_environment_path(
    server_path: Path,
    *,
    project_sha256: str,
) -> Path:
    """Resolve one source-addressed child environment without mutating it."""
    configured_cache = os.getenv("CLIO_KIT_CACHE_DIR")
    if configured_cache:
        cache_root = Path(configured_cache).expanduser()
    else:
        cache_root = (
            Path(os.getenv("XDG_CACHE_HOME", str(Path.home() / ".cache"))).expanduser()
            / "clio-kit"
        )
    return (
        cache_root / "mcp-environments" / f"{server_path.name}-{project_sha256[:24]}"
    ).resolve()


@click.group(invoke_without_command=True)
@click.pass_context
def main(ctx):
    """clio-kit: Unified launcher for MCP servers and AI prompts"""
    if ctx.invoked_subcommand is None:
        click.echo(
            "clio-kit: Unified launcher for MCP servers, AI prompts, and services"
        )
        click.echo("\nAvailable commands:")
        click.echo("  mcp-server   Run an MCP server")
        click.echo("  mcp-servers  List all available MCP servers")
        click.echo(
            "  search       Run agentic search (query, index, serve, list, seed)"
        )
        click.echo("  prompt       Print a prompt to stdout")
        click.echo("  prompts      List all available prompts")
        click.echo("\nUsage:")
        click.echo("  uvx clio-kit mcp-server <server-name>")
        click.echo("  uvx clio-kit search <subcommand>")
        click.echo("  uvx clio-kit prompt <prompt-name>")
        click.echo("\nFor more help: uvx clio-kit <command> --help")


@main.command(
    "mcp-server",
    context_settings={"ignore_unknown_options": True, "allow_extra_args": True},
)
@click.argument("server", required=False)
@click.option("-b", "--branch", help="Git branch to use (for development)")
@click.argument("args", nargs=-1, type=click.UNPROCESSED)
def mcp_server(server, branch, args):
    """Run an MCP server. List all if no server specified."""

    server_command_map, dir_name_map = auto_discover_mcps()

    if not server:
        click.echo("Available MCP servers:")
        for s in sorted(server_command_map.keys()):
            click.echo(f"  - {s}")
        click.echo("\nUsage: uvx clio-kit mcp-server <server-name>")
        click.echo("   or: clio-kit mcp-server <server-name> (if installed)")
        return

    # Normalize server name to lowercase
    server_lower = server.lower()

    if server_lower not in server_command_map:
        click.echo(f"Error: Unknown server '{server}'")
        click.echo(f"Available servers: {', '.join(sorted(server_command_map.keys()))}")
        sys.exit(1)

    # Get the entry point command and directory name
    entry_command = server_command_map[server_lower]
    actual_dir = dir_name_map[server_lower]

    child_environment = subprocess_env_with_github_https_rewrite()

    # Build the child launcher command.
    if branch:
        # Run from git branch
        cmd = [
            uvx_command(),
            "--from",
            f"git+https://github.com/iowarp/clio-kit.git@{branch}#subdirectory=clio-kit-mcp-servers/{actual_dir}",
            entry_command,
        ]
    else:
        # Run from local path in development mode
        servers_path = get_servers_path()
        server_path = servers_path / actual_dir

        if server_path.exists():
            # The root wheel includes each server's project and uv.lock. Use an
            # immutable install in a source-and-lock-keyed cache so the exact
            # outer wheel also binds the child dependency closure.
            cmd = locked_server_command(server_path, entry_command)
            runtime_identity = locked_server_project_identity(server_path)
            child_environment["UV_PROJECT_ENVIRONMENT"] = str(
                _locked_server_environment_path(
                    server_path,
                    project_sha256=runtime_identity["project_sha256"],
                )
            )
            child_environment[LOCKED_SERVER_SCHEMA_ENV] = runtime_identity[
                "schema_version"
            ]
            child_environment[LOCKED_SERVER_PROJECT_SHA_ENV] = runtime_identity[
                "project_sha256"
            ]
            child_environment[LOCKED_SERVER_LOCK_SHA_ENV] = runtime_identity[
                "lock_sha256"
            ]
            child_environment.pop("VIRTUAL_ENV", None)
        else:
            # Not in development, try to run the command directly (if installed)
            cmd = [entry_command]

    # Add any additional arguments
    cmd.extend(args)

    # Execute the command
    try:
        subprocess.run(cmd, check=True, env=child_environment)
    except subprocess.CalledProcessError as e:
        sys.exit(e.returncode)
    except FileNotFoundError:
        if cmd[0] == "uvx":
            click.echo(
                "Error: uvx not found. Please install uv: https://github.com/astral-sh/uv"
            )
        else:
            click.echo(
                f"Error: {entry_command} not found. Please install the server package."
            )
        sys.exit(1)


@main.command("mcp-servers")
def list_mcp_servers():
    """List all available MCP servers"""
    servers = list_available_servers()
    if servers:
        click.echo("Available MCP servers:")
        for s in servers:
            click.echo(f"  - {s}")
    else:
        click.echo("No MCP servers found.")


@main.command("prompt")
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
        click.echo("\nUsage: uvx clio-kit prompt <prompt-name>")
        click.echo("   or: clio-kit prompt <prompt-name> (if installed)")
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


@main.command("prompts")
def list_prompts_cmd():
    """List all available prompts"""
    prompts = list_available_prompts()
    if prompts:
        click.echo("Available prompts:")
        for p in prompts:
            click.echo(f"  - {p}")
    else:
        click.echo("No prompts found.")


@main.command(
    "search",
    context_settings=dict(
        ignore_unknown_options=True,
        allow_extra_args=True,
    ),
)
@click.argument("args", nargs=-1, type=click.UNPROCESSED)
def search(args):
    """Run agentic search commands (query, index, serve, list, seed)."""

    if not args:
        click.echo("clio-kit search: Hybrid retrieval engine for scientific corpora")
        click.echo("\nSubcommands:")
        click.echo("  query   Run retrieval queries")
        click.echo("  index   Index documents into a namespace")
        click.echo("  serve   Start the FastAPI server")
        click.echo("  list    List indexed documents")
        click.echo("  seed    Seed sample data")
        click.echo("\nUsage: uvx clio-kit search <subcommand> [options]")
        click.echo("\nExamples:")
        click.echo(
            '  uvx clio-kit search query --namespace local_fs --q "pressure > 200 kPa"'
        )
        click.echo("  uvx clio-kit search index --namespace local_fs")
        click.echo("  uvx clio-kit search serve --port 8080")
        return

    search_path = get_search_path()
    if not search_path.exists():
        click.echo(f"Error: clio-agentic-search not found at {search_path}")
        click.echo("Install from: https://github.com/iowarp/clio-kit")
        sys.exit(1)

    cmd = [uvx_command(), "--from", str(search_path), "clio"]
    cmd.extend(args)

    try:
        subprocess.run(cmd, check=True, env=subprocess_env_with_github_https_rewrite())
    except subprocess.CalledProcessError as e:
        sys.exit(e.returncode)
    except FileNotFoundError:
        click.echo(
            "Error: uvx not found. Please install uv: https://github.com/astral-sh/uv"
        )
        sys.exit(1)


def cli():
    """Entry point for the CLI"""
    main()


if __name__ == "__main__":
    main()
