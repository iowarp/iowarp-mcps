#!/usr/bin/env python3
"""Validate that an MCP server meets FastMCP 3.0 compliance requirements.

Run from within a server directory:
    cd clio-kit-mcp-servers/compression && uv run python ../../scripts/validate_fastmcp.py

Checks:
- instructions set on FastMCP constructor
- All tools have annotations (readOnlyHint, destructiveHint, idempotentHint)
- All tools have tags
- At least 1 resource registered
- At least 1 prompt registered
"""

import asyncio
import importlib
import sys
from pathlib import Path

try:
    import tomllib
except ImportError:
    import tomli as tomllib


def find_server_module() -> str:
    """Determine the server module name from pyproject.toml entry point."""
    pyproject_path = Path("pyproject.toml")
    if not pyproject_path.exists():
        print("ERROR: No pyproject.toml found in current directory")
        sys.exit(1)

    with open(pyproject_path, "rb") as f:
        data = tomllib.load(f)

    scripts = data.get("project", {}).get("scripts", {})
    if not scripts:
        print("ERROR: No [project.scripts] entry found in pyproject.toml")
        sys.exit(1)

    # Entry point format: "module.path:function"
    entry_point = next(iter(scripts.values()))
    module_path = entry_point.split(":")[0]
    return module_path


async def validate(module_path: str) -> list[str]:
    """Import the server module and validate FastMCP 3.0 compliance."""
    errors: list[str] = []

    try:
        module = importlib.import_module(module_path)
    except ImportError as e:
        errors.append(f"Cannot import {module_path}: {e}")
        return errors

    mcp = getattr(module, "mcp", None)
    if mcp is None:
        errors.append(f"No 'mcp' FastMCP instance found in {module_path}")
        return errors

    # Check instructions
    if not mcp.instructions:
        errors.append("Missing: instructions not set on FastMCP constructor")

    # Check tools
    tools = await mcp.list_tools()
    if not tools:
        errors.append("Missing: no tools registered")
    else:
        for tool in tools:
            if not tool.annotations:
                errors.append(f"Tool '{tool.name}': missing annotations")
            else:
                ann = tool.annotations.model_dump()
                for hint in ("readOnlyHint", "destructiveHint", "idempotentHint"):
                    if ann.get(hint) is None:
                        errors.append(
                            f"Tool '{tool.name}': annotation '{hint}' not set"
                        )

            if not hasattr(tool, "tags") or not tool.tags:
                errors.append(f"Tool '{tool.name}': missing tags")

    # Check resources (static or templates)
    resources = await mcp.list_resources()
    templates = await mcp.list_resource_templates()
    if not resources and not templates:
        errors.append("Missing: no resources registered (need >= 1)")

    # Check prompts
    prompts = await mcp.list_prompts()
    if not prompts:
        errors.append("Missing: no prompts registered (need >= 1)")

    return errors


def main() -> None:
    module_path = find_server_module()
    errors = asyncio.run(validate(module_path))

    server_name = Path.cwd().name
    if errors:
        print(f"FAIL: {server_name} ({len(errors)} issues)")
        for error in errors:
            print(f"  - {error}")
        sys.exit(1)
    else:
        print(f"PASS: {server_name} (FastMCP 3.0 compliant)")


if __name__ == "__main__":
    main()
