---
title: Slurm MCP
description: "MCP server for Slurm workload management and HPC job scheduling"
---

import MCPDetail from '@site/src/components/MCPDetail';

<MCPDetail
  name="Slurm"
  icon="🖥️"
  category="System Management"
  description="MCP server for Slurm workload management and HPC job scheduling"
  version="3.0.0"
  actions={["slurm_submit", "slurm_list", "slurm_describe", "slurm_cluster", "slurm_cancel"]}
  platforms={["claude", "cursor", "vscode"]}
  keywords={["MCP", "Slurm", "HPC", "job-management", "cluster-monitoring", "workload-management", "scientific-computing", "high-performance-computing"]}
  license="BSD-3-Clause"
  tools={[{"name": "slurm_submit", "description": "Submit one Slurm job or array and return its scheduler-native job ID. Set array only for an array submission.", "function_name": "slurm_submit"}, {"name": "slurm_list", "description": "List a bounded number of Slurm jobs with optional user, state, and partition filters. Returns native IDs and explicit truncation state.", "function_name": "slurm_list"}, {"name": "slurm_describe", "description": "Describe one scheduler-native Slurm job: lifecycle state, terminality, scheduler properties, and optional bounded stdout/stderr tails.", "function_name": "slurm_describe"}, {"name": "slurm_cluster", "description": "Inspect bounded Slurm partition and queue records in one snapshot. Node details are excluded by default and bounded when requested.", "function_name": "slurm_cluster"}, {"name": "slurm_cancel", "description": "Request destructive cancellation of one Slurm job. confirm_job_id must exactly repeat job_id; omission or mismatch is rejected without calling scancel.", "function_name": "slurm_cancel"}]}
>

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

</MCPDetail>
