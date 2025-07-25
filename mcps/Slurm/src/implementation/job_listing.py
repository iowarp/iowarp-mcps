"""
Slurm job listing capabilities.
Handles job queue listing and filtering.
"""
import subprocess
from typing import Optional
from .utils import check_slurm_available


def list_slurm_jobs(user: Optional[str] = None, state: Optional[str] = None) -> dict:
    """
    List Slurm jobs with optional filtering.
    
    Args:
        user: Username to filter by (default: current user)
        state: Job state to filter by (PENDING, RUNNING, COMPLETED, etc.)
        
    Returns:
        Dictionary with list of jobs
    """
    if not check_slurm_available():
        raise RuntimeError("Slurm is not available on this system. Please install Slurm.")
        
    try:
        # Build squeue command
        cmd = ["squeue", "--format=%i,%T,%j,%u,%M,%l,%D,%C", "--noheader"]
        
        if user:
            cmd.extend(["--user", user])
        if state:
            cmd.extend(["--states", state])
            
        result = subprocess.run(cmd, capture_output=True, text=True)
        
        if result.returncode == 0:
            jobs = []
            for line in result.stdout.strip().split('\n'):
                if line.strip():
                    parts = line.split(',')
                    if len(parts) >= 8:
                        jobs.append({
                            "job_id": parts[0],
                            "state": parts[1],
                            "name": parts[2],
                            "user": parts[3],
                            "time": parts[4],
                            "time_limit": parts[5],
                            "nodes": parts[6],
                            "cpus": parts[7]
                        })
            
            return {
                "jobs": jobs,
                "count": len(jobs),
                "user_filter": user,
                "state_filter": state,
                "real_slurm": True
            }
        else:
            # Command failed, return error but with proper structure
            return {
                "jobs": [],
                "count": 0,
                "user_filter": user,
                "state_filter": state,
                "error": result.stderr.strip(),
                "real_slurm": True
            }
    except Exception as e:
        return {
            "jobs": [],
            "error": str(e),
            "real_slurm": True
        }
