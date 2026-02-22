from fastmcp import FastMCP
from fastmcp.exceptions import ToolError
from fastmcp.prompts import Message
import os
from dotenv import load_dotenv
from typing import Optional
from .capabilities.jarvis_handler import (
    create_pipeline,
    load_pipeline,
    append_pkg,
    configure_pkg,
    unlink_pkg,
    remove_pkg,
    run_pipeline,
    destroy_pipeline,
    get_pkg_config,
    update_pipeline,
    build_pipeline_env,
)
from jarvis_cd.basic.jarvis_manager import JarvisManager

# Load environment variables from .env file
load_dotenv()

# Initialize FastMCP server instance
mcp: FastMCP = FastMCP(
    "jarvis",
    instructions=(
        "Manages JARVIS data pipelines for scientific computing. "
        "Create, configure, monitor, and manage data processing pipelines."
    ),
    list_page_size=10,
)

# Create a singleton instance of JarvisManager
manager = JarvisManager.get_instance()


# ─── RESOURCE ────────────────────────────────────────────────────────────────


@mcp.resource("jarvis://capabilities")
def jarvis_capabilities() -> dict:
    """JARVIS data pipeline capabilities."""
    return {
        "pipeline_types": ["streaming", "batch", "real-time"],
        "operations": ["create", "configure", "deploy", "monitor", "destroy"],
    }


# ─── PROMPT ──────────────────────────────────────────────────────────────────


@mcp.prompt()
def create_pipeline_workflow(name: str) -> list[Message]:
    """Guided workflow for creating and deploying a JARVIS pipeline."""
    return [
        Message(
            f"I need to create a new JARVIS pipeline called '{name}'. "
            "Help me configure it, set up the processing stages, deploy it, "
            "and verify it's running correctly."
        ),
    ]


# ─── PIPELINE TOOLS ─────────────────────────────────────────────────────────────


@mcp.tool(
    name="update_pipeline",
    description="Re-apply environment and configuration to every package in a pipeline.",
    annotations={
        "readOnlyHint": False,
        "destructiveHint": False,
        "idempotentHint": False,
    },
    tags={"jarvis", "pipeline"},
)
async def update_pipeline_tool(pipeline_id: str) -> dict:
    """Re-apply environment and configuration to every package in a Jarvis pipeline."""
    return await update_pipeline(pipeline_id)


@mcp.tool(
    name="build_pipeline_env",
    description="Rebuild a pipeline's env.yaml, capturing CMAKE_PREFIX_PATH and PATH.",
    annotations={
        "readOnlyHint": False,
        "destructiveHint": False,
        "idempotentHint": False,
    },
    tags={"jarvis", "pipeline"},
)
async def build_pipeline_env_tool(pipeline_id: str) -> dict:
    """Build the pipeline execution environment for a given pipeline."""
    return await build_pipeline_env(pipeline_id)


@mcp.tool(
    name="create_pipeline",
    description="Create a new Jarvis-CD pipeline environment.",
    annotations={
        "readOnlyHint": False,
        "destructiveHint": False,
        "idempotentHint": False,
    },
    tags={"jarvis", "pipeline"},
)
async def create_pipeline_tool(pipeline_id: str) -> dict:
    """Create a new pipeline environment for data-centric workflows."""
    return await create_pipeline(pipeline_id)


@mcp.tool(
    name="load_pipeline",
    description="Load an existing Jarvis-CD pipeline environment.",
    annotations={
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
    },
    tags={"jarvis", "pipeline"},
)
async def load_pipeline_tool(pipeline_id: Optional[str] = None) -> dict:
    """Load an existing pipeline environment by ID, or the current one if not specified."""
    return await load_pipeline(pipeline_id)


@mcp.tool(
    name="get_pkg_config",
    description="Retrieve the configuration of a specific package in a pipeline.",
    annotations={
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
    },
    tags={"jarvis", "pipeline"},
)
async def get_pkg_config_tool(pipeline_id: str, pkg_id: str) -> dict:
    """Retrieve the configuration of a specific package in a pipeline."""
    return await get_pkg_config(pipeline_id, pkg_id)


