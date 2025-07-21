# HDF5 MCP - Scientific Data Access for LLMs


## Description

HDF5 MCP is a comprehensive Model Context Protocol (MCP) server that enables Language Learning Models (LLMs) to access, analyze, and manipulate HDF5 scientific data files. This server provides advanced capabilities for hierarchical data structure inspection, dataset previewing, and comprehensive data reading with seamless integration with AI coding assistants.

**Key Features:**
- **Comprehensive HDF5 Access**: Full support for HDF5 file inspection, structure analysis, and data extraction
- **Intelligent Data Processing**: Automatic detection of groups, datasets, and attributes with metadata extraction
- **Flexible Data Operations**: File listing, structure inspection, data previewing, and complete dataset reading
- **Scientific Computing Support**: Multi-dimensional arrays, hierarchical data structures, and attribute handling
- **Performance Optimization**: Efficient data access with configurable preview limits and memory management
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
    "hdf5-mcp": {
      "command": "uvx",
      "args": ["iowarp-mcps", "hdf5"]
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
    "hdf5-mcp": {
      "type": "stdio",
      "command": "uvx",
      "args": ["iowarp-mcps", "hdf5"]
    }
  }
}
```

</details>

<details>
<summary><b>Install in Claude Code</b></summary>

Run this command. See [Claude Code MCP docs](https://docs.anthropic.com/en/docs/agents-and-tools/claude-code/tutorials#set-up-model-context-protocol-mcp) for more info.

```sh
claude mcp add hdf5-mcp -- uvx iowarp-mcps hdf5
```

</details>

<details>
<summary><b>Install in Claude Desktop</b></summary>

Add this to your Claude Desktop `claude_desktop_config.json` file. See [Claude Desktop MCP docs](https://modelcontextprotocol.io/quickstart/user) for more info.

```json
{
  "mcpServers": {
    "hdf5-mcp": {
      "command": "uvx",
      "args": ["iowarp-mcps", "hdf5"]
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
uv --directory=$CLONE_DIR/iowarp-mcps/mcps/HDF5 run hdf5-mcp --help
```

**Windows CMD:**
```cmd
set CLONE_DIR=%cd%
git clone https://github.com/iowarp/iowarp-mcps.git
uv --directory=%CLONE_DIR%\iowarp-mcps\mcps\HDF5 run hdf5-mcp --help
```

**Windows PowerShell:**
```powershell
$env:CLONE_DIR=$PWD
git clone https://github.com/iowarp/iowarp-mcps.git
uv --directory=$env:CLONE_DIR\iowarp-mcps\mcps\HDF5 run hdf5-mcp --help
```

</details>

## Available Actions

### `list_hdf5`
**Description**: List all HDF5 files in a specified directory with comprehensive file discovery and metadata extraction for scientific data management.

**Parameters**:
- `directory` (str, optional): Path to directory containing HDF5 files (default: "data/")

**Returns**: List of HDF5 files (.h5 and .hdf5 extensions) with file paths and basic metadata information.

### `inspect_hdf5`
**Description**: Inspect HDF5 file structure including detailed analysis of groups, datasets, and attributes for comprehensive data understanding.

**Parameters**:
- `filename` (str): Absolute path to HDF5 file

**Returns**: Detailed structure information including group hierarchy, dataset properties, attribute metadata, and data organization.

### `preview_hdf5`
**Description**: Preview first N elements of each dataset in an HDF5 file with configurable data sampling for efficient data exploration.

**Parameters**:
- `filename` (str): Absolute path to HDF5 file
- `count` (int, optional): Number of elements to preview from each dataset (default: 10)

**Returns**: Preview data from all datasets with specified element count, including data types and sample values.

### `read_all_hdf5`
**Description**: Read every element of every dataset in an HDF5 file with complete data extraction and memory-efficient processing.

**Parameters**:
- `filename` (str): Absolute path to HDF5 file

**Returns**: Complete dataset contents with all elements, maintaining original data structure and types.

## Examples

### 1. Scientific Data Structure Analysis
```
I have an HDF5 file containing simulation results at /data/climate_simulation.h5. Can you analyze its structure and show me what datasets are available?
```

**Tools called:**
- `inspect_hdf5` - Analyze the HDF5 file structure and organization
- `list_hdf5` - Discover available HDF5 files in the directory

This prompt will:
- Use `inspect_hdf5` to analyze the file structure, groups, and datasets
- Provide detailed information about data organization and attributes
- Offer insights into the simulation data architecture and available parameters

### 2. Multi-File Scientific Data Discovery
```
Explore my research data directory at /research/experiments/ to find all HDF5 files, then inspect the structure of the most recent experimental data file.
```

**Tools called:**
- `list_hdf5` - Discover all HDF5 files in the research directory
- `inspect_hdf5` - Analyze structure of selected experimental data file

This prompt will:
- Use `list_hdf5` to discover all available HDF5 files in the research directory
- Select and inspect the structure of experimental data using `inspect_hdf5`
- Provide comprehensive overview of research data organization and contents

### 3. Data Preview and Validation
```
Before processing the large dataset at /data/sensor_measurements.hdf5, I want to preview the first 20 data points from each sensor dataset to validate the data quality.
```

**Tools called:**
- `preview_hdf5` - Preview first 20 elements from each dataset
- `inspect_hdf5` - Get detailed dataset information

This prompt will:
- Use `preview_hdf5` with count=20 to sample data from each sensor dataset
- Provide data validation insights using `inspect_hdf5` for structure analysis
- Enable quality assessment before full-scale data processing

### 4. Complete Dataset Analysis
```
I need to perform comprehensive analysis on the experimental results stored in /experiments/trial_001.h5. Extract all data from every dataset for statistical processing.
```

**Tools called:**
- `read_all_hdf5` - Read complete datasets for analysis
- `inspect_hdf5` - Get dataset metadata and structure information

This prompt will:
- Use `read_all_hdf5` to extract complete dataset contents
- Provide structure analysis using `inspect_hdf5` for context
- Enable comprehensive statistical analysis and data processing workflows

### 5. Scientific Data Exploration Workflow
```
Help me understand the contents of my computational fluid dynamics results directory at /cfd/simulations/. Show me all HDF5 files, inspect their structures, and preview key datasets.
```

**Tools called:**
- `list_hdf5` - Discover all HDF5 files in simulation directory
- `inspect_hdf5` - Analyze structure of simulation files
- `preview_hdf5` - Preview key simulation datasets

This prompt will:
- Use `list_hdf5` to discover all CFD simulation files
- Analyze file structures using `inspect_hdf5` for each simulation
- Preview key datasets using `preview_hdf5` to understand simulation outputs
- Provide comprehensive overview of computational results and data organization

### 6. Research Data Management
```
I'm organizing my laboratory data stored in HDF5 format at /lab/measurements/. List all files, inspect their structures, and provide detailed previews of measurement datasets.
```

**Tools called:**
- `list_hdf5` - Inventory all HDF5 files in laboratory directory
- `inspect_hdf5` - Detailed structure analysis of measurement files
- `preview_hdf5` - Preview measurement datasets for quality assessment

This prompt will:
- Use `list_hdf5` to create comprehensive inventory of laboratory data files
- Analyze measurement file structures using `inspect_hdf5` for metadata extraction
- Preview measurement data using `preview_hdf5` for data quality validation
- Support research data management and organization workflows