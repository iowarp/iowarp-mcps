"""
Performance monitoring capabilities.
Handles real-time performance monitoring and metrics.
"""

import psutil
import time
from typing import Dict, Any
from capabilities.utils import format_bytes, format_percentage


def monitor_performance(duration: int = 5) -> Dict[str, Any]:
    """
    Monitor system performance for a specified duration.

    Args:
        duration: Duration in seconds to monitor

    Returns:
        Dictionary with performance metrics
    """
    try:
        # Initial readings
        start_time = time.time()
        psutil.cpu_percent(interval=None)
        psutil.virtual_memory()
        initial_disk_io = psutil.disk_io_counters()
        initial_net_io = psutil.net_io_counters()

        # Wait for the specified duration
        time.sleep(duration)

        # Final readings
        end_time = time.time()
        psutil.cpu_percent(interval=None)
        final_memory = psutil.virtual_memory()
        final_disk_io = psutil.disk_io_counters()
        final_net_io = psutil.net_io_counters()

        # Calculate differences
        actual_duration = end_time - start_time

        # CPU usage per core during monitoring
        cpu_usage = psutil.cpu_percent(interval=1, percpu=True)

        # Disk I/O rates
        disk_read_rate = 0.0
        disk_write_rate = 0.0
        if initial_disk_io and final_disk_io:
            disk_read_rate = (
                final_disk_io.read_bytes - initial_disk_io.read_bytes
            ) / actual_duration
            disk_write_rate = (
                final_disk_io.write_bytes - initial_disk_io.write_bytes
            ) / actual_duration

        # Network I/O rates
        net_recv_rate = 0.0
        net_sent_rate = 0.0
        if initial_net_io and final_net_io:
            net_recv_rate = (
                final_net_io.bytes_recv - initial_net_io.bytes_recv
            ) / actual_duration
            net_sent_rate = (
                final_net_io.bytes_sent - initial_net_io.bytes_sent
            ) / actual_duration

        # Load average (Unix systems)
        load_avg = {}
        try:
            if hasattr(psutil, "getloadavg"):
                load_avg = {
                    "1min": psutil.getloadavg()[0],
                    "5min": psutil.getloadavg()[1],
                    "15min": psutil.getloadavg()[2],
                }
        except Exception:
            pass

        result = {
            "monitoring_duration": {"requested": duration, "actual": actual_duration},
            "cpu": {
                "average_usage": sum(cpu_usage) / len(cpu_usage) if cpu_usage else 0,
                "usage_per_core": cpu_usage,
                "average_usage_formatted": format_percentage(
                    sum(cpu_usage) / len(cpu_usage) if cpu_usage else 0
                ),
                "load_average": load_avg,
            },
            "memory": {
                "current_usage": final_memory.percent,
                "current_usage_formatted": format_percentage(final_memory.percent),
                "current_available": final_memory.available,
                "current_available_formatted": format_bytes(final_memory.available),
                "current_used": final_memory.used,
                "current_used_formatted": format_bytes(final_memory.used),
            },
            "disk_io": {
                "read_rate": disk_read_rate,
                "write_rate": disk_write_rate,
                "read_rate_formatted": format_bytes(disk_read_rate) + "/s",
                "write_rate_formatted": format_bytes(disk_write_rate) + "/s",
            },
            "network_io": {
                "recv_rate": net_recv_rate,
                "sent_rate": net_sent_rate,
                "recv_rate_formatted": format_bytes(net_recv_rate) + "/s",
                "sent_rate_formatted": format_bytes(net_sent_rate) + "/s",
            },
            "timestamp": {
                "start": start_time,
                "end": end_time,
                "start_formatted": time.strftime(
                    "%Y-%m-%d %H:%M:%S", time.localtime(start_time)
                ),
                "end_formatted": time.strftime(
                    "%Y-%m-%d %H:%M:%S", time.localtime(end_time)
                ),
            },
        }

        return result

    except Exception as e:
        return {
            "monitoring_duration": {"requested": duration, "actual": 0},
            "error": str(e),
        }
