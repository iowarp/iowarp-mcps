"""
Slurm array job submission capabilities.
Handles array job creation and management.
"""

import os
import subprocess
import re
import tempfile
from typing import Optional
from .utils import check_slurm_available, ensure_logs_directory


def submit_array_job(
    script_path: str,
    array_range: str,
    cores: int = 1,
    memory: Optional[str] = None,
    time_limit: Optional[str] = None,
    job_name: Optional[str] = None,
    partition: Optional[str] = None,
) -> dict:
    """
    Submit a Slurm array job.

    Args:
        script_path: Path to the job script
        array_range: Array range specification (e.g., "1-10", "1-100:2")
        cores: Number of cores per array task
        memory: Memory per array task
        time_limit: Time limit per array task
        job_name: Base name for the array job
        partition: Slurm partition to use

    Returns:
        Dictionary with array job submission results
    """
    if not check_slurm_available():
        raise RuntimeError(
            "Slurm is not available on this system. Please install Slurm."
        )

    try:
        # Create SBATCH script with array directive
        with open(script_path, "r") as f:
            content = f.read()

        fd, temp_script = tempfile.mkstemp(suffix=".sh", prefix="slurm_array_")

        # Ensure logs directory exists
        logs_dir = ensure_logs_directory()

        with os.fdopen(fd, "w") as f:
            f.write("#!/bin/bash\n")
            f.write(f"#SBATCH --array={array_range}\n")
            f.write(f"#SBATCH --cpus-per-task={cores}\n")
            f.write(f"#SBATCH --job-name={job_name or 'array_job'}\n")
            f.write(f"#SBATCH --output={logs_dir}/slurm_%A_%a.out\n")
            f.write(f"#SBATCH --error={logs_dir}/slurm_%A_%a.err\n")

            if memory:
                f.write(f"#SBATCH --mem={memory}\n")
            if time_limit:
                f.write(f"#SBATCH --time={time_limit}\n")
            if partition:
                f.write(f"#SBATCH --partition={partition}\n")

            f.write("\n# Array job script content:\n")
            f.write(
                'echo "Array job ${SLURM_ARRAY_JOB_ID}, task ${SLURM_ARRAY_TASK_ID}"\n'
            )
            f.write('echo "Running on node: $(hostname)"\n')
            f.write("\n# Original script content:\n")

            # Skip shebang in original content if it exists
            lines = content.split("\n")
            if lines and lines[0].startswith("#!"):
                lines = lines[1:]

            f.write("\n".join(lines))

        os.chmod(temp_script, 0o755)

        # Submit the array job
        cmd = ["sbatch", temp_script]
        result = subprocess.run(cmd, capture_output=True, text=True)

        if result.returncode != 0:
            raise RuntimeError(f"sbatch failed: {result.stderr}")

        output = result.stdout.strip()

        # Parse the array job ID from sbatch output
        match = re.search(r"Submitted batch job (\d+)", output)
        if not match:
            raise RuntimeError(f"Could not parse job ID from sbatch output: {output}")

        array_job_id = match.group(1)

        return {
            "array_job_id": array_job_id,
            "array_range": array_range,
            "script_path": script_path,
            "cores": cores,
            "memory": memory,
            "time_limit": time_limit,
            "job_name": job_name,
            "partition": partition,
            "message": f"Array job {array_job_id} submitted successfully",
            "real_slurm": True,
        }

    except Exception as e:
        return {"error": str(e), "real_slurm": True}
    finally:
        # Clean up temporary script
        if "temp_script" in locals() and os.path.exists(temp_script):
            os.unlink(temp_script)
