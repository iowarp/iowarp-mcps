"""
MCP handlers for Node Hardware monitoring.
These handlers wrap the hardware capabilities for MCP protocol compliance.
"""

from typing import Optional, List
from utils.output_formatter import create_beautiful_response
from capabilities.cpu_info import get_cpu_info
from capabilities.memory_info import get_memory_info
from capabilities.disk_info import get_disk_info
from capabilities.network_info import get_network_info
from capabilities.system_info import get_system_info
from capabilities.process_info import get_process_info
from capabilities.hardware_summary import get_hardware_summary
from capabilities.performance_monitor import monitor_performance
from capabilities.gpu_info import get_gpu_info
from capabilities.sensor_info import get_sensor_info
from capabilities.remote_node_info import get_node_info, get_remote_node_info


def cpu_info_handler() -> dict:
    """
    Handler wrapping the CPU info capability for MCP.
    Returns CPU information with beautiful formatting.

    Returns:
        MCP-compliant response dictionary
    """
    try:
        result = get_cpu_info()

        # Generate summary
        summary = {
            "logical_cores": result.get("logical_cores", 0),
            "physical_cores": result.get("physical_cores", 0),
            "cpu_model": result.get("cpu_model", "Unknown"),
            "current_freq": result.get("frequency", {}).get("current", 0),
        }

        # Generate insights
        insights = []
        if result.get("logical_cores", 0) > 0:
            insights.append(f"System has {result.get('logical_cores')} logical cores")
        if result.get("physical_cores", 0) > 0:
            insights.append(f"System has {result.get('physical_cores')} physical cores")
        if result.get("cpu_usage"):
            avg_usage = sum(result["cpu_usage"]) / len(result["cpu_usage"])
            if avg_usage > 80:
                insights.append(
                    "High CPU usage detected - consider checking running processes"
                )
            elif avg_usage < 20:
                insights.append("Low CPU usage - system is running efficiently")

        return create_beautiful_response(
            operation="cpu_info",
            success=True,
            data=result,
            summary=summary,
            insights=insights,
        )

    except Exception as e:
        return create_beautiful_response(
            operation="cpu_info",
            success=False,
            error_message=str(e),
            error_type=type(e).__name__,
            suggestions=[
                "Check if the system supports CPU information retrieval",
                "Verify system permissions for hardware access",
                "Try running the tool as administrator/root if necessary",
            ],
        )


def memory_info_handler() -> dict:
    """
    Handler wrapping the memory info capability for MCP.
    Returns memory information with beautiful formatting.

    Returns:
        MCP-compliant response dictionary
    """
    try:
        result = get_memory_info()

        # Generate summary
        summary = {
            "total_memory": result.get("total", 0),
            "available_memory": result.get("available", 0),
            "used_memory": result.get("used", 0),
            "memory_percent": result.get("percent", 0),
        }

        # Generate insights
        insights = []
        if result.get("percent", 0) > 85:
            insights.append(
                "High memory usage detected - consider closing applications or adding more RAM"
            )
        elif result.get("percent", 0) < 50:
            insights.append(
                "Good memory utilization - system has sufficient available memory"
            )

        if result.get("swap_total", 0) > 0 and result.get("swap_used", 0) > 0:
            swap_percent = (
                result.get("swap_used", 0) / result.get("swap_total", 1)
            ) * 100
            if swap_percent > 50:
                insights.append(
                    "High swap usage detected - consider adding more physical memory"
                )

        return create_beautiful_response(
            operation="memory_info",
            success=True,
            data=result,
            summary=summary,
            insights=insights,
        )

    except Exception as e:
        return create_beautiful_response(
            operation="memory_info",
            success=False,
            error_message=str(e),
            error_type=type(e).__name__,
            suggestions=[
                "Check if the system supports memory information retrieval",
                "Verify system permissions for hardware access",
                "Ensure psutil library is properly installed",
            ],
        )


