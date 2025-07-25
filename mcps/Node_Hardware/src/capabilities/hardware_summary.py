"""
Hardware summary capabilities.
Provides comprehensive hardware summary combining all hardware information.
"""

from capabilities.cpu_info import get_cpu_info
from capabilities.memory_info import get_memory_info
from capabilities.disk_info import get_disk_info
from capabilities.network_info import get_network_info
from capabilities.system_info import get_system_info


def get_hardware_summary() -> dict:
    """
    Get comprehensive hardware summary.

    Returns:
        Dictionary with complete hardware summary
    """
    try:
        # Get all hardware information
        cpu_info = get_cpu_info()
        memory_info = get_memory_info()
        disk_info = get_disk_info()
        network_info = get_network_info()
        system_info = get_system_info()

        # Create summary
        summary = {
            "cpu": {
                "logical_cores": cpu_info.get("logical_cores"),
                "physical_cores": cpu_info.get("physical_cores"),
                "model": cpu_info.get("cpu_model"),
                "average_usage": cpu_info.get("average_usage"),
                "architecture": cpu_info.get("architecture"),
            },
            "memory": {
                "total": memory_info.get("virtual_memory", {}).get("total_formatted"),
                "available": memory_info.get("virtual_memory", {}).get(
                    "available_formatted"
                ),
                "used": memory_info.get("virtual_memory", {}).get("used_formatted"),
                "percent": memory_info.get("virtual_memory", {}).get(
                    "percent_formatted"
                ),
            },
            "disk": {
                "total_partitions": disk_info.get("total_partitions"),
                "total_size": disk_info.get("summary", {}).get("total_size_formatted"),
                "total_used": disk_info.get("summary", {}).get("total_used_formatted"),
                "total_free": disk_info.get("summary", {}).get("total_free_formatted"),
                "total_percent": disk_info.get("summary", {}).get(
                    "total_percent_formatted"
                ),
            },
            "network": {
                "total_interfaces": network_info.get("total_interfaces"),
                "bytes_sent": network_info.get("io_statistics", {}).get(
                    "bytes_sent_formatted"
                ),
                "bytes_recv": network_info.get("io_statistics", {}).get(
                    "bytes_recv_formatted"
                ),
                "total_connections": network_info.get("connections", {}).get(
                    "total_connections"
                ),
            },
            "system": {
                "os": system_info.get("os_info", {}).get("system"),
                "platform": system_info.get("os_info", {}).get("platform"),
                "hostname": system_info.get("hostname"),
                "uptime": system_info.get("uptime", {}).get("formatted"),
                "total_users": system_info.get("total_users"),
            },
        }

        result = {
            "summary": summary,
            "detailed": {
                "cpu": cpu_info,
                "memory": memory_info,
                "disk": disk_info,
                "network": network_info,
                "system": system_info,
            },
        }

        return result

    except Exception as e:
        return {"summary": {}, "detailed": {}, "error": str(e)}
