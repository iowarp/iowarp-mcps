---
title: Jarvis MCP
description: "Jarvis MCP is a Model Context Protocol server that enables LLMs to manage the full lifecycle of data-centric pipelines using the Jarvis framework, featuring pipeline creation, package management, configuration updates, environment building, and execution capabilities for high-performance computin..."
---

import MCPDetail from '@site/src/components/MCPDetail';

<MCPDetail 
  name="Jarvis"
  icon="🤖"
  category="Data Processing"
  description="Jarvis MCP is a Model Context Protocol server that enables LLMs to manage the full lifecycle of data-centric pipelines using the Jarvis framework, featuring pipeline creation, package management, configuration updates, environment building, and execution capabilities for high-performance computing and data science workflows."
  version="1.0.0"
  actions={["update_pipeline", "build_pipeline_env", "create_pipeline", "load_pipeline", "get_pkg_config", "append_pkg", "configure_pkg", "unlink_pkg", "remove_pkg", "run_pipeline", "destroy_pipeline", "jm_create_config", "jm_load_config", "jm_save_config", "jm_set_hostfile", "jm_bootstrap_from", "jm_bootstrap_list", "jm_reset", "jm_list_pipelines", "jm_cd", "jm_list_repos", "jm_add_repo", "jm_remove_repo", "jm_promote_repo", "jm_get_repo", "jm_construct_pkg", "jm_graph_show", "jm_graph_build", "jm_graph_modify"]}
  platforms={["claude", "cursor", "vscode"]}
  keywords={["jarvis", "pipeline-management", "high-performance-computing", "hpc", "workflow", "data-pipelines", "scientific-computing", "mcp", "package-management"]}
  license="MIT"
  tools={[{"name": "update_pipeline", "description": "Re-apply environment & configuration to every package in a Jarvis-CD pipeline.", "function_name": "update_pipeline_tool"}, {"name": "build_pipeline_env", "description": "Rebuild a Jarvis-CD pipeline\u2019s env.yaml, capturing only CMAKE_PREFIX_PATH and PATH", "function_name": "build_pipeline_env_tool"}, {"name": "create_pipeline", "description": "Create a new Jarvis-CD pipeline environment.", "function_name": "create_pipeline_tool"}, {"name": "load_pipeline", "description": "Load an existing Jarvis-CD pipeline environment.", "function_name": "load_pipeline_tool"}, {"name": "get_pkg_config", "description": "Retrieve the configuration of a specific package in a Jarvis-CD pipeline.", "function_name": "get_pkg_config_tool"}, {"name": "append_pkg", "description": "Append a package to a Jarvis-CD pipeline.", "function_name": "append_pkg_tool"}, {"name": "configure_pkg", "description": "Configure a package in a Jarvis-CD pipeline.", "function_name": "configure_pkg_tool"}, {"name": "unlink_pkg", "description": "Unlink a package from a Jarvis-CD pipeline (preserve files).", "function_name": "unlink_pkg_tool"}, {"name": "remove_pkg", "description": "Remove a package entirely from a Jarvis-CD pipeline.", "function_name": "remove_pkg_tool"}, {"name": "run_pipeline", "description": "Execute a Jarvis-CD pipeline end-to-end.", "function_name": "run_pipeline_tool"}, {"name": "destroy_pipeline", "description": "Destroy a Jarvis-CD pipeline environment and clean up files.", "function_name": "destroy_pipeline_tool"}, {"name": "jm_create_config", "description": "Initialize JarvisManager config directories.", "function_name": "jm_create_config"}, {"name": "jm_load_config", "description": "Load existing JarvisManager configuration.", "function_name": "jm_load_config"}, {"name": "jm_save_config", "description": "Save current JarvisManager configuration.", "function_name": "jm_save_config"}, {"name": "jm_set_hostfile", "description": "Set hostfile path for JarvisManager.", "function_name": "jm_set_hostfile"}, {"name": "jm_bootstrap_from", "description": "Bootstrap Jarvis config from a machine template.", "function_name": "jm_bootstrap_from"}, {"name": "jm_bootstrap_list", "description": "List available bootstrap machine templates.", "function_name": "jm_bootstrap_list"}, {"name": "jm_reset", "description": "Reset JarvisManager (destroy all pipelines and data).", "function_name": "jm_reset"}, {"name": "jm_list_pipelines", "description": "List all existing Jarvis pipelines.", "function_name": "jm_list_pipelines"}, {"name": "jm_cd", "description": "Change current Jarvis pipeline context.", "function_name": "jm_cd"}, {"name": "jm_list_repos", "description": "List all Jarvis repositories.", "function_name": "jm_list_repos"}, {"name": "jm_add_repo", "description": "Add a repository to JarvisManager.", "function_name": "jm_add_repo"}, {"name": "jm_remove_repo", "description": "Remove a repository from JarvisManager.", "function_name": "jm_remove_repo"}, {"name": "jm_promote_repo", "description": "Promote a repository in JarvisManager.", "function_name": "jm_promote_repo"}, {"name": "jm_get_repo", "description": "Get repository info from JarvisManager.", "function_name": "jm_get_repo"}, {"name": "jm_construct_pkg", "description": "Construct a package skeleton in JarvisManager.", "function_name": "jm_construct_pkg"}, {"name": "jm_graph_show", "description": "Print the current resource graph frames.", "function_name": "jm_graph_show"}, {"name": "jm_graph_build", "description": "Build or rebuild the resource graph with a net sleep interval.", "function_name": "jm_graph_build"}, {"name": "jm_graph_modify", "description": "Modify the resource graph using a net sleep interval.", "function_name": "jm_graph_modify"}]}
