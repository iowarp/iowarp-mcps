"""
Sensor information capabili                        temp_info = {
                            "label": sensor.label or "Unknown",
                            "current": sensor.current,
                            "high": sensor.high,
                            "critical": sensor.critical,
                            "current_formatted": f"{sensor.current:.1f}C"
                        }
                        if sensor.high:
                            temp_info["high_formatted"] = f"{sensor.high:.1f}C"
                        if sensor.critical:
                            temp_info["critical_formatted"] = f"{sensor.critical:.1f}C"es temperature and other sensor information.
"""
import psutil
from capabilities.utils import run_command, check_command_available


def get_sensor_info() -> dict:
    """
    Get sensor information including temperatures.
    
    Returns:
        Dictionary with sensor information
    """
    try:
        sensor_info = {
            "temperatures": {},
            "fans": {},
            "battery": {},
            "sensors_available": False
        }
        
        # Try to get temperature information using psutil
        try:
            temps = psutil.sensors_temperatures()
            if temps:
                sensor_info["sensors_available"] = True
                for sensor_name, sensor_list in temps.items():
                    sensor_info["temperatures"][sensor_name] = []
                    for sensor in sensor_list:
                        temp_info = {
                            "label": sensor.label or "Unknown",
                            "current": sensor.current,
                            "high": sensor.high,
                            "critical": sensor.critical,
                            "current_formatted": f"{sensor.current:.1f}C"
                        }
                        if sensor.high:
                            temp_info["high_formatted"] = f"{sensor.high:.1f}C"
                        if sensor.critical:
                            temp_info["critical_formatted"] = f"{sensor.critical:.1f}C"
                        
                        sensor_info["temperatures"][sensor_name].append(temp_info)
        except:
            pass
        
        # Try to get fan information using psutil
        try:
            fans = psutil.sensors_fans()
            if fans:
                sensor_info["sensors_available"] = True
                for fan_name, fan_list in fans.items():
                    sensor_info["fans"][fan_name] = []
                    for fan in fan_list:
                        fan_info = {
                            "label": fan.label or "Unknown",
                            "current": fan.current,
                            "current_formatted": f"{fan.current} RPM"
                        }
                        sensor_info["fans"][fan_name].append(fan_info)
        except:
            pass
        
        # Try to get battery information using psutil
        try:
            battery = psutil.sensors_battery()
            if battery:
                sensor_info["battery"] = {
                    "percent": battery.percent,
                    "power_plugged": battery.power_plugged,
                    "seconds_left": battery.secsleft,
                    "percent_formatted": f"{battery.percent:.1f}%"
                }
                
                if battery.secsleft != psutil.POWER_TIME_UNLIMITED and battery.secsleft != psutil.POWER_TIME_UNKNOWN:
                    hours, remainder = divmod(battery.secsleft, 3600)
                    minutes, _ = divmod(remainder, 60)
                    sensor_info["battery"]["time_left_formatted"] = f"{hours:02d}:{minutes:02d}"
        except:
            pass
        
        # Try to get sensor information using lm-sensors (Linux)
        if check_command_available("sensors"):
            sensors_result = run_command(["sensors", "-A"])
            
            if sensors_result["success"]:
                sensor_info["sensors_available"] = True
                sensor_info["lm_sensors_output"] = sensors_result["stdout"]
        
        # Try to get temperature from /sys/class/thermal (Linux)
        try:
            import os
            import glob
            
            thermal_zones = glob.glob("/sys/class/thermal/thermal_zone*/temp")
            if thermal_zones:
                sensor_info["thermal_zones"] = []
                for zone_file in thermal_zones:
                    try:
                        with open(zone_file, 'r') as f:
                            temp_millic = int(f.read().strip())
                            temp_celsius = temp_millic / 1000.0
                            
                        zone_name = zone_file.split('/')[-2]
                        sensor_info["thermal_zones"].append({
                            "zone": zone_name,
                            "temperature": temp_celsius,
                            "temperature_formatted": f"{temp_celsius:.1f}C"
                        })
                    except:
                        pass
        except:
            pass
        
        return sensor_info
        
    except Exception as e:
        return {
            "temperatures": {},
            "fans": {},
            "battery": {},
            "sensors_available": False,
            "error": str(e)
        }
