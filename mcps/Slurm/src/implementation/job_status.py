"""
Slurm job status checking capabilities.
Handles job status monitoring and checking.
"""

import subprocess
from .utils import check_slurm_available


def get_job_status(job_id: str) -> dict:
    """
    Get the status of a Slurm job.

    Args:
        job_id: The Slurm job ID

    Returns:
        Dictionary with job status information
    """
    if not check_slurm_available():
        raise RuntimeError(
            "Slurm is not available on this system. Please install Slurm."
        )

    try:
        cmd = ["squeue", "--job", job_id, "--format=%T,%R", "--noheader"]
        result = subprocess.run(cmd, capture_output=True, text=True)

        if result.returncode == 0 and result.stdout.strip():
            status_parts = result.stdout.strip().split(",")
            return {
                "job_id": job_id,
                "status": status_parts[0] if status_parts else "UNKNOWN",
                "reason": status_parts[1] if len(status_parts) > 1 else "N/A",
                "real_slurm": True,
            }
        else:
            return {
                "job_id": job_id,
                "status": "COMPLETED",
                "reason": "Job not found (may have completed)",
                "real_slurm": True,
            }
    except Exception as e:
        return {
            "job_id": job_id,
            "status": "ERROR",
            "reason": str(e),
            "real_slurm": True,
        }
