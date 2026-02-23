"""
MCP Handlers for Slurm MCP Server

This module provides MCP-specific handler functions that wrap the core Slurm capabilities
and return properly formatted responses for the Model Context Protocol.
"""

import logging
from typing import Any, Dict, Optional

# Import core implementation functions
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

# Set up logging
logger = logging.getLogger(__name__)


def _create_error_response(error_message: str, tool_name: str) -> Dict[str, Any]:
    """Create a standardized error response for MCP."""
    return {
        "isError": True,
        "content": [{"text": error_message}],
        "_meta": {"tool": tool_name, "error": True},
    }


def submit_slurm_job_handler(
    script_path: str,
    cores: int,
    memory: Optional[str] = None,
    time_limit: Optional[str] = None,
    job_name: Optional[str] = None,
    partition: Optional[str] = None,
    **kwargs,
) -> Dict[str, Any]:
    """
    MCP handler for submitting Slurm jobs.

    Args:
        script_path: Path to the job script
        cores: Number of CPU cores to request
        memory: Memory requirement (e.g., "4GB")
        time_limit: Time limit (e.g., "01:00:00")
        job_name: Optional job name
        partition: Slurm partition to use

    Returns:
        Dictionary with job submission results or error information
    """
    try:
        result = submit_slurm_job(
            script_path=script_path,
            cores=cores,
            memory=memory,
            time_limit=time_limit,
            job_name=job_name,
            partition=partition,
            **kwargs,
        )

        # Add MCP-specific fields if successful
        if isinstance(result, dict) and "job_id" in result:
            result.update(
                {
                    "script_path": script_path,
                    "cores": cores,
                    "status": "submitted",
                    "message": f"Job submitted successfully with ID: {result['job_id']}",
                }
            )
            if memory:
                result["memory"] = memory
            if time_limit:
                result["time_limit"] = time_limit
            if job_name:
                result["job_name"] = job_name
            if partition:
                result["partition"] = partition

        return result

    except Exception as e:
        logger.error(f"Error in submit_slurm_job_handler: {e}")
        return _create_error_response(str(e), "submit_slurm_job")


def check_job_status_handler(job_id: str) -> Dict[str, Any]:
    """
    MCP handler for checking job status.

    Args:
        job_id: The Slurm job ID

    Returns:
        Dictionary with job status information or error
    """
    try:
        result = get_job_status(job_id)

        # Ensure required fields for MCP
        if isinstance(result, dict):
            result["job_id"] = job_id
            if "real_slurm" not in result:
                result["real_slurm"] = False

        return result

    except Exception as e:
        logger.error(f"Error in check_job_status_handler: {e}")
        return _create_error_response(str(e), "check_job_status")


def cancel_slurm_job_handler(job_id: str) -> Dict[str, Any]:
    """
    MCP handler for canceling Slurm jobs.

    Args:
        job_id: The Slurm job ID to cancel

    Returns:
        Dictionary with cancellation results or error
    """
    try:
        result = cancel_slurm_job(job_id)

        # Ensure required fields for MCP
        if isinstance(result, dict):
            result["job_id"] = job_id
            if "real_slurm" not in result:
                result["real_slurm"] = False

        return result

    except Exception as e:
        logger.error(f"Error in cancel_slurm_job_handler: {e}")
        return _create_error_response(str(e), "cancel_slurm_job")


def list_slurm_jobs_handler(
    user: Optional[str] = None,
    state: Optional[str] = None,
    partition: Optional[str] = None,
) -> Dict[str, Any]:
    """
    MCP handler for listing Slurm jobs.

    Args:
        user: Filter by username
        state: Filter by job state
        partition: Filter by partition

    Returns:
        Dictionary with job list or error
    """
    try:
        result = list_slurm_jobs(user=user, state=state, partition=partition)

        # Add filter information to result
        if isinstance(result, dict):
            if user:
                result["user_filter"] = user
            if state:
                result["state_filter"] = state
            if partition:
                result["partition_filter"] = partition
            if "real_slurm" not in result:
                result["real_slurm"] = False

        return result

    except Exception as e:
        logger.error(f"Error in list_slurm_jobs_handler: {e}")
        return _create_error_response(str(e), "list_slurm_jobs")


