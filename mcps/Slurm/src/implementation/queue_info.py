"""
Slurm queue information capabilities.
Handles job queue monitoring and statistics.
"""
import subprocess
from typing import Optional
from .utils import check_slurm_available


def get_queue_info(partition: Optional[str] = None) -> dict:
    """
    Get information about the Slurm job queue.
    
    Args:
        partition: Specific partition to query (optional)
        
    Returns:
        Dictionary with queue information
    """
    if not check_slurm_available():
        raise RuntimeError("Slurm is not available on this system. Please install Slurm.")
        
    try:
        # Build squeue command for queue overview
        cmd = ["squeue", "--format=%i,%T,%j,%u,%P,%M,%l,%D,%C,%Q", "--noheader"]
        
        if partition:
            cmd.extend(["--partition", partition])
            
        result = subprocess.run(cmd, capture_output=True, text=True)
        
        if result.returncode == 0:
            jobs = []
            state_counts = {"PENDING": 0, "RUNNING": 0, "SUSPENDED": 0, "CANCELLED": 0, "COMPLETING": 0}
            
            for line in result.stdout.strip().split('\n'):
                if line.strip():
                    parts = line.split(',')
                    if len(parts) >= 9:
                        job_info = {
                            "job_id": parts[0],
                            "state": parts[1],
                            "name": parts[2],
                            "user": parts[3],
                            "partition": parts[4],
                            "time": parts[5],
                            "time_limit": parts[6],
                            "nodes": parts[7],
                            "cpus": parts[8],
                            "priority": parts[9] if len(parts) > 9 else "N/A"
                        }
                        jobs.append(job_info)
                        
                        # Count states
                        state = job_info["state"]
                        if state in state_counts:
                            state_counts[state] += 1
            
            return {
                "jobs": jobs,
                "total_jobs": len(jobs),
                "state_summary": state_counts,
                "partition_filter": partition,
                "real_slurm": True
            }
        else:
            return {
                "jobs": [],
                "total_jobs": 0,
                "state_summary": {"PENDING": 0, "RUNNING": 0, "SUSPENDED": 0, "CANCELLED": 0, "COMPLETING": 0},
                "partition_filter": partition,
                "error": result.stderr.strip(),
                "real_slurm": True
            }
    except Exception as e:
        return {
            "jobs": [],
            "total_jobs": 0,
            "state_summary": {"PENDING": 0, "RUNNING": 0, "SUSPENDED": 0, "CANCELLED": 0, "COMPLETING": 0},
            "partition_filter": partition,
            "error": str(e),
            "real_slurm": True
        }
