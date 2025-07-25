"""
Slurm capabilities module.

This module contains all Slurm-related functionality organized by capability.
"""

# Import all capability functions for backward compatibility
from .job_submission import submit_slurm_job
from .job_status import get_job_status
from .job_cancellation import cancel_slurm_job
from .job_listing import list_slurm_jobs
from .job_details import get_job_details
from .job_output import get_job_output
from .cluster_info import get_slurm_info
from .queue_info import get_queue_info
from .array_jobs import submit_array_job
from .node_info import get_node_info
from .node_allocation import allocate_nodes, deallocate_nodes, get_allocation_status
from .utils import check_slurm_available

__all__ = [
    'submit_slurm_job',
    'get_job_status',
    'cancel_slurm_job',
    'list_slurm_jobs',
    'get_job_details',
    'get_job_output',
    'get_slurm_info',
    'get_queue_info',
    'submit_array_job',
    'get_node_info',
    'allocate_nodes',
    'deallocate_nodes', 
    'get_allocation_status',
    'check_slurm_available'
]
