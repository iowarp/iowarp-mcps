"""
Slurm node information capabilities.
Handles cluster node monitoring and information retrieval.
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


def get_node_info(
    node: Optional[str] = None, *, max_records: Optional[int] = None
) -> dict:
    """
    Get information about cluster nodes.

    Args:
        node: Specific node name to query (optional)

    Returns:
        Dictionary with node information
    """
    if not check_slurm_available():
        raise RuntimeError(
            "Slurm is not available on this system. Please install Slurm."
        )
    if max_records is not None and max_records < 1:
        raise ValueError("max_records must be positive")

    try:
        delimiter = SLURM_FIELD_SEPARATOR
        cmd = [
            "sinfo",
            "--Node",
            f"--format=%N{delimiter}%T{delimiter}%C{delimiter}%m{delimiter}%f{delimiter}%G",
            "--noheader",
        ]
        if node:
            cmd.extend(["--nodes", node])
        max_bytes = (
            2 * 1024 * 1024 if max_records is None else max_records * 4096 + 4096
        )
        result = run_slurm_command(
            cmd,
            max_stdout_bytes=max_bytes,
            test_runner=subprocess.run,
        )

        if result.returncode == 0:
            nodes: list[dict[str, str]] = []
            truncated = result.stdout_truncated
            for line in complete_stdout_lines(result):
                if line.strip():
                    parts = split_slurm_fields(line)
                    if len(parts) >= 4:
                        if max_records is not None and len(nodes) >= max_records:
                            truncated = True
                            break
                        nodes.append(
                            {
                                "node_name": parts[0],
                                "state": parts[1],
                                "cpus": parts[2],
                                "memory": parts[3],
                                "features": parts[4] if len(parts) > 4 else "",
                                "gres": parts[5] if len(parts) > 5 else "",
                            }
                        )

            return {
                "nodes": nodes,
                "total_nodes": len(nodes),
                "truncated": truncated,
                "real_slurm": True,
            }
        else:
            return {
                "nodes": [],
                "total_nodes": 0,
                "error": result.stderr.strip(),
                "real_slurm": True,
            }
    except Exception as e:
        return {"nodes": [], "total_nodes": 0, "error": str(e), "real_slurm": True}
