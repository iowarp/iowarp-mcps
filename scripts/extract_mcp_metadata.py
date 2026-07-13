#!/usr/bin/env python3
"""Extract MCP server metadata via FastMCP 3.0 async API.

Run from within a server directory:
    cd clio-kit-mcp-servers/compression && uv run python ../../scripts/extract_mcp_metadata.py

Outputs JSON to stdout with tools, resources, prompts, annotations, and tags.
"""

import asyncio
import importlib
import json
import logging
import os
import sys
from pathlib import Path
from typing import Any, Callable, cast

try:
    import tomllib
except ImportError:
    import tomli as tomllib  # type: ignore[import-not-found,no-redef]


def find_server_module() -> str:
    """Determine the server module name from pyproject.toml entry point."""
    pyproject_path = Path("pyproject.toml")
    if not pyproject_path.exists():
        print("ERROR: No pyproject.toml found", file=sys.stderr)
        sys.exit(1)

    with open(pyproject_path, "rb") as f:
        data = tomllib.load(f)

    scripts = data.get("project", {}).get("scripts", {})
    if not scripts:
        print("ERROR: No [project.scripts] found", file=sys.stderr)
        sys.exit(1)

    entry_point = next(iter(scripts.values()))
    return entry_point.split(":")[0]


async def extract(module_path: str) -> dict[str, Any]:
    """Import the server and extract all metadata."""
    module = importlib.import_module(module_path)
    metadata_profile = getattr(module, "MCP_METADATA_PROFILE", None)
    if metadata_profile is not None:
        profile_applier = getattr(module, "apply_tool_profile", None)
        if not isinstance(metadata_profile, str) or not callable(profile_applier):
            raise RuntimeError("invalid MCP_METADATA_PROFILE contract")
        cast(Callable[[str], None], profile_applier)(metadata_profile)
    mcp = getattr(module, "mcp")

    tools = await mcp.list_tools()
    resources = await mcp.list_resources()
    templates = await mcp.list_resource_templates()
    prompts = await mcp.list_prompts()

    return {
        "name": mcp.name,
        "instructions": mcp.instructions or "",
        "tools": [
            {
                "name": t.name,
                "description": t.description or "",
                "annotations": t.annotations.model_dump() if t.annotations else {},
                "tags": sorted(t.tags) if hasattr(t, "tags") and t.tags else [],
            }
            for t in tools
        ],
        "resources": [
            {
                "uri": str(r.uri),
                "name": r.name,
                "description": r.description or "",
            }
            for r in resources
        ],
        "resource_templates": [
            {
                "uri_template": str(t.uri_template),
                "name": t.name,
                "description": t.description or "",
            }
            for t in templates
        ],
        "prompts": [
            {
                "name": p.name,
                "description": p.description or "",
            }
            for p in prompts
        ],
    }


def main() -> None:
    # Suppress all logging and stray prints during import
    logging.disable(logging.CRITICAL)
    # Redirect stdout during import, then restore for JSON output
    old_stdout = sys.stdout
    sys.stdout = open(os.devnull, "w")
    try:
        module_path = find_server_module()
        result = asyncio.run(extract(module_path))
    finally:
        sys.stdout.close()
        sys.stdout = old_stdout
        logging.disable(logging.NOTSET)
    print(json.dumps(result))


if __name__ == "__main__":
    main()
