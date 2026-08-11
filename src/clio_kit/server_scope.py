"""Published scope of each embedded MCP server, read from its own manifest.

The scope is resolved from the server's shipped ``server.json`` rather than the
repository's ``mcp-server-versions.toml``, because the wheel's shared data
carries the server projects but not that map. Keeping the lookup here also keeps
the launcher module from growing past its size baseline.
"""

import json
from pathlib import Path

DEFAULT_SERVER_SCOPE = "scientific"
SERVER_SCOPE_ORDER = ("scientific", "general")
SERVER_SCOPE_HEADINGS = {"scientific": "Scientific", "general": "General purpose"}


def read_server_scope(server_path: Path) -> str:
    """Return one server project's published scope.

    An unreadable, malformed, or unclassified manifest degrades to the
    scientific default so listing servers never fails on metadata alone.
    """
    try:
        with open(server_path / "server.json", "r", encoding="utf-8") as handle:
            scope = json.load(handle).get("scope")
    except (OSError, ValueError):
        return DEFAULT_SERVER_SCOPE
    if not isinstance(scope, str) or scope not in SERVER_SCOPE_ORDER:
        return DEFAULT_SERVER_SCOPE
    return scope


def group_by_scope(scopes: dict[str, str]) -> dict[str, list[str]]:
    """Group server names by scope, in the order the listing presents them."""
    grouped: dict[str, list[str]] = {}
    for name, scope in scopes.items():
        grouped.setdefault(scope, []).append(name)
    return {
        scope: sorted(grouped[scope])
        for scope in SERVER_SCOPE_ORDER
        if grouped.get(scope)
    }


def format_server_listing(
    servers_root: Path,
    dir_name_map: dict[str, str],
    only_scope: str | None = None,
) -> list[str]:
    """Render the grouped `clio-kit mcp-servers` listing as output lines."""
    if not dir_name_map:
        return ["No MCP servers found."]
    grouped = group_by_scope(
        {
            name: read_server_scope(servers_root / directory)
            for name, directory in dir_name_map.items()
        }
    )
    if only_scope is not None:
        grouped = {only_scope: grouped.get(only_scope, [])}
        if not grouped[only_scope]:
            return [f"No MCP servers found under scope '{only_scope}'."]
    lines: list[str] = []
    for scope, members in grouped.items():
        if lines:
            lines.append("")
        lines.append(f"{SERVER_SCOPE_HEADINGS[scope]}:")
        lines.extend(f"  - {member}" for member in members)
    return lines
