"""
Slurm job submission capabilities.
Handles job submission and script creation for Slurm.
"""
import os
import subprocess
import re
import tempfile
from typing import Optional
from .utils import check_slurm_available, ensure_logs_directory


def _create_sbatch_script(original_script: str, cores: int, memory: Optional[str] = None, 
                         time_limit: Optional[str] = None, job_name: Optional[str] = None, 
                         partition: Optional[str] = None) -> str:
    """
    Create a proper Slurm job script with SBATCH directives.
    
    Args:
        original_script: Path to the original script
        cores: Number of cores to request
        memory: Memory requirement (e.g., "4G", "2048M")
        time_limit: Time limit (e.g., "1:00:00")
        job_name: Name for the job
        partition: Slurm partition to use
        
    Returns:
        Path to the modified script with SBATCH directives
    """
    with open(original_script, 'r') as f:
        content = f.read()
    
    # Create a temporary script with SBATCH directives
    fd, temp_script = tempfile.mkstemp(suffix='.sh', prefix='slurm_job_')
    
    # Ensure logs directory exists
    logs_dir = ensure_logs_directory()
    output_path = f"{logs_dir}/slurm_%j.out"
    error_path = f"{logs_dir}/slurm_%j.err"
    
    with os.fdopen(fd, 'w') as f:
        f.write("#!/bin/bash\n")
        f.write(f"#SBATCH --cpus-per-task={cores}\n")
        f.write(f"#SBATCH --job-name={job_name or 'mcp_job'}\n")
        f.write(f"#SBATCH --output={output_path}\n")
        f.write(f"#SBATCH --error={error_path}\n")
        
        if memory:
            f.write(f"#SBATCH --mem={memory}\n")
        if time_limit:
            f.write(f"#SBATCH --time={time_limit}\n")
        if partition:
            f.write(f"#SBATCH --partition={partition}\n")
            
        f.write("\n# Original script content:\n")
        
        # Skip shebang in original content if it exists
        lines = content.split('\n')
        if lines and lines[0].startswith('#!'):
            lines = lines[1:]
        
        f.write('\n'.join(lines))
    
    os.chmod(temp_script, 0o755)
    return temp_script


def _submit_real_slurm_job(script_path: str, cores: int, memory: Optional[str] = None, 
                          time_limit: Optional[str] = None, job_name: Optional[str] = None, 
                          partition: Optional[str] = None) -> dict:
    """Submit a real Slurm job using sbatch."""
    # Create a proper SBATCH script
    sbatch_script = _create_sbatch_script(script_path, cores, memory, time_limit, job_name, partition)
    
    try:
        # Submit the job using sbatch
        cmd = ["sbatch", sbatch_script]
        result = subprocess.run(cmd, capture_output=True, text=True)
        
        if result.returncode != 0:
            raise RuntimeError(f"sbatch failed: {result.stderr}")
        
        output = result.stdout.strip()
        
        # Parse the job ID from sbatch output
        match = re.search(r"Submitted batch job (\d+)", output)
        if not match:
            raise RuntimeError(f"Could not parse job ID from sbatch output: {output}")
        
        job_id = match.group(1)
        print(f"✅ Real Slurm job submitted! Job ID: {job_id}")
        print(f"📄 SBATCH script: {sbatch_script}")
        print(f"💻 Cores requested: {cores}")
        
        return {
            "job_id": job_id,
            "status": "SUBMITTED",
            "script_path": script_path,
            "cores": cores,
            "memory": memory,
            "time_limit": time_limit,
            "job_name": job_name,
            "partition": partition,
            "real_slurm": True
        }
        
    finally:
        # Clean up temporary script
        if os.path.exists(sbatch_script):
            os.unlink(sbatch_script)


def submit_slurm_job(script_path: str, cores: int, memory: Optional[str] = None, 
                    time_limit: Optional[str] = None, job_name: Optional[str] = None, 
                    partition: Optional[str] = None) -> dict:
    """
    Submits a job to Slurm via sbatch with script path and cores.
    Requires Slurm to be installed and available on the system.

    Args:
        script_path: Path to the Slurm job script
        cores: Number of CPU cores to request
        memory: Memory requirement (e.g., "4G", "2048M")
        time_limit: Time limit (e.g., "1:00:00")
        job_name: Name for the job
        partition: Slurm partition to use

    Returns:
        Dictionary containing job submission details including job_id

    Raises:
        FileNotFoundError: If the script file does not exist
        ValueError: If cores <= 0
        RuntimeError: If job submission fails or Slurm is not available
    """
    # Validate inputs
    if not os.path.isfile(script_path):
        raise FileNotFoundError(f"Script file '{script_path}' not found")
    if cores <= 0:
        raise ValueError("Core count must be positive")

    if not check_slurm_available():
        raise RuntimeError("Slurm is not available on this system. Please install Slurm.")

    return _submit_real_slurm_job(script_path, cores, memory, time_limit, job_name, partition)
