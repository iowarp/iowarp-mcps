---
title: Slurm MCP
description: "Slurm MCP v1.0.0 - Part of CLIO Kit (IoWarp Platform). 13 tools for HPC cluster job management: submit jobs, monitor status, allocate nodes, manage queues. Enables AI agents to operate Slurm clusters through natural language."
---

import MCPDetail from '@site/src/components/MCPDetail';

<MCPDetail 
  name="Slurm"
  icon="🖥️"
  category="System Management"
  description="Slurm MCP v1.0.0 - Part of CLIO Kit (IoWarp Platform). 13 tools for HPC cluster job management: submit jobs, monitor status, allocate nodes, manage queues. Enables AI agents to operate Slurm clusters through natural language."
  version="1.0.0"
  actions={["submit_slurm_job", "check_job_status", "cancel_slurm_job", "list_slurm_jobs", "get_slurm_info", "get_job_details", "get_job_output", "get_queue_info", "submit_array_job", "get_node_info", "allocate_slurm_nodes", "deallocate_slurm_nodes", "get_allocation_status"]}
  platforms={["claude", "cursor", "vscode"]}
  keywords={["MCP", "Slurm", "HPC", "job-management", "cluster-monitoring", "workload-management", "scientific-computing", "high-performance-computing"]}
  license="BSD-3-Clause"
  tools={[{"name": "submit_slurm_job", "description": "Submit a job script to the Slurm scheduler with resource requirements.", "function_name": "submit_slurm_job"}, {"name": "check_job_status", "description": "Check the status of a Slurm job by its ID.", "function_name": "check_job_status"}, {"name": "cancel_slurm_job", "description": "Cancel a running or pending Slurm job.", "function_name": "cancel_slurm_job"}, {"name": "list_slurm_jobs", "description": "List Slurm jobs with optional filtering by user and state.", "function_name": "list_slurm_jobs"}, {"name": "get_slurm_info", "description": "Get Slurm cluster configuration, partitions, and resource availability.", "function_name": "get_slurm_info"}, {"name": "get_job_details", "description": "Get detailed information about a specific Slurm job.", "function_name": "get_job_details"}, {"name": "get_job_output", "description": "Retrieve stdout or stderr output from a Slurm job.", "function_name": "get_job_output"}, {"name": "get_queue_info", "description": "Get Slurm queue status and partition information.", "function_name": "get_queue_info"}, {"name": "submit_array_job", "description": "Submit a Slurm array job for parallel task execution.", "function_name": "submit_array_job"}, {"name": "get_node_info", "description": "Get information about Slurm cluster nodes and their resources.", "function_name": "get_node_info"}, {"name": "allocate_slurm_nodes", "description": "Allocate Slurm nodes for an interactive session using salloc.", "function_name": "allocate_slurm_nodes"}, {"name": "deallocate_slurm_nodes", "description": "Release a Slurm node allocation by canceling it.", "function_name": "deallocate_slurm_nodes"}, {"name": "get_allocation_status", "description": "Check the status of a Slurm node allocation.", "function_name": "get_allocation_status"}]}
>

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

</MCPDetail>

