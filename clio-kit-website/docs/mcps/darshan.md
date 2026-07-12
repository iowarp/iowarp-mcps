---
title: Darshan MCP
description: "Darshan MCP v1.0.0 - Part of CLIO Kit (IoWarp Platform). 10 tools for I/O performance analysis: load traces, analyze access patterns, identify bottlenecks, compare logs. Enables AI agents to analyze HPC application I/O performance."
---

import MCPDetail from '@site/src/components/MCPDetail';

<MCPDetail 
  name="Darshan"
  icon="⚡"
  category="Analysis & Visualization"
  description="Darshan MCP v1.0.0 - Part of CLIO Kit (IoWarp Platform). 10 tools for I/O performance analysis: load traces, analyze access patterns, identify bottlenecks, compare logs. Enables AI agents to analyze HPC application I/O performance."
  version="2.2.3"
  actions={["load_darshan_log", "get_job_summary", "analyze_file_access_patterns", "get_io_performance_metrics", "analyze_posix_operations", "analyze_mpiio_operations", "identify_io_bottlenecks", "get_timeline_analysis", "compare_darshan_logs", "generate_io_summary_report"]}
  platforms={["claude", "cursor", "vscode"]}
  keywords={["darshan", "i/o profiling", "performance analysis", "hpc", "mcp", "iowarp", "grc"]}
  license="BSD-3-Clause"
  tools={[{"name": "load_darshan_log", "description": "Load and parse a Darshan log file to extract I/O performance metrics and metadata.", "function_name": "load_darshan_log"}, {"name": "get_job_summary", "description": "Get job-level summary from a Darshan log including runtime, process count, and I/O volume.", "function_name": "get_job_summary"}, {"name": "analyze_file_access_patterns", "description": "Analyze file access patterns including read/write types and sequential vs random access.", "function_name": "analyze_file_access_patterns"}, {"name": "get_io_performance_metrics", "description": "Extract I/O performance metrics including bandwidth, IOPS, and request sizes.", "function_name": "get_io_performance_metrics"}, {"name": "analyze_posix_operations", "description": "Analyze POSIX I/O operations including read/write system calls and their frequency.", "function_name": "analyze_posix_operations"}, {"name": "analyze_mpiio_operations", "description": "Analyze MPI-IO operations including collective vs independent operations.", "function_name": "analyze_mpiio_operations"}, {"name": "identify_io_bottlenecks", "description": "Identify I/O performance bottlenecks by analyzing access patterns and operations.", "function_name": "identify_io_bottlenecks"}, {"name": "get_timeline_analysis", "description": "Generate timeline analysis showing I/O activity over time and temporal patterns.", "function_name": "get_timeline_analysis"}, {"name": "compare_darshan_logs", "description": "Compare two Darshan log files to identify performance differences between runs.", "function_name": "compare_darshan_logs"}, {"name": "generate_io_summary_report", "description": "Generate a comprehensive I/O summary report with findings and recommendations.", "function_name": "generate_io_summary_report"}]}
>

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

</MCPDetail>