def disk_info_handler() -> dict:
    """
    Handler wrapping the disk info capability for MCP.
    Returns disk information with beautiful formatting.

    Returns:
        MCP-compliant response dictionary
    """
    try:
        result = get_disk_info()

        # Generate summary
        summary = {
            "total_partitions": len(result.get("partitions", [])),
            "total_devices": len(result.get("disk_io", {})),
        }

        # Generate insights
        insights = []
        for partition in result.get("partitions", []):
            usage = partition.get("usage", {})
            if usage.get("percent", 0) > 85:
                insights.append(
                    f"High disk usage on {partition.get('mountpoint', 'unknown')} - consider cleanup"
                )
            elif usage.get("percent", 0) < 20:
                insights.append(
                    f"Good disk space on {partition.get('mountpoint', 'unknown')}"
                )

        return create_beautiful_response(
            operation="disk_info",
            success=True,
            data=result,
            summary=summary,
            insights=insights,
        )

    except Exception as e:
        return create_beautiful_response(
            operation="disk_info",
            success=False,
            error_message=str(e),
            error_type=type(e).__name__,
            suggestions=[
                "Check if the system supports disk information retrieval",
                "Verify system permissions for disk access",
                "Ensure all mounted filesystems are accessible",
            ],
        )


def network_info_handler() -> dict:
    """
    Handler wrapping the network info capability for MCP.
    Returns network information with beautiful formatting.

    Returns:
        MCP-compliant response dictionary
    """
    try:
        result = get_network_info()

        # Generate summary
        summary = {
            "total_interfaces": len(result.get("interfaces", [])),
            "active_interfaces": len(
                [
                    i
                    for i in result.get("interfaces", [])
                    if i.get("statistics", {}).get("is_up", False)
                ]
            ),
        }

        # Generate insights
        insights = []
        active_interfaces = [
            i
            for i in result.get("interfaces", [])
            if i.get("statistics", {}).get("is_up", False)
        ]
        if active_interfaces:
            insights.append(f"Found {len(active_interfaces)} active network interfaces")

        for interface in result.get("interfaces", []):
            if interface.get("statistics", {}).get("is_up", False):
                insights.append(
                    f"Interface {interface.get('name', 'unknown')} is up and running"
                )

        return create_beautiful_response(
            operation="network_info",
            success=True,
            data=result,
            summary=summary,
            insights=insights,
        )

    except Exception as e:
        return create_beautiful_response(
            operation="network_info",
            success=False,
            error_message=str(e),
            error_type=type(e).__name__,
            suggestions=[
                "Check if the system supports network information retrieval",
                "Verify system permissions for network access",
                "Ensure network interfaces are properly configured",
            ],
        )


def system_info_handler() -> dict:
    """
    Handler wrapping the system info capability for MCP.
    Returns system information with beautiful formatting.

    Returns:
        MCP-compliant response dictionary
    """
    try:
        result = get_system_info()

        # Generate summary
        summary = {
            "hostname": result.get("hostname", "unknown"),
            "os_system": result.get("os_info", {}).get("system", "unknown"),
            "uptime_days": result.get("uptime", {}).get("days", 0),
            "total_users": result.get("total_users", 0),
        }

        # Generate insights
        insights = []
        uptime_days = result.get("uptime", {}).get("days", 0)
        if uptime_days > 30:
            insights.append(
                "System has been running for over 30 days - consider reboot for updates"
            )
        elif uptime_days > 7:
            insights.append("System has good uptime stability")

        if result.get("total_users", 0) > 0:
            insights.append(f"System has {result.get('total_users')} active users")

        return create_beautiful_response(
            operation="system_info",
            success=True,
            data=result,
            summary=summary,
            insights=insights,
        )

    except Exception as e:
        return create_beautiful_response(
            operation="system_info",
            success=False,
            error_message=str(e),
            error_type=type(e).__name__,
            suggestions=[
                "Check if the system supports system information retrieval",
                "Verify system permissions for system access",
                "Ensure basic system utilities are available",
            ],
        )


def process_info_handler() -> dict:
    """
    Handler wrapping the process info capability for MCP.
    Returns process information with beautiful formatting.

    Returns:
        MCP-compliant response dictionary
    """
    try:
        result = get_process_info()

        # Generate summary
        summary = {
            "total_processes": len(result.get("processes", [])),
            "running_processes": len(
                [p for p in result.get("processes", []) if p.get("status") == "running"]
            ),
        }

        # Generate insights
        insights = []
        if result.get("processes"):
            insights.append(
                f"System is running {len(result.get('processes', []))} processes"
            )

            # Find high CPU processes
            high_cpu_processes = [
                p for p in result.get("processes", []) if p.get("cpu_percent", 0) > 10
            ]
            if high_cpu_processes:
                insights.append(
                    f"Found {len(high_cpu_processes)} processes with high CPU usage"
                )

        return create_beautiful_response(
            operation="process_info",
            success=True,
            data=result,
            summary=summary,
            insights=insights,
        )

    except Exception as e:
        return create_beautiful_response(
            operation="process_info",
            success=False,
            error_message=str(e),
            error_type=type(e).__name__,
            suggestions=[
                "Check if the system supports process information retrieval",
                "Verify system permissions for process access",
                "Ensure psutil library is properly installed",
            ],
        )


