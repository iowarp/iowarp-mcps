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

from clio_kit.community import (
    read_community_entries,
    read_federated_marketplaces,
    write_shipped_marketplaces,
)
from clio_kit.plugins import read_skill_frontmatter
from clio_kit.mcp_contracts import generate_user_contract_artifacts

try:
    import tomllib
except ImportError:
    import tomli as tomllib  # type: ignore[import-not-found,no-redef]

REPO_URL = "https://github.com/iowarp/clio-kit"
# Attribution carried by every generated plugin manifest. Without it
# `claude plugin validate --strict` warns once per plugin, which is what keeps
# CI from gating on strict mode.
PLUGIN_AUTHOR: dict[str, str] = {
    "name": "IoWarp Team - Gnosis Research Center",
    "email": "grc@illinoistech.edu",
    "url": REPO_URL,
}
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
    "geo": ["geospatial", "mapping", "geojson", "visualization"],
    "scientific-catalog": ["dataset-catalog", "scientific-computing", "discovery"],
    "seismology": ["seismology", "earthquake", "waveform", "sac", "catalog"],
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


def read_bundles(repo_root: Path) -> dict[str, dict[str, Any]]:
    """Read the workflow bundle definitions, in declaration order.

    Declaration order is preserved so the generated marketplace lists bundles
    the way the file reads rather than alphabetically, which puts the entry
    workflow first instead of burying it.
    """
    versions_path = repo_root / SERVER_VERSIONS_FILE
    with open(versions_path, "rb") as f:
        data = tomllib.load(f)
    raw_bundles = data.get("bundles")
    if not isinstance(raw_bundles, dict) or not raw_bundles:
        raise ValueError(f"{versions_path} must define at least one [bundles.*] table")

    bundles: dict[str, dict[str, Any]] = {}
    for name, spec in raw_bundles.items():
        if not isinstance(spec, dict):
            raise ValueError(f"{versions_path} bundle {name!r} must be a table")
        servers = spec.get("servers")
        version = spec.get("version")
        description = spec.get("description")
        if not isinstance(servers, list) or not servers:
            raise ValueError(f"{versions_path} bundle {name!r} needs a servers list")
        if not all(isinstance(server, str) and server for server in servers):
            raise ValueError(f"{versions_path} bundle {name!r} has an invalid server")
        if servers != sorted(servers):
            raise ValueError(f"{versions_path} bundle {name!r} servers must be sorted")
        if len(set(servers)) != len(servers):
            raise ValueError(f"{versions_path} bundle {name!r} has duplicate servers")
        if not isinstance(version, str) or not version:
            raise ValueError(f"{versions_path} bundle {name!r} needs a version")
        if not isinstance(description, str) or not description:
            raise ValueError(f"{versions_path} bundle {name!r} needs a description")
        bundles[name] = {
            "version": version,
            "description": description,
            "servers": [cast(str, server) for server in servers],
        }
    return bundles


def assert_bundles_partition_servers(
    bundles: dict[str, dict[str, Any]],
    discovered_servers: set[str],
) -> None:
    """Fail unless every shipped server sits in exactly one bundle.

    Both directions matter. A bundle naming a server that does not exist is a
    stale membership list; a shipped server named by no bundle is one that
    would publish outside the catalogue, reachable only by someone who already
    knows it exists.
    """
    placements: dict[str, list[str]] = {}
    for bundle_name, spec in bundles.items():
        for server in spec["servers"]:
            placements.setdefault(server, []).append(bundle_name)

    unknown = sorted(set(placements) - discovered_servers)
    unplaced = sorted(discovered_servers - set(placements))
    duplicated = sorted(
        f"{server} in {', '.join(names)}"
        for server, names in placements.items()
        if len(names) > 1
    )
    if unknown or unplaced or duplicated:
        raise ValueError(
            "Bundle membership must partition the shipped servers: "
            f"unknown={unknown}, unplaced={unplaced}, duplicated={duplicated}"
        )


