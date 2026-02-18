"""
Lmod handler for executing module commands and parsing their output.
"""

import asyncio
import os
import re
from typing import List, Dict, Optional, Any


async def _run_module_command(
    args: List[str], capture_stderr: bool = False
) -> tuple[str, str, int]:
    """
    Run a module command and return stdout, stderr, and return code.

    Args:
        args: Command arguments (e.g., ['list'])
        capture_stderr: Whether to capture stderr separately

    Returns:
        tuple: (stdout, stderr, return_code)
    """
    # Construct the full command
    cmd = ["module"] + args

    # Set up environment with LMOD_QUIET to reduce noise
    env = os.environ.copy()
    env["LMOD_QUIET"] = "1"

    try:
        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
            if capture_stderr
            else asyncio.subprocess.STDOUT,
            env=env,
        )
        stdout, stderr = await process.communicate()

        stdout_str = stdout.decode("utf-8") if stdout else ""
        stderr_str = stderr.decode("utf-8") if stderr else ""

        return stdout_str, stderr_str, process.returncode or 0
    except FileNotFoundError:
        return "", "Module command not found. Is Lmod installed and in PATH?", 1
    except Exception as e:
        return "", f"Error running module command: {str(e)}", 1


async def list_loaded_modules() -> Dict[str, Any]:
    """List all currently loaded modules."""
    stdout, stderr, returncode = await _run_module_command(
        ["list", "-t"], capture_stderr=True
    )

    if returncode != 0:
        return {
            "success": False,
            "error": stderr or "Failed to list modules",
            "modules": [],
        }

    # Parse module list (skip header lines)
    modules = []
    lines = stdout.strip().split("\n")

    for line in lines:
        line = line.strip()
        # Skip empty lines and headers
        if (
            line
            and not line.startswith("Currently Loaded")
            and not line.startswith("No modules")
        ):
            modules.append(line)

    return {"success": True, "modules": modules, "count": len(modules)}


async def search_available_modules(pattern: Optional[str] = None) -> Dict[str, Any]:
    """Search for available modules."""
    args = ["avail", "-t"]
    if pattern:
        args.append(pattern)

    # module avail writes to stderr by default
    stdout, stderr, returncode = await _run_module_command(args, capture_stderr=True)

    # For module avail, output is in stderr
    output = stderr if stderr else stdout

    if returncode != 0 and not output:
        return {"success": False, "error": "Failed to search modules", "modules": []}

    # Parse available modules
    modules = []
    lines = output.strip().split("\n")

    for line in lines:
        line = line.strip()
        # Skip headers and empty lines
        if line and not line.endswith(":") and not line.startswith("/"):
            modules.append(line)

    return {
        "success": True,
        "modules": sorted(modules),
        "count": len(modules),
        "pattern": pattern,
    }


async def show_module_details(module_name: str) -> Dict[str, Any]:
    """Show detailed information about a module."""
    stdout, stderr, returncode = await _run_module_command(
        ["show", module_name], capture_stderr=True
    )

    if returncode != 0:
        return {
            "success": False,
            "error": stderr or f"Module {module_name} not found",
            "module": module_name,
        }

    # Parse module information
    info: Dict[str, Any] = {
        "module": module_name,
        "path": None,
        "help": [],
        "whatis": [],
        "prerequisites": [],
        "conflicts": [],
        "environment": [],
    }

    # Ensure list fields are properly typed
    help_list: List[str] = info["help"]
    whatis_list: List[str] = info["whatis"]
    prereq_list: List[str] = info["prerequisites"]
    conflicts_list: List[str] = info["conflicts"]
    env_list: List[str] = info["environment"]

    lines = stdout.strip().split("\n")

    for line in lines:
        # Detect section headers
        if line.strip().endswith(":"):
            line.strip().rstrip(":").lower()
            continue

        # Skip separator lines
        if line.strip().startswith("---") or not line.strip():
            continue

        # Extract module path
        if ".lua" in line or ".tcl" in line:
            info["path"] = line.strip()
            continue

        # Parse content based on current section
        if "help" in line.lower():
            help_match = re.search(r"help\s*\(\s*\[\[(.+?)\]\]\s*\)", line)
            if help_match:
                help_list.append(help_match.group(1))
        elif "whatis" in line.lower():
            whatis_match = re.search(r'whatis\s*\(\s*"(.+?)"\s*\)', line)
            if whatis_match:
                whatis_list.append(whatis_match.group(1))
        elif "prereq" in line.lower():
            prereq_match = re.search(r'prereq\s*\(\s*"(.+?)"\s*\)', line)
            if prereq_match:
                prereq_list.append(prereq_match.group(1))
        elif "conflict" in line.lower():
            conflict_match = re.search(r'conflict\s*\(\s*"(.+?)"\s*\)', line)
            if conflict_match:
                conflicts_list.append(conflict_match.group(1))
        elif (
            "setenv" in line.lower()
            or "prepend_path" in line.lower()
            or "append_path" in line.lower()
        ):
            env_list.append(line.strip())

    # Update info dict with modified lists
    info.update(
        {
            "help": help_list,
            "whatis": whatis_list,
            "prerequisites": prereq_list,
            "conflicts": conflicts_list,
            "environment": env_list,
        }
    )

    return {"success": True, **info}


