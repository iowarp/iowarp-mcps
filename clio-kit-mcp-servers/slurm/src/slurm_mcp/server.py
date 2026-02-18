"""
Slurm MCP Server - HPC Job Management and Cluster Monitoring

Provides HPC job management and cluster monitoring through the Model Context Protocol,
enabling job submission, queue monitoring, cancellation, and node allocation on Slurm systems.
"""

import os
import sys
import logging
from typing import Optional

from fastmcp import FastMCP
from fastmcp.exceptions import ToolError
from fastmcp.prompts import Message

try:
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:
    print(
        "Warning: python-dotenv not available. Environment variables may not be loaded.",
        file=sys.stderr,
    )

from .implementation.job_submission import submit_slurm_job
from .implementation.job_status import get_job_status
from .implementation.job_cancellation import cancel_slurm_job
from .implementation.job_listing import list_slurm_jobs
from .implementation.cluster_info import get_slurm_info
from .implementation.job_details import get_job_details
from .implementation.job_output import get_job_output
from .implementation.queue_info import get_queue_info
from .implementation.array_jobs import submit_array_job
from .implementation.node_info import get_node_info
from .implementation.node_allocation import (
    allocate_nodes,
    deallocate_nodes,
    get_allocation_status,
)

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize FastMCP server instance
mcp: FastMCP = FastMCP(
    "slurm",
    instructions=(
        "Manages HPC jobs via the Slurm workload manager. "
        "Submit jobs, monitor queue status, cancel jobs, and manage node allocations."
    ),
    list_page_size=10,
)


# Custom exception for Slurm MCP errors
class SlurmMCPError(Exception):
    """Custom exception for Slurm MCP-related errors"""

    pass


# -----------------------------------------------------------------------
# SLURM JOB MANAGEMENT TOOLS
# -----------------------------------------------------------------------


@mcp.tool(
    name="submit_slurm_job",
    description="Submit a job script to the Slurm scheduler with resource requirements.",
    annotations={"readOnlyHint": False, "destructiveHint": False, "idempotentHint": False},
    tags={"jobs", "submission"},
)
async def submit_slurm_job_tool(
    script_path: str,
    cores: int = 1,
    memory: str = "1GB",
    time_limit: str = "01:00:00",
    job_name: Optional[str] = None,
    partition: Optional[str] = None,
) -> dict:
    """Submit a job script to Slurm scheduler with resource specification.

    Args:
        script_path: Path to the job script file (required)
        cores: Number of CPU cores to request (default: 1, must be > 0)
        memory: Memory requirement (e.g., "4G", "2048M", default: "1GB")
        time_limit: Time limit in HH:MM:SS format (default: "01:00:00")
        job_name: Custom job name for identification (default: derived from script)
        partition: Slurm partition to use (default: system default)

    Returns:
        Dictionary containing job submission results
    """
    try:
        logger.info(f"Submitting Slurm job: {script_path} with {cores} cores")

        return submit_slurm_job(
            script_path, cores, memory, time_limit, job_name, partition
        )
    except Exception as e:
        logger.error(f"Job submission error: {e}")
        raise ToolError(f"Job submission failed: {e}")


@mcp.tool(
    name="check_job_status",
    description="Check the status of a Slurm job by its ID.",
    annotations={"readOnlyHint": True, "destructiveHint": False, "idempotentHint": True},
    tags={"jobs", "monitoring"},
)
async def check_job_status_tool(job_id: str) -> dict:
    """Check status of a Slurm job.

    Args:
        job_id: The Slurm job ID to check (required)

    Returns:
        Dictionary containing job status information
    """
    try:
        logger.info(f"Checking status for job: {job_id}")

        return get_job_status(job_id)
    except Exception as e:
        logger.error(f"Job status check error: {e}")
        raise ToolError(f"Job status check failed: {e}")


@mcp.tool(
    name="cancel_slurm_job",
    description="Cancel a running or pending Slurm job.",
    annotations={"readOnlyHint": False, "destructiveHint": True, "idempotentHint": True},
    tags={"jobs", "management"},
)
async def cancel_slurm_job_tool(job_id: str) -> dict:
    """Cancel a Slurm job.

    Args:
        job_id: The Slurm job ID to cancel

    Returns:
        Dictionary with cancellation results
    """
    try:
        logger.info(f"Cancelling job: {job_id}")
        return cancel_slurm_job(job_id)
    except Exception as e:
        logger.error(f"Job cancellation error: {e}")
        raise ToolError(f"Job cancellation failed: {e}")


