#!/usr/bin/env python3
import dataclasses
import hashlib
import importlib.metadata as importlib_metadata
import json
import os
import shutil
import sys
import subprocess
import sysconfig
import tempfile
from pathlib import Path
import click

from clio_kit.env_cache import (
    CacheInUseError,
    EnvironmentInUseMarker,
    collect_cache_gc,
    default_event_emitter,
    discover_servers,
    load_cache_policy,
    maintain_after_build,
    measure_cache_budget,
)
from clio_kit.skills import SKILL_COMMANDS
from clio_kit.mcp_contracts import (
    load_mcp_user_contract,
    load_mcp_user_contract_index,
)

# Determine if we're running from development or installed package
MODULE_DIR = Path(__file__).parent
LOCKED_SERVER_LAUNCH_SCHEMA = "clio-kit.locked-server.v4"
_LOCKED_SERVER_RUNTIME_POLICY = "uv-run:materialized:frozen:no-editable:no-dev:v3"
LOCKED_SERVER_SCHEMA_ENV = "CLIO_KIT_LOCKED_SERVER_SCHEMA"
LOCKED_SERVER_PROJECT_SHA_ENV = "CLIO_KIT_LOCKED_SERVER_PROJECT_SHA256"
LOCKED_SERVER_LOCK_SHA_ENV = "CLIO_KIT_LOCKED_SERVER_LOCK_SHA256"
_RUNTIME_PROJECT_EXCLUDED_NAMES = frozenset(
    {
        ".git",
        ".coverage",
        ".DS_Store",
        ".mypy_cache",
        ".pytest_cache",
        ".ruff_cache",
        ".venv",
        ".virtualenv-app-data",
        "__pycache__",
        "dist",
        "coverage.xml",
        "htmlcov",
        "junit.xml",
        "tests",
    }
)
_MAX_RUNTIME_PROJECT_FILES = 20_000
_MAX_RUNTIME_PROJECT_BYTES = 512 * 1024 * 1024


def get_servers_path() -> Path:
    """Return server data owned by the active clio-kit installation."""
    shared_name = "clio-kit-mcp-servers"
    dev_path = MODULE_DIR.parent.parent / shared_name
    candidates = [
        # In an editable source checkout, the repository copy is authoritative.
        # The active environment may still contain shared data from an older
        # wheel build, so consulting distribution records first can silently
        # launch stale server code during contract generation and development.
        dev_path,
        *_distribution_shared_data_roots(shared_name),
        Path(sysconfig.get_path("data")) / shared_name,
        MODULE_DIR.parent / shared_name,
        MODULE_DIR / shared_name,
        Path(sys.prefix) / "share" / "clio-kit" / shared_name,
        Path(sys.executable).parent.parent / shared_name,
        Path(sys.executable).parent.parent / "share" / shared_name,
        Path(sys.executable).parent.parent / "purelib" / shared_name,
        Path(sys.executable).parent.parent / "data" / shared_name,
    ]
    seen: set[Path] = set()
    for candidate in candidates:
        try:
            resolved = candidate.resolve(strict=True)
        except OSError:
            continue
        if resolved in seen:
            continue
        seen.add(resolved)
        if _is_servers_root(resolved):
            return resolved
    # A mutable user-home compatibility directory is deliberately not a
    # fallback. Installed wheels must not be shadowed by legacy data.
    return dev_path


def _distribution_shared_data_roots(shared_name: str) -> list[Path]:
    """Locate shared data recorded by the active clio-kit distribution."""
    try:
        distribution = importlib_metadata.distribution("clio-kit")
    except importlib_metadata.PackageNotFoundError:
        return []
    for record in distribution.files or ():
        record_path = Path(str(record))
        if shared_name not in record_path.parts:
            continue
        try:
            located = Path(str(distribution.locate_file(record))).resolve(strict=True)
        except OSError:
            continue
        for parent in (located, *located.parents):
            if parent.name == shared_name and _is_servers_root(parent):
                return [parent]
    return []


