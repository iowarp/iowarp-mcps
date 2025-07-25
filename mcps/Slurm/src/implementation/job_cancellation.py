"""
Slurm job cancellation capabilities.
Handles job cancellation and termination.
"""
import subprocess
from .utils import check_slurm_available


def cancel_slurm_job(job_id: str) -> dict:
    """
    Cancel a Slurm job.
    
    Args:
        job_id: The Slurm job ID to cancel
        
    Returns:
        Dictionary with cancellation results
    """
    if not check_slurm_available():
        raise RuntimeError("Slurm is not available on this system. Please install Slurm.")
        
    try:
        cmd = ["scancel", job_id]
        result = subprocess.run(cmd, capture_output=True, text=True)
        
        if result.returncode == 0:
            return {
                "job_id": job_id,
                "status": "cancelled",
                "message": f"Job {job_id} cancelled successfully",
                "real_slurm": True
            }
        else:
            return {
                "job_id": job_id,
                "status": "error",
                "message": f"Failed to cancel job: {result.stderr.strip()}",
                "real_slurm": True
            }
    except Exception as e:
        return {
            "job_id": job_id,
            "status": "error",
            "message": str(e),
            "real_slurm": True
        }