@mcp.tool(
    name="append_pkg",
    description="Append a package to a Jarvis-CD pipeline.",
    annotations={
        "readOnlyHint": False,
        "destructiveHint": False,
        "idempotentHint": False,
    },
    tags={"jarvis", "pipeline"},
)
async def append_pkg_tool(
    pipeline_id: str,
    pkg_type: str,
    pkg_id: Optional[str] = None,
    do_configure: bool = True,
    extra_args: Optional[dict] = None,
) -> dict:
    """Add a package to a pipeline for execution or analysis."""
    return await append_pkg(
        pipeline_id,
        pkg_type,
        pkg_id=pkg_id,
        do_configure=do_configure,
        **(extra_args or {}),
    )


@mcp.tool(
    name="configure_pkg",
    description="Configure a package in a Jarvis-CD pipeline.",
    annotations={
        "readOnlyHint": False,
        "destructiveHint": False,
        "idempotentHint": False,
    },
    tags={"jarvis", "pipeline"},
)
async def configure_pkg_tool(
    pipeline_id: str, pkg_id: str, extra_args: Optional[dict] = None
) -> dict:
    """Configure a package in a pipeline with new settings."""
    return await configure_pkg(pipeline_id, pkg_id, **(extra_args or {}))


@mcp.tool(
    name="unlink_pkg",
    description="Unlink a package from a pipeline (preserve files).",
    annotations={
        "readOnlyHint": False,
        "destructiveHint": False,
        "idempotentHint": False,
    },
    tags={"jarvis", "pipeline"},
)
async def unlink_pkg_tool(pipeline_id: str, pkg_id: str) -> dict:
    """Unlink a package from a pipeline without deleting its files."""
    return await unlink_pkg(pipeline_id, pkg_id)


@mcp.tool(
    name="remove_pkg",
    description="Remove a package entirely from a pipeline.",
    annotations={
        "readOnlyHint": False,
        "destructiveHint": True,
        "idempotentHint": True,
    },
    tags={"jarvis", "pipeline"},
)
async def remove_pkg_tool(pipeline_id: str, pkg_id: str) -> dict:
    """Remove a package and its files from a pipeline."""
    return await remove_pkg(pipeline_id, pkg_id)


@mcp.tool(
    name="run_pipeline",
    description="Execute a Jarvis-CD pipeline end-to-end.",
    annotations={
        "readOnlyHint": False,
        "destructiveHint": False,
        "idempotentHint": False,
    },
    tags={"jarvis", "pipeline"},
)
async def run_pipeline_tool(pipeline_id: str) -> dict:
    """Execute the pipeline, running all configured steps."""
    return await run_pipeline(pipeline_id)


@mcp.tool(
    name="destroy_pipeline",
    description="Destroy a pipeline environment and clean up files.",
    annotations={
        "readOnlyHint": False,
        "destructiveHint": True,
        "idempotentHint": True,
    },
    tags={"jarvis", "pipeline"},
)
async def destroy_pipeline_tool(pipeline_id: str) -> dict:
    """Destroy a pipeline and clean up all associated files and resources."""
    return await destroy_pipeline(pipeline_id)


@mcp.tool(
    name="jm_create_config",
    description="Initialize JarvisManager config directories.",
    annotations={
        "readOnlyHint": False,
        "destructiveHint": False,
        "idempotentHint": False,
    },
    tags={"jarvis", "management"},
)
def jm_create_config(
    config_dir: str, private_dir: str, shared_dir: Optional[str] = None
) -> list:
    """Initialize manager directories and persist configuration."""
    try:
        manager.create(config_dir, private_dir, shared_dir)
        manager.save()
        return [{"type": "text", "text": "Jarvis configuration initialized."}]
    except Exception as e:
        raise ToolError(f"Error: {e}")


@mcp.tool(
    name="jm_load_config",
    description="Load existing JarvisManager configuration.",
    annotations={
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
    },
    tags={"jarvis", "management"},
)
def jm_load_config() -> list:
    """Load manager configuration from saved state."""
    try:
        manager.load()
        return [{"type": "text", "text": "Configuration loaded."}]
    except Exception as e:
        raise ToolError(f"Error: {e}")