def _is_servers_root(path: Path) -> bool:
    """Return whether a directory contains at least one embedded server project."""
    return path.is_dir() and any(path.glob("*/pyproject.toml"))


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


def list_available_servers():
    """List all available servers"""
    server_command_map, _ = auto_discover_mcps()
    return sorted(server_command_map.keys())


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
        "--no-dev",
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


def _runtime_project_files(server_path: Path) -> list[Path]:
    """Return bounded regular files that define one embedded server runtime."""
    try:
        root = server_path.resolve(strict=True)
    except OSError as exc:
        raise click.ClickException(
            f"Embedded MCP server path is unavailable: {server_path}"
        ) from exc
    is_junction = getattr(server_path, "is_junction", lambda: False)
    if not root.is_dir() or server_path.is_symlink() or is_junction():
        raise click.ClickException(
            f"Embedded MCP server '{server_path.name}' is not a real directory."
        )

    inputs: list[Path] = []
    total_bytes = 0
    for current_root, directory_names, file_names in os.walk(
        root,
        topdown=True,
        followlinks=False,
    ):
        current = Path(current_root)
        retained_directories: list[str] = []
        for directory_name in sorted(directory_names):
            if directory_name in _RUNTIME_PROJECT_EXCLUDED_NAMES:
                continue
            directory = current / directory_name
            directory_is_junction = getattr(directory, "is_junction", lambda: False)
            if directory.is_symlink() or directory_is_junction():
                raise click.ClickException(
                    f"Embedded MCP server '{server_path.name}' contains a linked path: "
                    f"{directory.relative_to(root)}"
                )
            retained_directories.append(directory_name)
        directory_names[:] = retained_directories
        for file_name in sorted(file_names):
            if file_name in _RUNTIME_PROJECT_EXCLUDED_NAMES:
                continue
            path = current / file_name
            file_is_junction = getattr(path, "is_junction", lambda: False)
            if path.is_symlink() or file_is_junction() or not path.is_file():
                raise click.ClickException(
                    f"Embedded MCP server '{server_path.name}' contains a non-regular "
                    f"runtime file: {path.relative_to(root)}"
                )
            inputs.append(path)
            total_bytes += path.stat().st_size
            if (
                len(inputs) > _MAX_RUNTIME_PROJECT_FILES
                or total_bytes > _MAX_RUNTIME_PROJECT_BYTES
            ):
                raise click.ClickException(
                    f"Embedded MCP server '{server_path.name}' exceeds the runtime "
                    "materialization bound."
                )
    for required_name in ("pyproject.toml", "uv.lock"):
        if root / required_name not in inputs:
            raise click.ClickException(
                f"Embedded MCP server '{server_path.name}' is incomplete: "
                f"missing {required_name}."
            )
    return inputs


def locked_server_project_identity(server_path: Path) -> dict[str, str]:
    """Hash the embedded server source and lock that define its child runtime."""
    root = server_path.resolve(strict=True)
    digest = hashlib.sha256()
    policy = _LOCKED_SERVER_RUNTIME_POLICY.encode("utf-8")
    digest.update(len(policy).to_bytes(8, "big"))
    digest.update(policy)
    inputs = _runtime_project_files(root)
    ordered_inputs = sorted(inputs, key=lambda item: item.relative_to(root).as_posix())
    digest.update(len(ordered_inputs).to_bytes(8, "big"))
    for path in ordered_inputs:
        relative_path = path.relative_to(root).as_posix().encode("utf-8")
        digest.update(len(relative_path).to_bytes(8, "big"))
        digest.update(relative_path)
        content_digest = hashlib.sha256()
        content_length = 0
        with path.open("rb") as stream:
            while chunk := stream.read(1024 * 1024):
                content_length += len(chunk)
                content_digest.update(chunk)
        digest.update(content_length.to_bytes(8, "big"))
        digest.update(content_digest.digest())
    lock_sha256 = hashlib.sha256((root / "uv.lock").read_bytes()).hexdigest()
    return {
        "schema_version": LOCKED_SERVER_LAUNCH_SCHEMA,
        "server_name": server_path.name,
        "project_sha256": digest.hexdigest(),
        "lock_sha256": lock_sha256,
    }


