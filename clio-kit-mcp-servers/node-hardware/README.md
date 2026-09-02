# Node Hardware MCP Server

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![PyPI version](https://img.shields.io/pypi/v/node-hardware-mcp.svg)](https://pypi.org/project/node-hardware-mcp/)
[![Python](https://img.shields.io/badge/Python-3.10%2B-blue)](https://www.python.org/)

**Part of [CLIO Kit](https://docs.iowarp.ai/) - Gnosis Research Center**

Node Hardware MCP is a Model Context Protocol server that enables LLMs to monitor and analyze system hardware information including CPU specifications, memory usage, disk performance, network interfaces, GPU details, and sensor data for both local and remote nodes via SSH connections, providing c...

## Quick Start

```bash
uvx clio-kit mcp-server node-hardware
```

## Documentation

- **Full Documentation**: [CLIO Kit Website](https://docs.iowarp.ai/)
- **Installation Guide**: See [INSTALLATION.md](../../../CLAUDE.md#setup--installation)
- **Contributing**: See [Contribution Guide](https://github.com/iowarp/clio-kit/wiki/Contribution)

---

## Description

Node Hardware MCP is a Model Context Protocol server that enables LLMs to monitor and analyze system hardware information including CPU specifications, memory usage, disk performance, network interfaces, GPU details, and sensor data for both local and remote nodes via SSH connections, providing comprehensive hardware monitoring and performance analysis capabilities.


## 🛠️ Installation

### Requirements

- Python 3.10 or higher
- [uv](https://docs.astral.sh/uv/) package manager (recommended)
- SSH client (for remote node capabilities)

<details>
<summary><b>Install in Cursor</b></summary>

Go to: `Settings` -> `Cursor Settings` -> `MCP` -> `Add new global MCP server`

Pasting the following configuration into your Cursor `~/.cursor/mcp.json` file is the recommended approach. You may also install in a specific project by creating `.cursor/mcp.json` in your project folder. See [Cursor MCP docs](https://docs.cursor.com/context/model-context-protocol) for more info.

```json
{
  "mcpServers": {
    "node-hardware-mcp": {
      "command": "uvx",
      "args": ["clio-kit", "mcp-server", "node-hardware"]
    }
  }
}
```

</details>

<details>
<summary><b>Install in VS Code</b></summary>

Add this to your VS Code MCP config file. See [VS Code MCP docs](https://code.visualstudio.com/docs/copilot/chat/mcp-servers) for more info.

```json
"mcp": {
  "servers": {
    "node-hardware-mcp": {
      "type": "stdio",
      "command": "uvx",
      "args": ["clio-kit", "mcp-server", "node-hardware"]
    }
  }
}
```

</details>

<details>
<summary><b>Install in Claude Code</b></summary>

Run this command. See [Claude Code MCP docs](https://docs.anthropic.com/en/docs/agents-and-tools/claude-code/tutorials#set-up-model-context-protocol-mcp) for more info.

```sh
claude mcp add node-hardware-mcp -- uvx clio-kit mcp-server node-hardware
```

</details>

<details>
<summary><b>Install in Claude Desktop</b></summary>

Add this to your Claude Desktop `claude_desktop_config.json` file. See [Claude Desktop MCP docs](https://modelcontextprotocol.io/quickstart/user) for more info.

```json
{
  "mcpServers": {
    "node-hardware-mcp": {
      "command": "uvx",
      "args": ["clio-kit", "mcp-server", "node-hardware"]
    }
  }
}
```

</details>

<details>
<summary><b>Manual Setup</b></summary>

**Linux/macOS:**
```bash
CLONE_DIR=$(pwd)
git clone https://github.com/iowarp/clio-kit.git
uv --directory=$CLONE_DIR/clio-kit/clio-kit-mcp-servers/node-hardware run node-hardware-mcp --help
```

**Windows CMD:**
```cmd
set CLONE_DIR=%cd%
git clone https://github.com/iowarp/clio-kit.git
uv --directory=%CLONE_DIR%\clio-kit\clio-kit-mcp-servers\node-hardware run node-hardware-mcp --help
```

**Windows PowerShell:**
```powershell
$env:CLONE_DIR=$PWD
git clone https://github.com/iowarp/clio-kit.git
uv --directory=$env:CLONE_DIR\clio-kit\clio-kit-mcp-servers\node-hardware run node-hardware-mcp --help
```

</details>

## Capabilities

### `get_cpu_info`
**Description**: Get CPU specifications, core counts, frequencies, and per-core usage.
**Hints**: read-only, idempotent
**Tags**: cpu, hardware

### `get_memory_info`
**Description**: Get RAM and swap capacity, usage percentages, and availability.
**Hints**: read-only, idempotent
**Tags**: hardware, memory

### `get_system_info`
**Description**: Get OS details, hostname, uptime, and active users.
**Hints**: read-only, idempotent
**Tags**: hardware, system

### `get_disk_info`
**Description**: Get disk partitions, usage statistics, and I/O counters.
**Hints**: read-only, idempotent
**Tags**: disk, hardware

### `get_network_info`
**Description**: Get network interfaces, IP addresses, and I/O statistics.
**Hints**: read-only, idempotent
**Tags**: hardware, network

### `get_gpu_info`
**Description**: Get GPU model, memory, temperature, and utilization via nvidia-smi/rocm-smi.
**Hints**: read-only, idempotent
**Tags**: gpu, hardware

### `get_sensor_info`
**Description**: Get temperature, fan speed, and battery sensor readings.
**Hints**: read-only, idempotent
**Tags**: hardware, sensor

### `get_process_info`
**Description**: Get running processes with CPU, memory, and status details.
**Hints**: read-only, idempotent
**Tags**: hardware, process

### `get_performance_info`
**Description**: Get real-time CPU, memory, disk, and network performance metrics.
**Hints**: read-only, idempotent
**Tags**: hardware, performance

### `get_remote_node_info`
**Description**: Collect hardware info from a remote node via SSH. Supports component filtering.
**Hints**: read-only, idempotent
**Tags**: hardware, remote, ssh

### `health_check`
**Description**: Verify server health and hardware monitoring capability status.
**Hints**: read-only, idempotent
**Tags**: diagnostics, hardware

### Resources

- `node-hardware://system-info` - Basic system identification info.

### Prompts

- **system_health_check**: Guided workflow for a full system health check.
## Claude Code

```bash
claude mcp add clio-node-hardware -- uvx clio-kit node-hardware
```

Or install via the CLIO Kit plugin marketplace:

```
/plugin marketplace add iowarp/clio-kit
/plugin install clio-node-hardware@iowarp-clio-kit
```
## Claude Desktop

Add to your Claude Desktop config (`claude_desktop_config.json`):

```json
{
  "mcpServers": {
    "clio-node-hardware": {
      "command": "uvx",
      "args": [
        "clio-kit",
        "node-hardware"
      ]
    }
  }
}
```

## Examples

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