>

### 1. Pipeline Creation and Basic Management
```
I need to set up a new HPC pipeline called "performance_test" for running performance benchmarks. Initialize the Jarvis configuration, create the pipeline, and add the IOR package to it.
```

**Tools called:**
- `jm_create_config` - Initialize Jarvis configuration directories
- `create_pipeline` - Create new pipeline environment  
- `append_pkg` - Add IOR package to the pipeline

This prompt will:
- Initialize Jarvis with proper configuration directories
- Create a new pipeline for performance testing
- Add the IOR I/O benchmarking package with default settings
- Prepare the pipeline for further configuration and execution

### 2. Package Configuration and Environment Setup
```
For the "performance_test" pipeline, configure the IOR package to use 16 processes, then build the pipeline environment and execute it.
```

**Tools called:**
- `get_pkg_config` - Retrieve current IOR package configuration
- `configure_pkg` - Configure IOR package with 16 processes
- `build_pipeline_env` - Build pipeline execution environment
- `run_pipeline` - Execute the configured pipeline

This prompt will:
- Display current package configuration settings
- Update IOR package to use 16 processes for the benchmark
- Build the complete pipeline environment with all dependencies
- Execute the pipeline end-to-end with proper resource allocation

### 3. Repository Management and Package Discovery
```
Show me all available repositories in the system, add a new custom repository at "/path/to/custom/repo", and promote it to higher priority for package resolution.
```

**Tools called:**
- `jm_list_repos` - List all configured repositories
- `jm_add_repo` - Add custom repository to the system
- `jm_promote_repo` - Promote repository to higher priority

This prompt will:
- Display all currently configured repositories with their status
- Add a new repository to expand available packages
- Promote the custom repository for prioritized package discovery
- Update the system configuration with the new repository settings

### 4. Advanced Pipeline Operations and Package Management
```
Create a comprehensive workflow: list all existing pipelines, load pipeline "data_analysis", show configuration of the "pandas" package, update its memory settings to 32GB, and rebuild the environment.
```

**Tools called:**
- `jm_list_pipelines` - List all existing pipelines
- `load_pipeline` - Load the data_analysis pipeline
- `get_pkg_config` - Show pandas package configuration  
- `configure_pkg` - Update memory settings for pandas package
- `update_pipeline` - Re-apply configurations to all packages
- `build_pipeline_env` - Rebuild environment with new settings

This prompt will:
- Show all available pipelines in the system
- Load the specific data analysis pipeline
- Display current pandas package configuration
- Update memory allocation for the pandas package
- Ensure all package configurations are current and consistent
- Rebuild the execution environment with optimized settings