@mcp.tool(
    name="jm_save_config",
    description="Save current JarvisManager configuration.",
    annotations={
        "readOnlyHint": False,
        "destructiveHint": False,
        "idempotentHint": True,
    },
    tags={"jarvis", "management"},
)
def jm_save_config() -> list:
    """Save current configuration state to disk."""
    try:
        manager.save()
        return [{"type": "text", "text": "Configuration saved."}]
    except Exception as e:
        raise ToolError(f"Error: {e}")


@mcp.tool(
    name="jm_set_hostfile",
    description="Set hostfile path for JarvisManager.",
    annotations={
        "readOnlyHint": False,
        "destructiveHint": False,
        "idempotentHint": True,
    },
    tags={"jarvis", "management"},
)
def jm_set_hostfile(path: str) -> list:
    """Set and save the path to the hostfile for deployments."""
    try:
        manager.set_hostfile(path)
        manager.save()
        return [{"type": "text", "text": f"Hostfile set to '{path}'"}]
    except Exception as e:
        raise ToolError(f"Error: {e}")


@mcp.tool(
    name="jm_bootstrap_from",
    description="Bootstrap Jarvis config from a machine template.",
    annotations={
        "readOnlyHint": False,
        "destructiveHint": False,
        "idempotentHint": False,
    },
    tags={"jarvis", "management"},
)
def jm_bootstrap_from(machine: str) -> list:
    """Bootstrap configuration based on a predefined machine template."""
    try:
        manager.bootstrap_from(machine)
        return [{"type": "text", "text": f"Bootstrapped from '{machine}'"}]
    except Exception as e:
        raise ToolError(f"Error: {e}")


@mcp.tool(
    name="jm_bootstrap_list",
    description="List available bootstrap machine templates.",
    annotations={
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
    },
    tags={"jarvis", "management"},
)
def jm_bootstrap_list() -> list:
    """List all bootstrap templates available."""
    try:
        return [{"type": "text", "text": m} for m in manager.bootstrap_list()]
    except Exception as e:
        raise ToolError(f"Error: {e}")


@mcp.tool(
    name="jm_reset",
    description="Reset JarvisManager (destroy all pipelines and data).",
    annotations={
        "readOnlyHint": False,
        "destructiveHint": True,
        "idempotentHint": True,
    },
    tags={"jarvis", "management"},
)
def jm_reset() -> list:
    """Reset manager to a clean state by destroying all pipelines and config."""
    try:
        manager.reset()
        return [{"type": "text", "text": "All pipelines and data reset."}]
    except Exception as e:
        raise ToolError(f"Error: {e}")


@mcp.tool(
    name="jm_list_pipelines",
    description="List all existing Jarvis pipelines.",
    annotations={
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
    },
    tags={"jarvis", "monitoring"},
)
def jm_list_pipelines() -> list:
    """List all current pipelines under management."""
    try:
        return [{"type": "text", "text": p} for p in manager.list_pipelines()]
    except Exception as e:
        raise ToolError(f"Error: {e}")


@mcp.tool(
    name="jm_cd",
    description="Change current Jarvis pipeline context.",
    annotations={
        "readOnlyHint": False,
        "destructiveHint": False,
        "idempotentHint": True,
    },
    tags={"jarvis", "management"},
)
def jm_cd(pipeline_id: str) -> list:
    """Set the working pipeline context."""
    try:
        manager.cd(pipeline_id)
        manager.save()
        return [{"type": "text", "text": f"Current pipeline set to '{pipeline_id}'"}]
    except Exception as e:
        raise ToolError(f"Error: {e}")


@mcp.tool(
    name="jm_list_repos",
    description="List all Jarvis repositories.",
    annotations={
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
    },
    tags={"jarvis", "monitoring"},
)
def jm_list_repos() -> list:
    """List all registered repositories."""
    try:
        return [{"type": "text", "text": str(repo)} for repo in manager.list_repos()]
    except Exception as e:
        raise ToolError(f"Error: {e}")


@mcp.tool(
    name="jm_add_repo",
    description="Add a repository to JarvisManager.",
    annotations={
        "readOnlyHint": False,
        "destructiveHint": False,
        "idempotentHint": False,
    },
    tags={"jarvis", "management"},
)
def jm_add_repo(path: str, force: bool = False) -> list:
    """Add a repository path to the manager."""
    try:
        manager.add_repo(path, force)
        manager.save()
        return [{"type": "text", "text": f"Repo added: {path}"}]
    except Exception as e:
        raise ToolError(f"Error: {e}")


