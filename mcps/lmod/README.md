# Lmod MCP - Environment Module Management for LLMs


## Description

Lmod MCP is a comprehensive Model Context Protocol (MCP) server that enables Language Learning Models (LLMs) to manage environment modules using the Lmod system. This server provides advanced module management capabilities, environment configuration tools, and HPC workflow support with seamless integration with AI coding assistants.

**Key Features:**
- **Comprehensive Module Management**: List, search, load, unload, and inspect modules with intelligent dependency handling
- **Advanced Search Capabilities**: Spider search through entire module hierarchy with pattern matching and filtering
- **Environment Collections**: Save and restore complete module configurations for reproducible environments
- **Atomic Operations**: Safe module swapping and dependency-aware loading with conflict resolution
- **HPC Integration**: Optimized for scientific computing workflows with batch job environment management
- **MCP Integration**: Full Model Context Protocol compliance for seamless LLM integration


## 🛠️ Installation

### Requirements

- Python 3.10 or higher
- [uv](https://docs.astral.sh/uv/) package manager (recommended)
- Lmod system installed and available in PATH
- HPC environment with module system access

<details>
<summary><b>Install in Cursor</b></summary>

Go to: `Settings` -> `Cursor Settings` -> `MCP` -> `Add new global MCP server`

Pasting the following configuration into your Cursor `~/.cursor/mcp.json` file is the recommended approach. You may also install in a specific project by creating `.cursor/mcp.json` in your project folder. See [Cursor MCP docs](https://docs.cursor.com/context/model-context-protocol) for more info.

```json
{
  "mcpServers": {
    "lmod-mcp": {
      "command": "uvx",
      "args": ["iowarp-mcps", "lmod"]
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
    "lmod-mcp": {
      "type": "stdio",
      "command": "uvx",
      "args": ["iowarp-mcps", "lmod"]
    }
  }
}
```

</details>

<details>
<summary><b>Install in Claude Code</b></summary>

Run this command. See [Claude Code MCP docs](https://docs.anthropic.com/en/docs/agents-and-tools/claude-code/tutorials#set-up-model-context-protocol-mcp) for more info.

```sh
claude mcp add lmod-mcp -- uvx iowarp-mcps lmod
```

</details>

<details>
<summary><b>Install in Claude Desktop</b></summary>

Add this to your Claude Desktop `claude_desktop_config.json` file. See [Claude Desktop MCP docs](https://modelcontextprotocol.io/quickstart/user) for more info.

```json
{
  "mcpServers": {
    "lmod-mcp": {
      "command": "uvx",
      "args": ["iowarp-mcps", "lmod"]
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
git clone https://github.com/iowarp/iowarp-mcps.git
uv --directory=$CLONE_DIR/iowarp-mcps/mcps/lmod run lmod-mcp --help
```

**Windows CMD:**
```cmd
set CLONE_DIR=%cd%
git clone https://github.com/iowarp/iowarp-mcps.git
uv --directory=%CLONE_DIR%\iowarp-mcps\mcps\lmod run lmod-mcp --help
```

**Windows PowerShell:**
```powershell
$env:CLONE_DIR=$PWD
git clone https://github.com/iowarp/iowarp-mcps.git
uv --directory=$env:CLONE_DIR\iowarp-mcps\mcps\lmod run lmod-mcp --help
```

</details>

## Available Actions

### `module_list`
**Description**: List all currently loaded environment modules with their versions and status information.

**Parameters**: None

**Returns**: Dictionary with list of loaded modules, count, and module status information.

### `module_avail`
**Description**: Search for available modules that can be loaded with optional pattern matching and filtering.

**Parameters**:
- `pattern` (str, optional): Search pattern with wildcards (e.g., 'python*', 'gcc/*')

**Returns**: Dictionary with available modules matching the search criteria and their descriptions.

### `module_show`
**Description**: Display comprehensive information about a specific module including dependencies and environment changes.

**Parameters**:
- `module_name` (str): Name of the module (e.g., 'python/3.9.0')

**Returns**: Dictionary with detailed module information, dependencies, and environment modifications.

### `module_load`
**Description**: Load one or more environment modules with automatic dependency resolution and conflict detection.

**Parameters**:
- `modules` (list): List of module names to load

**Returns**: Dictionary with loading status, any conflicts detected, and environment changes applied.

### `module_unload`
**Description**: Unload one or more currently loaded modules with dependency checking and cleanup.

**Parameters**:
- `modules` (list): List of module names to unload

**Returns**: Dictionary with unloading status and environment restoration information.

### `module_swap`
**Description**: Atomically swap one module for another, handling dependencies and version conflicts automatically.

**Parameters**:
- `old_module` (str): Module to unload
- `new_module` (str): Module to load in its place

**Returns**: Dictionary with swap operation status and any dependency adjustments made.

### `module_spider`
**Description**: Search the entire module tree comprehensively with deep hierarchy exploration and metadata extraction.

**Parameters**:
- `pattern` (str, optional): Search pattern for comprehensive module discovery

**Returns**: Dictionary with comprehensive search results including hidden modules and dependency information.

### `module_save`
**Description**: Save the current set of loaded modules as a named collection for reproducible environments.

**Parameters**:
- `collection_name` (str): Name for the saved collection

**Returns**: Dictionary with collection save status and included modules list.

### `module_restore`
**Description**: Restore a previously saved module collection with automatic environment configuration.

**Parameters**:
- `collection_name` (str): Name of the collection to restore

**Returns**: Dictionary with restoration status and any conflicts or missing modules.

### `module_savelist`
**Description**: List all saved module collections with creation dates and module counts.

**Parameters**: None

**Returns**: Dictionary with list of saved collections and their metadata information.

## Examples

### 1. HPC Development Environment Setup
```
Set up my development environment by loading the latest GCC compiler, Python 3.9, and OpenMPI. Save this configuration as 'dev_env' for future use.
```

**Tools called:**
- `module_avail` - Search for available versions
- `module_load` - Load development tools
- `module_save` - Save configuration as collection

This prompt will:
- Use `module_avail` to find latest versions of GCC, Python, and OpenMPI
- Load required modules using `module_load` with dependency resolution
- Save the configuration using `module_save` for reproducible environments
- Provide complete development environment setup

### 2. Scientific Computing Environment
```
I need to switch from Intel compilers to GNU compilers for my simulation. Show me what's currently loaded, find GNU alternatives, and make the switch safely.
```

**Tools called:**
- `module_list` - Show current environment
- `module_avail` - Find GNU compiler alternatives
- `module_swap` - Switch compiler toolchains
- `module_show` - Verify new configuration

This prompt will:
- List current modules using `module_list`
- Search for GNU alternatives using `module_avail`
- Perform safe compiler switch using `module_swap`
- Verify configuration using `module_show`

### 3. Reproducible Research Environment
```
Create a reproducible environment for my research project by restoring my 'research_v2' module collection and verifying all dependencies are properly loaded.
```

**Tools called:**
- `module_savelist` - List available collections
- `module_restore` - Restore research environment
- `module_list` - Verify loaded modules

This prompt will:
- List available collections using `module_savelist`
- Restore specific environment using `module_restore`
- Verify environment using `module_list`
- Ensure reproducible research conditions

### 4. Module Discovery and Analysis
```
I'm looking for machine learning libraries and frameworks. Search the module system comprehensively and show me detailed information about the most relevant options.
```

**Tools called:**
- `module_spider` - Comprehensive module search
- `module_avail` - Search for ML-related modules
- `module_show` - Get detailed module information

This prompt will:
- Perform comprehensive search using `module_spider`
- Find ML-related modules using `module_avail`
- Extract detailed information using `module_show`
- Provide comprehensive module discovery and analysis

### 5. Environment Cleanup and Optimization
```
Clean up my current module environment by unloading unnecessary modules and optimizing for performance computing workflows.
```

**Tools called:**
- `module_list` - Assess current environment
- `module_show` - Analyze module dependencies
- `module_unload` - Remove unnecessary modules

This prompt will:
- Assess current environment using `module_list`
- Analyze dependencies using `module_show`
- Remove unnecessary modules using `module_unload`
- Optimize environment for performance computing