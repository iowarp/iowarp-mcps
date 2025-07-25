"""
Slurm cluster information capabilities.
Handles cluster configuration and information retrieval.
"""
import subprocess
from .utils import check_slurm_available


def get_slurm_info() -> dict:
    """
    Get information about the Slurm cluster.
    
    Returns:
        Dictionary with cluster information
    """
    if not check_slurm_available():
        raise RuntimeError("Slurm is not available on this system. Please install Slurm.")
        
    try:
        # Get cluster info using sinfo
        cmd = ["sinfo", "--format=%P,%A,%l,%D,%T,%N", "--noheader"]
        result = subprocess.run(cmd, capture_output=True, text=True)
        
        partitions = []
        if result.returncode == 0:
            for line in result.stdout.strip().split('\n'):
                if line.strip():
                    parts = line.split(',')
                    if len(parts) >= 6:
                        partitions.append({
                            "partition": parts[0].rstrip('*'),
                            "avail_idle": parts[1],
                            "timelimit": parts[2],
                            "nodes": parts[3],
                            "state": parts[4],
                            "nodelist": parts[5]
                        })
        
        # Get cluster name and version
        cluster_info = {
            "cluster_name": "slurm-cluster",
            "partitions": partitions,
            "real_slurm": True
        }
        
        # Try to get Slurm version
        try:
            version_cmd = ["sinfo", "--version"]
            version_result = subprocess.run(version_cmd, capture_output=True, text=True)
            if version_result.returncode == 0:
                cluster_info["version"] = version_result.stdout.strip()
        except:
            pass
            
        return cluster_info
        
    except Exception as e:
        return {
            "error": str(e),
            "real_slurm": True
        }
