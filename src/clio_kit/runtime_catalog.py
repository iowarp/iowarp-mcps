"""Build-time catalog for shared server execution; no server imports required."""

from __future__ import annotations

import hashlib
import json
import tomllib
from pathlib import Path
from typing import Any

CATALOG_SCHEMA = "clio-kit.runtime-catalog.v1"


def digest_json(value: Any) -> str:
    """Hash a canonical JSON value with unambiguous framing."""
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


def build_catalog(servers_root: Path) -> dict[str, Any]:
    """Describe embedded server source and dependency declarations independently."""
    servers: dict[str, Any] = {}
    for project_path in sorted(servers_root.glob("*/pyproject.toml")):
        root = project_path.parent
        project = tomllib.loads(project_path.read_text(encoding="utf-8"))["project"]
        requirements = sorted(project.get("dependencies", []))
        sources = {
            path.relative_to(root).as_posix(): hashlib.sha256(
                path.read_bytes()
            ).hexdigest()
            for path in sorted((root / "src").rglob("*"))
            if path.is_file()
            and "__pycache__" not in path.parts
            and path.suffix not in {".pyc", ".pyo"}
        }
        for command, entry in project.get("scripts", {}).items():
            if not command.endswith("-mcp"):
                continue
            name = command.removesuffix("-mcp")
            servers[name] = {
                "directory": root.name,
                "command": command,
                "entry_point": entry,
                "extra": root.name,
                "requirements": requirements,
                "requires_python": project.get("requires-python", ">=3.10"),
                "source_sha256": digest_json(sources),
                "requirements_sha256": digest_json(
                    {
                        "requirements": requirements,
                        "requires_python": project.get("requires-python", ">=3.10"),
                    }
                ),
            }
    return {"schema_version": CATALOG_SCHEMA, "servers": servers}


def write_catalog(servers_root: Path, destination: Path) -> None:
    """Generate the catalog during a wheel build or an explicit source update."""
    destination.write_text(
        json.dumps(build_catalog(servers_root), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def discover_commands(servers_root: Path) -> tuple[dict[str, str], dict[str, str]]:
    """Read available commands without importing or hashing server source."""
    commands: dict[str, str] = {}
    directories: dict[str, str] = {}
    for path in sorted(servers_root.glob("*/pyproject.toml")):
        try:
            project = tomllib.loads(path.read_text(encoding="utf-8"))["project"]
        except (OSError, ValueError, KeyError):
            continue
        for command in project.get("scripts", {}):
            if command.endswith("-mcp"):
                name = command.removesuffix("-mcp").lower()
                commands[name] = command
                directories[name] = path.parent.name
    return commands, directories
