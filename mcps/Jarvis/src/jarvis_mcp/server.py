from fastmcp import FastMCP
import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Import Jarvis-CD pipeline capabilities
from jarvis_mcp.capabilities.jarvis_handler import (
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
    build_pipeline_env
)

# Import JarvisManager (singleton-based configuration and repo manager)
from jarvis_cd.basic.jarvis_manager import JarvisManager
import sys

# Initialize FastMCP server instance
mcp = FastMCP("JarvisServer")

# Create a singleton instance of JarvisManager
manager = JarvisManager.get_instance()


# ─── PIPELINE TOOLS ─────────────────────────────────────────────────────────────

@mcp.tool(
    name="update_pipeline",
    description="Re-apply environment & configuration to every package in a Jarvis-CD pipeline."
)
async def update_pipeline_tool(pipeline_id: str) -> dict:
    """
    Re-apply environment and configuration to every package in a Jarvis pipeline.

    Args:
        pipeline_id (str): ID of the pipeline to update

    Returns:
        dict: Status and results of the update operation.
    """
    return await update_pipeline(pipeline_id)

@mcp.tool(
    name="build_pipeline_env",
    description="Rebuild a Jarvis-CD pipeline’s env.yaml, capturing only CMAKE_PREFIX_PATH and PATH"
)
async def build_pipeline_env_tool(
    pipeline_id: str
) -> dict:
    """
    Build the pipeline execution environment for a given pipeline.

    Args:
        pipeline_id (str): ID of the pipeline to build

    Returns:
        dict: Status and results of the environment build operation.
    """
    return await build_pipeline_env(pipeline_id)



@mcp.tool(name="create_pipeline", description="Create a new Jarvis-CD pipeline environment.")
async def create_pipeline_tool(pipeline_id: str) -> dict:
    """
    Create a new pipeline environment for data-centric workflows.

    Args:
        pipeline_id (str): Name/ID for the new pipeline

    Returns:
        dict: Status and details of the created pipeline.
    """
    return await create_pipeline(pipeline_id)


@mcp.tool(name="load_pipeline", description="Load an existing Jarvis-CD pipeline environment.")
async def load_pipeline_tool(pipeline_id: str = None) -> dict:
    """
    Load an existing pipeline environment by ID, or the current one if not specified.

    Args:
        pipeline_id (str, optional): ID of the pipeline to load

    Returns:
        dict: Status and details of the loaded pipeline.
    """
    return await load_pipeline(pipeline_id)

@mcp.tool(name="get_pkg_config",description="Retrieve the configuration of a specific package in a Jarvis-CD pipeline.")
async def get_pkg_config_tool(pipeline_id: str, pkg_id: str) -> dict:
    """
    Retrieve the configuration of a specific package in a pipeline.

    Args:
        pipeline_id (str): ID of the pipeline
        pkg_id (str): ID of the package

    Returns:
        dict: Current configuration of the package.
    """
    return await get_pkg_config(pipeline_id, pkg_id)

@mcp.tool(name="append_pkg", description="Append a package to a Jarvis-CD pipeline.")
async def append_pkg_tool(pipeline_id: str, pkg_type: str, pkg_id: str = None, do_configure: bool = True, extra_args: dict = None) -> dict:
    """
    Add a package to a pipeline for execution or analysis.

    Args:
        pipeline_id (str): ID of the pipeline
        pkg_type (str): Type of package to add
        pkg_id (str, optional): ID for the new package
        do_configure (bool, optional): Whether to configure after adding
        extra_args (dict, optional): Additional configuration arguments

    Returns:
        dict: Status and details of the package addition.
    """
    return await append_pkg(pipeline_id,pkg_type,pkg_id=pkg_id,do_configure=do_configure,**(extra_args or {}))


@mcp.tool(name="configure_pkg", description="Configure a package in a Jarvis-CD pipeline.")
async def configure_pkg_tool(pipeline_id: str, pkg_id: str, extra_args: dict = None) -> dict:
    """
    Configure a package in a pipeline with new settings.

    Args:
        pipeline_id (str): ID of the pipeline
        pkg_id (str): ID of the package
        extra_args (dict, optional): Configuration arguments

    Returns:
        dict: Status and details of the configuration operation.
    """
    return await configure_pkg(pipeline_id, pkg_id, **(extra_args or {}))


@mcp.tool(name="unlink_pkg", description="Unlink a package from a Jarvis-CD pipeline (preserve files).")
async def unlink_pkg_tool(pipeline_id: str, pkg_id: str) -> dict:
    """
    Unlink a package from a pipeline without deleting its files.

    Args:
        pipeline_id (str): ID of the pipeline
        pkg_id (str): ID of the package to unlink

    Returns:
        dict: Status and details of the unlink operation.
    """
    return await unlink_pkg(pipeline_id, pkg_id)


