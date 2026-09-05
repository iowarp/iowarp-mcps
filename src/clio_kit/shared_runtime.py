"""Execute MCP servers in their shared CLIO Kit installation (#1319).

Invocation never installs packages or allocates an environment. Server source
and dependency declarations have independent build identities; the installed
dependency inventory is observed on demand, not mislabeled as a frozen lock.
"""

from __future__ import annotations

import importlib
import json
import os
import platform
import sys
from importlib import metadata
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlsplit

import click
from packaging.requirements import Requirement
from packaging.specifiers import SpecifierSet
from packaging.utils import canonicalize_name

from clio_kit.runtime_catalog import CATALOG_SCHEMA, digest_json

RUNTIME_SCHEMA = "clio-kit.shared-runtime.v1"


def load_catalog() -> dict[str, Any]:
    """Read the small catalog shipped with the active installation."""
    path = Path(__file__).with_name("runtime-catalog.json")
    try:
        catalog = json.loads(path.read_text(encoding="utf-8"))
        if (
            not isinstance(catalog, dict)
            or catalog.get("schema_version") != CATALOG_SCHEMA
            or not isinstance(catalog.get("servers"), dict)
        ):
            raise ValueError("unsupported runtime catalog")
        return catalog["servers"]
    except (OSError, ValueError) as exc:
        raise click.ClickException(
            "CLIO Kit runtime catalog is unavailable; reinstall CLIO Kit."
        ) from exc


def server_spec(name: str) -> dict[str, Any]:
    """Resolve a server without scanning or importing every server project."""
    servers = load_catalog()
    try:
        return dict(servers[name.lower()])
    except KeyError as exc:
        raise click.ClickException(
            f"Unknown MCP server {name!r}. Available: {', '.join(sorted(servers))}"
        ) from exc


def dependency_problems(spec: dict[str, Any]) -> list[str]:
    """Check declared production dependencies in the current interpreter."""
    problems: list[str] = []
    if not SpecifierSet(spec["requires_python"]).contains(
        platform.python_version(), prereleases=True
    ):
        problems.append(f"Python {spec['requires_python']} required")
    for raw in spec["requirements"]:
        requirement = Requirement(raw)
        if requirement.marker and not requirement.marker.evaluate({"extra": ""}):
            continue
        try:
            version = metadata.version(requirement.name)
        except metadata.PackageNotFoundError:
            problems.append(f"{requirement.name} missing")
            continue
        if requirement.url:
            # External wheels are an explicit deployment input. A package with
            # the same name from an index does not prove the pinned artifact.
            direct = metadata.distribution(requirement.name).read_text(
                "direct_url.json"
            )
            try:
                origin = json.loads(direct or "{}")
                if not isinstance(origin, dict) or not isinstance(
                    origin.get("archive_info", {}), dict
                ):
                    raise ValueError("invalid direct URL metadata")
                expected = urlsplit(requirement.url)
                hashes = origin.get("archive_info", {}).get("hashes", {})
                if not isinstance(hashes, dict):
                    raise ValueError("invalid archive hash metadata")
                expected_hash = parse_qs(expected.fragment).get("sha256", [None])[0]
                if origin.get("url") != requirement.url.split("#", 1)[0] or (
                    expected_hash and hashes.get("sha256") != expected_hash
                ):
                    problems.append(
                        f"{requirement.name} requires the declared external artifact"
                    )
            except (ValueError, TypeError):
                problems.append(
                    f"{requirement.name} has invalid installation origin metadata"
                )
        if requirement.specifier and not requirement.specifier.contains(
            version, prereleases=True
        ):
            problems.append(
                f"{requirement.name}{requirement.specifier} required (installed {version})"
            )
    return problems


def run_server(name: str, args: tuple[str, ...]) -> None:
    """Run one server in this process and installation, preserving workspace/env."""
    spec = server_spec(name)
    problems = dependency_problems(spec)
    if problems:
        external = " ".join(
            f"--with '{raw}'" for raw in spec["requirements"] if Requirement(raw).url
        )
        raise click.ClickException(
            f"MCP server {name!r} needs dependencies in this CLIO Kit installation: "
            f"{'; '.join(problems)}. Install 'clio-kit[{spec['extra']}]' in the same "
            "environment, combining all desired extras (e.g. 'clio-kit[science]'). "
            f"External artifact options: {external or 'none'}. No environment was created."
        )
    from clio_kit import get_servers_path

    source = get_servers_path() / spec["directory"] / "src"
    if not source.is_dir():
        raise click.ClickException(
            f"Installed MCP source is missing: {source}; reinstall CLIO Kit."
        )
    # A shared install must never claim the old per-server frozen-lock evidence,
    # including when invoked from a parent with stale inherited launcher values.
    for key in tuple(os.environ):
        if key.startswith("CLIO_KIT_LOCKED_SERVER_"):
            del os.environ[key]
    os.environ.update(
        {
            "CLIO_KIT_RUNTIME_SCHEMA": RUNTIME_SCHEMA,
            "CLIO_KIT_RUNTIME_PREFIX": sys.prefix,
            "CLIO_KIT_RUNTIME_SOURCE_SHA256": spec["source_sha256"],
            "CLIO_KIT_RUNTIME_REQUIREMENTS_SHA256": spec["requirements_sha256"],
            "CLIO_KIT_RUNTIME_DEPENDENCY_POLICY": "installed",
        }
    )
    sys.path.insert(0, str(source))
    sys.argv = [spec["command"], *(args[1:] if args[:1] == ("--",) else args)]
    module_name, function_name = spec["entry_point"].split(":", 1)
    try:
        entry = getattr(importlib.import_module(module_name), function_name)
    except ImportError as exc:
        raise click.ClickException(
            f"MCP server {name!r} could not import its installed runtime: {exc}"
        ) from exc
    entry()


def runtime_info(names: tuple[str, ...]) -> dict[str, Any]:
    """Report observed installation identity without claiming a per-server lock."""
    catalog = load_catalog()
    selected = names or tuple(sorted(catalog))
    rows = {name: server_spec(name) for name in selected}
    inventory = sorted(
        {
            (canonicalize_name(distribution.metadata["Name"]), distribution.version)
            for distribution in metadata.distributions()
            if distribution.metadata["Name"]
            and canonicalize_name(distribution.metadata["Name"]) != "clio-kit"
        }
    )
    dependency_identity = {
        "python": platform.python_version(),
        "implementation": platform.python_implementation(),
        "platform": sys.platform,
        "machine": platform.machine(),
        "packages": inventory,
    }
    return {
        "schema_version": RUNTIME_SCHEMA,
        "python": sys.executable,
        "prefix": sys.prefix,
        "dependency_evidence": "installed-version-inventory",
        "source_evidence": "build-recorded-source",
        "dependency_sha256": digest_json(dependency_identity),
        "dependencies": dependency_identity,
        "servers": {
            name: {**spec, "problems": dependency_problems(spec)}
            for name, spec in rows.items()
        },
    }


@click.command("runtime-info")
@click.argument("servers", nargs=-1)
def runtime_info_command(servers: tuple[str, ...]) -> None:
    """Report the shared interpreter, source identities and dependency inventory."""
    click.echo(json.dumps(runtime_info(servers), sort_keys=True))
