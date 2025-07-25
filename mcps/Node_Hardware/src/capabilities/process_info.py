"""
Process information capabilities.
Handles process monitoring and detailed process information.
"""
import psutil
from capabilities.utils import format_bytes, format_percentage


def get_process_info(limit: int = 10) -> dict:
    """
    Get process information.
    
    Args:
        limit: Maximum number of processes to return
        
    Returns:
        Dictionary with process information
    """
    try:
        # Get all processes
        processes = []
        for proc in psutil.process_iter(['pid', 'name', 'cpu_percent', 'memory_percent', 'memory_info', 'status', 'create_time', 'username']):
            try:
                process_info = proc.info
                # Convert memory info to more readable format
                if process_info['memory_info']:
                    process_info['memory_rss_formatted'] = format_bytes(process_info['memory_info'].rss)
                    process_info['memory_vms_formatted'] = format_bytes(process_info['memory_info'].vms)
                
                process_info['cpu_percent_formatted'] = format_percentage(process_info['cpu_percent'] or 0)
                process_info['memory_percent_formatted'] = format_percentage(process_info['memory_percent'] or 0)
                
                processes.append(process_info)
            except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                # Process terminated or access denied
                pass
        
        # Sort by CPU usage (descending)
        processes.sort(key=lambda x: x['cpu_percent'] or 0, reverse=True)
        
        # Get top processes
        top_processes = processes[:limit]
        
        # Get process statistics
        total_processes = len(processes)
        running_processes = len([p for p in processes if p['status'] == 'running'])
        sleeping_processes = len([p for p in processes if p['status'] == 'sleeping'])
        stopped_processes = len([p for p in processes if p['status'] == 'stopped'])
        zombie_processes = len([p for p in processes if p['status'] == 'zombie'])
        
        # Calculate total CPU and memory usage
        total_cpu = sum(p['cpu_percent'] or 0 for p in processes)
        total_memory = sum(p['memory_percent'] or 0 for p in processes)
        
        result = {
            "processes": top_processes,
            "total_processes": total_processes,
            "statistics": {
                "running": running_processes,
                "sleeping": sleeping_processes,
                "stopped": stopped_processes,
                "zombie": zombie_processes,
                "total_cpu_percent": total_cpu,
                "total_memory_percent": total_memory,
                "total_cpu_percent_formatted": format_percentage(total_cpu),
                "total_memory_percent_formatted": format_percentage(total_memory)
            },
            "limit": limit
        }
        
        return result
        
    except Exception as e:
        return {
            "processes": [],
            "total_processes": 0,
            "statistics": {},
            "limit": limit,
            "error": str(e)
        }
