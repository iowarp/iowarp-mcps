"""
Slurm job output retrieval capabilities.
Handles job output and log file access.
"""

import os
import stat
from typing import Optional

from .utils import check_slurm_available
from .job_details import get_job_details


def get_job_output(
    job_id: str,
    output_type: str = "stdout",
    *,
    max_chars: Optional[int] = None,
) -> dict:
    """
    Get job output files (stdout/stderr).

    Args:
        job_id: The Slurm job ID
        output_type: Type of output ("stdout" or "stderr")
        max_chars: Optional maximum trailing characters to read. The legacy
            default reads the complete file.

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
                content, truncated = _read_output(output_file, max_chars=max_chars)

                return {
                    "job_id": job_id,
                    "output_type": output_type,
                    "file_path": output_file,
                    "content": content,
                    "truncated": truncated,
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


def _read_output(path: str, *, max_chars: Optional[int]) -> tuple[str, bool]:
    """Read an output file completely or as a bounded UTF-8-safe tail."""
    if max_chars is None:
        with open(path, "r", encoding="utf-8", errors="replace") as stream:
            return stream.read(), False
    if max_chars < 1:
        raise ValueError("max_chars must be positive")

    byte_window = max_chars * 4
    with open(path, "rb") as stream:
        metadata = os.fstat(stream.fileno())
        if not stat.S_ISREG(metadata.st_mode):
            raise ValueError(f"job output is not a regular file: {path}")
        if metadata.st_size > byte_window:
            stream.seek(metadata.st_size - byte_window, os.SEEK_SET)
        content = stream.read(byte_window).decode("utf-8", errors="replace")
    truncated = metadata.st_size > byte_window or len(content) > max_chars
    return content[-max_chars:], truncated