def hardware_summary_handler() -> dict:
    """
    Handler wrapping the hardware summary capability for MCP.
    Returns hardware summary with beautiful formatting.

    Returns:
        MCP-compliant response dictionary
    """
    try:
        result = get_hardware_summary()

        # Generate summary
        summary = {
            "components_gathered": len(
                [k for k in result.keys() if not k.startswith("_")]
            ),
            "hostname": result.get("hostname", "unknown"),
        }

        # Generate insights
        insights = []
        if result.get("cpu_info"):
            insights.append("CPU information successfully collected")
        if result.get("memory_info"):
            insights.append("Memory information successfully collected")
        if result.get("disk_info"):
            insights.append("Disk information successfully collected")
        if result.get("network_info"):
            insights.append("Network information successfully collected")

        return create_beautiful_response(
            operation="hardware_summary",
            success=True,
            data=result,
            summary=summary,
            insights=insights,
        )

    except Exception as e:
        return create_beautiful_response(
            operation="hardware_summary",
            success=False,
            error_message=str(e),
            error_type=type(e).__name__,
            suggestions=[
                "Check if the system supports hardware information retrieval",
                "Verify system permissions for hardware access",
                "Ensure all required libraries are properly installed",
            ],
        )


def performance_monitor_handler() -> dict:
    """
    Handler wrapping the performance monitor capability for MCP.
    Returns performance monitoring with beautiful formatting.

    Returns:
        MCP-compliant response dictionary
    """
    try:
        result = monitor_performance()

        # Generate summary
        summary = {
            "cpu_usage": result.get("cpu_usage", 0),
            "memory_usage": result.get("memory_usage", 0),
            "disk_usage": result.get("disk_usage", 0),
        }

        # Generate insights
        insights = []
        if result.get("cpu_usage", 0) > 80:
            insights.append("High CPU usage detected - system may be under heavy load")
        if result.get("memory_usage", 0) > 85:
            insights.append(
                "High memory usage detected - consider closing applications"
            )
        if result.get("disk_usage", 0) > 90:
            insights.append(
                "High disk usage detected - consider cleanup or storage expansion"
            )

        return create_beautiful_response(
            operation="performance_monitor",
            success=True,
            data=result,
            summary=summary,
            insights=insights,
        )

    except Exception as e:
        return create_beautiful_response(
            operation="performance_monitor",
            success=False,
            error_message=str(e),
            error_type=type(e).__name__,
            suggestions=[
                "Check if the system supports performance monitoring",
                "Verify system permissions for performance access",
                "Ensure monitoring tools are available",
            ],
        )


def gpu_info_handler() -> dict:
    """
    Handler wrapping the GPU info capability for MCP.
    Returns GPU information with beautiful formatting.

    Returns:
        MCP-compliant response dictionary
    """
    try:
        result = get_gpu_info()

        # Generate summary
        summary = {
            "gpu_count": len(result.get("gpus", [])),
            "nvidia_available": result.get("nvidia_available", False),
        }

        # Generate insights
        insights = []
        if result.get("gpus"):
            insights.append(f"Found {len(result.get('gpus', []))} GPU(s)")
        else:
            insights.append("No GPUs detected or GPU information unavailable")

        return create_beautiful_response(
            operation="gpu_info",
            success=True,
            data=result,
            summary=summary,
            insights=insights,
        )

    except Exception as e:
        return create_beautiful_response(
            operation="gpu_info",
            success=False,
            error_message=str(e),
            error_type=type(e).__name__,
            suggestions=[
                "Check if the system has GPU hardware",
                "Verify GPU drivers are properly installed",
                "Ensure nvidia-smi is available for NVIDIA GPUs",
            ],
        )