@mcp.tool(name="remove_pkg", description="Remove a package entirely from a Jarvis-CD pipeline.")
async def remove_pkg_tool(pipeline_id: str, pkg_id: str) -> dict:
    """
    Remove a package and its files from a pipeline.

    Args:
        pipeline_id (str): ID of the pipeline
        pkg_id (str): ID of the package to remove

    Returns:
        dict: Status and details of the removal operation.
    """
    return await remove_pkg(pipeline_id, pkg_id)


@mcp.tool(name="run_pipeline", description="Execute a Jarvis-CD pipeline end-to-end.")
async def run_pipeline_tool(pipeline_id: str) -> dict:
    """
    Execute the pipeline, running all configured steps.

    Args:
        pipeline_id (str): ID of the pipeline to run

    Returns:
        dict: Status and results of the pipeline execution.
    """
    return await run_pipeline(pipeline_id)


@mcp.tool(name="destroy_pipeline", description="Destroy a Jarvis-CD pipeline environment and clean up files.")
async def destroy_pipeline_tool(pipeline_id: str) -> dict:
    """
    Destroy a pipeline and clean up all associated files and resources.

    Args:
        pipeline_id (str): ID of the pipeline to destroy

    Returns:
        dict: Status and details of the destruction operation.
    """
    return await destroy_pipeline(pipeline_id)


@mcp.tool(name="jm_create_config", description="Initialize JarvisManager config directories.")
def jm_create_config(config_dir: str, private_dir: str, shared_dir: str = None) -> list:
    """Initialize manager directories and persist configuration."""
    try:
        manager.create(config_dir, private_dir, shared_dir)
        manager.save()
        return [{"type": "text", "text": "Jarvis configuration initialized."}]
    except Exception as e:
        return [{"type": "text", "text": f"Error: {e}"}]


@mcp.tool(name="jm_load_config", description="Load existing JarvisManager configuration.")
def jm_load_config() -> list:
    """Load manager configuration from saved state."""
    try:
        manager.load()
        return [{"type": "text", "text": "Configuration loaded."}]
    except Exception as e:
        return [{"type": "text", "text": f"Error: {e}"}]


@mcp.tool(name="jm_save_config", description="Save current JarvisManager configuration.")
def jm_save_config() -> list:
    """Save current configuration state to disk."""
    try:
        manager.save()
        return [{"type": "text", "text": "Configuration saved."}]
    except Exception as e:
        return [{"type": "text", "text": f"Error: {e}"}]


@mcp.tool(name="jm_set_hostfile", description="Set hostfile path for JarvisManager.")
def jm_set_hostfile(path: str) -> list:
    """Set and save the path to the hostfile for deployments."""
    try:
        manager.set_hostfile(path)
        manager.save()
        return [{"type": "text", "text": f"Hostfile set to '{path}'"}]
    except Exception as e:
        return [{"type": "text", "text": f"Error: {e}"}]


@mcp.tool(name="jm_bootstrap_from", description="Bootstrap Jarvis config from a machine template.")
def jm_bootstrap_from(machine: str) -> list:
    """Bootstrap configuration based on a predefined machine template."""
    try:
        manager.bootstrap_from(machine)
        return [{"type": "text", "text": f"Bootstrapped from '{machine}'"}]
    except Exception as e:
        return [{"type": "text", "text": f"Error: {e}"}]


@mcp.tool(name="jm_bootstrap_list", description="List available bootstrap machine templates.")
def jm_bootstrap_list() -> list:
    """List all bootstrap templates available."""
    try:
        return [{"type": "text", "text": m} for m in manager.bootstrap_list()]
    except Exception as e:
        return [{"type": "text", "text": f"Error: {e}"}]


@mcp.tool(name="jm_reset", description="Reset JarvisManager (destroy all pipelines and data).")
def jm_reset() -> list:
    """Reset manager to a clean state by destroying all pipelines and config."""
    try:
        manager.reset()
        return [{"type": "text", "text": "All pipelines and data reset."}]
    except Exception as e:
        return [{"type": "text", "text": f"Error: {e}"}]


@mcp.tool(name="jm_list_pipelines", description="List all existing Jarvis pipelines.")
def jm_list_pipelines() -> list:
    """List all current pipelines under management."""
    try:
        return [{"type": "text", "text": p} for p in manager.list_pipelines()]
    except Exception as e:
        return [{"type": "text", "text": f"Error: {e}"}]


