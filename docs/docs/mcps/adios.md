---
title: Adios MCP
description: "ADIOS MCP is a comprehensive Model Context Protocol (MCP) server that enables Language Learning Models (LLMs) to access and analyze scientific simulation and real-time data through the ADIOS2 framework. This server provides read-only access to BP5 datasets with intelligent data handling and seaml..."
---

import MCPDetail from '@site/src/components/MCPDetail';

<MCPDetail 
  name="Adios"
  icon="📊"
  category="Data Processing"
  description="ADIOS MCP is a comprehensive Model Context Protocol (MCP) server that enables Language Learning Models (LLMs) to access and analyze scientific simulation and real-time data through the ADIOS2 framework. This server provides read-only access to BP5 datasets with intelligent data handling and seamless integration with AI coding assistants."
  version="1.0.0"
  actions={["list_bp5", "inspect_variables", "inspect_variables_at_step", "inspect_attributes", "read_variable_at_step"]}
  platforms={["claude", "cursor", "vscode"]}
  keywords={["mcp", "adios2", "bp5", "scientific data", "data access", "variable inspection", "attribute extraction"]}
  license="MIT"
  tools={[{"name": "list_bp5", "description": "Lists all BP5 files in a given directory, the bp5 files are actually directories so both file and directory words are correct. The 'directory' parameter must be an absolute path.", "function_name": "list_bp5_tool"}, {"name": "inspect_variables", "description": "Inspects variables in a BP5 file. If variable_name is provided, returns data for that specific variable. Otherwise, shows type, shape, and steps for all variables. The 'filename' parameter must be an absolute path to the BP5 file.", "function_name": "inspect_variables_tool"}, {"name": "inspect_variables_at_step", "description": "Inspects a specific variable at a given step in a BP5 file. Shows variable type, shape, min, max. All parameters are required. The 'filename' must be an absolute path.", "function_name": "inspect_variables_at_step_tool"}, {"name": "inspect_attributes", "description": "Reads global or variable-specific attributes from a BP5 file. The 'filename' parameter must be an absolute path. The 'variable_name' is optional.", "function_name": "inspect_attributes_tool"}, {"name": "read_variable_at_step", "description": "Reads a named variable at a specific step from a BP5 file. All parameters are required. The 'filename' must be an absolute path.", "function_name": "read_variable_at_step_tool"}]}
>

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

</MCPDetail>

