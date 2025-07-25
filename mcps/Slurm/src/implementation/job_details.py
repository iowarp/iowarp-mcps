"""
Slurm job details capabilities.
Handles detailed job information retrieval.
"""
import subprocess
from .utils import check_slurm_available


def get_job_details(job_id: str) -> dict:
    """
    Get detailed information about a specific Slurm job.
    
    Args:
        job_id: The Slurm job ID
        
    Returns:
        Dictionary with detailed job information
    """
    if not check_slurm_available():
        raise RuntimeError("Slurm is not available on this system. Please install Slurm.")
        
    try:
        # Use scontrol to get detailed job information
        cmd = ["scontrol", "show", "job", job_id]
        result = subprocess.run(cmd, capture_output=True, text=True)
        
        if result.returncode == 0:
            job_info = {}
            output = result.stdout.strip()
            
            # Parse scontrol output
            for line in output.split('\n'):
                for item in line.split():
                    if '=' in item:
                        key, value = item.split('=', 1)
                        job_info[key.lower()] = value
            
            return {
                "job_id": job_id,
                "details": job_info,
                "real_slurm": True
            }
        else:
            # Try sacct for completed jobs
            cmd = ["sacct", "-j", job_id, "--format=JobID,JobName,Partition,Account,AllocCPUS,State,ExitCode,Start,End,Elapsed,MaxRSS,MaxVMSize", "--parsable2", "--noheader"]
            result = subprocess.run(cmd, capture_output=True, text=True)
            
            if result.returncode == 0 and result.stdout.strip():
                lines = result.stdout.strip().split('\n')
                if lines:
                    fields = ["jobid", "jobname", "partition", "account", "alloccpus", "state", "exitcode", "start", "end", "elapsed", "maxrss", "maxvmsize"]
                    values = lines[0].split('|')
                    
                    job_details = {}
                    for i, field in enumerate(fields):
                        if i < len(values):
                            job_details[field] = values[i]
                    
                    return {
                        "job_id": job_id,
                        "details": job_details,
                        "real_slurm": True,
                        "source": "accounting"
                    }
            
            return {
                "job_id": job_id,
                "error": "Job not found",
                "real_slurm": True
            }
    except Exception as e:
        return {
            "job_id": job_id,
            "error": str(e),
            "real_slurm": True
        }
