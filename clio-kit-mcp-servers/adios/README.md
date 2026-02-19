# Adios MCP Server

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![PyPI version](https://img.shields.io/pypi/v/adios-mcp.svg)](https://pypi.org/project/adios-mcp/)
[![Python](https://img.shields.io/badge/Python-3.10%2B-blue)](https://www.python.org/)

**Part of [CLIO Kit](https://toolkit.iowarp.ai/) - Gnosis Research Center**

ADIOS MCP is a comprehensive Model Context Protocol (MCP) server that enables Language Learning Models (LLMs) to access and analyze scientific simulation and real-time data through the ADIOS2 framework. This server provides read-only access to BP5 datasets with intelligent data handling and seaml...

## Quick Start

```bash
uvx clio-kit mcp-server adios
```

## Documentation

- **Full Documentation**: [CLIO Kit Website](https://toolkit.iowarp.ai/)
- **Installation Guide**: See [INSTALLATION.md](../../../CLAUDE.md#setup--installation)
- **Contributing**: See [Contribution Guide](https://github.com/iowarp/clio-kit/wiki/Contribution)

---

## Description

ADIOS MCP is a comprehensive Model Context Protocol (MCP) server that enables Language Learning Models (LLMs) to access and analyze scientific simulation and real-time data through the ADIOS2 framework. This server provides read-only access to BP5 datasets with intelligent data handling and seamless integration with AI coding assistants.



**Key Features:**
- **High-Performance Data Access**: Read-only access to ADIOS2 BP5 files with optimized I/O operations
- **Intelligent Data Processing**: Automatic variable type detection, shape analysis, and step-based data handling
- **Multiple Data Operations**: Variable inspection, attribute reading, data slicing, and statistical analysis
- **Scientific Computing Support**: Time-series analysis, multi-dimensional arrays, and metadata handling
- **Cross-Platform Compatibility**: Pure Python implementation for Linux, macOS, and Windows
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
    "adios-mcp": {
      "command": "uvx",
      "args": ["clio-kit", "mcp-server", "adios"]
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
    "adios-mcp": {
      "type": "stdio",
      "command": "uvx",
      "args": ["clio-kit", "mcp-server", "adios"]
    }
  }
}
```

</details>

<details>
<summary><b>Install in Claude Code</b></summary>

Run this command. See [Claude Code MCP docs](https://docs.anthropic.com/en/docs/agents-and-tools/claude-code/tutorials#set-up-model-context-protocol-mcp) for more info.

```sh
claude mcp add adios-mcp -- uvx clio-kit mcp-server adios
```

</details>

<details>
<summary><b>Install in Claude Desktop</b></summary>

Add this to your Claude Desktop `claude_desktop_config.json` file. See [Claude Desktop MCP docs](https://modelcontextprotocol.io/quickstart/user) for more info.

```json
{
  "mcpServers": {
    "adios-mcp": {
      "command": "uvx",
      "args": ["clio-kit", "mcp-server", "adios"]
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
uv --directory=$CLONE_DIR/clio-kit/clio-kit-mcp-servers/adios run adios-mcp --help
```
 
**Windows CMD:**
```cmd
set CLONE_DIR=%cd%
git clone https://github.com/iowarp/clio-kit.git
uv --directory=%CLONE_DIR%\clio-kit\clio-kit-mcp-servers\adios run adios-mcp --help
```
 
**Windows PowerShell:**
```powershell
$env:CLONE_DIR=$PWD
git clone https://github.com/iowarp/clio-kit.git
uv --directory=$env:CLONE_DIR\clio-kit\clio-kit-mcp-servers\adios run adios-mcp --help
```

</details>

## Capabilities

### `list_bp5`
**Description**: Lists all BP5 files in a given directory. The 'directory' parameter must be an absolute path.
**Hints**: read-only, idempotent
**Tags**: adios, scientific-io

### `inspect_variables`
**Description**: Inspects variables in a BP5 file, returning type, shape, and steps. Optionally filters by variable name.
**Hints**: read-only, idempotent
**Tags**: adios, variables

### `inspect_variables_at_step`
**Description**: Inspects a specific variable at a given step in a BP5 file. All parameters are required.
**Hints**: read-only, idempotent
**Tags**: adios, variables

### `inspect_attributes`
**Description**: Reads global or variable-specific attributes from a BP5 file. The 'variable_name' is optional.
**Hints**: read-only, idempotent
**Tags**: adios, attributes

### `read_variable_at_step`
**Description**: Reads a named variable at a specific step from a BP5 file. All parameters are required.
**Hints**: read-only, idempotent
**Tags**: adios, variables

### Resources

- `adios://capabilities` - ADIOS2 file format capabilities and supported engines.

### Prompts

- **explore_bp_file**: Guided workflow for exploring an ADIOS2 BP file.

## Claude Code

```bash
claude mcp add clio-adios -- uvx clio-kit adios
```

Or install via the CLIO Kit plugin marketplace:

```
/plugin marketplace add iowarp/clio-kit
/plugin install clio-adios@iowarp-clio-kit
```



## Claude Desktop

Add to your Claude Desktop config (`claude_desktop_config.json`):

```json
{
  "mcpServers": {
    "clio-adios": {
      "command": "uvx",
      "args": [
        "clio-kit",
        "adios"
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
    "clio-adios": {
      "command": "uvx",
      "args": [
        "clio-kit",
        "adios"
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

### 1. Scientific Data Structure Analysis
```
I have a BP5 simulation file at /data/simulation_results.bp. Can you first analyze the data structure and then show me the temperature variable evolution over time?
```

**Tools called:**
- `inspect_variables` - Analyze the dataset structure and available variables
- `read_variable_at_step` - Read temperature data at specific time steps

This prompt will:
- Use `inspect_variables` to analyze the BP5 file structure and discover all variables
- Extract temperature variable data using `read_variable_at_step` at different time steps
- Provide insights about the simulation data structure and temporal evolution

### 2. Multi-Variable Scientific Analysis
```
Using the file /data/fluid_dynamics.bp, perform a comprehensive analysis showing:
1. All available variables and their properties
2. Pressure field at step 50
3. Variable metadata and attributes for the pressure field
```

**Tools called:**
- `inspect_variables` - List all available variables and properties
- `read_variable_at_step` - Extract pressure field at step 50
- `inspect_attributes` - Get pressure variable metadata

This prompt will:
- Generate comprehensive variable inventory using `inspect_variables`
- Extract specific time step data using `read_variable_at_step`
- Analyze variable metadata with `inspect_attributes`
- Provide detailed analysis of fluid dynamics simulation data

### 3. Time-Series Variable Inspection
```
From /data/climate_model.bp, I want to understand the temperature variable structure across different time steps and inspect its properties at step 25.
```

**Tools called:**
- `inspect_variables` - Get temperature variable structure and available steps
- `inspect_variables_at_step` - Detailed inspection at step 25

This prompt will:
- Use `inspect_variables` to understand overall variable structure
- Use `inspect_variables_at_step` to get detailed information at a specific time step
- Provide comprehensive time-series data structure analysis

### 4. High-Performance Computing Data Analysis
```
Analyze the simulation output at /data/parallel_computation.bp - show me the variable structure, read specific computational domain data, and extract metadata attributes.
```

**Tools called:**
- `inspect_variables` - Analyze computational variables and structure
- `inspect_attributes` - Extract simulation metadata and parameters
- `read_variable_at_step` - Read domain-specific data

This prompt will:
- Use `inspect_variables` to understand parallel computation structure
- Extract simulation parameters with `inspect_attributes`
- Read specific computational domain data using `read_variable_at_step`
- Provide HPC-focused data analysis

### 5. Scientific Data Validation and Exploration
```
I need to validate the integrity of my ADIOS dataset at /data/experimental_results.bp - check all variables, their step-wise properties, and ensure metadata completeness.
```

**Tools called:**
- `inspect_variables` - Comprehensive variable structure validation
- `inspect_variables_at_step` - Step-specific variable validation
- `inspect_attributes` - Metadata integrity check

This prompt will:
- Use `inspect_variables` to validate overall data structure integrity
- Perform step-specific analysis with `inspect_variables_at_step`
- Check metadata completeness with `inspect_attributes`
- Provide comprehensive data quality assessment for scientific workflows

### 6. Quick BP5 File Discovery
```
Show me all BP5 files in my simulation directory at /data/simulations/ and provide a quick overview of their contents and structure.
```

**Tools called:**
- `list_bp5` - Directory-wide BP5 file discovery
- `inspect_variables` - Quick structure overview for each file

This prompt will:
- Use `list_bp5` to discover all BP5 files in the directory
- Use `inspect_variables` to provide structural overview of discovered files
- Generate comprehensive overview of available simulation datasets
- Suggest optimal data access strategies based on file contents