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
import subprocess
import sys
from pathlib import Path
from typing import Any

try:
    import tomllib
except ImportError:
    import tomli as tomllib  # type: ignore[import-not-found,no-redef]

REPO_URL = "https://github.com/iowarp/clio-kit"
MAX_DESCRIPTION_LENGTH = 100

# Domain-specific tags for each server
SERVER_TAGS: dict[str, list[str]] = {
    "adios": ["scientific-computing", "adios2", "bp5", "data-io", "hpc"],
    "arxiv": ["research", "arxiv", "papers", "literature-search"],
    "chronolog": ["logging", "distributed-systems", "hpc", "time-series"],
    "compression": ["compression", "gzip", "file-operations", "data-management"],
    "darshan": ["io-profiling", "performance-analysis", "hpc", "darshan"],
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
    "slurm": ["hpc", "slurm", "job-scheduling", "cluster-management"],
    "spack": ["package-management", "hpc", "scientific-computing"],
}


def read_root_version(repo_root: Path) -> str:
    """Read the root pyproject.toml version (the PyPI package version)."""
    pyproject_path = repo_root / "pyproject.toml"
    with open(pyproject_path, "rb") as f:
        data = tomllib.load(f)
    return data.get("project", {}).get("version", "1.0.0")


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
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)
        f.write("\n")


# --- MCP Registry (server.json) ---


def build_server_json(
    server_name: str,
    project: dict[str, Any],
    metadata: dict[str, Any],
    pypi_version: str = "1.0.0",
) -> dict[str, Any]:
    """Build the server.json manifest for the official MCP registry."""
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
        "version": pypi_version,
        "repository": {"url": REPO_URL, "source": "github"},
        "packages": [
            {
                "registryType": "pypi",
                "identifier": "clio-kit",
                "version": pypi_version,
                "transport": {"type": "stdio"},
                "arguments": ["clio-kit", "mcp-server", server_name],
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
    return server_json


# --- Claude Code Plugin Marketplace ---


def write_claude_plugin_files(
    server_dir: Path,
    server_name: str,
    project: dict[str, Any],
) -> None:
    """Write .claude-plugin/plugin.json and .mcp.json for a server."""
    description = project.get("description", "")
    version = project.get("version", "1.0.0")

    plugin_json = {
        "name": f"clio-{server_name}",
        "description": description,
        "version": version,
    }
    _write_json(server_dir / ".claude-plugin" / "plugin.json", plugin_json)

    mcp_json = {
        f"clio-{server_name}": {
            "command": "uvx",
            "args": ["clio-kit", "mcp-server", server_name],
        }
    }
    _write_json(server_dir / ".mcp.json", mcp_json)


def build_marketplace_json(
    server_entries: list[dict[str, Any]],
) -> dict[str, Any]:
    """Build the .claude-plugin/marketplace.json for the repo root."""
    return {
        "name": "clio-kit",
        "owner": {
            "name": "IoWarp Team - Gnosis Research Center",
            "email": "grc@illinoistech.edu",
        },
        "metadata": {
            "description": "CLIO Kit - MCP Servers for Scientific Computing and HPC",
            "version": "1.0.0",
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
            "command": "uvx",
            "args": ["clio-kit", "mcp-server", name],
        }
    return {"mcpServers": servers}


# --- Gemini CLI Extension ---


def build_gemini_extension(server_names: list[str]) -> dict[str, Any]:
    """Build gemini-extension.json bundling all servers."""
    mcp_servers: dict[str, Any] = {}
    for name in sorted(server_names):
        mcp_servers[f"clio-{name}"] = {
            "command": "uvx",
            "args": ["clio-kit", "mcp-server", name],
        }
    return {
        "name": "clio-kit",
        "version": "1.0.0",
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
    print(f"Root PyPI version: {pypi_version}")
    generated: list[str] = []
    failed: list[str] = []
    marketplace_plugins: list[dict[str, Any]] = []

    for server_dir in sorted(mcps_path.iterdir()):
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
                server_name, project, metadata, pypi_version=pypi_version
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
        write_claude_plugin_files(server_dir, server_name, project)
        print("  Wrote .claude-plugin/plugin.json + .mcp.json")

        # Collect marketplace entry
        description = project.get("description", "")
        version = project.get("version", "1.0.0")
        marketplace_plugins.append(
            {
                "name": f"clio-{server_name}",
                "source": f"./clio-kit-mcp-servers/{server_name}",
                "description": description,
                "version": version,
                "category": "development",
                "keywords": SERVER_TAGS.get(server_name, []),
                "license": "BSD-3-Clause",
                "repository": REPO_URL,
            }
        )

        generated.append(server_name)

    # Claude Code marketplace manifest
    marketplace = build_marketplace_json(marketplace_plugins)
    _write_json(repo_root / ".claude-plugin" / "marketplace.json", marketplace)
    print(
        f"\nWrote .claude-plugin/marketplace.json ({len(marketplace_plugins)} plugins)"
    )

    # Claude Desktop master config
    claude_config = build_claude_desktop_config(generated)
    _write_json(repo_root / "claude_desktop_config.json", claude_config)
    print(f"Wrote claude_desktop_config.json ({len(generated)} servers)")

    # Gemini CLI extension manifest
    gemini_ext = build_gemini_extension(generated)
    _write_json(repo_root / "gemini-extension.json", gemini_ext)
    print(f"Wrote gemini-extension.json ({len(generated)} servers)")

    # Summary
    print(f"\nGenerated: {len(generated)} servers")
    if failed:
        print(f"Failed: {len(failed)} servers: {', '.join(failed)}")


def main() -> None:
    mcps_dir = sys.argv[1] if len(sys.argv) > 1 else "clio-kit-mcp-servers"
    generate_all(mcps_dir)


if __name__ == "__main__":
    main()