async def load_modules(modules: List[str]) -> Dict[str, Any]:
    """Load specified modules."""
    results = []
    all_success = True

    for module in modules:
        stdout, stderr, returncode = await _run_module_command(
            ["load", module], capture_stderr=True
        )

        if returncode != 0:
            all_success = False
            results.append(
                {
                    "module": module,
                    "success": False,
                    "error": stderr or f"Failed to load {module}",
                }
            )
        else:
            results.append(
                {
                    "module": module,
                    "success": True,
                    "message": f"Successfully loaded {module}",
                }
            )

    return {"success": all_success, "results": results}


async def unload_modules(modules: List[str]) -> Dict[str, Any]:
    """Unload specified modules."""
    results = []
    all_success = True

    for module in modules:
        stdout, stderr, returncode = await _run_module_command(
            ["unload", module], capture_stderr=True
        )

        if returncode != 0:
            all_success = False
            results.append(
                {
                    "module": module,
                    "success": False,
                    "error": stderr or f"Failed to unload {module}",
                }
            )
        else:
            results.append(
                {
                    "module": module,
                    "success": True,
                    "message": f"Successfully unloaded {module}",
                }
            )

    return {"success": all_success, "results": results}


async def swap_modules(old_module: str, new_module: str) -> Dict[str, Any]:
    """Swap one module for another."""
    stdout, stderr, returncode = await _run_module_command(
        ["swap", old_module, new_module], capture_stderr=True
    )

    if returncode != 0:
        return {
            "success": False,
            "error": stderr or f"Failed to swap {old_module} with {new_module}",
            "old_module": old_module,
            "new_module": new_module,
        }

    return {
        "success": True,
        "message": f"Successfully swapped {old_module} with {new_module}",
        "old_module": old_module,
        "new_module": new_module,
    }


async def spider_search(pattern: Optional[str] = None) -> Dict[str, Any]:
    """Search entire module tree using spider."""
    args = ["spider", "-t"]
    if pattern:
        args.append(pattern)

    stdout, stderr, returncode = await _run_module_command(args, capture_stderr=True)

    # Spider output is typically in stderr
    output = stderr if stderr else stdout

    if returncode != 0 and not output:
        return {"success": False, "error": "Failed to run spider search", "modules": []}

    # Parse spider output
    modules = {}
    lines = output.strip().split("\n")

    for line in lines:
        line = line.strip()
        if (
            line
            and not line.startswith("The following")
            and not line.startswith("To find")
        ):
            # Extract module name and versions
            if ":" in line:
                name, versions = line.split(":", 1)
                modules[name.strip()] = [v.strip() for v in versions.strip().split(",")]
            else:
                modules[line] = []

    return {"success": True, "modules": modules, "pattern": pattern}


async def save_module_collection(collection_name: str) -> Dict[str, Any]:
    """Save current module configuration."""
    stdout, stderr, returncode = await _run_module_command(
        ["save", collection_name], capture_stderr=True
    )

    if returncode != 0:
        return {
            "success": False,
            "error": stderr or f"Failed to save collection {collection_name}",
            "collection": collection_name,
        }

    return {
        "success": True,
        "message": f"Successfully saved module collection as {collection_name}",
        "collection": collection_name,
    }


async def restore_module_collection(collection_name: str) -> Dict[str, Any]:
    """Restore a saved module collection."""
    stdout, stderr, returncode = await _run_module_command(
        ["restore", collection_name], capture_stderr=True
    )

    if returncode != 0:
        return {
            "success": False,
            "error": stderr or f"Failed to restore collection {collection_name}",
            "collection": collection_name,
        }

    # Get the list of loaded modules after restore
    loaded_modules = await list_loaded_modules()

    return {
        "success": True,
        "message": f"Successfully restored module collection {collection_name}",
        "collection": collection_name,
        "loaded_modules": loaded_modules.get("modules", []),
    }


async def list_saved_collections() -> Dict[str, Any]:
    """List all saved module collections."""
    stdout, stderr, returncode = await _run_module_command(
        ["savelist"], capture_stderr=True
    )

    if returncode != 0:
        return {
            "success": False,
            "error": stderr or "Failed to list saved collections",
            "collections": [],
        }

    # Parse collection names
    collections = []
    lines = stdout.strip().split("\n")

    for line in lines:
        line = line.strip()
        # Skip headers and empty lines
        if (
            line
            and not line.startswith("Named collection")
            and not line.startswith("No named")
        ):
            # Extract collection names (patterns like "1) name   2) name2   3) name3")
            matches = re.findall(r"\d+\)\s*([^\d\)]+?)(?=\s*\d+\)|$)", line)
            if matches:
                for match in matches:
                    collections.append(match.strip())
            elif line and not any(char in line for char in [":", "(", ")"]):
                collections.append(line)

    return {"success": True, "collections": collections, "count": len(collections)}
