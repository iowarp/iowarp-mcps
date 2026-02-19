# Slurm MCP Server

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![PyPI version](https://img.shields.io/pypi/v/slurm-mcp.svg)](https://pypi.org/project/slurm-mcp/)
[![Python](https://img.shields.io/badge/Python-3.10%2B-blue)](https://www.python.org/)

**Part of [CLIO Kit](https://toolkit.iowarp.ai/) - Gnosis Research Center**

Slurm MCP is a Model Context Protocol server that enables LLMs to manage HPC workloads on Slurm-managed clusters with comprehensive job submission, monitoring, and resource management capabilities, featuring intelligent job scheduling, cluster monitoring, array job support, and interactive node a...

## Quick Start

```bash
uvx clio-kit mcp-server slurm
```

## Documentation

- **Full Documentation**: [CLIO Kit Website](https://toolkit.iowarp.ai/)
- **Installation Guide**: See [INSTALLATION.md](../../../CLAUDE.md#setup--installation)
- **Contributing**: See [Contribution Guide](https://github.com/iowarp/clio-kit/wiki/Contribution)

---

## Description

Slurm MCP is a Model Context Protocol server that enables LLMs to manage HPC workloads on Slurm-managed clusters with comprehensive job submission, monitoring, and resource management capabilities, featuring intelligent job scheduling, cluster monitoring, array job support, and interactive node allocation for seamless high-performance computing workflows.


## 🛠️ Installation

### Requirements

- Python 3.10 or higher
- [uv](https://docs.astral.sh/uv/) package manager (recommended)

<details>
<summary><b>Install in Cursor</b></summary>

Go to: `Settings` -> `Cursor Settings` -> `MCP` -> `Add new global MCP server`

Pasting the following configuration into your Cursor `~/.cursor/mcp.json` file is the recommended approach. You may also install in a specific project by creating `.cursor/mcp.json` in your project folder. See [Cursor MCP docs](https://docs.cursor.com/context/model-context-protocol) for more info.

```json
{
  "mcpServers": {
    "slurm-mcp": {
      "command": "uvx",
      "args": ["clio-kit", "mcp-server", "slurm"]
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
    "slurm-mcp": {
      "type": "stdio",
      "command": "uvx",
      "args": ["clio-kit", "mcp-server", "slurm"]
    }
  }
}
```

</details>

<details>
<summary><b>Install in Claude Code</b></summary>

Run this command. See [Claude Code MCP docs](https://docs.anthropic.com/en/docs/agents-and-tools/claude-code/tutorials#set-up-model-context-protocol-mcp) for more info.

```sh
claude mcp add slurm-mcp -- uvx clio-kit mcp-server slurm
```

</details>

<details>
<summary><b>Install in Claude Desktop</b></summary>

Add this to your Claude Desktop `claude_desktop_config.json` file. See [Claude Desktop MCP docs](https://modelcontextprotocol.io/quickstart/user) for more info.

```json
{
  "mcpServers": {
    "slurm-mcp": {
      "command": "uvx",
      "args": ["clio-kit", "mcp-server", "slurm"]
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
uv --directory=$CLONE_DIR/clio-kit/clio-kit-mcp-servers/slurm run slurm-mcp --help
```

**Windows CMD:**
```cmd
set CLONE_DIR=%cd%
git clone https://github.com/iowarp/clio-kit.git
uv --directory=%CLONE_DIR%\clio-kit\clio-kit-mcp-servers\slurm run slurm-mcp --help
```

**Windows PowerShell:**
```powershell
$env:CLONE_DIR=$PWD
git clone https://github.com/iowarp/clio-kit.git
uv --directory=$env:CLONE_DIR\clio-kit\clio-kit-mcp-servers\slurm run slurm-mcp --help
```

</details>

## Capabilities

### `submit_slurm_job`
**Description**: Submit a job script to the Slurm scheduler with resource requirements.
**Tags**: jobs, submission

### `check_job_status`
**Description**: Check the status of a Slurm job by its ID.
**Hints**: read-only, idempotent
**Tags**: jobs, monitoring

### `cancel_slurm_job`
**Description**: Cancel a running or pending Slurm job.
**Hints**: destructive, idempotent
**Tags**: jobs, management

### `list_slurm_jobs`
**Description**: List Slurm jobs with optional filtering by user and state.
**Hints**: read-only, idempotent
**Tags**: jobs, monitoring

### `get_slurm_info`
**Description**: Get Slurm cluster configuration, partitions, and resource availability.
**Hints**: read-only, idempotent
**Tags**: jobs, monitoring

### `get_job_details`
**Description**: Get detailed information about a specific Slurm job.
**Hints**: read-only, idempotent
**Tags**: jobs, monitoring

### `get_job_output`
**Description**: Retrieve stdout or stderr output from a Slurm job.
**Hints**: read-only, idempotent
**Tags**: jobs, monitoring

### `get_queue_info`
**Description**: Get Slurm queue status and partition information.
**Hints**: read-only, idempotent
**Tags**: jobs, monitoring

### `submit_array_job`
**Description**: Submit a Slurm array job for parallel task execution.
**Tags**: jobs, submission

### `get_node_info`
**Description**: Get information about Slurm cluster nodes and their resources.
**Hints**: read-only, idempotent
**Tags**: jobs, monitoring

### `allocate_slurm_nodes`
**Description**: Allocate Slurm nodes for an interactive session using salloc.
**Tags**: jobs, submission

### `deallocate_slurm_nodes`
**Description**: Release a Slurm node allocation by canceling it.
**Hints**: destructive, idempotent
**Tags**: jobs, management

### `get_allocation_status`
**Description**: Check the status of a Slurm node allocation.
**Hints**: read-only, idempotent
**Tags**: jobs, monitoring

### Resources

- `slurm://cluster-info` - Basic Slurm cluster configuration.

### Prompts

- **submit_job_workflow**: Guided workflow for submitting and monitoring a Slurm job.

## Claude Code

```bash
claude mcp add clio-slurm -- uvx clio-kit slurm
```

Or install via the CLIO Kit plugin marketplace:

```
/plugin marketplace add iowarp/clio-kit
/plugin install clio-slurm@iowarp-clio-kit
```



## Claude Desktop

Add to your Claude Desktop config (`claude_desktop_config.json`):

```json
{
  "mcpServers": {
    "clio-slurm": {
      "command": "uvx",
      "args": [
        "clio-kit",
        "slurm"
      ]
    }
  }
}
```



## Gemini CLI

Add to `~/.gemini/settings.json`:

```json
{
  "mcpServers": {
    "clio-slurm": {
      "command": "uvx",
      "args": [
        "clio-kit",
        "slurm"
      ]
    }
  }
}
```

Or install the CLIO Kit extension:

```bash
gemini extensions install https://github.com/iowarp/clio-kit
```


## Examples

### 1. Job Submission and Monitoring
```
I need to submit a Python simulation script to Slurm with 16 cores and 32GB memory, then monitor its progress until completion.
```

**Tools called:**
- `submit_slurm_job` - Submit job with resource specification
- `check_job_status` - Monitor job progress and performance

### 2. Array Job Management
```
Submit an array job for parameter sweep analysis with 100 tasks, each requiring 4 cores and 8GB memory, then check the overall progress.
```

**Tools called:**
- `submit_array_job` - Submit parallel array job
- `list_slurm_jobs` - Monitor array job progress
- `get_job_details` - Get detailed array job information

### 3. Interactive Session Management
```
Allocate 2 compute nodes with 8 cores each for an interactive analysis session, then deallocate when finished.
```

**Tools called:**
- `allocate_slurm_nodes` - Allocate interactive nodes
- `get_node_info` - Check node status and resources
- `deallocate_slurm_nodes` - Clean up allocated resources

### 4. Job Management and Cleanup
```
I have a long-running job that needs to be cancelled, and I want to retrieve the output from a completed job before cleaning up.
```

**Tools called:**
- `cancel_slurm_job` - Cancel running job with cleanup
- `get_job_output` - Retrieve completed job outputs
- `get_job_details` - Get final job performance metrics

### 5. Allocation Status and Monitoring
```
Check the status of my current interactive allocation and monitor its resource usage efficiency.
```

**Tools called:**
- `get_allocation_status` - Monitor allocation efficiency
- `get_node_info` - Check node resource usage
- `deallocate_slurm_nodes` - Clean up when finished

### 6. Comprehensive Cluster Analysis
```
Analyze the current cluster queue status, identify bottlenecks, and suggest optimal resource allocation for my pending jobs.
```

**Tools called:**
- `get_slurm_info` - Get cluster status and capacity
- `get_queue_info` - Analyze queue performance and bottlenecks
- `list_slurm_jobs` - Review pending job queue and priorities