### 5. Resource Monitoring and System Management
```
I need to monitor system resources and manage pipeline contexts. Show me the current resource graph, build a new resource graph with 2.0 second intervals, and set "hpc_workflow" as the current working pipeline.
```

**Tools called:**
- `jm_graph_show` - Display current resource graph frames
- `jm_graph_build` - Build resource graph with custom intervals
- `jm_cd` - Change current pipeline context

This prompt will:
- Display the current system resource graph for monitoring
- Build an updated resource graph with 2.0 second monitoring intervals
- Set the HPC workflow as the active working pipeline
- Provide comprehensive system resource visibility and management

### 6. Package Lifecycle Management
```
For troubleshooting purposes, I need to unlink the "tensorflow" package from "ml_pipeline" without deleting files, then completely remove the "outdated_tool" package, and finally destroy the "test_pipeline" entirely.
```

**Tools called:**
- `unlink_pkg` - Unlink tensorflow package while preserving files
- `remove_pkg` - Completely remove outdated_tool package  
- `destroy_pipeline` - Destroy entire test pipeline and cleanup

This prompt will:
- Safely unlink tensorflow package preserving data and configurations
- Completely remove outdated tools with full cleanup
- Destroy test pipeline and clean up all associated resources
- Provide safe package and pipeline lifecycle management

### 7. Configuration Management and Bootstrapping
```
Initialize a new Jarvis setup by listing available bootstrap templates, bootstrap from "cluster_template", save the configuration, and create a package skeleton for a "mpi_application" type.
```

**Tools called:**
- `jm_bootstrap_list` - List available bootstrap machine templates
- `jm_bootstrap_from` - Bootstrap configuration from cluster template
- `jm_save_config` - Save current configuration state
- `jm_construct_pkg` - Create MPI application package skeleton

This prompt will:
- Show all available system templates for quick setup
- Bootstrap Jarvis configuration from a cluster-optimized template  
- Persist the configuration for future use
- Generate a complete package skeleton for MPI applications
- Provide rapid deployment capabilities for HPC environments

### 8. System Reset and Repository Information
```
I need to perform maintenance on the Jarvis system: get detailed information about the "hpc_tools" repository, then perform a complete system reset to clean state for testing.
```

**Tools called:**
- `jm_get_repo` - Get detailed repository information
- `jm_reset` - Reset entire Jarvis system to clean state

This prompt will:
- Retrieve comprehensive information about the specified repository
- Perform complete system reset destroying all pipelines and configurations
- Provide clean slate for testing and development
- Ensure system maintenance and troubleshooting capabilities

### 9. Advanced Resource Graph Management
```
Set up comprehensive resource monitoring by modifying the resource graph with 1.5 second intervals, then display the updated graph frames for analysis.
```

**Tools called:**
- `jm_graph_modify` - Modify resource graph with custom intervals
- `jm_graph_show` - Display current resource graph frames

This prompt will:
- Modify the existing resource graph with optimized monitoring intervals
- Display the updated resource graph for comprehensive system analysis
- Provide advanced resource monitoring and performance tracking
- Enable real-time system resource visualization and management

### 10. Complete Pipeline Lifecycle with Configuration Management
```
Load my existing configuration, set hostfile to "/etc/hosts.cluster", remove the deprecated "old_repo" repository, and create a comprehensive workflow pipeline.
```

**Tools called:**
- `jm_load_config` - Load existing Jarvis configuration
- `jm_set_hostfile` - Configure hostfile for deployments
- `jm_remove_repo` - Remove deprecated repository
- `create_pipeline` - Create new comprehensive workflow pipeline

This prompt will:
- Load existing system configuration and settings
- Configure cluster hostfile for distributed deployments
- Remove outdated repository to clean system state
- Create a new pipeline ready for comprehensive workflow management
- Provide complete system configuration and lifecycle management

##### 1. **Initialize Jarvis**

The first step is to initialize Jarvis. This prepares the system for interaction.

```bash
```

</MCPDetail>