def write_bundle_plugin(
    repo_root: Path,
    bundle_name: str,
    spec: dict[str, Any],
) -> dict[str, Any]:
    """Write one bundle manifest and return its marketplace entry.

    The manifest carries no components of its own -- only the dependency list.
    Dependencies are bare names rather than version constraints because a
    constrained dependency resolves against a git tag named
    ``{plugin-name}--v{version}``, which would mean tagging every server plugin
    on every release for a pin nothing yet needs.
    """
    dependencies = [f"clio-{server}" for server in spec["servers"]]
    if (repo_root / "skills" / f"{bundle_name}-skills").is_dir():
        dependencies.append(f"{bundle_name}-skills")
    plugin_json = {
        "name": bundle_name,
        "description": spec["description"],
        "version": spec["version"],
        "author": PLUGIN_AUTHOR,
        "homepage": REPO_URL,
        "repository": REPO_URL,
        "license": "BSD-3-Clause",
        "dependencies": dependencies,
    }
    _write_json(
        repo_root / "plugins" / bundle_name / ".claude-plugin" / "plugin.json",
        plugin_json,
    )
    return {
        "name": bundle_name,
        "source": f"./plugins/{bundle_name}",
        "description": spec["description"],
        "version": spec["version"],
        "category": "workflow",
        "keywords": sorted(
            {tag for s in spec["servers"] for tag in SERVER_TAGS.get(s, [])}
        ),
        "license": "BSD-3-Clause",
        "repository": REPO_URL,
    }


