# Slurm MCP Server

[![License: BSD-3-Clause](https://img.shields.io/badge/License-BSD--3--Clause-blue.svg)](../../LICENSE)
[![PyPI version](https://img.shields.io/pypi/v/slurm-mcp.svg)](https://pypi.org/project/slurm-mcp/)
[![Python](https://img.shields.io/badge/Python-3.10%2B-blue)](https://www.python.org/)

**Part of [CLIO Kit](https://docs.iowarp.ai/) - Gnosis Research Center**

Slurm MCP gives agents a compact, typed interface for submitting, inspecting,
and explicitly cancelling workloads on Slurm-managed clusters. Granular
scheduler and interactive-allocation operations remain available to operators.

## Quick Start

```bash
uv tool install "clio-kit==2.3.0"
clio-kit mcp-server slurm
```

`uv tool install` is the supported setup for a permanent MCP server. It gives
CLIO Kit a persistent, isolated environment instead of recreating a temporary
`uvx` environment on agent startup.

## Documentation

- **Full Documentation**: [CLIO Kit Website](https://docs.iowarp.ai/)
- **Installation Guide**: See [INSTALLATION.md](../../../CLAUDE.md#setup--installation)
- **Contributing**: See [Contribution Guide](https://github.com/iowarp/clio-kit/wiki/Contribution)

---

## Description

The default surface is organized around scheduling intent rather than exposing a
one-to-one copy of the Slurm command API. It supports single and array jobs,
scheduler-native identifiers, unified lifecycle inspection, bounded output, and
closed machine-readable contracts.


## Installation

### Requirements

- Python 3.10 or higher
- [uv](https://docs.astral.sh/uv/) package manager (recommended)

Install the released CLIO Kit command once:

```bash
uv tool install "clio-kit==2.3.0"
clio-kit mcp-server slurm --help
```

For a one-shot probe or development check only, the equivalent temporary command
is `uvx --from "clio-kit==2.3.0" clio-kit mcp-server slurm`.

<details>
<summary><b>Install in Cursor</b></summary>

Go to: `Settings` -> `Cursor Settings` -> `MCP` -> `Add new global MCP server`

Pasting the following configuration into your Cursor `~/.cursor/mcp.json` file is the recommended approach. You may also install in a specific project by creating `.cursor/mcp.json` in your project folder. See [Cursor MCP docs](https://docs.cursor.com/context/model-context-protocol) for more info.

```json
{
  "mcpServers": {
    "slurm-mcp": {
      "command": "clio-kit",
      "args": ["mcp-server", "slurm"]
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
      "command": "clio-kit",
      "args": ["mcp-server", "slurm"]
    }
  }
}
```

</details>

<details>
<summary><b>Install in Claude Code</b></summary>

Run this command. See [Claude Code MCP docs](https://docs.anthropic.com/en/docs/agents-and-tools/claude-code/tutorials#set-up-model-context-protocol-mcp) for more info.

```sh
claude mcp add slurm-mcp -- clio-kit mcp-server slurm
```

</details>

<details>
<summary><b>Install in Claude Desktop</b></summary>

Add this to your Claude Desktop `claude_desktop_config.json` file. See [Claude Desktop MCP docs](https://modelcontextprotocol.io/quickstart/user) for more info.

```json
{
  "mcpServers": {
    "slurm-mcp": {
      "command": "clio-kit",
      "args": ["mcp-server", "slurm"]
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

The default `user` profile exposes a compact, agent-facing contract:

- `slurm_submit`: submit one job or array and receive its scheduler-native ID.
- `slurm_list`: find jobs using optional user, state, and partition filters.
- `slurm_describe`: combine status, scheduler details, and optional bounded output.
- `slurm_cluster`: inspect partitions and queue state, with node detail opt-in.
- `slurm_cancel`: request destructive cancellation only after an exact
  `confirm_job_id` match.

All five tools have closed input and output schemas. See
[the v3 contract and transformation table](docs/agent-contract-v3.md) for the
stable result envelopes and exact mapping from the original tools.

The original 13 granular operations remain available with `--profile legacy`.
Use `--profile admin` to expose compact and granular tools together. Unknown
profiles fail closed.

### Resources

- `slurm://cluster-info` - Basic Slurm cluster configuration.

### Prompts

- **submit_job_workflow**: Guided workflow for submitting and monitoring a Slurm job.
## Claude Code

```bash
claude mcp add clio-slurm -- clio-kit mcp-server slurm
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
      "command": "clio-kit",
      "args": [
        "mcp-server",
        "slurm"
      ]
    }
  }
}
```

## Examples

### 1. Job Submission and Monitoring
```
I need to submit a Python simulation script to Slurm with 16 cores and 32GB memory, then monitor its progress until completion.
```

**Tools called:**
- `slurm_submit` - Submit the job with its resource request
- `slurm_describe` - Query lifecycle state and scheduler details

### 2. Array Job Management
```
Submit an array job for parameter sweep analysis with 100 tasks, each requiring 4 cores and 8GB memory, then check the overall progress.
```

**Tools called:**
- `slurm_submit` with `array` - Submit the parallel array
- `slurm_list` - Find its scheduler-native job ID
- `slurm_describe` - Query array state and details

### 3. Interactive Session Management
```
Allocate 2 compute nodes with 8 cores each for an interactive analysis session, then deallocate when finished.
```

**Admin/legacy tools called:**
- `allocate_slurm_nodes` - Allocate interactive nodes
- `get_node_info` - Check node status and resources
- `deallocate_slurm_nodes` - Clean up allocated resources

### 4. Job Management and Cleanup
```
I have a long-running job that needs to be cancelled, and I want to retrieve the output from a completed job before cleaning up.
```

**Tools called:**
- `slurm_describe` with bounded output - Review job state and logs
- `slurm_cancel` with exact ID confirmation - Request cancellation

### 5. Allocation Status and Monitoring
```
Check the status of my current interactive allocation and monitor its resource usage efficiency.
```

**Admin/legacy tools called:**
- `get_allocation_status` - Monitor allocation efficiency
- `get_node_info` - Check node resource usage
- `deallocate_slurm_nodes` - Clean up when finished

### 6. Comprehensive Cluster Analysis
```
Analyze the current cluster queue status, identify bottlenecks, and suggest optimal resource allocation for my pending jobs.
```

**Tools called:**
- `slurm_cluster` - Inspect partitions, queue state, and capacity
- `slurm_list` - Review the user's pending jobs and scheduler-native IDs