def materialize_locked_server_project(
    server_path: Path,
    *,
    identity: dict[str, str] | None = None,
) -> Path:
    """Atomically copy a wheel-embedded project outside uv's archive cache."""
    expected = identity or locked_server_project_identity(server_path)
    project_sha256 = expected["project_sha256"]
    target = (
        _clio_cache_root() / "mcp-projects" / server_path.name / project_sha256
    ).resolve()

    def verify_materialized(path: Path) -> None:
        actual = locked_server_project_identity(path)
        if (
            actual["schema_version"] != expected["schema_version"]
            or actual["project_sha256"] != project_sha256
            or actual["lock_sha256"] != expected["lock_sha256"]
        ):
            raise click.ClickException(
                f"Cached MCP server project failed identity verification: {path}"
            )

    if target.exists():
        verify_materialized(target)
        return target

    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = Path(
        tempfile.mkdtemp(
            dir=target.parent,
            prefix=f".{project_sha256}.",
            suffix=".tmp",
        )
    )
    source_root = server_path.resolve(strict=True)
    try:
        for source in _runtime_project_files(source_root):
            destination = temporary / source.relative_to(source_root)
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, destination)
        verify_materialized(temporary)
        try:
            os.replace(temporary, target)
        except OSError:
            if not target.is_dir():
                raise
        verify_materialized(target)
        return target
    finally:
        if temporary.exists():
            shutil.rmtree(temporary)


def _clio_cache_root() -> Path:
    """Return the operator-configurable cache root used by child runtimes."""
    configured_cache = os.getenv("CLIO_KIT_CACHE_DIR")
    if configured_cache:
        return Path(configured_cache).expanduser().resolve()
    return (
        Path(os.getenv("XDG_CACHE_HOME", str(Path.home() / ".cache"))).expanduser()
        / "clio-kit"
    ).resolve()


def _locked_server_environment_path(
    server_path: Path,
    *,
    project_sha256: str,
) -> Path:
    """Resolve one source-addressed child environment without mutating it."""
    return (
        _clio_cache_root()
        / "mcp-environments"
        / f"{server_path.name}-{project_sha256[:24]}"
    ).resolve()


@click.group(invoke_without_command=True)
@click.pass_context
def main(ctx):
    """clio-kit: Unified launcher for MCP servers, skills, and services"""
    if ctx.invoked_subcommand is None:
        click.echo("clio-kit: Unified launcher for MCP servers, skills, and services")
        click.echo("\nAvailable commands:")
        click.echo("  mcp-server   Run an MCP server")
        click.echo("  mcp-servers  List all available MCP servers")
        click.echo(
            "  search       Run agentic search (query, index, serve, list, seed)"
        )
        click.echo("  skill        Print a skill to stdout")
        click.echo("  skills       List all available skills")
        click.echo("\nUsage:")
        click.echo("  clio-kit mcp-server <server-name>")
        click.echo("  clio-kit search <subcommand>")
        click.echo("  clio-kit skill <skill-name>")
        click.echo("\nFor more help: clio-kit <command> --help")


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
        click.echo("\nUsage: clio-kit mcp-server <server-name>")
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

    if branch:
        # Run from a git branch: uvx owns its own ephemeral environment, so the
        # bounded local runtime cache does not apply.
        cmd = [
            uvx_command(),
            "--from",
            f"git+https://github.com/iowarp/clio-kit.git@{branch}#subdirectory=clio-kit-mcp-servers/{actual_dir}",
            entry_command,
        ]
        cmd.extend(args)
        _run_child_command(cmd, entry_command, child_environment)
        return

    server_path = get_servers_path() / actual_dir
    if server_path.exists():
        _run_locked_local_server(server_path, entry_command, args, child_environment)
        return

    # Not in development: try to run the installed console script directly.
    _run_child_command([entry_command, *args], entry_command, child_environment)


