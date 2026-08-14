"""Find the MCP servers a checkout or wheel ships, and how to start each one.

Discovery used to work by string-matching ``-mcp =`` inside each server's
``pyproject.toml`` and stripping that suffix to get a name. That is fragile in
two directions: any unrelated line containing ``-mcp =`` wins, because the
first match is taken, and it can only ever find Python projects, since a Go or
TypeScript server has no ``pyproject.toml`` to match against.

A generated ``clio-server.toml`` in each server directory states the same facts
outright -- what the server is called, what runtime starts it, and which lock
file pins it. The Python fallback below stays for a tree generated before the
descriptors existed, and for the source checkouts of forks that have not
regenerated.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

try:
    import tomllib
except ImportError:  # pragma: no cover - Python 3.10 fallback
    import tomli as tomllib  # type: ignore[import-not-found,no-redef]

DESCRIPTOR_NAME = "clio-server.toml"

# The runtime a descriptor may claim, and the lock file that pins it. Only
# `python` is startable from this repository today; the rest are named so a
# descriptor can be written and validated before the launcher can act on it,
# and so an unsupported runtime fails with its own name rather than as a
# missing-file error.
RUNTIME_LOCKS: dict[str, str] = {
    "python": "uv.lock",
    "node": "package-lock.json",
    "go": "go.sum",
}


def read_server_descriptor(server_dir: Path) -> dict[str, Any] | None:
    """Read one server's descriptor, or None when it has none."""
    descriptor_path = server_dir / DESCRIPTOR_NAME
    if not descriptor_path.is_file():
        return None
    with open(descriptor_path, "rb") as handle:
        data = tomllib.load(handle)

    name = data.get("name")
    runtime = data.get("runtime")
    entry = data.get("entry")
    if not isinstance(name, str) or not name:
        raise ValueError(f"{descriptor_path} needs a name")
    if runtime not in RUNTIME_LOCKS:
        raise ValueError(
            f"{descriptor_path} declares runtime {runtime!r}; "
            f"expected one of {sorted(RUNTIME_LOCKS)}"
        )
    if not isinstance(entry, str) or not entry:
        raise ValueError(f"{descriptor_path} needs an entry")
    return {"name": name, "runtime": runtime, "entry": entry}


def _entry_point_from_pyproject(server_dir: Path) -> str | None:
    """Recover a Python server's console script from its project metadata.

    Kept for trees generated before descriptors existed. Unlike the string
    match it replaces, this parses the file and reads ``[project.scripts]``, so
    a stray ``-mcp =`` elsewhere in the document cannot win.
    """
    pyproject = server_dir / "pyproject.toml"
    if not pyproject.is_file():
        return None
    try:
        with open(pyproject, "rb") as handle:
            data = tomllib.load(handle)
    except (OSError, tomllib.TOMLDecodeError):
        return None
    scripts = data.get("project", {}).get("scripts", {})
    if not isinstance(scripts, dict):
        return None
    for script_name in scripts:
        if isinstance(script_name, str) and script_name.endswith("-mcp"):
            return script_name
    return None


def is_servers_root(path: Path) -> bool:
    """Return whether a directory holds at least one embedded server."""
    if not path.is_dir():
        return False
    return any(path.glob(f"*/{DESCRIPTOR_NAME}")) or any(path.glob("*/pyproject.toml"))


def discover_servers_in(servers_path: Path) -> tuple[dict[str, str], dict[str, str]]:
    """Map each server name to its entry command and to its directory name.

    Two maps rather than one because a server's name and its directory are
    allowed to differ, and callers need both: the name is what a user types,
    the directory is where the locked project lives.
    """
    entry_commands: dict[str, str] = {}
    directories: dict[str, str] = {}
    if not servers_path.exists():
        return entry_commands, directories

    for item in sorted(servers_path.iterdir()):
        if not item.is_dir() or item.name.startswith("."):
            continue
        try:
            descriptor = read_server_descriptor(item)
        except (ValueError, OSError):
            # A malformed descriptor must not take the whole catalogue down
            # with it; the rest of the servers still start.
            continue
        if descriptor is not None:
            entry_commands[descriptor["name"]] = descriptor["entry"]
            directories[descriptor["name"]] = item.name
            continue

        entry_point = _entry_point_from_pyproject(item)
        if entry_point:
            entry_commands[entry_point.removesuffix("-mcp").lower()] = entry_point
            directories[entry_point.removesuffix("-mcp").lower()] = item.name
    return entry_commands, directories