@mcp.tool(
    name="list_slurm_jobs",
    description="List Slurm jobs with optional filtering by user and state.",
    annotations={"readOnlyHint": True, "destructiveHint": False, "idempotentHint": True},
    tags={"jobs", "monitoring"},
)
async def list_slurm_jobs_tool(
    user: Optional[str] = None, state: Optional[str] = None
) -> dict:
    """List Slurm jobs with optional filtering.

    Args:
        user: Username to filter by (default: current user)
        state: Job state to filter by (PENDING, RUNNING, COMPLETED, etc.)

    Returns:
        Dictionary with list of jobs
    """
    try:
        logger.info(f"Listing jobs for user: {user}, state: {state}")
        return list_slurm_jobs(user, state)
    except Exception as e:
        logger.error(f"Job listing error: {e}")
        raise ToolError(f"Job listing failed: {e}")


@mcp.tool(
    name="get_slurm_info",
    description="Get Slurm cluster configuration, partitions, and resource availability.",
    annotations={"readOnlyHint": True, "destructiveHint": False, "idempotentHint": True},
    tags={"jobs", "monitoring"},
)
async def get_slurm_info_tool() -> dict:
    """Get information about the Slurm cluster.

    Returns:
        Dictionary with cluster information
    """
    try:
        logger.info("Getting Slurm cluster information")
        return get_slurm_info()
    except Exception as e:
        logger.error(f"Cluster info error: {e}")
        raise ToolError(f"Cluster info retrieval failed: {e}")


@mcp.tool(
    name="get_job_details",
    description="Get detailed information about a specific Slurm job.",
    annotations={"readOnlyHint": True, "destructiveHint": False, "idempotentHint": True},
    tags={"jobs", "monitoring"},
)
async def get_job_details_tool(job_id: str) -> dict:
    """Get detailed information about a Slurm job.

    Args:
        job_id: The Slurm job ID

    Returns:
        Dictionary with detailed job information
    """
    try:
        logger.info(f"Getting detailed information for job: {job_id}")
        return get_job_details(job_id)
    except Exception as e:
        logger.error(f"Job details error: {e}")
        raise ToolError(f"Job details retrieval failed: {e}")


@mcp.tool(
    name="get_job_output",
    description="Retrieve stdout or stderr output from a Slurm job.",
    annotations={"readOnlyHint": True, "destructiveHint": False, "idempotentHint": True},
    tags={"jobs", "monitoring"},
)
async def get_job_output_tool(job_id: str, output_type: str = "stdout") -> dict:
    """Get job output content.

    Args:
        job_id: The Slurm job ID
        output_type: Type of output ("stdout" or "stderr")

    Returns:
        Dictionary with job output content
    """
    try:
        logger.info(f"Getting {output_type} for job: {job_id}")
        return get_job_output(job_id, output_type)
    except Exception as e:
        logger.error(f"Job output error: {e}")
        raise ToolError(f"Job output retrieval failed: {e}")


@mcp.tool(
    name="get_queue_info",
    description="Get Slurm queue status and partition information.",
    annotations={"readOnlyHint": True, "destructiveHint": False, "idempotentHint": True},
    tags={"jobs", "monitoring"},
)
async def get_queue_info_tool(partition: Optional[str] = None) -> dict:
    """Get job queue information.

    Args:
        partition: Specific partition to query (optional)

    Returns:
        Dictionary with queue information
    """
    try:
        logger.info(f"Getting queue information for partition: {partition}")
        return get_queue_info(partition)
    except Exception as e:
        logger.error(f"Queue info error: {e}")
        raise ToolError(f"Queue info retrieval failed: {e}")


@mcp.tool(
    name="submit_array_job",
    description="Submit a Slurm array job for parallel task execution.",
    annotations={"readOnlyHint": False, "destructiveHint": False, "idempotentHint": False},
    tags={"jobs", "submission"},
)
async def submit_array_job_tool(
    script_path: str,
    array_range: str,
    cores: int = 1,
    memory: str = "1GB",
    time_limit: str = "01:00:00",
    job_name: Optional[str] = None,
    partition: Optional[str] = None,
) -> dict:
    """Submit an array job to Slurm scheduler.

    Args:
        script_path: Path to the job script file
        array_range: Array range specification (e.g., "1-10", "1-100:2")
        cores: Number of cores per array task (default: 1)
        memory: Memory per array task (default: "1GB")
        time_limit: Time limit per array task in HH:MM:SS format (default: "01:00:00")
        job_name: Base name for the array job (default: derived from script)
        partition: Slurm partition to use (default: system default)

    Returns:
        Dictionary with array job submission results
    """
    try:
        logger.info(
            f"Submitting array job: {script_path}, range: {array_range}, cores: {cores}"
        )
        return submit_array_job(
            script_path, array_range, cores, memory, time_limit, job_name, partition
        )
    except Exception as e:
        logger.error(f"Array job submission error: {e}")
        raise ToolError(f"Array job submission failed: {e}")