@mcp.tool(name="jm_cd", description="Change current Jarvis pipeline context.")
def jm_cd(pipeline_id: str) -> list:
    """Set the working pipeline context."""
    try:
        manager.cd(pipeline_id)
        manager.save()
        return [{"type": "text", "text": f"Current pipeline set to '{pipeline_id}'"}]
    except Exception as e:
        return [{"type": "text", "text": f"Error: {e}"}]


@mcp.tool(name="jm_list_repos", description="List all Jarvis repositories.")
def jm_list_repos() -> list:
    """List all registered repositories."""
    try:
        return [{"type": "text", "text": str(repo)} for repo in manager.list_repos()]
    except Exception as e:
        return [{"type": "text", "text": f"Error: {e}"}]


@mcp.tool(name="jm_add_repo", description="Add a repository to JarvisManager.")
def jm_add_repo(path: str, force: bool = False) -> list:
    """Add a repository path to the manager."""
    try:
        manager.add_repo(path, force)
        manager.save()
        return [{"type": "text", "text": f"Repo added: {path}"}]
    except Exception as e:
        return [{"type": "text", "text": f"Error: {e}"}]


@mcp.tool(name="jm_remove_repo", description="Remove a repository from JarvisManager.")
def jm_remove_repo(repo_name: str) -> list:
    """Remove a repository from configuration."""
    try:
        manager.remove_repo(repo_name)
        manager.save()
        return [{"type": "text", "text": f"Repo removed: {repo_name}"}]
    except Exception as e:
        return [{"type": "text", "text": f"Error: {e}"}]


@mcp.tool(name="jm_promote_repo", description="Promote a repository in JarvisManager.")
def jm_promote_repo(repo_name: str) -> list:
    """Promote a repository to higher priority."""
    try:
        manager.promote_repo(repo_name)
        manager.save()
        return [{"type": "text", "text": f"Repo promoted: {repo_name}"}]
    except Exception as e:
        return [{"type": "text", "text": f"Error: {e}"}]


@mcp.tool(name="jm_get_repo", description="Get repository info from JarvisManager.")
def jm_get_repo(repo_name: str) -> list:
    """Get detailed information about a repository."""
    try:
        return [{"type": "text", "text": str(manager.get_repo(repo_name))}]
    except Exception as e:
        return [{"type": "text", "text": f"Error: {e}"}]


@mcp.tool(name="jm_construct_pkg", description="Construct a package skeleton in JarvisManager.")
def jm_construct_pkg(pkg_type: str) -> list:
    """Generate a new package skeleton by type."""
    try:
        obj = manager.construct_pkg(pkg_type)
        return [{"type": "text", "text": f"Constructed pkg: {obj.__class__.__name__}"}]
    except Exception as e:
        return [{"type": "text", "text": f"Error: {e}"}]


@mcp.tool(name="jm_graph_show", description="Print the current resource graph frames.")
def jm_graph_show() -> list:
    """Print the resource graph to the console."""
    try:
        manager.resource_graph_show()
        return [{"type": "text", "text": "Resource graph printed to console."}]
    except Exception as e:
        return [{"type": "text", "text": f"Error: {e}"}]


@mcp.tool(name="jm_graph_build", description="Build or rebuild the resource graph with a net sleep interval.")
def jm_graph_build(net_sleep: float) -> list:
    """Construct or rebuild the graph with a given sleep delay."""
    try:
        manager.resource_graph_build(net_sleep)
        return [{"type": "text", "text": "Resource graph built."}]
    except Exception as e:
        return [{"type": "text", "text": f"Error: {e}"}]


@mcp.tool(name="jm_graph_modify", description="Modify the resource graph using a net sleep interval.")
def jm_graph_modify(net_sleep: float) -> list:
    """Modify the current resource graph with a delay between operations."""
    try:
        manager.resource_graph_modify(net_sleep)
        return [{"type": "text", "text": "Resource graph modified."}]
    except Exception as e:
        return [{"type": "text", "text": f"Error: {e}"}]


def main():
    """
    Main entry point to start the FastMCP server using the specified transport.
    Chooses between stdio and SSE based on MCP_TRANSPORT environment variable.
    """
    transport = os.getenv("MCP_TRANSPORT", "stdio").lower()
    if transport == "sse":
        host = os.getenv("MCP_SSE_HOST", "0.0.0.0")
        port = int(os.getenv("MCP_SSE_PORT", "8000"))
        print(f"Starting SSE on {host}:{port}", file=sys.stderr)
        mcp.run(transport="sse", host=host, port=port)
    else:
        print("Starting stdio transport", file=sys.stderr)
        mcp.run(transport="stdio")
        mcp.run(transport="sse",)


if __name__ == "__main__":
    main()