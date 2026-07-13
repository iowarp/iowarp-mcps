"""
Slurm job status checking capabilities.
Handles job status monitoring and checking.
"""

import subprocess
from .utils import (
    SLURM_FIELD_SEPARATOR,
    check_slurm_available,
    run_slurm_command,
    split_slurm_fields,
)


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
        delimiter = SLURM_FIELD_SEPARATOR
        cmd = [
            "squeue",
            "--job",
            job_id,
            f"--format=%T{delimiter}%R",
            "--noheader",
        ]
        result = run_slurm_command(
            cmd,
            max_stdout_bytes=64 * 1024,
            test_runner=subprocess.run,
        )

        if result.returncode == 0 and result.stdout.strip():
            status_parts = split_slurm_fields(result.stdout.strip())
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