def sensor_info_handler() -> dict:
    """
    Handler wrapping the sensor info capability for MCP.
    Returns sensor information with beautiful formatting.

    Returns:
        MCP-compliant response dictionary
    """
    try:
        result = get_sensor_info()

        # Generate summary
        summary = {
            "sensor_count": len(result.get("sensors", [])),
            "temperature_sensors": len(
                [
                    s
                    for s in result.get("sensors", [])
                    if "temperature" in s.get("type", "").lower()
                ]
            ),
        }

        # Generate insights
        insights = []
        if result.get("sensors"):
            insights.append(f"Found {len(result.get('sensors', []))} sensors")
        else:
            insights.append("No sensors detected or sensor information unavailable")

        return create_beautiful_response(
            operation="sensor_info",
            success=True,
            data=result,
            summary=summary,
            insights=insights,
        )

    except Exception as e:
        return create_beautiful_response(
            operation="sensor_info",
            success=False,
            error_message=str(e),
            error_type=type(e).__name__,
            suggestions=[
                "Check if the system supports sensor information",
                "Verify system permissions for sensor access",
                "Ensure sensor libraries are properly installed",
            ],
        )


def get_node_info_handler(
    include_filters: Optional[List[str]] = None,
    exclude_filters: Optional[List[str]] = None,
    max_response_size: Optional[int] = None,
) -> dict:
    """
    Handler for comprehensive local node information with filtering and size control.

    Args:
        include_filters: List of components to include
        exclude_filters: List of components to exclude
        max_response_size: Maximum response size in bytes (for token limit control)

    Returns:
        MCP-compliant response dictionary
    """
    try:
        # Validate input parameters
        if include_filters is not None and not isinstance(include_filters, list):
            return create_beautiful_response(
                operation="get_node_info",
                success=False,
                error_message=f"include_filters must be a list, got {type(include_filters).__name__}",
                error_type="InvalidParameterType",
                suggestions=[
                    "Pass components as a list, e.g., ['cpu', 'memory']",
                    "Do not pass components as a string",
                    "Use valid component names: cpu, memory, disk, network, system, processes, gpu, sensors, hardware_summary",
                ],
            )

        if exclude_filters is not None and not isinstance(exclude_filters, list):
            return create_beautiful_response(
                operation="get_node_info",
                success=False,
                error_message=f"exclude_filters must be a list, got {type(exclude_filters).__name__}",
                error_type="InvalidParameterType",
                suggestions=[
                    "Pass exclude_components as a list, e.g., ['processes', 'sensors']",
                    "Do not pass exclude_components as a string",
                    "Use valid component names: cpu, memory, disk, network, system, processes, gpu, sensors, hardware_summary",
                ],
            )

        # Set default max response size if not specified (to prevent token limit issues)
        if max_response_size is None:
            max_response_size = 15000  # Conservative limit to stay under 25k tokens

        result = get_node_info(include_filters, exclude_filters, max_response_size)

        # Check if there was an error in the underlying function
        if "error" in result:
            return create_beautiful_response(
                operation="get_node_info",
                success=False,
                error_message=result["error"],
                error_type=result.get("error_type", "UnknownError"),
                suggestions=[
                    "Check if the system supports the requested components",
                    "Verify system permissions for hardware access",
                    "Try with different component combinations",
                    "Use fewer components to reduce response size",
                ],
            )

        # Generate summary
        metadata = result.get("_metadata", {})
        summary = {
            "hostname": metadata.get("hostname", "unknown"),
            "components_requested": len(metadata.get("components_requested", [])),
            "components_collected": len(metadata.get("components_collected", [])),
            "collection_method": metadata.get("collection_method", "unknown"),
            "errors": len(metadata.get("errors", [])),
            "response_size_controlled": metadata.get("response_size_controlled", False),
        }

        # Generate insights
        insights = []
        if metadata.get("errors"):
            insights.append(
                f"Encountered {len(metadata.get('errors', []))} errors during collection"
            )
        else:
            insights.append("All requested components collected successfully")

        if include_filters:
            insights.append(f"Applied include filters: {', '.join(include_filters)}")
        if exclude_filters:
            insights.append(f"Applied exclude filters: {', '.join(exclude_filters)}")

        if metadata.get("response_size_controlled"):
            insights.append(
                "Response size was controlled to prevent token limit issues"
            )

        # Add helpful suggestions for token limit issues
        suggestions = []
        if len(metadata.get("components_collected", [])) < len(
            metadata.get("components_requested", [])
        ):
            suggestions.append(
                "Some components were excluded due to response size limits"
            )
            suggestions.append(
                "Try requesting fewer components or use specific component filters"
            )

        return create_beautiful_response(
            operation="get_node_info",
            success=True,
            data=result,
            summary=summary,
            insights=insights,
            metadata={
                "filters_applied": bool(include_filters or exclude_filters),
                "total_components": len(metadata.get("components_requested", [])),
                "max_response_size": max_response_size,
                "valid_components": [
                    "cpu",
                    "memory",
                    "disk",
                    "network",
                    "system",
                    "processes",
                    "gpu",
                    "sensors",
                    "hardware_summary",
                ],
            },
        )

    except Exception as e:
        return create_beautiful_response(
            operation="get_node_info",
            success=False,
            error_message=str(e),
            error_type=type(e).__name__,
            suggestions=[
                "Check if the system supports node information retrieval",
                "Verify system permissions for hardware access",
                "Ensure all required libraries are properly installed",
                "Try with different filter combinations",
                "Use specific component filters to reduce response size",
            ],
        )


