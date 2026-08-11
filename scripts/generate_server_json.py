#!/usr/bin/env python3
"""Generate publishing manifests for MCP registries and client integrations.

Iterates each server in clio-kit-mcp-servers/, extracts live FastMCP metadata via
extract_mcp_metadata.py, reads pyproject.toml for version/description, and writes:
  - clio-kit-mcp-servers/{name}/server.json              (MCP registry manifest)
  - clio-kit-mcp-servers/{name}/.claude-plugin/plugin.json (Claude Code plugin)
  - clio-kit-mcp-servers/{name}/.mcp.json                (Claude Code MCP config)
  - .claude-plugin/marketplace.json                      (Claude Code marketplace)
  - claude_desktop_config.json                           (Claude Desktop config)
  - gemini-extension.json                                (Gemini CLI extension)

Usage:
    python scripts/generate_server_json.py [clio-kit-mcp-servers]
"""

import json
import re
import subprocess
import sys
from pathlib import Path
from typing import Any, cast

from clio_kit.mcp_contracts import generate_user_contract_artifacts

try:
    import tomllib
except ImportError:
    import tomli as tomllib  # type: ignore[import-not-found,no-redef]

REPO_URL = "https://github.com/iowarp/clio-kit"
MAX_DESCRIPTION_LENGTH = 100
SERVER_VERSIONS_FILE = "mcp-server-versions.toml"
STABLE_VERSION_PATTERN = re.compile(r"[1-9][0-9]*\.[0-9]+\.[0-9]+")

# Domain-specific tags for each server
SERVER_TAGS: dict[str, list[str]] = {
    "adios": ["scientific-computing", "adios2", "bp5", "data-io", "hpc"],
    "arxiv": ["research", "arxiv", "papers", "literature-search"],
    "chronolog": ["logging", "distributed-systems", "hpc", "time-series"],
    "compression": ["compression", "gzip", "file-operations", "data-management"],
    "darshan": ["io-profiling", "performance-analysis", "hpc", "darshan"],
    "geo": ["geospatial", "mapping", "geojson", "visualization"],
    "hdf5": ["scientific-computing", "hdf5", "data-analysis", "hierarchical-data"],
    "jarvis": ["pipeline-management", "hpc", "workflow-automation"],
    "lmod": ["environment-modules", "hpc", "lmod", "system-administration"],
    "ndp": ["datasets", "ckan", "national-data-platform", "data-discovery"],
    "node-hardware": ["hardware-monitoring", "system-info", "performance"],
    "pandas": ["data-analysis", "pandas", "dataframes", "statistics"],
    "parallel-sort": ["log-processing", "sorting", "large-files", "hpc"],
    "paraview": ["scientific-visualization", "paraview", "3d-rendering", "hpc"],
    "parquet": ["parquet", "apache-arrow", "columnar-data", "data-analysis"],
    "plot": ["data-visualization", "matplotlib", "plotting", "charts"],
    "scientific-catalog": ["dataset-catalog", "scientific-computing", "discovery"],
    "seismology": ["seismology", "earthquake", "waveform", "sac", "catalog"],
    "slurm": ["hpc", "slurm", "job-scheduling", "cluster-management"],
    "spack": ["package-management", "hpc", "scientific-computing"],
    "terrain": ["terrain", "dem", "point-cloud", "geospatial"],
    "web": ["web", "fetch", "search", "agentic-web"],
}


def read_root_version(repo_root: Path) -> str:
    """Read the root pyproject.toml version (the PyPI package version)."""
    pyproject_path = repo_root / "pyproject.toml"
    with open(pyproject_path, "rb") as f:
        data = tomllib.load(f)
    return data.get("project", {}).get("version", "1.0.0")


def read_server_versions(repo_root: Path) -> dict[str, str]:
    """Read the independent MCP Registry contract versions."""
    versions_path = repo_root / SERVER_VERSIONS_FILE
    with open(versions_path, "rb") as f:
        data = tomllib.load(f)

    if data.get("schema-version") != 1:
        raise ValueError(f"{versions_path} must use schema-version = 1")
    raw_versions = data.get("servers")
    if not isinstance(raw_versions, dict) or not raw_versions:
        raise ValueError(f"{versions_path} must define a nonempty [servers] table")

    versions: dict[str, str] = {}
    for raw_name, raw_version in raw_versions.items():
        if not isinstance(raw_name, str) or not raw_name:
            raise ValueError(f"{versions_path} contains an invalid server name")
        if (
            not isinstance(raw_version, str)
            or STABLE_VERSION_PATTERN.fullmatch(raw_version) is None
        ):
            raise ValueError(
                f"{versions_path} has an invalid stable version for {raw_name!r}"
            )
        versions[raw_name] = raw_version
    if list(versions) != sorted(versions):
        raise ValueError(f"{versions_path} server inventory must be sorted")
    return versions


