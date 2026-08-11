"""Signposts for MCP servers that merged into another server.

A retired name must not fail with a bare "unknown server". Anyone whose client
config still names it needs to be told where the capability went, in the same
breath as the failure -- otherwise the only signal a merge produces is an error
that looks like a typo.

Kept for one major after the merge, then removed with the entry here.
"""

RETIRED_SERVERS: dict[str, tuple[str, str]] = {
    "geojson": (
        "geo",
        "Its tools (inspect_geojson, validate_geojson, summarize_geojson, "
        "feature_bbox) ship in geo under the same names.",
    ),
    "seismic": (
        "sac",
        "Its tools (analyze_sequence, plot_sequence) ship in sac under the same names.",
    ),
}


def retirement_notice(server_name: str) -> str | None:
    """Return guidance for a retired server name, or None if it is not retired."""
    entry = RETIRED_SERVERS.get(server_name.lower())
    if entry is None:
        return None
    successor, detail = entry
    return (
        f"'{server_name}' merged into '{successor}' in clio-kit 2.8. {detail} "
        f"Run `clio-kit mcp-server {successor}` and update any client config "
        f"that still names '{server_name}'."
    )


def unknown_server_lines(server_name: str, available: object) -> list[str]:
    """Return the output for a server name the launcher cannot resolve.

    A retired name gets its successor and the reason; anything else gets the
    list of what is actually available.
    """
    notice = retirement_notice(server_name)
    if notice is not None:
        return [f"Error: Unknown server '{server_name}'", notice]
    names = ", ".join(sorted(available)) if available else ""
    return [f"Error: Unknown server '{server_name}'", f"Available servers: {names}"]
