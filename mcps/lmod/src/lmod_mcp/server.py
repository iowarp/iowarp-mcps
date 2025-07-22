#!/usr/bin/env python3
"""
Lmod MCP Server for managing environment modules.
Provides tools to search, load, unload, and inspect modules using the Lmod system.
"""
import os
import sys
from mcp.server.fastmcp import FastMCP
from dotenv import load_dotenv
import logging

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Ensure project root is on path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Load environment variables
load_dotenv()

from lmod_mcp.capabilities import lmod_handler

# Initialize MCP server
mcp = FastMCP("LmodMCP")

@mcp.tool(
    name="module_list",
    description="List all currently loaded environment modules. Shows the active modules in your current shell environment."
)
async def module_list_tool() -> dict:
    """
    List all currently loaded environment modules with their versions and status information.

    Returns:
        dict: Dictionary with list of loaded modules, count, and module status information.
    """
    return await lmod_handler.list_loaded_modules()

@mcp.tool(
    name="module_avail",
    description="Search for available modules that can be loaded. Optionally filter by name pattern (e.g., 'python', 'gcc/*', '*mpi*')."
)
async def module_avail_tool(pattern: str = None) -> dict:
    """
    Search for available modules that can be loaded with optional pattern matching and filtering.

    Args:
        pattern (str, optional): Search pattern with wildcards (e.g., 'python*', 'gcc/*')

    Returns:
        dict: Dictionary with available modules matching the search criteria and their descriptions.
    """
    return await lmod_handler.search_available_modules(pattern)

@mcp.tool(
    name="module_show",
    description="Display detailed information about a specific module including its description, dependencies, environment variables it sets, and conflicts."
)
async def module_show_tool(module_name: str) -> dict:
    """
    Display comprehensive information about a specific module including dependencies and environment changes.

    Args:
        module_name (str): Name of the module (e.g., 'python/3.9.0')

    Returns:
        dict: Dictionary with detailed module information, dependencies, and environment modifications.
    """
    return await lmod_handler.show_module_details(module_name)

@mcp.tool(
    name="module_load",
    description="Load one or more environment modules into the current session. Modules modify environment variables like PATH, LD_LIBRARY_PATH, etc."
)
async def module_load_tool(modules: list[str]) -> dict:
    """
    Load one or more environment modules with automatic dependency resolution and conflict detection.

    Args:
        modules (list): List of module names to load

    Returns:
        dict: Dictionary with loading status, any conflicts detected, and environment changes applied.
    """
    return await lmod_handler.load_modules(modules)

@mcp.tool(
    name="module_unload",
    description="Unload (remove) one or more currently loaded modules from the environment. Reverses the changes made by module load."
)
async def module_unload_tool(modules: list[str]) -> dict:
    """
    Unload one or more currently loaded modules with dependency checking and cleanup.

    Args:
        modules (list): List of module names to unload

    Returns:
        dict: Dictionary with unloading status and environment restoration information.
    """
    return await lmod_handler.unload_modules(modules)

@mcp.tool(
    name="module_swap",
    description="Swap one module for another (unload old_module and load new_module atomically). Useful for switching between different versions."
)
async def module_swap_tool(old_module: str, new_module: str) -> dict:
    """
    Atomically swap one module for another, handling dependencies and version conflicts automatically.

    Args:
        old_module (str): Module to unload
        new_module (str): Module to load in its place

    Returns:
        dict: Dictionary with swap operation status and any dependency adjustments made.
    """
    return await lmod_handler.swap_modules(old_module, new_module)

@mcp.tool(
    name="module_spider",
    description="Search the entire module tree for modules matching a pattern. More comprehensive than module_avail, shows all versions and variants."
)
async def module_spider_tool(pattern: str = None) -> dict:
    """
    Search the entire module tree comprehensively with deep hierarchy exploration and metadata extraction.

    Args:
        pattern (str, optional): Search pattern for comprehensive module discovery

    Returns:
        dict: Dictionary with comprehensive search results including hidden modules and dependency information.
    """
    return await lmod_handler.spider_search(pattern)

@mcp.tool(
    name="module_save",
    description="Save the current set of loaded modules as a named collection for easy restoration later."
)
async def module_save_tool(collection_name: str) -> dict:
    """
    Save the current set of loaded modules as a named collection for reproducible environments.

    Args:
        collection_name (str): Name for the saved collection

    Returns:
        dict: Dictionary with collection save status and included modules list.
    """
    return await lmod_handler.save_module_collection(collection_name)

@mcp.tool(
    name="module_restore",
    description="Restore a previously saved module collection, loading all modules that were saved in that collection."
)
async def module_restore_tool(collection_name: str) -> dict:
    """
    Restore a previously saved module collection with automatic environment configuration.

    Args:
        collection_name (str): Name of the collection to restore

    Returns:
        dict: Dictionary with restoration status and any conflicts or missing modules.
    """
    return await lmod_handler.restore_module_collection(collection_name)

@mcp.tool(
    name="module_savelist",
    description="List all saved module collections available for restoration."
)
async def module_savelist_tool() -> dict:
    """
    List all saved module collections with creation dates and module counts.

    Returns:
        dict: Dictionary with list of saved collections and their metadata information.
    """
    return await lmod_handler.list_saved_collections()

def main():
    """Main entry point for the server."""
    import asyncio
    
    # Run the FastMCP server
    asyncio.run(mcp.run())

if __name__ == "__main__":
    main()