"""
Disk information capabilities.
Handles disk usage reporting and detailed disk information.
"""
import psutil
from capabilities.utils import format_bytes, format_percentage


def get_disk_info() -> dict:
    """
    Get comprehensive disk information.
    
    Returns:
        Dictionary with disk information
    """
    try:
        # Get disk partitions
        partitions = psutil.disk_partitions()
        
        disk_info = []
        total_size = 0
        total_used = 0
        total_free = 0
        
        for partition in partitions:
            try:
                partition_usage = psutil.disk_usage(partition.mountpoint)
                
                partition_info = {
                    "device": partition.device,
                    "mountpoint": partition.mountpoint,
                    "filesystem": partition.fstype,
                    "total": partition_usage.total,
                    "used": partition_usage.used,
                    "free": partition_usage.free,
                    "percent": (partition_usage.used / partition_usage.total) * 100 if partition_usage.total > 0 else 0,
                    "total_formatted": format_bytes(partition_usage.total),
                    "used_formatted": format_bytes(partition_usage.used),
                    "free_formatted": format_bytes(partition_usage.free),
                    "percent_formatted": format_percentage((partition_usage.used / partition_usage.total) * 100 if partition_usage.total > 0 else 0)
                }
                
                disk_info.append(partition_info)
                
                # Add to totals (only for physical drives, not virtual ones)
                if not partition.device.startswith(('/dev/loop', '/dev/ram', '/snap')):
                    total_size += partition_usage.total
                    total_used += partition_usage.used
                    total_free += partition_usage.free
                    
            except PermissionError:
                # This can happen on Windows or with certain mount points
                partition_info = {
                    "device": partition.device,
                    "mountpoint": partition.mountpoint,
                    "filesystem": partition.fstype,
                    "error": "Permission denied"
                }
                disk_info.append(partition_info)
        
        # Get disk I/O statistics
        disk_io = psutil.disk_io_counters()
        io_info = {}
        if disk_io:
            io_info = {
                "read_count": disk_io.read_count,
                "write_count": disk_io.write_count,
                "read_bytes": disk_io.read_bytes,
                "write_bytes": disk_io.write_bytes,
                "read_time": disk_io.read_time,
                "write_time": disk_io.write_time,
                "read_bytes_formatted": format_bytes(disk_io.read_bytes),
                "write_bytes_formatted": format_bytes(disk_io.write_bytes)
            }
        
        result = {
            "partitions": disk_info,
            "total_partitions": len(disk_info),
            "summary": {
                "total_size": total_size,
                "total_used": total_used,
                "total_free": total_free,
                "total_percent": (total_used / total_size) * 100 if total_size > 0 else 0,
                "total_size_formatted": format_bytes(total_size),
                "total_used_formatted": format_bytes(total_used),
                "total_free_formatted": format_bytes(total_free),
                "total_percent_formatted": format_percentage((total_used / total_size) * 100 if total_size > 0 else 0)
            },
            "io_statistics": io_info
        }
        
        return result
        
    except Exception as e:
        return {
            "partitions": [],
            "total_partitions": 0,
            "summary": {},
            "io_statistics": {},
            "error": str(e)
        }
