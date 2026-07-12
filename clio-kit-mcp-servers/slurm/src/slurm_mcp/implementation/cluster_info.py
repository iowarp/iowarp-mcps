"""
Slurm cluster information capabilities.
Handles cluster configuration and information retrieval.
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


def get_slurm_info(*, max_records: Optional[int] = None) -> dict:
    """
    Get information about the Slurm cluster.

    Returns:
        Dictionary with cluster information
    """
    if not check_slurm_available():
        raise RuntimeError(
            "Slurm is not available on this system. Please install Slurm."
        )
    if max_records is not None and max_records < 1:
        raise ValueError("max_records must be positive")

    try:
        # Get cluster info using sinfo
        delimiter = SLURM_FIELD_SEPARATOR
        cmd = [
            "sinfo",
            f"--format=%P{delimiter}%A{delimiter}%l{delimiter}%D{delimiter}%T{delimiter}%N",
            "--noheader",
        ]
        max_bytes = (
            2 * 1024 * 1024 if max_records is None else max_records * 4096 + 4096
        )
        result = run_slurm_command(
            cmd,
            max_stdout_bytes=max_bytes,
            test_runner=subprocess.run,
        )

        partitions: list[dict[str, str]] = []
        truncated = result.stdout_truncated
        if result.returncode == 0:
            for line in complete_stdout_lines(result):
                if line.strip():
                    parts = split_slurm_fields(line)
                    if len(parts) >= 6:
                        if max_records is not None and len(partitions) >= max_records:
                            truncated = True
                            break
                        partitions.append(
                            {
                                "partition": parts[0].rstrip("*"),
                                "avail_idle": parts[1],
                                "timelimit": parts[2],
                                "nodes": parts[3],
                                "state": parts[4],
                                "nodelist": parts[5],
                            }
                        )

        # Get cluster name and version
        cluster_info = {
            "cluster_name": "slurm-cluster",
            "partitions": partitions,
            "truncated": truncated,
            "real_slurm": True,
        }

        # Try to get Slurm version
        try:
            version_cmd = ["sinfo", "--version"]
            version_result = run_slurm_command(
                version_cmd,
                max_stdout_bytes=4096,
                test_runner=subprocess.run,
            )
            if version_result.returncode == 0:
                cluster_info["version"] = version_result.stdout.strip()
        except Exception:
            pass

        return cluster_info

    except Exception as e:
        return {"error": str(e), "real_slurm": True}