def _run_locked_local_server(
    server_path: Path,
    entry_command: str,
    args: tuple[str, ...],
    child_environment: dict[str, str],
) -> None:
    """Build, evict, and launch one embedded server from its source-locked cache.

    The root wheel ships each server's project and ``uv.lock``. The child runs
    from an immutable, source-and-lock-keyed environment so the outer wheel binds
    the child dependency closure exactly. After the environment for the current
    spec is confirmed built, older specs of this server are evicted and the
    private uv cache is pruned, keeping steady-state disk bounded to the newest
    spec. The in-use marker is held across the whole launch so a concurrent
    launch or ``cache gc`` never evicts the environment this process is using.
    """
    runtime_identity = locked_server_project_identity(server_path)
    runtime_project = materialize_locked_server_project(
        server_path,
        identity=runtime_identity,
    )
    project_sha256 = runtime_identity["project_sha256"]
    cache_root = _clio_cache_root()
    environment_path = _locked_server_environment_path(
        server_path,
        project_sha256=project_sha256,
    )
    child_environment["UV_PROJECT_ENVIRONMENT"] = str(environment_path)
    child_environment[LOCKED_SERVER_SCHEMA_ENV] = runtime_identity["schema_version"]
    child_environment[LOCKED_SERVER_PROJECT_SHA_ENV] = project_sha256
    child_environment[LOCKED_SERVER_LOCK_SHA_ENV] = runtime_identity["lock_sha256"]
    child_environment["UV_CACHE_DIR"] = str((cache_root / "uv-cache").resolve())
    child_environment["UV_PRERELEASE"] = "allow"
    child_environment.pop("VIRTUAL_ENV", None)

    uv = uv_command()
    try:
        environment_path.mkdir(parents=True, exist_ok=True)
    except OSError:
        pass
    with EnvironmentInUseMarker(cache_root, environment_path.name):
        if _build_locked_environment(uv, runtime_project, child_environment):
            try:
                maintain_after_build(
                    cache_root,
                    server_path.name,
                    project_sha256=project_sha256,
                    uv_executable=uv,
                )
            except Exception as exc:  # noqa: BLE001 - launch must never be blocked
                default_event_emitter(
                    {
                        "event": "cache_maintenance_failed",
                        "server": server_path.name,
                        "reason": repr(exc),
                    }
                )
        else:
            default_event_emitter(
                {
                    "event": "cache_maintenance_skipped",
                    "server": server_path.name,
                    "reason": "environment_build_failed",
                }
            )
        cmd = locked_server_command(runtime_project, entry_command)
        cmd.extend(args)
        _run_child_command(cmd, entry_command, child_environment)


def _build_locked_environment(
    uv: str,
    runtime_project: Path,
    child_environment: dict[str, str],
) -> bool:
    """Materialize the child environment for the current spec from its lock.

    A discrete, frozen sync gives a verifiable "environment built" signal before
    eviction removes any older spec, so a failed upgrade never destroys the
    previously working environment. Its output is confined to stderr because the
    child server's stdout is the JSON-RPC channel.
    """
    try:
        completed = subprocess.run(
            [
                uv,
                "sync",
                "--no-dev",
                "--no-editable",
                "--frozen",
                "--project",
                str(runtime_project),
            ],
            env=child_environment,
            capture_output=True,
        )
    except OSError:
        return False
    for stream in (completed.stdout, completed.stderr):
        if stream:
            sys.stderr.write(stream.decode("utf-8", errors="replace"))
    sys.stderr.flush()
    return completed.returncode == 0


def _run_child_command(
    cmd: list[str],
    entry_command: str,
    child_environment: dict[str, str],
) -> None:
    """Execute a child command, translating spawn failures to launcher errors."""
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


@main.command("mcp-contracts")
def list_mcp_contracts() -> None:
    """List shipped locked-server user contracts and their canonical digests."""
    index = load_mcp_user_contract_index()
    for entry in index["contracts"]:
        click.echo(f"{entry['contract_id']} {entry['contract_sha256']}")


