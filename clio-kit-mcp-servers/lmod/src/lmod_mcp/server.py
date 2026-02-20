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
        "Manages Lmod environment modules on HPC systems. "
        "Load, unload, swap, and search modules. Save and restore module collections."
    ),
    list_page_size=10,
)


@mcp.tool(
    name="module_list",
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
    name="module_load",
    description="Load one or more environment modules into the current session.",
    annotations={
        "readOnlyHint": False,
        "destructiveHint": False,
        "idempotentHint": False,
    },
    tags={"modules", "management"},
)
async def module_load_tool(modules: list[str]) -> dict:
    """Load one or more environment modules with dependency resolution."""
    result = await lmod_handler.load_modules(modules)
    if not result.get("success"):
        failed = [r for r in result.get("results", []) if not r.get("success")]
        errors = "; ".join(r.get("error", "unknown error") for r in failed)
        raise ToolError(f"Failed to load modules: {errors}")
    return result


@mcp.tool(
    name="module_unload",
    description="Unload one or more currently loaded modules from the environment.",
    annotations={
        "readOnlyHint": False,
        "destructiveHint": False,
        "idempotentHint": False,
    },
    tags={"modules", "management"},
)
async def module_unload_tool(modules: list[str]) -> dict:
    """Unload one or more modules, reversing their environment changes."""
    result = await lmod_handler.unload_modules(modules)
    if not result.get("success"):
        failed = [r for r in result.get("results", []) if not r.get("success")]
        errors = "; ".join(r.get("error", "unknown error") for r in failed)
        raise ToolError(f"Failed to unload modules: {errors}")
    return result


@mcp.tool(
    name="module_swap",
    description="Swap one module for another atomically.",
    annotations={
        "readOnlyHint": False,
        "destructiveHint": False,
        "idempotentHint": False,
    },
    tags={"modules", "management"},
)
async def module_swap_tool(old_module: str, new_module: str) -> dict:
    """Swap one module for another, useful for switching versions."""
    result = await lmod_handler.swap_modules(old_module, new_module)
    if not result.get("success"):
        raise ToolError(
            result.get("error", f"Failed to swap {old_module} with {new_module}")
        )
    return result


@mcp.tool(
    name="module_spider",
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
            "load",
            "unload",
            "swap",
            "save",
            "restore",
            "spider",
        ],
    }


@mcp.prompt()
def setup_environment(software: str) -> list[Message]:
    """Guided workflow for setting up an HPC software environment."""
    return [
        Message(
            f"I need to set up an environment for {software}. "
            "Search available modules, load the appropriate version, "
            "verify it's loaded, and save the collection for future use."
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
        mcp.run(transport=transport, host=args.host, port=args.port)

    else:
        mcp.run(transport=transport)


if __name__ == "__main__":
    main()