def get_slurm_info_handler() -> Dict[str, Any]:
    """
    MCP handler for getting cluster information.

    Returns:
        Dictionary with cluster information or error
    """
    try:
        result = get_slurm_info()

        if isinstance(result, dict) and "real_slurm" not in result:
            result["real_slurm"] = False

        return result

    except Exception as e:
        logger.error(f"Error in get_slurm_info_handler: {e}")
        return _create_error_response(str(e), "get_slurm_info")


def get_job_details_handler(job_id: str) -> Dict[str, Any]:
    """
    MCP handler for getting detailed job information.

    Args:
        job_id: The Slurm job ID

    Returns:
        Dictionary with job details or error
    """
    try:
        result = get_job_details(job_id)

        if isinstance(result, dict):
            result["job_id"] = job_id
            if "real_slurm" not in result:
                result["real_slurm"] = False

        return result

    except Exception as e:
        logger.error(f"Error in get_job_details_handler: {e}")
        return _create_error_response(str(e), "get_job_details")


def get_job_output_handler(job_id: str, output_type: str = "stdout") -> Dict[str, Any]:
    """
    MCP handler for getting job output.

    Args:
        job_id: The Slurm job ID
        output_type: Type of output ("stdout" or "stderr")

    Returns:
        Dictionary with job output or error
    """
    try:
        result = get_job_output(job_id, output_type)

        if isinstance(result, dict):
            result["job_id"] = job_id
            result["output_type"] = output_type
            if "real_slurm" not in result:
                result["real_slurm"] = False

        return result

    except Exception as e:
        logger.error(f"Error in get_job_output_handler: {e}")
        return _create_error_response(str(e), "get_job_output")


def get_queue_info_handler(partition: Optional[str] = None) -> Dict[str, Any]:
    """
    MCP handler for getting queue information.

    Args:
        partition: Optional partition filter

    Returns:
        Dictionary with queue information or error
    """
    try:
        result = get_queue_info(partition=partition)

        if isinstance(result, dict):
            if partition:
                result["partition_filter"] = partition
            if "real_slurm" not in result:
                result["real_slurm"] = False

        return result

    except Exception as e:
        logger.error(f"Error in get_queue_info_handler: {e}")
        return _create_error_response(str(e), "get_queue_info")


def submit_array_job_handler(
    script_path: str,
    array_range: str,
    cores: int = 1,
    memory: Optional[str] = None,
    time_limit: Optional[str] = None,
    job_name: Optional[str] = None,
    **kwargs,
) -> Dict[str, Any]:
    """
    MCP handler for submitting array jobs.

    Args:
        script_path: Path to the job script
        array_range: Array specification (e.g., "1-10")
        cores: Number of CPU cores per task
        memory: Memory requirement per task
        time_limit: Time limit per task
        job_name: Optional job name

    Returns:
        Dictionary with array job submission results or error
    """
    try:
        result = submit_array_job(
            script_path=script_path,
            array_range=array_range,
            cores=cores,
            memory=memory,
            time_limit=time_limit,
            job_name=job_name,
            **kwargs,
        )

        if isinstance(result, dict):
            result["array_range"] = array_range
            if "real_slurm" not in result:
                result["real_slurm"] = False

        return result

    except Exception as e:
        logger.error(f"Error in submit_array_job_handler: {e}")
        return _create_error_response(str(e), "submit_array_job")


def get_node_info_handler(node: Optional[str] = None) -> Dict[str, Any]:
    """
    MCP handler for getting node information.

    Args:
        node: Optional specific node name

    Returns:
        Dictionary with node information or error
    """
    try:
        result = get_node_info(node=node)

        if isinstance(result, dict) and "real_slurm" not in result:
            result["real_slurm"] = False

        return result

    except Exception as e:
        logger.error(f"Error in get_node_info_handler: {e}")
        return _create_error_response(str(e), "get_node_info")