@mcp.tool(
    name="get_node_info",
    description="Get information about Slurm cluster nodes and their resources.",
    annotations={"readOnlyHint": True, "destructiveHint": False, "idempotentHint": True},
    tags={"jobs", "monitoring"},
)
async def get_node_info_tool() -> dict:
    """Get cluster node information.

    Returns:
        Dictionary with node information
    """
    try:
        logger.info("Getting cluster node information")
        return get_node_info()
    except Exception as e:
        logger.error(f"Node info error: {e}")
        raise ToolError(f"Node info retrieval failed: {e}")


@mcp.tool(
    name="allocate_slurm_nodes",
    description="Allocate Slurm nodes for an interactive session using salloc.",
    annotations={"readOnlyHint": False, "destructiveHint": False, "idempotentHint": False},
    tags={"jobs", "submission"},
)
async def allocate_slurm_nodes_tool(
    nodes: int = 1,
    cores: int = 1,
    memory: Optional[str] = None,
    time_limit: str = "01:00:00",
    partition: Optional[str] = None,
    job_name: Optional[str] = None,
    immediate: bool = False,
) -> dict:
    """Allocate Slurm nodes using salloc command.

    Args:
        nodes: Number of nodes to allocate (default: 1)
        cores: Number of cores per node (default: 1)
        memory: Memory requirement (e.g., "4G", "2048M")
        time_limit: Time limit (e.g., "1:00:00", default: "01:00:00")
        partition: Slurm partition to use
        job_name: Name for the allocation
        immediate: Whether to return immediately without waiting

    Returns:
        Dictionary with allocation information
    """
    try:
        logger.info(f"Allocating {nodes} nodes with {cores} cores each")
        return allocate_nodes(
            nodes, cores, memory, time_limit, partition, job_name, immediate
        )
    except Exception as e:
        logger.error(f"Node allocation error: {e}")
        raise ToolError(f"Node allocation failed: {e}")


@mcp.tool(
    name="deallocate_slurm_nodes",
    description="Release a Slurm node allocation by canceling it.",
    annotations={"readOnlyHint": False, "destructiveHint": True, "idempotentHint": True},
    tags={"jobs", "management"},
)
async def deallocate_slurm_nodes_tool(allocation_id: str) -> dict:
    """Deallocate Slurm nodes by canceling the allocation.

    Args:
        allocation_id: The allocation ID to cancel

    Returns:
        Dictionary with deallocation status
    """
    try:
        logger.info(f"Deallocating allocation {allocation_id}")
        return deallocate_nodes(allocation_id)
    except Exception as e:
        logger.error(f"Node deallocation error: {e}")
        raise ToolError(f"Node deallocation failed: {e}")


@mcp.tool(
    name="get_allocation_status",
    description="Check the status of a Slurm node allocation.",
    annotations={"readOnlyHint": True, "destructiveHint": False, "idempotentHint": True},
    tags={"jobs", "monitoring"},
)
async def get_allocation_status_tool(allocation_id: str) -> dict:
    """Get status of a node allocation.

    Args:
        allocation_id: The allocation ID to check

    Returns:
        Dictionary with allocation status information
    """
    try:
        logger.info(f"Checking status of allocation {allocation_id}")
        return get_allocation_status(allocation_id)
    except Exception as e:
        logger.error(f"Allocation status error: {e}")
        raise ToolError(f"Allocation status check failed: {e}")


# -----------------------------------------------------------------------
# RESOURCES
# -----------------------------------------------------------------------


@mcp.resource("slurm://cluster-info")
def cluster_info() -> dict:
    """Basic Slurm cluster configuration."""
    return {
        "scheduler": "slurm",
        "operations": ["submit", "cancel", "status", "queue", "accounting"],
        "description": "Slurm workload manager for HPC job scheduling",
    }


# -----------------------------------------------------------------------
# PROMPTS
# -----------------------------------------------------------------------


@mcp.prompt()
def submit_job_workflow(script_path: str) -> list[Message]:
    """Guided workflow for submitting and monitoring a Slurm job."""
    return [
        Message(
            f"I need to submit the job script at {script_path}. "
            "First check the queue status, then submit with appropriate resources, "
            "and set up monitoring for the job."
        ),
    ]


def main() -> None:
    """Main entry point for the Slurm MCP server."""
    import argparse

    parser = argparse.ArgumentParser(description="Slurm MCP Server")
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