def read_registry_publish_servers(repo_root: Path) -> tuple[str, ...]:
    """Read the MCP servers whose contract versions this release publishes.

    An empty list is valid and expected: it means no server's registry
    contract (tool names/schemas under [servers]) changed this release, so
    there is nothing to republish. A server is only listed here alongside a
    real version bump under [servers], in the same PR that changes its
    contract; it is removed again once published so the next release does
    not collide with an already-published version.
    """
    versions_path = repo_root / SERVER_VERSIONS_FILE
    with open(versions_path, "rb") as f:
        data = tomllib.load(f)
    release = data.get("mcp-registry-release")
    raw_servers = release.get("publish") if isinstance(release, dict) else None
    if not isinstance(raw_servers, list):
        raise ValueError(
            f"{versions_path} must define mcp-registry-release.publish as a list"
        )
    if not all(isinstance(server, str) and server for server in raw_servers):
        raise ValueError(f"{versions_path} has an invalid publish server")
    servers = tuple(cast(str, server) for server in raw_servers)
    if len(set(servers)) != len(servers):
        raise ValueError(f"{versions_path} has duplicate publish servers")
    if servers != tuple(sorted(servers)):
        raise ValueError(f"{versions_path} publish inventory must be sorted")
    return servers


def read_server_classification(
    repo_root: Path,
    server_versions: dict[str, str],
) -> dict[str, str]:
    """Resolve every server's published scope from the version map.

    Servers are scientific unless [classification] lists them as general, so the
    table records only the exceptions. Every listed name must exist under
    [servers]: a rename or removal then fails generation loudly instead of
    leaving a server silently misclassified in the published manifests.
    """
    versions_path = repo_root / SERVER_VERSIONS_FILE
    with open(versions_path, "rb") as f:
        data = tomllib.load(f)
    classification = data.get("classification")
    raw_general = (
        classification.get("general") if isinstance(classification, dict) else None
    )
    if not isinstance(raw_general, list):
        raise ValueError(
            f"{versions_path} must define classification.general as a list"
        )
    if not all(isinstance(server, str) and server for server in raw_general):
        raise ValueError(f"{versions_path} has an invalid general server")
    general = tuple(cast(str, server) for server in raw_general)
    if len(set(general)) != len(general):
        raise ValueError(f"{versions_path} has duplicate general servers")
    if general != tuple(sorted(general)):
        raise ValueError(f"{versions_path} general inventory must be sorted")
    unknown = sorted(set(general) - set(server_versions))
    if unknown:
        raise ValueError(
            f"{versions_path} classifies unknown servers: {', '.join(unknown)}"
        )
    return {
        name: ("general" if name in set(general) else "scientific")
        for name in server_versions
    }


def read_pyproject(server_dir: Path) -> dict[str, Any]:
    """Read pyproject.toml and return the [project] table."""
    pyproject_path = server_dir / "pyproject.toml"
    with open(pyproject_path, "rb") as f:
        data = tomllib.load(f)
    return data.get("project", {})


def extract_metadata(server_dir: Path) -> dict[str, Any] | None:
    """Run extract_mcp_metadata.py in the server's environment."""
    script_path = Path(__file__).parent / "extract_mcp_metadata.py"
    try:
        result = subprocess.run(
            ["uv", "run", "python", str(script_path)],
            cwd=str(server_dir),
            capture_output=True,
            text=True,
            timeout=60,
        )
        if result.returncode != 0:
            print(
                f"  Warning: metadata extraction failed: {result.stderr.strip()[:200]}"
            )
            return None
        return json.loads(result.stdout)
    except (subprocess.TimeoutExpired, json.JSONDecodeError, FileNotFoundError) as e:
        print(f"  Warning: could not extract metadata: {e}")
        return None