@main.command("mcp-contract")
@click.argument("contract_id")
def show_mcp_contract(contract_id: str) -> None:
    """Print one verified locked-server user contract as machine-readable JSON."""
    artifact = load_mcp_user_contract(contract_id)
    click.echo(json.dumps(artifact, separators=(",", ":"), sort_keys=True))


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
        click.echo("\nUsage: clio-kit search <subcommand> [options]")
        click.echo("\nExamples:")
        click.echo(
            '  clio-kit search query --namespace local_fs --q "pressure > 200 kPa"'
        )
        click.echo("  clio-kit search index --namespace local_fs")
        click.echo("  clio-kit search serve --port 8080")
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


@main.group("cache")
def cache_group() -> None:
    """Inspect and reclaim the private MCP runtime cache."""


@cache_group.command("gc")
@click.option(
    "--keep",
    type=int,
    default=None,
    help="Environments to keep per server (overrides CLIO_KIT_ENV_KEEP).",
)
@click.option(
    "--dry-run",
    is_flag=True,
    help="Report what would be evicted without deleting anything.",
)
def cache_gc(keep: int | None, dry_run: bool) -> None:
    """Collapse every server to its newest N specs and prune the uv cache.

    This is the manual reclaim path for a box already polluted by unbounded
    environment history. It refuses to run while any environment is held by a
    live server, because deleting an environment mid-spawn corrupts the cache.
    """
    cache_root = _clio_cache_root()
    policy = load_cache_policy()
    if keep is not None:
        if keep < 1:
            raise click.ClickException("--keep must be >= 1")
        policy = dataclasses.replace(policy, keep_per_server=keep)
    try:
        eviction, prune = collect_cache_gc(
            cache_root,
            policy=policy,
            uv_executable=uv_command(),
            dry_run=dry_run,
        )
    except CacheInUseError as exc:
        raise click.ClickException(str(exc)) from exc
    budget = measure_cache_budget(cache_root, policy=policy)
    click.echo(
        json.dumps(
            {
                "dry_run": dry_run,
                "keep_per_server": policy.keep_per_server,
                "evicted": [
                    {
                        "server": entry.server,
                        "hash_prefix": entry.hash_prefix,
                        "bytes_freed": entry.bytes_freed,
                    }
                    for entry in eviction.evicted
                ],
                "skipped_in_use": [
                    {"server": entry.server, "hash_prefix": entry.hash_prefix}
                    for entry in eviction.skipped_in_use
                ],
                "bytes_freed": eviction.bytes_freed,
                "uv_cache_prune": {
                    "ran": prune.ran,
                    "ok": prune.ok,
                    "reason": prune.reason,
                },
                "cache_total_bytes": budget.total_bytes,
                "over_budget": budget.over_budget,
            },
            sort_keys=True,
        )
    )


@cache_group.command("status")
def cache_status() -> None:
    """Print a machine-readable summary of the private runtime cache footprint."""
    cache_root = _clio_cache_root()
    policy = load_cache_policy()
    budget = measure_cache_budget(cache_root, policy=policy)
    environments_root = cache_root / "mcp-environments"
    per_server: dict[str, int] = {}
    if environments_root.is_dir():
        for server in sorted(discover_servers(cache_root)):
            token = f"{server}-"
            per_server[server] = sum(
                1
                for child in environments_root.iterdir()
                if child.is_dir() and child.name.startswith(token)
            )
    click.echo(
        json.dumps(
            {
                "cache_root": str(cache_root),
                "total_bytes": budget.total_bytes,
                "max_bytes": budget.max_bytes,
                "over_budget": budget.over_budget,
                "keep_per_server": policy.keep_per_server,
                "environments_per_server": per_server,
            },
            sort_keys=True,
        )
    )


for _skill_command in SKILL_COMMANDS:
    main.add_command(_skill_command)


def cli():
    """Entry point for the CLI"""
    main()


if __name__ == "__main__":
    main()
