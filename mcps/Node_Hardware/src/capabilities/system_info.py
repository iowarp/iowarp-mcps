"""
System information capabilities.
Handles general system information reporting.
"""

import psutil
import platform
import datetime
from capabilities.utils import get_os_info


def get_system_info() -> dict:
    """
    Get comprehensive system information.

    Returns:
        Dictionary with system information
    """
    try:
        # Get OS information
        os_info = get_os_info()

        # Get boot time
        boot_time = psutil.boot_time()
        boot_time_formatted = datetime.datetime.fromtimestamp(boot_time).strftime(
            "%Y-%m-%d %H:%M:%S"
        )

        # Calculate uptime
        uptime_seconds = datetime.datetime.now().timestamp() - boot_time
        uptime_days = int(uptime_seconds // 86400)
        uptime_hours = int((uptime_seconds % 86400) // 3600)
        uptime_minutes = int((uptime_seconds % 3600) // 60)

        # Get users
        users = psutil.users()
        user_info = []
        for user in users:
            user_info.append(
                {
                    "name": user.name,
                    "terminal": user.terminal,
                    "host": user.host,
                    "started": datetime.datetime.fromtimestamp(user.started).strftime(
                        "%Y-%m-%d %H:%M:%S"
                    ),
                }
            )

        # Get Python information
        python_info = {
            "version": platform.python_version(),
            "implementation": platform.python_implementation(),
            "compiler": platform.python_compiler(),
        }

        result = {
            "os_info": os_info,
            "boot_time": boot_time,
            "boot_time_formatted": boot_time_formatted,
            "uptime": {
                "seconds": uptime_seconds,
                "days": uptime_days,
                "hours": uptime_hours,
                "minutes": uptime_minutes,
                "formatted": f"{uptime_days} days, {uptime_hours} hours, {uptime_minutes} minutes",
            },
            "users": user_info,
            "total_users": len(user_info),
            "python_info": python_info,
            "hostname": platform.node(),
            "current_time": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        }

        return result

    except Exception as e:
        return {"os_info": get_os_info(), "error": str(e)}
