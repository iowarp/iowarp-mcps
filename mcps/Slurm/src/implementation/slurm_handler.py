"""
Slurm job management capabilities (Backward compatibility module).
This module re-exports all functions from individual capability modules
to maintain backward compatibility with existing code.

For new code, consider importing directly from specific capability modules:
- job_submission: submit_slurm_job
- job_status: get_job_status
- job_cancellation: cancel_slurm_job
- job_listing: list_slurm_jobs
- job_details: get_job_details
- job_output: get_job_output
- cluster_info: get_slurm_info
- queue_info: get_queue_info
- array_jobs: submit_array_job
- node_info: get_node_info
- utils: check_slurm_available
"""

# Re-export all functions for backward compatibility
from .job_submission import (
    submit_slurm_job,
    _submit_real_slurm_job,
    _create_sbatch_script,
)
from .job_status import get_job_status
from .job_cancellation import cancel_slurm_job
from .job_listing import list_slurm_jobs
from .job_details import get_job_details
from .job_output import get_job_output
from .cluster_info import get_slurm_info
from .queue_info import get_queue_info
from .array_jobs import submit_array_job
from .node_info import get_node_info
from .utils import check_slurm_available


# Keep old function name for backward compatibility
def _check_slurm_available():
    """Check if Slurm is available on the system (deprecated - use check_slurm_available)."""
    return check_slurm_available()


__all__ = [
    "submit_slurm_job",
    "_submit_real_slurm_job",
    "_create_sbatch_script",
    "get_job_status",
    "cancel_slurm_job",
    "list_slurm_jobs",
    "get_job_details",
    "get_job_output",
    "get_slurm_info",
    "get_queue_info",
    "submit_array_job",
    "get_node_info",
    "_check_slurm_available",
    "check_slurm_available",
]
