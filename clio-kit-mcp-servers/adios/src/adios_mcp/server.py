# server.py

#  Created on: 2nd June, 2025
#      Author: Soham Sonar ssonar2@hawk.illinoistech.edu


import os
from fastmcp import FastMCP
from fastmcp.exceptions import ToolError  # noqa: F401 (re-exported for consumers)
from fastmcp.prompts import Message
from typing import Optional
from . import mcp_handlers

# Initialize FastMCP server
mcp: FastMCP = FastMCP(
    "adios",
    instructions=(
        "Reads and inspects ADIOS2 BP files for scientific I/O. "
        "Use list_variables to see available data, read_variable to extract values, "
        "and get_file_info for metadata overview."
    ),
)

# ─── ADIOS BP5 TOOLS ─────────────────────────────────────────────────────────


# List BP5 Files Tool
@mcp.tool(
    name="list_bp5",
    title="list(bp5)",
    description="Lists all BP5 files in a given directory. The 'directory' parameter must be an absolute path.",
    annotations={
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
    },
    tags={"adios", "scientific-io"},
)
async def list_bp5_tool(directory: str = "data/") -> dict:
    """List all BP5 files in a specified directory with file metadata."""
    return await mcp_handlers.list_bp5_files(directory)


# ─── INSPECT VARIABLES ───────────────────────────────────────────────────────
@mcp.tool(
    name="inspect_variables",
    title="inspect(vars)",
    description="Inspects variables in a BP5 file, returning type, shape, and steps. Optionally filters by variable name.",
    annotations={
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
    },
    tags={"adios", "variables"},
)
async def inspect_variables_tool(
    filename: str, variable_name: Optional[str] = None
) -> dict:
    """Inspect all variables in a BP5 file or a specific variable by name."""
    return await mcp_handlers.inspect_variables_handler(filename, variable_name)


# ─── INSPECT VARIABLES AT STEP ─────────────────────────────────────────────────
@mcp.tool(
    name="inspect_variables_at_step",
    title="inspect(step)",
    description="Inspects a specific variable at a given step in a BP5 file. All parameters are required.",
    annotations={
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
    },
    tags={"adios", "variables"},
)
async def inspect_variables_at_step_tool(
    filename: str, variable_name: str, step: int
) -> dict:
    """Inspect a specific variable at a given step in a BP5 file."""
    return await mcp_handlers.inspect_variables_at_step_handler(
        filename, variable_name, step
    )


# ─── INSPECT ATTRIBUTES ──────────────────────────────────────────────────────
@mcp.tool(
    name="inspect_attributes",
    title="inspect(attrs)",
    description="Reads global or variable-specific attributes from a BP5 file. The 'variable_name' is optional.",
    annotations={
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
    },
    tags={"adios", "attributes"},
)
async def inspect_attributes_tool(
    filename: str, variable_name: Optional[str] = None
) -> dict:
    """Read global or variable-specific attributes from a BP5 file."""
    return await mcp_handlers.inspect_attributes_handler(filename, variable_name)


# ─── READ VARIABLE AT STEP ────────────────────────────────────────────────────
@mcp.tool(
    name="read_variable_at_step",
    title="read(step)",
    description="Reads a named variable at a specific step from a BP5 file. All parameters are required.",
    annotations={
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
    },
    tags={"adios", "variables"},
)
async def read_variable_at_step_tool(
    filename: str, variable_name: str, target_step: int
) -> dict:
    """Read a named variable at a specific time step from a BP5 file."""
    return await mcp_handlers.read_variable_at_step_handler(
        filename, variable_name, target_step
    )


# ─── RESOURCES ────────────────────────────────────────────────────────────────


@mcp.resource("adios://capabilities")
def adios_capabilities() -> dict:
    """ADIOS2 file format capabilities and supported engines."""
    return {
        "supported_formats": ["BP4", "BP5"],
        "operations": ["read", "inspect", "list variables", "read attributes"],
    }


# ─── PROMPTS ──────────────────────────────────────────────────────────────────


@mcp.prompt()
def explore_bp_file(file_path: str) -> list[Message]:
    """Guided workflow for exploring an ADIOS2 BP file."""
    return [
        Message(
            f"I need to explore the ADIOS2 BP file at {file_path}. "
            "First get the file info, then list all variables, "
            "and read the first few values of the most important variables."
        ),
    ]


def main() -> None:
    """Main entry point for the ADIOS MCP server."""
    import argparse

    parser = argparse.ArgumentParser(description="ADIOS MCP Server")
    parser.add_argument("--transport", choices=["stdio", "http"], default=None)
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--port", type=int, default=8000)
    args = parser.parse_args()
    transport = args.transport or os.getenv("MCP_TRANSPORT", "stdio")
    if transport == "http":
        mcp.run(transport="http", host=args.host, port=args.port)
    else:
        mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
