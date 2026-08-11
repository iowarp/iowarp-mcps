#!/usr/bin/env python3
"""
Lmod MCP Server for managing environment modules.
Provides tools to search, load, unload, and inspect modules using the Lmod system.
"""

import os
from fastmcp import FastMCP
from fastmcp.exceptions import ToolError
from fastmcp.prompts import Message
from typing import Optional
from dotenv import load_dotenv
import logging
from .capabilities import lmod_handler

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

# Initialize MCP server
mcp: FastMCP = FastMCP(
    "lmod",
    instructions=(
        "Inspects Lmod environment modules on HPC systems: list loaded modules, "
        "search what is available, show module details, and manage saved "
        "collections. This server does not load modules. A module load only "
        "lives for the process that performed it, so loading here could not "
        "affect any later tool call or job; ask the system that owns the "
        "runtime environment to load modules instead."
    ),
    list_page_size=10,
)


@mcp.tool(
    name="module_list",
    title="List Loaded",
    description="List all currently loaded environment modules.",
    annotations={
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
    },
    tags={"modules", "query"},
)
async def module_list_tool() -> dict:
    """List all currently loaded environment modules with their versions and status."""
    result = await lmod_handler.list_loaded_modules()
    if not result.get("success"):
        raise ToolError(result.get("error", "Failed to list modules"))
    return result


@mcp.tool(
    name="module_avail",
    title="Search Available",
    description="Search for available modules, optionally filtered by name pattern.",
    annotations={
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
    },
    tags={"modules", "query"},
)
async def module_avail_tool(pattern: Optional[str] = None) -> dict:
    """Search for available modules with optional pattern matching."""
    result = await lmod_handler.search_available_modules(pattern)
    if not result.get("success"):
        raise ToolError(result.get("error", "Failed to search modules"))
    return result


@mcp.tool(
    name="module_show",
    title="Show Module",
    description="Display detailed information about a specific module.",
    annotations={
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
    },
    tags={"modules", "query"},
)
async def module_show_tool(module_name: str) -> dict:
    """Show detailed module info including dependencies and environment changes."""
    result = await lmod_handler.show_module_details(module_name)
    if not result.get("success"):
        raise ToolError(result.get("error", f"Module {module_name} not found"))
    return result


@mcp.tool(
    name="module_spider",
    title="Spider Search",
    description="Search the entire module tree comprehensively for matching modules.",
    annotations={
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
    },
    tags={"modules", "query"},
)
async def module_spider_tool(pattern: Optional[str] = None) -> dict:
    """Search the full module tree, showing all versions and variants."""
    result = await lmod_handler.spider_search(pattern)
    if not result.get("success"):
        raise ToolError(result.get("error", "Failed to run spider search"))
    return result


@mcp.tool(
    name="module_save",
    title="Save Collection",
    description="Save currently loaded modules as a named collection.",
    annotations={
        "readOnlyHint": False,
        "destructiveHint": False,
        "idempotentHint": False,
    },
    tags={"modules", "management"},
)
async def module_save_tool(collection_name: str) -> dict:
    """Save the current module set as a named collection for later restoration."""
    result = await lmod_handler.save_module_collection(collection_name)
    if not result.get("success"):
        raise ToolError(
            result.get("error", f"Failed to save collection {collection_name}")
        )
    return result


@mcp.tool(
    name="module_restore",
    title="Restore Collection",
    description="Restore a previously saved module collection.",
    annotations={
        "readOnlyHint": False,
        "destructiveHint": False,
        "idempotentHint": False,
    },
    tags={"modules", "management"},
)
async def module_restore_tool(collection_name: str) -> dict:
    """Restore a saved module collection, loading all its modules."""
    result = await lmod_handler.restore_module_collection(collection_name)
    if not result.get("success"):
        raise ToolError(
            result.get("error", f"Failed to restore collection {collection_name}")
        )
    return result


@mcp.tool(
    name="module_savelist",
    title="List Collections",
    description="List all saved module collections.",
    annotations={
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
    },
    tags={"modules", "query"},
)
async def module_savelist_tool() -> dict:
    """List all saved module collections with their metadata."""
    result = await lmod_handler.list_saved_collections()
    if not result.get("success"):
        raise ToolError(result.get("error", "Failed to list saved collections"))
    return result


@mcp.resource("lmod://status")
def module_system_status() -> dict:
    """Current Lmod module system status."""
    return {
        "system": "lmod",
        "description": "Environment module system for HPC",
        "operations": [
            "list",
            "avail",
            "show",
            "spider",
            "save",
            "restore",
            "savelist",
        ],
    }


@mcp.resource("lmod://capabilities")
def module_capabilities() -> dict:
    """Describe the stateless Lmod contract exposed by this server."""
    return {
        "operations": ["list", "avail", "show", "spider"],
        "collection_operations": ["save", "restore", "savelist"],
        "stateful_load_exposed": False,
        "runtime_owner": "jarvis_run",
    }


@mcp.prompt()
def setup_environment(software: str) -> list[Message]:
    """Guided workflow for setting up an HPC software environment."""
    return [
        Message(
            f"I need to set up an environment for {software}. "
            "Search available modules with module_avail, inspect the candidate "
            "with module_show, then hand the exact module names to whatever "
            "runs the job (jarvis_run) so it loads them in the runtime "
            "environment. This server reports modules; it does not load them."
        ),
    ]


def main() -> None:
    """Main entry point for the Lmod MCP server."""
    import argparse

    parser = argparse.ArgumentParser(description="Lmod MCP Server")
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