def get_remote_node_info_handler(
    hostname: str,
    username: Optional[str] = None,
    port: int = 22,
    ssh_key: Optional[str] = None,
    timeout: int = 30,
    include_filters: Optional[List[str]] = None,
    exclude_filters: Optional[List[str]] = None,
) -> dict:
    """
    Handler for remote node information retrieval via SSH.

    Args:
        hostname: Target hostname or IP address
        username: SSH username
        port: SSH port
        ssh_key: Path to SSH private key file
        timeout: SSH timeout in seconds
        include_filters: List of components to include
        exclude_filters: List of components to exclude

    Returns:
        MCP-compliant response dictionary
    """
    try:
        result = get_remote_node_info(
            hostname=hostname,
            username=username,
            port=port,
            ssh_key=ssh_key,
            timeout=timeout,
            include_filters=include_filters,
            exclude_filters=exclude_filters,
        )

        if result.get("error"):
            return create_beautiful_response(
                operation="get_remote_node_info",
                success=False,
                error_message=result.get("error", "Unknown error"),
                error_type=result.get("error_type", "UnknownError"),
                hostname=hostname,
                suggestions=[
                    "Check if the hostname is reachable",
                    "Verify SSH credentials and permissions",
                    "Ensure SSH service is running on target host",
                    "Try with different SSH parameters",
                    "Check firewall and network connectivity",
                ],
            )

        # Generate summary
        metadata = result.get("_metadata", {})
        summary = {
            "hostname": metadata.get("hostname", hostname),
            "ssh_hostname": metadata.get("ssh_hostname", hostname),
            "ssh_username": metadata.get("ssh_username", username),
            "collection_method": metadata.get("collection_method", "unknown"),
            "ssh_timeout": metadata.get("ssh_timeout", timeout),
        }

        # Generate insights
        insights = []
        insights.append(f"Successfully connected to {hostname} via SSH")
        if metadata.get("ssh_key_used"):
            insights.append("SSH key authentication used")
        else:
            insights.append("Password authentication used")

        if include_filters:
            insights.append(f"Applied include filters: {', '.join(include_filters)}")
        if exclude_filters:
            insights.append(f"Applied exclude filters: {', '.join(exclude_filters)}")

        return create_beautiful_response(
            operation="get_remote_node_info",
            success=True,
            data=result,
            summary=summary,
            insights=insights,
            hostname=hostname,
            metadata={
                "ssh_connection": True,
                "filters_applied": bool(include_filters or exclude_filters),
                "ssh_parameters": {
                    "hostname": hostname,
                    "username": username,
                    "port": port,
                    "timeout": timeout,
                },
            },
        )

    except Exception as e:
        return create_beautiful_response(
            operation="get_remote_node_info",
            success=False,
            error_message=str(e),
            error_type=type(e).__name__,
            hostname=hostname,
            suggestions=[
                "Check if the hostname is reachable",
                "Verify SSH credentials and permissions",
                "Ensure SSH service is running on target host",
                "Try with different SSH parameters",
                "Check firewall and network connectivity",
            ],
        )
