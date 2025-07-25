"""
Network information capabilities.
Handles network interface reporting and detailed network information.
"""

import psutil
from typing import Dict, List, Any
from capabilities.utils import format_bytes


def get_network_info() -> Dict[str, Any]:
    """
    Get comprehensive network information.

    Returns:
        Dictionary with network information
    """
    try:
        # Get network interfaces
        network_interfaces = psutil.net_if_addrs()
        network_stats = psutil.net_if_stats()

        interfaces: List[Dict[str, Any]] = []
        for interface_name, addresses in network_interfaces.items():
            interface_info: Dict[str, Any] = {"name": interface_name, "addresses": []}

            # Get interface statistics
            if interface_name in network_stats:
                stats = network_stats[interface_name]
                interface_info["statistics"] = {
                    "is_up": stats.isup,
                    "duplex": stats.duplex,
                    "speed": stats.speed,
                    "mtu": stats.mtu,
                }

            # Get addresses
            for addr in addresses:
                addr_info = {
                    "family": addr.family.name
                    if hasattr(addr.family, "name")
                    else str(addr.family),
                    "address": addr.address,
                    "netmask": addr.netmask,
                    "broadcast": addr.broadcast,
                    "ptp": addr.ptp,
                }
                interface_info["addresses"].append(addr_info)

            interfaces.append(interface_info)

        # Get network I/O statistics
        net_io = psutil.net_io_counters()
        io_info = {}
        if net_io:
            io_info = {
                "bytes_sent": net_io.bytes_sent,
                "bytes_recv": net_io.bytes_recv,
                "packets_sent": net_io.packets_sent,
                "packets_recv": net_io.packets_recv,
                "errin": net_io.errin,
                "errout": net_io.errout,
                "dropin": net_io.dropin,
                "dropout": net_io.dropout,
                "bytes_sent_formatted": format_bytes(net_io.bytes_sent),
                "bytes_recv_formatted": format_bytes(net_io.bytes_recv),
            }

        # Get per-interface I/O statistics
        per_interface_io = psutil.net_io_counters(pernic=True)
        interface_io = {}
        for interface_name, io_stats in per_interface_io.items():
            interface_io[interface_name] = {
                "bytes_sent": io_stats.bytes_sent,
                "bytes_recv": io_stats.bytes_recv,
                "packets_sent": io_stats.packets_sent,
                "packets_recv": io_stats.packets_recv,
                "errin": io_stats.errin,
                "errout": io_stats.errout,
                "dropin": io_stats.dropin,
                "dropout": io_stats.dropout,
                "bytes_sent_formatted": format_bytes(io_stats.bytes_sent),
                "bytes_recv_formatted": format_bytes(io_stats.bytes_recv),
            }

        # Get network connections
        try:
            connections = psutil.net_connections()
            connection_info = {
                "total_connections": len(connections),
                "tcp_connections": len(
                    [c for c in connections if c.type == 1]
                ),  # SOCK_STREAM
                "udp_connections": len(
                    [c for c in connections if c.type == 2]
                ),  # SOCK_DGRAM
                "listening_ports": len(
                    [c for c in connections if c.status == "LISTEN"]
                ),
            }
        except Exception:
            connection_info = {
                "total_connections": 0,
                "tcp_connections": 0,
                "udp_connections": 0,
                "listening_ports": 0,
            }

        result = {
            "interfaces": interfaces,
            "total_interfaces": len(interfaces),
            "io_statistics": io_info,
            "per_interface_io": interface_io,
            "connections": connection_info,
        }

        return result

    except Exception as e:
        return {
            "interfaces": [],
            "total_interfaces": 0,
            "io_statistics": {},
            "per_interface_io": {},
            "connections": {},
            "error": str(e),
        }
