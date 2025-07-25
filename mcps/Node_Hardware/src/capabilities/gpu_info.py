"""
GPU information capabilities.
Handles GPU information reporting (if available).
"""

from typing import Dict, Any
from capabilities.utils import run_command, check_command_available


def get_gpu_info() -> Dict[str, Any]:
    """
    Get GPU information if available.

    Returns:
        Dictionary with GPU information
    """
    try:
        gpu_info: Dict[str, Any] = {
            "gpus": [],
            "nvidia_available": False,
            "amd_available": False,
            "intel_available": False,
        }

        # Try to get NVIDIA GPU information
        if check_command_available("nvidia-smi"):
            nvidia_result = run_command(
                [
                    "nvidia-smi",
                    "--query-gpu=index,name,memory.total,memory.used,memory.free,temperature.gpu,utilization.gpu,utilization.memory",
                    "--format=csv,noheader,nounits",
                ]
            )

            if nvidia_result["success"]:
                gpu_info["nvidia_available"] = True
                lines = nvidia_result["stdout"].strip().split("\n")

                for line in lines:
                    if line.strip():
                        parts = [part.strip() for part in line.split(",")]
                        if len(parts) >= 8:
                            gpu_info["gpus"].append(
                                {
                                    "vendor": "NVIDIA",
                                    "index": parts[0],
                                    "name": parts[1],
                                    "memory_total": f"{parts[2]} MB",
                                    "memory_used": f"{parts[3]} MB",
                                    "memory_free": f"{parts[4]} MB",
                                    "temperature": f"{parts[5]}C",
                                    "utilization_gpu": f"{parts[6]}%",
                                    "utilization_memory": f"{parts[7]}%",
                                }
                            )

        # Try to get AMD GPU information (using rocm-smi if available)
        if check_command_available("rocm-smi"):
            amd_result = run_command(
                [
                    "rocm-smi",
                    "--showid",
                    "--showproductname",
                    "--showmeminfo",
                    "--showuse",
                    "--showtemp",
                ]
            )

            if amd_result["success"]:
                gpu_info["amd_available"] = True
                # Parse AMD GPU info (this is a simplified version)
                gpu_info["amd_info"] = amd_result["stdout"]

        # Try to get Intel GPU information (using intel_gpu_top if available)
        if check_command_available("intel_gpu_top"):
            intel_result = run_command(["intel_gpu_top", "-l", "-o", "-"])

            if intel_result["success"]:
                gpu_info["intel_available"] = True
                gpu_info["intel_info"] = "Intel GPU detected"

        # If no specific GPU tools available, try lspci
        if not gpu_info["gpus"] and check_command_available("lspci"):
            lspci_result = run_command(["lspci", "-nn"])

            if lspci_result["success"]:
                gpu_lines = [
                    line
                    for line in lspci_result["stdout"].split("\n")
                    if "VGA" in line or "Display" in line or "3D" in line
                ]

                for line in gpu_lines:
                    gpu_info["gpus"].append(
                        {"vendor": "Unknown", "name": line.strip(), "source": "lspci"}
                    )

        # Get general GPU information from /proc/driver/nvidia/gpus if available
        try:
            import os

            if os.path.exists("/proc/driver/nvidia/gpus"):
                gpu_dirs = os.listdir("/proc/driver/nvidia/gpus")
                gpu_info["nvidia_proc_gpus"] = len(gpu_dirs)
        except (FileNotFoundError, OSError, PermissionError):
            pass

        return gpu_info

    except Exception as e:
        return {
            "gpus": [],
            "nvidia_available": False,
            "amd_available": False,
            "intel_available": False,
            "error": str(e),
        }
