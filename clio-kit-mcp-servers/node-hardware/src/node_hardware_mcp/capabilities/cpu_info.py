"""
CPU information capabilities.
Handles CPU core reporting and detailed CPU information.
"""

import os
import psutil
import platform


def get_cpu_info() -> dict:
    """
    Get comprehensive CPU information.

    Returns:
        Dictionary with CPU information
    """
    try:
        # Basic CPU info using psutil
        logical_cores = psutil.cpu_count(logical=True)
        physical_cores = psutil.cpu_count(logical=False)

        # Fallback to os.cpu_count() if psutil returns None
        if logical_cores is None:
            logical_cores = os.cpu_count()

        # Get CPU frequency
        cpu_freq = psutil.cpu_freq()
        freq_info = {}
        if cpu_freq:
            freq_info = {
                "current": cpu_freq.current,
                "min": cpu_freq.min,
                "max": cpu_freq.max,
            }

        # Get CPU usage per core
        cpu_usage = psutil.cpu_percent(interval=1, percpu=True)

        # Get CPU times
        cpu_times = psutil.cpu_times()

        # Try to get additional CPU info from /proc/cpuinfo on Linux
        cpu_model = platform.processor()
        cpu_vendor = ""
        cpu_flags = []

        if platform.system() == "Linux" and os.path.exists("/proc/cpuinfo"):
            try:
                with open("/proc/cpuinfo", "r") as f:
                    content = f.read()

                # Extract CPU model
                for line in content.split("\n"):
                    if "model name" in line:
                        cpu_model = line.split(":")[1].strip()
                        break
                    elif "vendor_id" in line:
                        cpu_vendor = line.split(":")[1].strip()
                    elif "flags" in line:
                        cpu_flags = line.split(":")[1].strip().split()
            except (FileNotFoundError, IOError, OSError):
                pass

        # Get load average on Unix systems
        load_avg = {}
        try:
            if hasattr(os, "getloadavg"):
                load_avg = {
                    "1min": os.getloadavg()[0],
                    "5min": os.getloadavg()[1],
                    "15min": os.getloadavg()[2],
                }
        except (OSError, AttributeError):
            pass

        result = {
            "logical_cores": logical_cores,
            "physical_cores": physical_cores,
            "cpu_model": cpu_model,
            "cpu_vendor": cpu_vendor,
            "architecture": platform.machine(),
            "frequency": freq_info,
            "usage_per_core": cpu_usage,
            "average_usage": sum(cpu_usage) / len(cpu_usage) if cpu_usage else 0,
            "cpu_times": {
                "user": cpu_times.user,
                "system": cpu_times.system,
                "idle": cpu_times.idle,
            },
            "load_average": load_avg,
            "cpu_flags": cpu_flags[:20] if cpu_flags else [],  # First 20 flags
            "system": platform.system(),
        }

        return result

    except Exception as e:
        return {
            "logical_cores": os.cpu_count(),
            "physical_cores": None,
            "error": str(e),
            "system": platform.system(),
        }