@mcp.tool(
    name="jm_remove_repo",
    description="Remove a repository from JarvisManager.",
    annotations={
        "readOnlyHint": False,
        "destructiveHint": True,
        "idempotentHint": True,
    },
    tags={"jarvis", "management"},
)
def jm_remove_repo(repo_name: str) -> list:
    """Remove a repository from configuration."""
    try:
        manager.remove_repo(repo_name)
        manager.save()
        return [{"type": "text", "text": f"Repo removed: {repo_name}"}]
    except Exception as e:
        raise ToolError(f"Error: {e}")


@mcp.tool(
    name="jm_promote_repo",
    description="Promote a repository in JarvisManager.",
    annotations={
        "readOnlyHint": False,
        "destructiveHint": False,
        "idempotentHint": True,
    },
    tags={"jarvis", "management"},
)
def jm_promote_repo(repo_name: str) -> list:
    """Promote a repository to higher priority."""
    try:
        manager.promote_repo(repo_name)
        manager.save()
        return [{"type": "text", "text": f"Repo promoted: {repo_name}"}]
    except Exception as e:
        raise ToolError(f"Error: {e}")


@mcp.tool(
    name="jm_get_repo",
    description="Get repository info from JarvisManager.",
    annotations={
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
    },
    tags={"jarvis", "monitoring"},
)
def jm_get_repo(repo_name: str) -> list:
    """Get detailed information about a repository."""
    try:
        return [{"type": "text", "text": str(manager.get_repo(repo_name))}]
    except Exception as e:
        raise ToolError(f"Error: {e}")


@mcp.tool(
    name="jm_construct_pkg",
    description="Construct a package skeleton in JarvisManager.",
    annotations={
        "readOnlyHint": False,
        "destructiveHint": False,
        "idempotentHint": False,
    },
    tags={"jarvis", "pipeline"},
)
def jm_construct_pkg(pkg_type: str) -> list:
    """Generate a new package skeleton by type."""
    try:
        obj = manager.construct_pkg(pkg_type)
        return [{"type": "text", "text": f"Constructed pkg: {obj.__class__.__name__}"}]
    except Exception as e:
        raise ToolError(f"Error: {e}")


@mcp.tool(
    name="jm_graph_show",
    description="Print the current resource graph frames.",
    annotations={
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
    },
    tags={"jarvis", "monitoring"},
)
def jm_graph_show() -> list:
    """Print the resource graph to the console."""
    try:
        manager.resource_graph_show()
        return [{"type": "text", "text": "Resource graph printed to console."}]
    except Exception as e:
        raise ToolError(f"Error: {e}")


@mcp.tool(
    name="jm_graph_build",
    description="Build or rebuild the resource graph with a net sleep interval.",
    annotations={
        "readOnlyHint": False,
        "destructiveHint": False,
        "idempotentHint": False,
    },
    tags={"jarvis", "pipeline"},
)
def jm_graph_build(net_sleep: float) -> list:
    """Construct or rebuild the graph with a given sleep delay."""
    try:
        manager.resource_graph_build(net_sleep)
        return [{"type": "text", "text": "Resource graph built."}]
    except Exception as e:
        raise ToolError(f"Error: {e}")


@mcp.tool(
    name="jm_graph_modify",
    description="Modify the resource graph using a net sleep interval.",
    annotations={
        "readOnlyHint": False,
        "destructiveHint": False,
        "idempotentHint": False,
    },
    tags={"jarvis", "pipeline"},
)
def jm_graph_modify(net_sleep: float) -> list:
    """Modify the current resource graph with a delay between operations."""
    try:
        manager.resource_graph_modify(net_sleep)
        return [{"type": "text", "text": "Resource graph modified."}]
    except Exception as e:
        raise ToolError(f"Error: {e}")


def main() -> None:
    """Main entry point for the Jarvis MCP server."""
    import argparse

    parser = argparse.ArgumentParser(description="Jarvis MCP Server")
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
