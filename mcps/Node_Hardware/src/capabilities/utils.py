"""
Utility functions for hardware capabilities.
"""

import platform
import subprocess
import shutil


def check_command_available(command: str) -> bool:
    """
    Check if a command is available on the system.

    Args:
        command: Command to check

    Returns:
        True if command is available, False otherwise
    """
    return shutil.which(command) is not None


def run_command(command: list, timeout: int = 30) -> dict:
    """
    Run a system command and return the result.

    Args:
        command: Command to run as a list
        timeout: Command timeout in seconds

    Returns:
        Dictionary with command results
    """
    try:
        result = subprocess.run(
            command, capture_output=True, text=True, timeout=timeout
        )
        return {
            "success": result.returncode == 0,
            "stdout": result.stdout,
            "stderr": result.stderr,
            "returncode": result.returncode,
        }
    except subprocess.TimeoutExpired:
        return {
            "success": False,
            "stdout": "",
            "stderr": "Command timed out",
            "returncode": -1,
        }
    except Exception as e:
        return {"success": False, "stdout": "", "stderr": str(e), "returncode": -1}


def get_os_info() -> dict:
    """
    Get basic OS information.

    Returns:
        Dictionary with OS information
    """
    return {
        "system": platform.system(),
        "release": platform.release(),
        "version": platform.version(),
        "machine": platform.machine(),
        "processor": platform.processor(),
        "architecture": platform.architecture()[0],
        "platform": platform.platform(),
    }


def format_bytes(bytes_value: int) -> str:
    """
    Format bytes into human-readable string.

    Args:
        bytes_value: Size in bytes

    Returns:
        Formatted string (e.g., "1.5 GB")
    """
    if bytes_value == 0:
        return "0 B"

    units = ["B", "KB", "MB", "GB", "TB", "PB"]
    unit_index = 0
    size = float(bytes_value)

    while size >= 1024 and unit_index < len(units) - 1:
        size /= 1024
        unit_index += 1

    return f"{size:.2f} {units[unit_index]}"


def format_percentage(value: float) -> str:
    """
    Format percentage value.

    Args:
        value: Percentage value

    Returns:
        Formatted percentage string
    """
    return f"{value:.1f}%"
