# server.py

#  Created on: 2nd June, 2025
#      Author: Soham Sonar ssonar2@hawk.illinoistech.edu


import os
import sys
import json
from fastmcp import FastMCP
from dotenv import load_dotenv
from typing import Optional
import mcp_handlers

# Ensure parent directory is on PYTHONPATH so "capabilities" can be found
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Load .env variables, if any
load_dotenv()

# Initialize FastMCP server
mcp: FastMCP = FastMCP("ADIOSMCP")

# ─── ADIOS BP5 TOOLS ─────────────────────────────────────────────────────────


# List BP5 Files Tool
@mcp.tool(
    name="list_bp5",
    description="Lists all BP5 files in a given directory, the bp5 files are actually directories so both file and directory words are correct. The 'directory' parameter must be an absolute path.",
)
async def list_bp5_tool(directory: str = "data/") -> dict:
    """
    List all BP5 files in a specified directory with comprehensive file information including metadata and structure details.

    Args:
        directory (str): Absolute path to directory containing BP5 files

    Returns:
        List of BP5 files with metadata, size information, and basic structure details.
    """
    try:
        return await mcp_handlers.list_bp5_files(directory)
    except Exception as e:
        return {
            "content": [{"text": json.dumps({"error": str(e)})}],
            "_meta": {"tool": "list_bp5", "error": type(e).__name__},
            "isError": True,
        }


# ─── INSPECT VARIABLES ───────────────────────────────────────────────────────
@mcp.tool(
    name="inspect_variables",
    description="Inspects variables in a BP5 file. If variable_name is provided, returns data for that specific variable. Otherwise, shows type, shape, and steps for all variables. The 'filename' parameter must be an absolute path to the BP5 file.",
)
async def inspect_variables_tool(
    filename: str, variable_name: Optional[str] = None
) -> dict:
    """
    Inspect all variables in a BP5 file including type information, shape dimensions, and available time steps for comprehensive data structure analysis. If variable_name is provided, returns data for that specific variable.

    Args:
        filename (str): Absolute path to BP5 file
        variable_name (str, optional): Specific variable name for targeted inspection

    Returns:
        Complete variable inventory with types, shapes, step counts, and data structure information for all variables or specific variable.
    """
    try:
        return await mcp_handlers.inspect_variables_handler(filename, variable_name)
    except Exception as e:
        return {
            "content": [{"text": json.dumps({"error": str(e)})}],
            "_meta": {"tool": "inspect_variables", "error": type(e).__name__},
            "isError": True,
        }


# ─── INSPECT VARIABLES AT STEP ─────────────────────────────────────────────────
@mcp.tool(
    name="inspect_variables_at_step",
    description="Inspects a specific variable at a given step in a BP5 file. Shows variable type, shape, min, max. All parameters are required. The 'filename' must be an absolute path.",
)
async def inspect_variables_at_step_tool(
    filename: str, variable_name: str, step: int
) -> dict:
    """
    Inspect a specific variable at a given step in a BP5 file. Shows variable type, shape, and metadata at the specified time step.

    Args:
        filename (str): Absolute path to BP5 file
        variable_name (str): Name of the variable to inspect
        step (int): Step number to inspect

    Returns:
        Variable information at the specified step including type, shape, and available metadata.
    """
    try:
        return await mcp_handlers.inspect_variables_at_step_handler(
            filename, variable_name, step
        )
    except Exception as e:
        return {
            "content": [{"text": json.dumps({"error": str(e)})}],
            "_meta": {"tool": "inspect_variables_at_step", "error": type(e).__name__},
            "isError": True,
        }


# ─── INSPECT ATTRIBUTES ──────────────────────────────────────────────────────
@mcp.tool(
    name="inspect_attributes",
    description="Reads global or variable-specific attributes from a BP5 file. The 'filename' parameter must be an absolute path. The 'variable_name' is optional.",
)
async def inspect_attributes_tool(
    filename: str, variable_name: Optional[str] = None
) -> dict:
    """
    Read global or variable-specific attributes from a BP5 file with detailed metadata extraction and attribute value analysis.

    Args:
        filename (str): Absolute path to BP5 file
        variable_name (str, optional): Specific variable name for targeted attribute inspection

    Returns:
        Comprehensive attribute dictionary with metadata, variable-specific attributes, and global file attributes.
    """
    try:
        return await mcp_handlers.inspect_attributes_handler(filename, variable_name)
    except Exception as e:
        return {
            "content": [{"text": json.dumps({"error": str(e)})}],
            "_meta": {"tool": "inspect_attributes", "error": type(e).__name__},
            "isError": True,
        }


# ─── READ VARIABLE AT STEP ────────────────────────────────────────────────────
@mcp.tool(
    name="read_variable_at_step",
    description="Reads a named variable at a specific step from a BP5 file. All parameters are required. The 'filename' must be an absolute path.",
)
async def read_variable_at_step_tool(
    filename: str, variable_name: str, target_step: int
) -> dict:
    """
    Read a named variable at a specific time step from a BP5 file with full data extraction and conversion to Python native types.

    Args:
        filename (str): Absolute path to BP5 file
        variable_name (str): Name of variable to read
        target_step (int): Time step number to read from

    Returns:
        Variable data as Python scalar or list (flattened array) at the specified step.
    """
    return await mcp_handlers.read_variable_at_step_handler(
        filename, variable_name, target_step
    )


def main():
    """
    Main entry point to run the ADIOS MCP server.
    Chooses between stdio or SSE transport based on MCP_TRANSPORT.
    """
    try:
        transport = os.getenv("MCP_TRANSPORT", "stdio").lower()
        if transport == "sse":
            host = os.getenv("MCP_SSE_HOST", "0.0.0.0")
            port = int(os.getenv("MCP_SSE_PORT", "8000"))
            print(
                json.dumps({"message": f"Starting SSE on {host}:{port}"}),
                file=sys.stderr,
            )
            mcp.run(transport="sse", host=host, port=port)
        else:
            # print(json.dumps({"message": "Starting stdio transport"}), file=sys.stderr)
            mcp.run(transport="stdio")
    except Exception as e:
        print(json.dumps({"error": str(e)}), file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