def _write_json(path: Path, data: dict[str, Any]) -> None:
    """Write a dict as formatted JSON to a file, creating parent dirs."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        json.dump(data, f, indent=2)
        f.write("\n")


# --- MCP Registry (server.json) ---


def build_server_json(
    server_name: str,
    project: dict[str, Any],
    metadata: dict[str, Any],
    *,
    server_version: str,
    pypi_version: str,
    scope: str,
) -> dict[str, Any]:
    """Build a registry manifest with independent server and wheel versions."""
    description = project.get("description", "")
    if len(description) > MAX_DESCRIPTION_LENGTH:
        description = (
            description[: MAX_DESCRIPTION_LENGTH - 3].rsplit(" ", 1)[0] + "..."
        )

    tools = [
        {"name": t["name"], "description": t["description"]}
        for t in metadata.get("tools", [])
    ]
    resources = [
        {"uri": r["uri"], "name": r["name"], "description": r["description"]}
        for r in metadata.get("resources", [])
    ]
    resource_templates = [
        {
            "uri_template": t["uri_template"],
            "name": t["name"],
            "description": t["description"],
        }
        for t in metadata.get("resource_templates", [])
    ]
    prompts = [
        {"name": p["name"], "description": p["description"]}
        for p in metadata.get("prompts", [])
    ]

    server_json: dict[str, Any] = {
        "$schema": "https://static.modelcontextprotocol.io/schemas/2025-12-11/server.schema.json",
        "name": f"io.github.iowarp/{server_name}-mcp",
        "title": f"CLIO {server_name.replace('-', ' ').title()}",
        "description": description,
        "version": server_version,
        "repository": {"url": REPO_URL, "source": "github"},
        "packages": [
            {
                "registryType": "pypi",
                "identifier": "clio-kit",
                "version": pypi_version,
                "transport": {"type": "stdio"},
                "packageArguments": [
                    {"type": "positional", "value": "mcp-server"},
                    {"type": "positional", "value": server_name},
                ],
            }
        ],
        "tools": tools,
    }

    if resources:
        server_json["resources"] = resources
    if resource_templates:
        server_json["resource_templates"] = resource_templates
    if prompts:
        server_json["prompts"] = prompts

    server_json["tags"] = SERVER_TAGS.get(server_name, [])
    # Shipped beside each server so the launcher can group its listing without
    # the version map, which the wheel's shared-data does not carry.
    server_json["scope"] = scope
    return server_json


# --- Claude Code Plugin Marketplace ---


def write_claude_plugin_files(
    server_dir: Path,
    server_name: str,
    project: dict[str, Any],
    *,
    server_version: str,
) -> None:
    """Write one contract-versioned plugin and its persistent MCP config."""
    description = project.get("description", "")

    plugin_json = {
        "name": f"clio-{server_name}",
        "description": description,
        "version": server_version,
    }
    _write_json(server_dir / ".claude-plugin" / "plugin.json", plugin_json)

    mcp_json = {
        f"clio-{server_name}": {
            "command": "clio-kit",
            "args": ["mcp-server", server_name],
        }
    }
    _write_json(server_dir / ".mcp.json", mcp_json)


def build_marketplace_json(
    server_entries: list[dict[str, Any]],
    *,
    pypi_version: str,
) -> dict[str, Any]:
    """Build the root-versioned marketplace of contract-versioned plugins."""
    return {
        "name": "clio-kit",
        "owner": {
            "name": "IoWarp Team - Gnosis Research Center",
            "email": "grc@illinoistech.edu",
        },
        "metadata": {
            "description": "CLIO Kit - MCP Servers for Scientific Computing and HPC",
            "version": pypi_version,
            "pluginRoot": "./clio-kit-mcp-servers",
        },
        "plugins": server_entries,
    }


# --- Claude Desktop Config ---


def build_claude_desktop_config(server_names: list[str]) -> dict[str, Any]:
    """Build a master claude_desktop_config.json with all servers."""
    servers: dict[str, Any] = {}
    for name in sorted(server_names):
        servers[f"clio-{name}"] = {
            "command": "clio-kit",
            "args": ["mcp-server", name],
        }
    return {"mcpServers": servers}


# --- Gemini CLI Extension ---


def build_gemini_extension(
    server_names: list[str],
    *,
    pypi_version: str,
) -> dict[str, Any]:
    """Build the root-versioned Gemini extension bundling all servers."""
    mcp_servers: dict[str, Any] = {}
    for name in sorted(server_names):
        mcp_servers[f"clio-{name}"] = {
            "command": "clio-kit",
            "args": ["mcp-server", name],
        }
    return {
        "name": "clio-kit",
        "version": pypi_version,
        "mcpServers": mcp_servers,
    }


# --- Main Generation ---


def generate_all(mcps_dir: str) -> None:
    """Generate all publishing manifests."""
    mcps_path = Path(mcps_dir)
    if not mcps_path.exists():
        print(f"Error: {mcps_dir} does not exist")
        sys.exit(1)

    repo_root = mcps_path.parent
    pypi_version = read_root_version(repo_root)
    server_versions = read_server_versions(repo_root)
    registry_publish_servers = read_registry_publish_servers(repo_root)
    server_scopes = read_server_classification(repo_root, server_versions)
    print(f"Root PyPI version: {pypi_version}")
    generated: list[str] = []
    failed: list[str] = []
    marketplace_plugins: list[dict[str, Any]] = []

    server_dirs = sorted(
        server_dir
        for server_dir in mcps_path.iterdir()
        if server_dir.is_dir()
        and not server_dir.name.startswith(".")
        and (server_dir / "pyproject.toml").exists()
    )
    discovered_servers = {server_dir.name for server_dir in server_dirs}
    configured_servers = set(server_versions)
    if discovered_servers != configured_servers:
        missing = sorted(discovered_servers - configured_servers)
        unknown = sorted(configured_servers - discovered_servers)
        raise ValueError(
            "MCP server version inventory differs from shipped projects: "
            f"missing={missing}, unknown={unknown}"
        )
    unknown_publish_servers = set(registry_publish_servers) - discovered_servers
    if unknown_publish_servers:
        raise ValueError(
            "MCP Registry release inventory contains unknown projects: "
            f"{sorted(unknown_publish_servers)}"
        )

    for server_dir in server_dirs:
        if not server_dir.is_dir() or server_dir.name.startswith("."):
            continue

        pyproject_file = server_dir / "pyproject.toml"
        if not pyproject_file.exists():
            continue

        server_name = server_dir.name
        print(f"Processing {server_name}...")

        project = read_pyproject(server_dir)

        # server.json: only update if metadata extraction succeeds
        metadata = extract_metadata(server_dir)
        if metadata is not None:
            server_json = build_server_json(
                server_name,
                project,
                metadata,
                server_version=server_versions[server_name],
                pypi_version=pypi_version,
                scope=server_scopes[server_name],
            )
            _write_json(server_dir / "server.json", server_json)
            tool_count = len(server_json.get("tools", []))
            print(f"  Wrote server.json ({tool_count} tools)")
        elif not (server_dir / "server.json").exists():
            print("  Warning: no metadata and no existing server.json")
            failed.append(server_name)
            continue
        else:
            print("  Skipped server.json (using existing, extraction failed)")

        # Claude Code plugin files: always write (no metadata needed)
        write_claude_plugin_files(
            server_dir,
            server_name,
            project,
            server_version=server_versions[server_name],
        )
        print("  Wrote .claude-plugin/plugin.json + .mcp.json")

        # Collect marketplace entry
        description = project.get("description", "")
        marketplace_plugins.append(
            {
                "name": f"clio-{server_name}",
                "source": f"./clio-kit-mcp-servers/{server_name}",
                "description": description,
                "version": server_versions[server_name],
                "category": server_scopes[server_name],
                "keywords": SERVER_TAGS.get(server_name, []),
                "license": "BSD-3-Clause",
                "repository": REPO_URL,
            }
        )

        generated.append(server_name)

    # Claude Code marketplace manifest
    marketplace = build_marketplace_json(
        marketplace_plugins,
        pypi_version=pypi_version,
    )
    _write_json(repo_root / ".claude-plugin" / "marketplace.json", marketplace)
    print(
        f"\nWrote .claude-plugin/marketplace.json ({len(marketplace_plugins)} plugins)"
    )

    # Claude Desktop master config
    claude_config = build_claude_desktop_config(generated)
    _write_json(repo_root / "claude_desktop_config.json", claude_config)
    print(f"Wrote claude_desktop_config.json ({len(generated)} servers)")

    # Gemini CLI extension manifest
    gemini_ext = build_gemini_extension(generated, pypi_version=pypi_version)
    _write_json(repo_root / "gemini-extension.json", gemini_ext)
    print(f"Wrote gemini-extension.json ({len(generated)} servers)")

    # The registry manifest intentionally carries only abbreviated tool metadata.
    # Bind the full locked JARVIS, SLURM, and Spack user schemas from actual stdio
    # tools/list responses in separately shipped canonical artifacts.
    contracts = generate_user_contract_artifacts(repo_root)
    for contract in contracts:
        print(
            "Wrote MCP user contract "
            f"{contract['contract_id']} ({contract['contract_sha256']})"
        )

    # Summary
    print(f"\nGenerated: {len(generated)} servers")
    if failed:
        print(f"Failed: {len(failed)} servers: {', '.join(failed)}")


def main() -> None:
    mcps_dir = sys.argv[1] if len(sys.argv) > 1 else "clio-kit-mcp-servers"
    generate_all(mcps_dir)


if __name__ == "__main__":
    main()