def write_skills_plugin(
    repo_root: Path,
    bundle_name: str,
    spec: dict[str, Any],
) -> dict[str, Any] | None:
    """Write one bundle's skill plugin, or None when it has no skills yet.

    Skills are their own plugin rather than a path on the bundle because a
    plugin's component paths cannot traverse outside its own directory --
    anything beyond the plugin root is not copied to the cache on install, so
    a bundle pointing at a shared ``skills/`` folder would resolve to nothing.
    Making them a plugin means the bundle refers to them exactly as it refers
    to a server, and someone who wants the guidance without the servers can
    install the skill plugin on its own.
    """
    plugin_name = f"{bundle_name}-skills"
    plugin_dir = repo_root / "skills" / plugin_name
    if not plugin_dir.is_dir():
        return None

    skill_dirs = sorted(
        path for path in (plugin_dir / "skills").iterdir() if path.is_dir()
    )
    if not skill_dirs:
        raise ValueError(f"{plugin_dir} exists but ships no skills")
    skill_names = []
    for skill_dir in skill_dirs:
        skill_names.append(read_skill_frontmatter(skill_dir)["name"])
        # A skill with no recorded scenarios is untested by definition, and an
        # untested skill costs tokens in every session while nothing shows it
        # earns them. Recording the RED-GREEN scenarios is the minimum bar to
        # ship; running them is a separate step.
        if not (skill_dir / "evals.md").is_file():
            raise ValueError(
                f"{skill_dir} ships no evals.md; record the scenarios that "
                "distinguish this skill's behaviour from the baseline first"
            )

    workflow = spec["description"].rstrip(".")
    description = (
        f"Skills for the {bundle_name} workflow: {workflow[0].lower()}{workflow[1:]}."
    )
    plugin_json = {
        "name": plugin_name,
        "description": description,
        "version": spec["version"],
        "author": PLUGIN_AUTHOR,
        "homepage": REPO_URL,
        "repository": REPO_URL,
        "license": "BSD-3-Clause",
    }
    _write_json(plugin_dir / ".claude-plugin" / "plugin.json", plugin_json)
    return {
        "name": plugin_name,
        "source": f"./skills/{plugin_name}",
        "description": description,
        "version": spec["version"],
        "category": "skills",
        "keywords": skill_names,
        "license": "BSD-3-Clause",
        "repository": REPO_URL,
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
    repo_root: Path,
) -> None:
    """Write one contract-versioned plugin and its persistent MCP config."""
    description = project.get("description", "")

    plugin_json = {
        "name": f"clio-{server_name}",
        "description": description,
        "version": server_version,
        "author": PLUGIN_AUTHOR,
        "homepage": REPO_URL,
        "repository": REPO_URL,
        "license": "BSD-3-Clause",
    }
    # The plugin is written to its own directory under plugins/, NOT into the
    # server directory. A plugin's `source` is copied wholesale by the client
    # on install, and the server directory holds src/, tests/ and (in a working
    # clone) a built .venv -- none of which the plugin executes, because
    # .mcp.json invokes the separately installed `clio-kit` launcher. Pointing
    # `source` at the server directory copied ~180 MB per server and about a
    # gigabyte for a six-server bundle, all of it code that never runs.
    #
    # Users install by name (`clio-adios@clio-kit`), never by path, so moving
    # the manifest changes no user-facing coordinate. The registry coordinate
    # in server.json and the launcher's own discovery path are untouched.
    plugin_dir = repo_root / "plugins" / f"clio-{server_name}"
    _write_json(plugin_dir / ".claude-plugin" / "plugin.json", plugin_json)

    mcp_json = {
        f"clio-{server_name}": {
            "command": "clio-kit",
            "args": ["mcp-server", server_name],
        }
    }
    _write_json(plugin_dir / ".mcp.json", mcp_json)

    # Runtime descriptor: states outright what discovery used to infer by
    # string-matching pyproject.toml, and is the seam a non-Python server
    # would be described through.
    entry_point = next(
        (name for name in project.get("scripts", {}) if name.endswith("-mcp")),
        f"{server_name}-mcp",
    )
    descriptor = "\n".join(
        [
            "# Generated by scripts/generate_server_json.py -- do not edit.",
            f'name = "{server_name}"',
            'runtime = "python"',
            f'version = "{server_version}"',
            'lock = "uv.lock"',
            f'entry = "{entry_point}"',
            "",
        ]
    )
    (server_dir / "clio-server.toml").write_text(
        descriptor, encoding="utf-8", newline="\n"
    )


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
            "pluginRoot": "./plugins",
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
    bundles = read_bundles(repo_root)
    assert_bundles_partition_servers(bundles, discovered_servers)

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
            repo_root=repo_root,
        )
        print(f"  Wrote plugins/clio-{server_name} (manifest only, no source)")

        # Collect marketplace entry
        description = project.get("description", "")
        marketplace_plugins.append(
            {
                "name": f"clio-{server_name}",
                "source": f"./plugins/clio-{server_name}",
                "description": description,
                "version": server_versions[server_name],
                "category": server_scopes[server_name],
                "keywords": SERVER_TAGS.get(server_name, []),
                "license": "BSD-3-Clause",
                "repository": REPO_URL,
            }
        )

        generated.append(server_name)

    # Workflow bundles: dependency-only plugins over the servers just
    # generated, plus each bundle's skill plugin where one exists yet.
    for bundle_name, spec in bundles.items():
        skills_entry = write_skills_plugin(repo_root, bundle_name, spec)
        if skills_entry is not None:
            marketplace_plugins.append(skills_entry)
            skill_count = len(skills_entry["keywords"])
            print(f"Wrote skills/{skills_entry['name']} ({skill_count} skills)")
        marketplace_plugins.append(write_bundle_plugin(repo_root, bundle_name, spec))
        member_count = len(spec["servers"])
        suffix = " + skills" if skills_entry is not None else ""
        print(f"Wrote plugins/{bundle_name} ({member_count} servers{suffix})")

    # Outside contributions, indexed rather than vendored. They land in the
    # same catalogue as ours so both are found the same way.
    community_entries = read_community_entries(repo_root)
    generated_names = {entry["name"] for entry in marketplace_plugins}
    colliding = sorted(
        entry["name"] for entry in community_entries if entry["name"] in generated_names
    )
    if colliding:
        raise ValueError(
            f"community entries collide with generated plugins: {colliding}"
        )
    marketplace_plugins.extend(community_entries)
    if community_entries:
        print(f"Merged {len(community_entries)} community entries")

    # Federated marketplaces cannot ride in `plugins`: Claude Code has no
    # nested-marketplace concept and reports an unrecognised entry as an
    # unknown field it ignores. They are baked into the package instead, where
    # `clio-kit marketplaces` can print the one command that adds each.
    federated = read_federated_marketplaces(repo_root)
    write_shipped_marketplaces(repo_root / "src" / "clio_kit", federated)
    print(f"Wrote {len(federated)} federated marketplace referral(s)")

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
