// MCP data structure for tile-based showcase
export const mcpData = {
  "parquet": {
    "name": "Parquet",
    "category": "Data Processing",
    "description": "Parquet MCP is a comprehensive Model Context Protocol (MCP) server that enables Language Learning Models (LLMs) to access, analyze, and manipulate Parquet columnar data files. This server provides advanced capabilities for efficient data reading, column-based operations, and high-performance analytics with seamless integration with AI coding assistants.",
    "icon": "\ud83d\udccb",
    "actions": [],
    "stats": {
      "version": "1.0.0",
      "updated": "2025-07-24"
    },
    "platforms": [
      "claude",
      "cursor",
      "vscode"
    ],
    "slug": "parquet"
  },
  "node_hardware": {
    "name": "Node-Hardware",
    "category": "Analysis & Visualization",
    "description": "Node Hardware MCP is a Model Context Protocol server that enables LLMs to monitor and analyze system hardware information including CPU specifications, memory usage, disk performance, network interfaces, GPU details, and sensor data for both local and remote nodes via SSH connections, providing comprehensive hardware monitoring and performance analysis capabilities.",
    "icon": "\ud83d\udcbb",
    "actions": [
      "get_cpu_info",
      "get_memory_info",
      "get_system_info",
      "get_disk_info",
      "get_network_info",
      "get_gpu_info",
      "get_sensor_info",
      "get_process_info",
      "get_performance_info",
      "get_remote_node_info",
      "health_check"
    ],
    "stats": {
      "version": "1.0.0",
      "updated": "2025-07-24"
    },
    "platforms": [
      "claude",
      "cursor",
      "vscode"
    ],
    "slug": "node_hardware"
  },
  "arxiv": {
    "name": "Arxiv",
    "category": "Data Processing",
    "description": "ArXiv MCP is a comprehensive Model Context Protocol (MCP) server that enables Language Learning Models (LLMs) to search, analyze, and access research papers from the ArXiv preprint repository. This server provides advanced search capabilities, paper analysis tools, and citation management with seamless integration with AI coding assistants.",
    "icon": "\ud83d\udcc4",
    "actions": [
      "search_arxiv",
      "get_recent_papers",
      "search_papers_by_author",
      "search_by_title",
      "search_by_abstract",
      "search_by_subject",
      "search_date_range",
      "get_paper_details",
      "export_to_bibtex",
      "find_similar_papers",
      "download_paper_pdf",
      "get_pdf_url",
      "download_multiple_pdfs"
    ],
    "stats": {
      "version": "1.0.0",
      "updated": "2025-07-24"
    },
    "platforms": [
      "claude",
      "cursor",
      "vscode"
    ],
    "slug": "arxiv"
  },
  "slurm": {
    "name": "Slurm",
    "category": "System Management",
    "description": "Slurm MCP is a Model Context Protocol server that enables LLMs to manage HPC workloads on Slurm-managed clusters with comprehensive job submission, monitoring, and resource management capabilities, featuring intelligent job scheduling, cluster monitoring, array job support, and interactive node allocation for seamless high-performance computing workflows.",
    "icon": "\ud83d\udda5\ufe0f",
    "actions": [
      "submit_slurm_job",
      "check_job_status",
      "cancel_slurm_job",
      "list_slurm_jobs",
      "get_slurm_info",
      "get_job_details",
      "get_job_output",
      "get_queue_info",
      "submit_array_job",
      "get_node_info",
      "allocate_slurm_nodes",
      "deallocate_slurm_nodes",
      "get_allocation_status"
    ],
    "stats": {
      "version": "1.0.0",
      "updated": "2025-07-24"
    },
    "platforms": [
      "claude",
      "cursor",
      "vscode"
    ],
    "slug": "slurm"
  },
  "plot": {
    "name": "Plot",
    "category": "Data Processing",
    "description": "Plot MCP is a Model Context Protocol server that enables LLMs to create professional data visualizations from CSV and Excel files with intelligent data processing capabilities. The server automatically handles data cleaning, type inference, and missing value processing while supporting multiple visualization types including line plots, bar charts, scatter plots, histograms, and correlation heatmaps.",
    "icon": "\ud83d\udcc8",
    "actions": [
      "line_plot",
      "bar_plot",
      "scatter_plot",
      "histogram_plot",
      "heatmap_plot",
      "data_info"
    ],
    "stats": {
      "version": "0.1.0",
      "updated": "2025-07-24"
    },
    "platforms": [
      "claude",
      "cursor",
      "vscode"
    ],
    "slug": "plot"
  },
  "parallel_sort": {
    "name": "Parallel-Sort",
    "category": "Data Processing",
    "description": "Parallel Sort MCP is a comprehensive Model Context Protocol (MCP) server that enables Language Learning Models (LLMs) to perform high-performance log file processing and analysis operations. This server provides advanced log sorting, filtering, analysis tools, and scalable data processing capabilities with seamless integration with AI coding assistants. Key Features: - Log File Sorting: Timestamp-based sorting with parallel processing for large log files - Advanced Filtering: Multi-condition filtering by time range, log level, keywords, and custom patterns - Pattern Detection: Anomaly detection, error clustering, and trend analysis - Statistical Analysis: Comprehensive log statistics, temporal patterns, and quality metrics - Multiple Export Formats: Support for JSON, CSV, and text output with metadata - Scalable Processing: Handle large log files with memory-efficient chunked processing - MCP Integration: Full Model Context Protocol compliance for seamless LLM integration",
    "icon": "\ud83d\udd04",
    "actions": [
      "sort_log_by_timestamp",
      "parallel_sort_large_file",
      "analyze_log_statistics",
      "detect_log_patterns",
      "filter_logs",
      "filter_by_time_range",
      "filter_by_log_level",
      "filter_by_keyword",
      "apply_filter_preset",
      "export_to_json",
      "export_to_csv",
      "export_to_text",
      "generate_summary_report"
    ],
    "stats": {
      "version": "1.0.0",
      "updated": "2025-07-24"
    },
    "platforms": [
      "claude",
      "cursor",
      "vscode"
    ],
    "slug": "parallel_sort"
  },
  "lmod": {
    "name": "Lmod",
    "category": "System Management",
    "description": "Lmod MCP is a comprehensive Model Context Protocol (MCP) server that enables Language Learning Models (LLMs) to manage environment modules using the Lmod system. This server provides advanced module management capabilities, environment configuration tools, and HPC workflow support with seamless integration with AI coding assistants.",
    "icon": "\ud83d\udce6",
    "actions": [
      "module_list",
      "module_avail",
      "module_show",
      "module_load",
      "module_unload",
      "module_swap",
      "module_spider",
      "module_save",
      "module_restore",
      "module_savelist"
    ],
    "stats": {
      "version": "1.0.0",
      "updated": "2025-07-24"
    },
    "platforms": [
      "claude",
      "cursor",
      "vscode"
    ],
    "slug": "lmod"
  },
  "compression": {
    "name": "Compression",
    "category": "Utilities",
    "description": "Compression MCP is a comprehensive Model Context Protocol (MCP) server that enables Language Learning Models (LLMs) to perform efficient file compression operations using industry-standard algorithms. This server provides high-performance gzip compression with detailed statistics and seamless integration with AI coding assistants.",
    "icon": "\ud83d\udddc\ufe0f",
    "actions": [
      "compress_file"
    ],
    "stats": {
      "version": "1.0.0",
      "updated": "2025-07-24"
    },
    "platforms": [
      "claude",
      "cursor",
      "vscode"
    ],
    "slug": "compression"
  },
  "pandas": {
    "name": "Pandas",
    "category": "Data Processing",
    "description": "Pandas MCP is a Model Context Protocol server that enables LLMs to perform advanced data analysis and manipulation using the powerful Pandas library, featuring comprehensive statistical analysis, data cleaning and transformation, time series operations, multi-format data I/O (CSV, Excel, JSON, Parquet, HDF5), and intelligent data quality assessment for seamless data science workflows.",
    "icon": "\ud83d\udc3c",
    "actions": [
      "load_data",
      "save_data",
      "statistical_summary",
      "correlation_analysis",
      "hypothesis_testing",
      "handle_missing_data",
      "clean_data",
      "groupby_operations",
      "merge_datasets",
      "pivot_table",
      "time_series_operations",
      "validate_data",
      "filter_data",
      "optimize_memory",
      "profile_data"
    ],
    "stats": {
      "version": "1.0.0",
      "updated": "2025-07-24"
    },
    "platforms": [
      "claude",
      "cursor",
      "vscode"
    ],
    "slug": "pandas"
  },
  "chronolog": {
    "name": "Chronolog",
    "category": "Data Processing",
    "description": "ChronoLog MCP is a comprehensive Model Context Protocol (MCP) server that integrates with ChronoLog, a scalable, high-performance distributed shared log store. This server enables Language Learning Models (LLMs) to capture, manage, and retrieve conversational interactions in a structured format with enterprise-grade logging capabilities and real-time event processing.",
    "icon": "\u23f0",
    "actions": [
      "start_chronolog",
      "record_interaction",
      "stop_chronolog",
      "retrieve_interaction"
    ],
    "stats": {
      "version": "1.0.0",
      "updated": "2025-07-24"
    },
    "platforms": [
      "claude",
      "cursor",
      "vscode"
    ],
    "slug": "chronolog"
  },
  "darshan": {
    "name": "Darshan",
    "category": "Utilities",
    "description": "Darshan MCP is a comprehensive Model Context Protocol (MCP) server that enables Language Learning Models (LLMs) to analyze HPC application I/O performance through Darshan profiler trace files. This server provides advanced I/O analysis capabilities, performance bottleneck identification, and comprehensive reporting tools with seamless integration with AI coding assistants.",
    "icon": "\u26a1",
    "actions": [
      "load_darshan_log",
      "get_job_summary",
      "analyze_file_access_patterns",
      "get_io_performance_metrics",
      "analyze_posix_operations",
      "analyze_mpiio_operations",
      "identify_io_bottlenecks",
      "get_timeline_analysis",
      "compare_darshan_logs",
      "generate_io_summary_report",
      "load_darshan_log",
      "get_job_summary",
      "analyze_file_access_patterns",
      "get_io_performance_metrics",
      "analyze_posix_operations",
      "analyze_mpiio_operations",
      "identify_io_bottlenecks",
      "get_timeline_analysis",
      "compare_darshan_logs",
      "generate_io_summary_report"
    ],
    "stats": {
      "version": "0.1.0",
      "updated": "2025-07-24"
    },
    "platforms": [
      "claude",
      "cursor",
      "vscode"
    ],
    "slug": "darshan"
  },
  "hdf5": {
    "name": "Hdf5",
    "category": "Data Processing",
    "description": "HDF5 MCP is a comprehensive Model Context Protocol (MCP) server that enables Language Learning Models (LLMs) to access, analyze, and manipulate HDF5 scientific data files. This server provides advanced capabilities for hierarchical data structure inspection, dataset previewing, and comprehensive data reading with seamless integration with AI coding assistants.",
    "icon": "\ud83d\uddc2\ufe0f",
    "actions": [
      "list_hdf5",
      "inspect_hdf5",
      "preview_hdf5",
      "read_all_hdf5"
    ],
    "stats": {
      "version": "1.0.0",
      "updated": "2025-07-24"
    },
    "platforms": [
      "claude",
      "cursor",
      "vscode"
    ],
    "slug": "hdf5"
  },
  "adios": {
    "name": "Adios",
    "category": "Data Processing",
    "description": "ADIOS MCP is a comprehensive Model Context Protocol (MCP) server that enables Language Learning Models (LLMs) to access and analyze scientific simulation and real-time data through the ADIOS2 framework. This server provides read-only access to BP5 datasets with intelligent data handling and seamless integration with AI coding assistants.",
    "icon": "\ud83d\udcca",
    "actions": [
      "list_bp5",
      "inspect_variables",
      "inspect_variables_at_step",
      "inspect_attributes",
      "read_variable_at_step"
    ],
    "stats": {
      "version": "1.0.0",
      "updated": "2025-07-24"
    },
    "platforms": [
      "claude",
      "cursor",
      "vscode"
    ],
    "slug": "adios"
  },
  "jarvis": {
    "name": "Jarvis",
    "category": "Data Processing",
    "description": "Jarvis MCP is a Model Context Protocol server that enables LLMs to manage the full lifecycle of data-centric pipelines using the Jarvis framework, featuring pipeline creation, package management, configuration updates, environment building, and execution capabilities for high-performance computing and data science workflows.",
    "icon": "\ud83e\udd16",
    "actions": [
      "update_pipeline",
      "build_pipeline_env",
      "create_pipeline",
      "load_pipeline",
      "get_pkg_config",
      "append_pkg",
      "configure_pkg",
      "unlink_pkg",
      "remove_pkg",
      "run_pipeline",
      "destroy_pipeline",
      "jm_create_config",
      "jm_load_config",
      "jm_save_config",
      "jm_set_hostfile",
      "jm_bootstrap_from",
      "jm_bootstrap_list",
      "jm_reset",
      "jm_list_pipelines",
      "jm_cd",
      "jm_list_repos",
      "jm_add_repo",
      "jm_remove_repo",
      "jm_promote_repo",
      "jm_get_repo",
      "jm_construct_pkg",
      "jm_graph_show",
      "jm_graph_build",
      "jm_graph_modify"
    ],
    "stats": {
      "version": "1.0.0",
      "updated": "2025-07-24"
    },
    "platforms": [
      "claude",
      "cursor",
      "vscode"
    ],
    "slug": "jarvis"
  }
};

// Categories with counts and colors
export const categories = {
  "All": {
    "count": 14,
    "color": "#6b7280",
    "icon": "\ud83d\udd0d"
  },
  "Data Processing": {
    "count": 9,
    "color": "#3b82f6",
    "icon": "\ud83d\udcca"
  },
  "Analysis & Visualization": {
    "count": 1,
    "color": "#10b981",
    "icon": "\ud83d\udcc8"
  },
  "System Management": {
    "count": 2,
    "color": "#f59e0b",
    "icon": "\ud83d\udda5\ufe0f"
  },
  "Utilities": {
    "count": 2,
    "color": "#ef4444",
    "icon": "\ud83d\udd27"
  }
};

// Popular MCPs for featured section
export const popularMcps = [
  "jarvis",
  "darshan",
  "pandas",
  "arxiv",
  "slurm",
  "parallel_sort"
];
