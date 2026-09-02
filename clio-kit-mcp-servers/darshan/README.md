# Darshan MCP Server

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![PyPI version](https://img.shields.io/pypi/v/darshan-mcp.svg)](https://pypi.org/project/darshan-mcp/)
[![Python](https://img.shields.io/badge/Python-3.10%2B-blue)](https://www.python.org/)

**Part of [CLIO Kit](https://docs.iowarp.ai/) - Gnosis Research Center**

Darshan MCP is a comprehensive Model Context Protocol (MCP) server that enables Language Learning Models (LLMs) to analyze HPC application I/O performance through Darshan profiler trace files. This server provides advanced I/O analysis capabilities, performance bottleneck identification, and comp...

## Quick Start

```bash
uvx clio-kit mcp-server darshan
```

## Documentation

- **Full Documentation**: [CLIO Kit Website](https://docs.iowarp.ai/)
- **Installation Guide**: See [INSTALLATION.md](../../../CLAUDE.md#setup--installation)
- **Contributing**: See [Contribution Guide](https://github.com/iowarp/clio-kit/wiki/Contribution)

---

## Description

Darshan MCP is a comprehensive Model Context Protocol (MCP) server that enables Language Learning Models (LLMs) to analyze HPC application I/O performance through Darshan profiler trace files. This server provides advanced I/O analysis capabilities, performance bottleneck identification, and comprehensive reporting tools with seamless integration with AI coding assistants.

**Key Features:**
- **Comprehensive I/O Analysis**: Load and parse Darshan logs with metadata extraction and performance metrics calculation
- **Performance Metrics**: Calculate bandwidth, IOPS, request size statistics, and access pattern analysis
- **Bottleneck Detection**: Automatically identify potential I/O performance issues and optimization opportunities
- **Multi-Protocol Support**: Analyze both POSIX system calls and MPI-IO operations with detailed pattern recognition
- **Timeline Analysis**: Understand I/O activity over time with temporal performance visualization
- **Comparative Analysis**: Compare multiple trace files to identify performance changes and optimization results
- **MCP Integration**: Full Model Context Protocol compliance for seamless LLM integration


## 🛠️ Installation

### Requirements

- Python 3.10 or higher
- [uv](https://docs.astral.sh/uv/) package manager (recommended)
- Darshan tools (`darshan-parser` in PATH)
- Python libraries: numpy, pandas, matplotlib

<details>
<summary><b>Install in Cursor</b></summary>

Go to: `Settings` -> `Cursor Settings` -> `MCP` -> `Add new global MCP server`

Pasting the following configuration into your Cursor `~/.cursor/mcp.json` file is the recommended approach. You may also install in a specific project by creating `.cursor/mcp.json` in your project folder. See [Cursor MCP docs](https://docs.cursor.com/context/model-context-protocol) for more info.

```json
{
  "mcpServers": {
    "darshan-mcp": {
      "command": "uvx",
      "args": ["clio-kit", "mcp-server", "darshan"]
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
    "darshan-mcp": {
      "type": "stdio",
      "command": "uvx",
      "args": ["clio-kit", "mcp-server", "darshan"]
    }
  }
}
```

</details>

<details>
<summary><b>Install in Claude Code</b></summary>

Run this command. See [Claude Code MCP docs](https://docs.anthropic.com/en/docs/agents-and-tools/claude-code/tutorials#set-up-model-context-protocol-mcp) for more info.

```sh
claude mcp add darshan-mcp -- uvx clio-kit mcp-server darshan
```

</details>

<details>
<summary><b>Install in Claude Desktop</b></summary>

Add this to your Claude Desktop `claude_desktop_config.json` file. See [Claude Desktop MCP docs](https://modelcontextprotocol.io/quickstart/user) for more info.

```json
{
  "mcpServers": {
    "darshan-mcp": {
      "command": "uvx",
      "args": ["clio-kit", "mcp-server", "darshan"]
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
uv --directory=$CLONE_DIR/clio-kit/clio-kit-mcp-servers/darshan run darshan-mcp --help
```

**Windows CMD:**
```cmd
set CLONE_DIR=%cd%
git clone https://github.com/iowarp/clio-kit.git
uv --directory=%CLONE_DIR%\clio-kit\clio-kit-mcp-servers\darshan run darshan-mcp --help
```

**Windows PowerShell:**
```powershell
$env:CLONE_DIR=$PWD
git clone https://github.com/iowarp/clio-kit.git
uv --directory=$env:CLONE_DIR\clio-kit\clio-kit-mcp-servers\darshan run darshan-mcp --help
```

</details>

## Capabilities

### `load_darshan_log`
**Description**: Load and parse a Darshan log file to extract I/O performance metrics and metadata.
**Hints**: read-only, idempotent
**Tags**: darshan, io-analysis

### `get_job_summary`
**Description**: Get job-level summary from a Darshan log including runtime, process count, and I/O volume.
**Hints**: read-only, idempotent
**Tags**: darshan, io-analysis

### `analyze_file_access_patterns`
**Description**: Analyze file access patterns including read/write types and sequential vs random access.
**Hints**: read-only, idempotent
**Tags**: darshan, io-analysis

### `get_io_performance_metrics`
**Description**: Extract I/O performance metrics including bandwidth, IOPS, and request sizes.
**Hints**: read-only, idempotent
**Tags**: darshan, performance

### `analyze_posix_operations`
**Description**: Analyze POSIX I/O operations including read/write system calls and their frequency.
**Hints**: read-only, idempotent
**Tags**: darshan, io-analysis

### `analyze_mpiio_operations`
**Description**: Analyze MPI-IO operations including collective vs independent operations.
**Hints**: read-only, idempotent
**Tags**: darshan, io-analysis

### `identify_io_bottlenecks`
**Description**: Identify I/O performance bottlenecks by analyzing access patterns and operations.
**Hints**: read-only, idempotent
**Tags**: darshan, performance

### `get_timeline_analysis`
**Description**: Generate timeline analysis showing I/O activity over time and temporal patterns.
**Hints**: read-only, idempotent
**Tags**: darshan, performance

### `compare_darshan_logs`
**Description**: Compare two Darshan log files to identify performance differences between runs.
**Hints**: read-only, idempotent
**Tags**: darshan, performance

### `generate_io_summary_report`
**Description**: Generate a comprehensive I/O summary report with findings and recommendations.
**Hints**: read-only, idempotent
**Tags**: darshan, performance

### Resources

- `darshan://capabilities` - Darshan I/O profiling analysis capabilities.

### Prompts

- **analyze_io_performance**: Guided workflow for analyzing I/O performance from a Darshan log.
## Claude Code

```bash
claude mcp add clio-darshan -- uvx clio-kit darshan
```

Or install via the CLIO Kit plugin marketplace:

```
/plugin marketplace add iowarp/clio-kit
/plugin install clio-darshan@iowarp-clio-kit
```
## Claude Desktop

Add to your Claude Desktop config (`claude_desktop_config.json`):

```json
{
  "mcpServers": {
    "clio-darshan": {
      "command": "uvx",
      "args": [
        "clio-kit",
        "darshan"
      ]
    }
  }
}
```

## Examples

### 1. HPC Application Performance Analysis
```
Analyze the I/O performance of my application using the Darshan log at /data/app_trace.darshan. Identify bottlenecks and provide optimization recommendations.
```

**Tools called:**
- `load_darshan_log` - Parse the Darshan trace file
- `get_job_summary` - Extract job-level statistics
- `identify_io_bottlenecks` - Find performance issues
- `get_io_performance_metrics` - Calculate detailed metrics

This prompt will:
- Use `load_darshan_log` to parse the trace file and extract metadata
- Generate job summary using `get_job_summary` for runtime and I/O statistics
- Identify performance bottlenecks using `identify_io_bottlenecks`
- Provide comprehensive performance analysis with optimization recommendations

### 2. I/O Pattern Optimization Study
```
Compare the I/O patterns between /data/before_opt.darshan and /data/after_opt.darshan to validate our optimization efforts and measure performance improvements.
```

**Tools called:**
- `analyze_file_access_patterns` - Analyze access patterns for both files
- `compare_darshan_logs` - Compare performance metrics
- `get_io_performance_metrics` - Extract detailed performance data

This prompt will:
- Analyze access patterns using `analyze_file_access_patterns` for both traces
- Compare performance metrics using `compare_darshan_logs`
- Extract detailed metrics using `get_io_performance_metrics`
- Provide comprehensive optimization validation and improvement quantification

### 3. MPI-IO Collective Performance Analysis
```
Examine the MPI-IO operations in /data/parallel_app.darshan, focusing on collective vs independent I/O patterns and their impact on overall performance.
```

**Tools called:**
- `analyze_mpiio_operations` - Analyze MPI-IO patterns
- `get_timeline_analysis` - Understand temporal patterns
- `generate_io_summary_report` - Create comprehensive report

This prompt will:
- Analyze MPI-I/O operations using `analyze_mpiio_operations`
- Generate temporal analysis using `get_timeline_analysis`
- Create detailed report using `generate_io_summary_report`
- Provide insights into collective I/O efficiency and optimization opportunities

### 4. POSIX System Call Analysis
```
Investigate the POSIX I/O operations in /data/serial_app.darshan to understand file access patterns and identify potential optimizations for system call efficiency.
```

**Tools called:**
- `analyze_posix_operations` - Examine POSIX system calls
- `analyze_file_access_patterns` - Study file access behavior
- `identify_io_bottlenecks` - Find system-level bottlenecks

This prompt will:
- Analyze POSIX operations using `analyze_posix_operations`
- Study file access patterns using `analyze_file_access_patterns`
- Identify bottlenecks using `identify_io_bottlenecks`
- Provide system call optimization recommendations

### 5. Comprehensive I/O Performance Report
```
Generate a complete I/O performance analysis report for /data/production_app.darshan including all metrics, visualizations, and recommendations for our production environment.
```

**Tools called:**
- `load_darshan_log` - Load and validate trace file
- `generate_io_summary_report` - Create comprehensive analysis
- `get_timeline_analysis` - Add temporal performance data

This prompt will:
- Load and validate trace using `load_darshan_log`
- Generate complete report using `generate_io_summary_report`
- Add timeline analysis using `get_timeline_analysis`
- Provide production-ready performance assessment with actionable insights