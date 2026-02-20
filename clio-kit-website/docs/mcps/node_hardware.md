---
title: Node-Hardware MCP
description: "Node-Hardware MCP v1.0.0 - Part of CLIO Kit (IoWarp Platform). 11 tools for hardware monitoring: CPU, memory, GPU, disk, network info, remote SSH monitoring. Enables AI agents to monitor and analyze system hardware."
---

import MCPDetail from '@site/src/components/MCPDetail';

<MCPDetail 
  name="Node-Hardware"
  icon="💻"
  category="Analysis & Visualization"
  description="Node-Hardware MCP v1.0.0 - Part of CLIO Kit (IoWarp Platform). 11 tools for hardware monitoring: CPU, memory, GPU, disk, network info, remote SSH monitoring. Enables AI agents to monitor and analyze system hardware."
  version="1.0.0"
  actions={["get_cpu_info", "get_memory_info", "get_system_info", "get_disk_info", "get_network_info", "get_gpu_info", "get_sensor_info", "get_process_info", "get_performance_info", "get_remote_node_info", "health_check"]}
  platforms={["claude", "cursor", "vscode"]}
  keywords={["hardware-monitoring", "system-analysis", "performance-metrics", "node-information", "ssh-monitoring", "remote-hardware", "mcp", "llm-integration", "infrastructure-monitoring", "distributed-systems"]}
  license="BSD-3-Clause"
  tools={[{"name": "get_cpu_info", "description": "Get CPU specifications, core counts, frequencies, and per-core usage.", "function_name": "get_cpu_info"}, {"name": "get_memory_info", "description": "Get RAM and swap capacity, usage percentages, and availability.", "function_name": "get_memory_info"}, {"name": "get_system_info", "description": "Get OS details, hostname, uptime, and active users.", "function_name": "get_system_info"}, {"name": "get_disk_info", "description": "Get disk partitions, usage statistics, and I/O counters.", "function_name": "get_disk_info"}, {"name": "get_network_info", "description": "Get network interfaces, IP addresses, and I/O statistics.", "function_name": "get_network_info"}, {"name": "get_gpu_info", "description": "Get GPU model, memory, temperature, and utilization via nvidia-smi/rocm-smi.", "function_name": "get_gpu_info"}, {"name": "get_sensor_info", "description": "Get temperature, fan speed, and battery sensor readings.", "function_name": "get_sensor_info"}, {"name": "get_process_info", "description": "Get running processes with CPU, memory, and status details.", "function_name": "get_process_info"}, {"name": "get_performance_info", "description": "Get real-time CPU, memory, disk, and network performance metrics.", "function_name": "get_performance_info"}, {"name": "get_remote_node_info", "description": "Collect hardware info from a remote node via SSH. Supports component filtering.", "function_name": "get_remote_node_info"}, {"name": "health_check", "description": "Verify server health and hardware monitoring capability status.", "function_name": "health_check"}]}
>

### 1. Local Hardware Overview
```
I need a comprehensive overview of my local system's hardware including CPU, memory, disk, and network components.
```

**Tools called:**
- `get_node_info` - Get complete local hardware information with all components
- Components collected: cpu, memory, disk, network, system, summary

### 2. Remote Server Monitoring
```
Monitor the hardware status of a remote server via SSH, focusing on CPU and memory utilization for performance analysis.
```

**Tools called:**
- `get_remote_node_info` - Connect to remote host with SSH authentication
- Components collected: cpu, memory, performance, system

### 3. GPU and Thermal Monitoring
```
Check GPU specifications and thermal sensors on both local and remote systems for machine learning workloads.
```

**Tools called:**
- `get_node_info` - Local GPU and sensor monitoring  
- `get_remote_node_info` - Remote GPU and thermal analysis
- Components collected: gpu, sensors, performance

### 4. System Health Assessment
```
Perform a comprehensive health check of system capabilities and verify all monitoring tools are working correctly.
```

**Tools called:**
- `health_check` - System health verification and diagnostic assessment
- `get_node_info` - Comprehensive local system analysis with health metrics

### 5. Performance Bottleneck Analysis  
```
Identify performance bottlenecks on a production server by analyzing CPU, memory, disk I/O, and running processes.
```

**Tools called:**
- `get_remote_node_info` - Remote performance analysis via SSH
- Components collected: cpu, memory, disk, performance, processes

### 6. Storage and Network Analysis
```
Analyze storage health and network interface performance on multiple systems for infrastructure monitoring.
```

**Tools called:**
- `get_node_info` - Local storage and network analysis
- `get_remote_node_info` - Remote storage and network monitoring  
- Components collected: disk, network, system, summary

</MCPDetail>

