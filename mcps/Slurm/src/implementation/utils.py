"""
Utility functions for Slurm capabilities.
Common functions used across multiple Slurm capabilities.
"""

import shutil
import os


def check_slurm_available() -> bool:
    """Check if Slurm is available on the system."""
    return shutil.which("sbatch") is not None


def ensure_logs_directory() -> str:
    """
    Ensure the logs/slurm_output directory exists.

    Returns:
        Path to the logs/slurm_output directory
    """
    logs_dir = "logs/slurm_output"
    os.makedirs(logs_dir, exist_ok=True)
    return logs_dir
