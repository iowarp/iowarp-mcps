"""
Slurm job listing capabilities.
Handles job queue listing and filtering.
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


def list_slurm_jobs(
    user: Optional[str] = None,
    state: Optional[str] = None,
    partition: Optional[str] = None,
    *,
    max_records: Optional[int] = None,
) -> dict:
    """
    List Slurm jobs with optional filtering.

    Args:
        user: Username to filter by (default: current user)
        state: Job state to filter by (PENDING, RUNNING, COMPLETED, etc.)
        partition: Partition to filter by

    Returns:
        Dictionary with list of jobs
    """
    if not check_slurm_available():
        raise RuntimeError(
            "Slurm is not available on this system. Please install Slurm."
        )
    if max_records is not None and max_records < 1:
        raise ValueError("max_records must be positive")

    try:
        # Build squeue command
        delimiter = SLURM_FIELD_SEPARATOR
        cmd = [
            "squeue",
            f"--format=%i{delimiter}%T{delimiter}%j{delimiter}%u{delimiter}"
            f"%M{delimiter}%l{delimiter}%D{delimiter}%C",
            "--noheader",
        ]

        if user:
            cmd.extend(["--user", user])
        if state:
            cmd.extend(["--states", state])
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
            truncated = result.stdout_truncated
            for line in complete_stdout_lines(result):
                if line.strip():
                    parts = split_slurm_fields(line)
                    if len(parts) >= 8:
                        if max_records is not None and len(jobs) >= max_records:
                            truncated = True
                            break
                        jobs.append(
                            {
                                "job_id": parts[0],
                                "state": parts[1],
                                "name": parts[2],
                                "user": parts[3],
                                "time": parts[4],
                                "time_limit": parts[5],
                                "nodes": parts[6],
                                "cpus": parts[7],
                            }
                        )

            return {
                "jobs": jobs,
                "count": len(jobs),
                "user_filter": user,
                "state_filter": state,
                "partition_filter": partition,
                "truncated": truncated,
                "real_slurm": True,
            }
        else:
            # Command failed, return error but with proper structure
            return {
                "jobs": [],
                "count": 0,
                "user_filter": user,
                "state_filter": state,
                "error": result.stderr.strip(),
                "real_slurm": True,
            }
    except Exception as e:
        return {"jobs": [], "error": str(e), "real_slurm": True}
