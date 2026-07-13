"""
Slurm queue information capabilities.
Handles job queue monitoring and statistics.
"""

import subprocess
from typing import Optional
from .utils import (
    SLURM_FIELD_SEPARATOR,
    check_slurm_available,
    complete_stdout_lines,
    run_slurm_command,
    split_slurm_fields,
)


def get_queue_info(
    partition: Optional[str] = None, *, max_records: Optional[int] = None
) -> dict:
    """
    Get information about the Slurm job queue.

    Args:
        partition: Specific partition to query (optional)

    Returns:
        Dictionary with queue information
    """
    if not check_slurm_available():
        raise RuntimeError(
            "Slurm is not available on this system. Please install Slurm."
        )
    if max_records is not None and max_records < 1:
        raise ValueError("max_records must be positive")

    try:
        # Build squeue command for queue overview
        delimiter = SLURM_FIELD_SEPARATOR
        cmd = [
            "squeue",
            f"--format=%i{delimiter}%T{delimiter}%j{delimiter}%u{delimiter}"
            f"%P{delimiter}%M{delimiter}%l{delimiter}%D{delimiter}%C{delimiter}%Q",
            "--noheader",
        ]

        if partition:
            cmd.extend(["--partition", partition])

        max_bytes = (
            2 * 1024 * 1024 if max_records is None else max_records * 2048 + 2048
        )
        result = run_slurm_command(
            cmd,
            max_stdout_bytes=max_bytes,
            test_runner=subprocess.run,
        )

        if result.returncode == 0:
            jobs: list[dict[str, str]] = []
            state_counts = {
                "PENDING": 0,
                "RUNNING": 0,
                "SUSPENDED": 0,
                "CANCELLED": 0,
                "COMPLETING": 0,
            }

            truncated = result.stdout_truncated
            for line in complete_stdout_lines(result):
                if line.strip():
                    parts = split_slurm_fields(line)
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
                            "priority": parts[9] if len(parts) > 9 else "N/A",
                        }
                        if max_records is not None and len(jobs) >= max_records:
                            truncated = True
                            break
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
                "truncated": truncated,
                "real_slurm": True,
            }
        else:
            return {
                "jobs": [],
                "total_jobs": 0,
                "state_summary": {
                    "PENDING": 0,
                    "RUNNING": 0,
                    "SUSPENDED": 0,
                    "CANCELLED": 0,
                    "COMPLETING": 0,
                },
                "partition_filter": partition,
                "error": result.stderr.strip(),
                "real_slurm": True,
            }
    except Exception as e:
        return {
            "jobs": [],
            "total_jobs": 0,
            "state_summary": {
                "PENDING": 0,
                "RUNNING": 0,
                "SUSPENDED": 0,
                "CANCELLED": 0,
                "COMPLETING": 0,
            },
            "partition_filter": partition,
            "error": str(e),
            "real_slurm": True,
        }
