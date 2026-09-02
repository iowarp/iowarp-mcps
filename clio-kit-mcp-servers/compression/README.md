# Compression MCP Server

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![PyPI version](https://img.shields.io/pypi/v/compression-mcp.svg)](https://pypi.org/project/compression-mcp/)
[![Python](https://img.shields.io/badge/Python-3.10%2B-blue)](https://www.python.org/)

**Part of [CLIO Kit](https://docs.iowarp.ai/) - Gnosis Research Center**

Compression MCP is a comprehensive Model Context Protocol (MCP) server that enables Language Learning Models (LLMs) to perform efficient file compression operations using industry-standard algorithms. This server provides high-performance gzip compression with detailed statistics and seamless int...

## Quick Start

```bash
uvx clio-kit mcp-server compression
```

## Documentation

- **Full Documentation**: [CLIO Kit Website](https://docs.iowarp.ai/)
- **Installation Guide**: See [INSTALLATION.md](../../../CLAUDE.md#setup--installation)
- **Contributing**: See [Contribution Guide](https://github.com/iowarp/clio-kit/wiki/Contribution)

---

## Description

Compression MCP is a comprehensive Model Context Protocol (MCP) server that enables Language Learning Models (LLMs) to perform efficient file compression operations using industry-standard algorithms. This server provides high-performance gzip compression with detailed statistics and seamless integration with AI coding assistants.


**Key Features:**
- **High-Performance Compression**: Efficient gzip compression with optimal performance algorithms
- **Detailed Analytics**: Comprehensive compression statistics including ratios, file sizes, and space savings
- **Robust Error Handling**: Professional error management with informative messages and graceful failure handling
- **Universal File Support**: Handles all file types including text, binary, logs, and data files
- **Storage Optimization**: Significant space savings for data archival and transfer operations
- **MCP Integration**: Full Model Context Protocol compliance for seamless LLM integration



## 🛠️ Installation

### Requirements

- Python 3.10 or higher
- [uv](https://docs.astral.sh/uv/) package manager (recommended)
- Linux/macOS environment (Windows supported)

<details>
<summary><b>Install in Cursor</b></summary>

Go to: `Settings` -> `Cursor Settings` -> `MCP` -> `Add new global MCP server`

Pasting the following configuration into your Cursor `~/.cursor/mcp.json` file is the recommended approach. You may also install in a specific project by creating `.cursor/mcp.json` in your project folder. See [Cursor MCP docs](https://docs.cursor.com/context/model-context-protocol) for more info.

```json
{
  "mcpServers": {
    "compression-mcp": {
      "command": "uvx",
      "args": ["clio-kit", "mcp-server", "compression"]
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
    "compression-mcp": {
      "type": "stdio",
      "command": "uvx",
      "args": ["clio-kit", "mcp-server", "compression"]
    }
  }
}
```

</details>

<details>
<summary><b>Install in Claude Code</b></summary>

Run this command. See [Claude Code MCP docs](https://docs.anthropic.com/en/docs/agents-and-tools/claude-code/tutorials#set-up-model-context-protocol-mcp) for more info.

```sh
claude mcp add compression-mcp -- uvx clio-kit mcp-server compression
```

</details>

<details>
<summary><b>Install in Claude Desktop</b></summary>

Add this to your Claude Desktop `claude_desktop_config.json` file. See [Claude Desktop MCP docs](https://modelcontextprotocol.io/quickstart/user) for more info.

```json
{
  "mcpServers": {
    "compression-mcp": {
      "command": "uvx",
      "args": ["clio-kit", "mcp-server", "compression"]
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
uv --directory=$CLONE_DIR/clio-kit/clio-kit-mcp-servers/compression run compression-mcp --help
```

**Windows CMD:**
```cmd
set CLONE_DIR=%cd%
git clone https://github.com/iowarp/clio-kit.git
uv --directory=%CLONE_DIR%\clio-kit\clio-kit-mcp-servers\compression run compression-mcp --help
```

**Windows PowerShell:**
```powershell
$env:CLONE_DIR=$PWD
git clone https://github.com/iowarp/clio-kit.git
uv --directory=$env:CLONE_DIR\clio-kit\clio-kit-mcp-servers\compression run compression-mcp --help
```

</details>

## Capabilities

### `compress_file_tool`
**Description**: Compress a file using gzip. Returns original/compressed sizes and compression ratio.
**Hints**: idempotent
**Tags**: compression, file-io

### `decompress_file_tool`
**Description**: Decompress a gzip-compressed (.gz) file back to its original form.
**Hints**: idempotent
**Tags**: decompression, file-io

### Resources

- `compression://capabilities` - Supported compression formats and their capabilities.

### Prompts

- **compress_workflow**: Guided workflow for compressing a file and verifying the result.
## Claude Code

```bash
claude mcp add clio-compression -- uvx clio-kit compression
```

Or install via the CLIO Kit plugin marketplace:

```
/plugin marketplace add iowarp/clio-kit
/plugin install clio-compression@iowarp-clio-kit
```
## Claude Desktop

Add to your Claude Desktop config (`claude_desktop_config.json`):

```json
{
  "mcpServers": {
    "clio-compression": {
      "command": "uvx",
      "args": [
        "clio-kit",
        "compression"
      ]
    }
  }
}
```

## Examples

### 1. Log File Compression and Storage Optimization
```
I have large log files in my application directory at /var/log/application.log that are taking up significant storage space. Can you compress them to save storage?
```

**Tools called:**
- `compress_file` - Compress the log file with gzip compression

This prompt will:
- Use `compress_file` to compress the log file using efficient gzip algorithms
- Provide detailed compression statistics including space savings
- Generate compressed output file with .gz extension for storage optimization

### 2. Data Archival and Backup Preparation
```
I need to archive my research data files before backing them up. Compress the dataset file at /data/research/experimental_results.csv to reduce backup time and storage requirements.
```

**Tools called:**
- `compress_file` - Compress the research dataset for archival

This prompt will:
- Apply gzip compression to the CSV dataset using `compress_file`
- Provide comprehensive compression analytics including ratio and file size reduction
- Prepare the compressed file for efficient backup and archival operations

### 3. Transfer Optimization for Network Efficiency
```
Before transferring large data files over the network, I want to compress /home/user/documents/large_document.pdf to reduce transfer time and bandwidth usage.
```

**Tools called:**
- `compress_file` - Compress document for network transfer optimization

This prompt will:
- Use `compress_file` to apply gzip compression to the PDF document
- Generate detailed compression statistics for transfer planning
- Create compressed file optimized for network transmission efficiency

### 4. Bulk Storage Management
```
My application generates large output files at /tmp/processing_output.txt that need to be compressed for long-term storage management.
```

**Tools called:**
- `compress_file` - Compress application output files

This prompt will:
- Apply professional-grade gzip compression using `compress_file`
- Provide detailed analytics on storage space savings and compression efficiency
- Generate compressed files suitable for long-term storage and archival systems

### 5. Development Environment Cleanup
```
I have temporary files and logs in my development environment that are consuming too much disk space. Compress /dev/temp/debug_output.log to free up storage.
```

**Tools called:**
- `compress_file` - Compress development files for space management

This prompt will:
- Use `compress_file` to compress debug logs with optimal compression algorithms
- Provide comprehensive compression statistics for storage management decisions
- Create space-efficient compressed files while preserving original data integrity

### 6. System Administration and Maintenance
```
As part of system maintenance, I need to compress old system logs at /var/log/system.log to maintain system performance and storage efficiency.
```

**Tools called:**
- `compress_file` - Compress system logs for maintenance operations

This prompt will:
- Apply gzip compression to system logs using `compress_file`
- Generate detailed compression reports for system administration monitoring
- Create compressed log files that maintain data accessibility while reducing storage footprint