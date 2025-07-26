"""
Memory information capabilities.
Handles memory reporting and detailed memory information.
"""

import psutil
from capabilities.utils import format_bytes, format_percentage


def get_memory_info() -> dict:
    """
    Get comprehensive memory information.

    Returns:
        Dictionary with memory information
    """
    try:
        # Virtual memory information
        virtual_memory = psutil.virtual_memory()

        # Swap memory information
        swap_memory = psutil.swap_memory()

        result = {
            "virtual_memory": {
                "total": virtual_memory.total,
                "available": virtual_memory.available,
                "used": virtual_memory.used,
                "free": virtual_memory.free,
                "percent": virtual_memory.percent,
                "total_formatted": format_bytes(virtual_memory.total),
                "available_formatted": format_bytes(virtual_memory.available),
                "used_formatted": format_bytes(virtual_memory.used),
                "free_formatted": format_bytes(virtual_memory.free),
                "percent_formatted": format_percentage(virtual_memory.percent),
            },
            "swap_memory": {
                "total": swap_memory.total,
                "used": swap_memory.used,
                "free": swap_memory.free,
                "percent": swap_memory.percent,
                "total_formatted": format_bytes(swap_memory.total),
                "used_formatted": format_bytes(swap_memory.used),
                "free_formatted": format_bytes(swap_memory.free),
                "percent_formatted": format_percentage(swap_memory.percent),
            },
        }

        # Add additional memory info if available
        if hasattr(virtual_memory, "buffers"):
            result["virtual_memory"]["buffers"] = virtual_memory.buffers
            result["virtual_memory"]["buffers_formatted"] = format_bytes(
                virtual_memory.buffers
            )

        if hasattr(virtual_memory, "cached"):
            result["virtual_memory"]["cached"] = virtual_memory.cached
            result["virtual_memory"]["cached_formatted"] = format_bytes(
                virtual_memory.cached
            )

        if hasattr(virtual_memory, "shared"):
            result["virtual_memory"]["shared"] = virtual_memory.shared
            result["virtual_memory"]["shared_formatted"] = format_bytes(
                virtual_memory.shared
            )

        return result

    except Exception as e:
        return {"virtual_memory": {}, "swap_memory": {}, "error": str(e)}
