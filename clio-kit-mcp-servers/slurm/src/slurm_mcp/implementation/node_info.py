"""
Slurm node information capabilities.
Handles cluster node monitoring and information retrieval.
"""

import subprocess
from .utils import check_slurm_available


def get_node_info() -> dict:
    """
    Get information about cluster nodes.

    Returns:
        Dictionary with node information
    """
    if not check_slurm_available():
        raise RuntimeError(
            "Slurm is not available on this system. Please install Slurm."
        )

    try:
        cmd = ["sinfo", "--Node", "--format=%N,%T,%C,%m,%f,%G", "--noheader"]
        result = subprocess.run(cmd, capture_output=True, text=True)

        if result.returncode == 0:
            nodes = []
            for line in result.stdout.strip().split("\n"):
                if line.strip():
                    parts = line.split(",")
                    if len(parts) >= 4:
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

            return {"nodes": nodes, "total_nodes": len(nodes), "real_slurm": True}
        else:
            return {
                "nodes": [],
                "total_nodes": 0,
                "error": result.stderr.strip(),
                "real_slurm": True,
            }
    except Exception as e:
        return {"nodes": [], "total_nodes": 0, "error": str(e), "real_slurm": True}
