"""
Slurm job output retrieval capabilities.
Handles job output and log file access.
"""

import os
from .utils import check_slurm_available
from .job_details import get_job_details


def get_job_output(job_id: str, output_type: str = "stdout") -> dict:
    """
    Get job output files (stdout/stderr).

    Args:
        job_id: The Slurm job ID
        output_type: Type of output ("stdout" or "stderr")

    Returns:
        Dictionary with job output content
    """
    if not check_slurm_available():
        raise RuntimeError(
            "Slurm is not available on this system. Please install Slurm."
        )

    try:
        # First get job details to find output files
        details = get_job_details(job_id)

        if "details" in details:
            job_details = details["details"]

            # Look for standard output file patterns in logs directory
            output_file = None
            if output_type == "stdout":
                # Try multiple possible locations
                possible_files = [
                    job_details.get("stdout"),
                    f"logs/slurm_output/slurm_{job_id}.out",
                    f"slurm_{job_id}.out",  # fallback for old files
                ]
                for file_path in possible_files:
                    if file_path and os.path.exists(file_path):
                        output_file = file_path
                        break
            elif output_type == "stderr":
                # Try multiple possible locations
                possible_files = [
                    job_details.get("stderr"),
                    f"logs/slurm_output/slurm_{job_id}.err",
                    f"slurm_{job_id}.err",  # fallback for old files
                ]
                for file_path in possible_files:
                    if file_path and os.path.exists(file_path):
                        output_file = file_path
                        break

            if output_file and os.path.exists(output_file):
                with open(output_file, "r") as f:
                    content = f.read()

                return {
                    "job_id": job_id,
                    "output_type": output_type,
                    "file_path": output_file,
                    "content": content,
                    "real_slurm": True,
                }
            else:
                return {
                    "job_id": job_id,
                    "output_type": output_type,
                    "error": f"Output file not found: {output_file}",
                    "real_slurm": True,
                }
        else:
            return {
                "job_id": job_id,
                "output_type": output_type,
                "error": "Could not get job details",
                "real_slurm": True,
            }

    except Exception as e:
        return {
            "job_id": job_id,
            "output_type": output_type,
            "error": str(e),
            "real_slurm": True,
        }
