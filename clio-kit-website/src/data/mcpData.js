// MCP data structure for tile-based showcase
export const mcpData = {
  "adios": {
    "name": "Adios",
    "category": "Data Processing",
    "description": "Read BP5 files. Inspect variables. Check attributes. Read at timestep. 5 tools for ADIOS2 scientific data I/O.",
    "icon": "\ud83d\udcca",
    "actions": [],
    "stats": {
      "version": "1.0.0",
      "updated": "2026-02-19"
    },
    "platforms": [
      "claude",
      "cursor",
      "vscode"
    ],
    "slug": "adios"
  },
  "arxiv": {
    "name": "Arxiv",
    "category": "Data Processing",
    "description": "Search papers. Download PDFs. Export BibTeX. Find by author, title, date, subject. 13 tools for academic research. ArXiv.org integration through AI.",
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
      "updated": "2026-02-19"
    },
    "platforms": [
      "claude",
      "cursor",
      "vscode"
    ],
    "slug": "arxiv"
  },
  "chronolog": {
    "name": "Chronolog",
    "category": "Data Processing",
    "description": "Start logging sessions. Record AI interactions. Stop and save. Retrieve historical data. 4 tools for distributed logging on HPC systems.",
    "icon": "\u23f0",
    "actions": [],
    "stats": {
      "version": "1.0.0",
      "updated": "2026-02-19"
    },
    "platforms": [
      "claude",
      "cursor",
      "vscode"
    ],
    "slug": "chronolog"
  },
  "compression": {
    "name": "Compression",
    "category": "Utilities",
    "description": "Compress files with GZIP. Reduce storage. Fast compression. Decompress archives. 1 simple tool for file compression operations.",
    "icon": "\ud83d\udddc\ufe0f",
    "actions": [
      "compress_file_tool",
      "decompress_file_tool"
    ],
    "stats": {
      "version": "1.0.0",
      "updated": "2026-02-19"
    },
    "platforms": [
      "claude",
      "cursor",
      "vscode"
    ],
    "slug": "compression"
  },
  "darshan": {
    "name": "Darshan",
    "category": "Analysis & Visualization",
    "description": "Load logs. Analyze I/O patterns. Identify bottlenecks. Performance metrics. Compare runs. 10 tools for I/O profiling. Darshan log analysis via AI.",
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
      "generate_io_summary_report"
    ],
    "stats": {
      "version": "1.0.0",
      "updated": "2026-02-19"
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
    "description": "Read HDF5 files. Explore datasets. Extract data. AI-powered insights. Parallel batch ops (4-8x faster). LRU cache (1000x faster). 27 tools for scientific HDF5 data.",
    "icon": "\ud83d\uddc2\ufe0f",
    "actions": [
      "open_file",
      "close_file",
      "get_filename",
      "get_mode",
      "get_by_path",
      "list_keys",
      "visit",
      "read_full_dataset",
      "read_partial_dataset",
      "get_shape",
      "get_dtype",
      "get_size",
      "get_chunks",
      "read_attribute",
      "list_attributes",
      "hdf5_parallel_scan",
      "hdf5_batch_read",
      "hdf5_stream_data",
      "hdf5_aggregate_stats",
      "analyze_dataset_structure",
      "find_similar_datasets",
      "suggest_next_exploration",
      "identify_io_bottlenecks",
      "optimize_access_pattern",
      "refresh_hdf5_resources",
      "list_available_hdf5_files",
      "export_dataset"
    ],
    "stats": {
      "version": "1.0.0",
      "updated": "2026-02-19"
    },
    "platforms": [
      "claude",
      "cursor",
      "vscode"
    ],
    "slug": "hdf5"
  },
  "jarvis": {
    "name": "Jarvis",
    "category": "Data Processing",
    "description": "Create pipelines. Build environments. Configure packages. Run workflows. 27 tools for data pipeline management. Jarvis-CD integration for HPC.",
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
      "updated": "2026-02-19"
    },
    "platforms": [
      "claude",
      "cursor",
      "vscode"
    ],
    "slug": "jarvis"
  },
  "lmod": {
    "name": "Lmod",
    "category": "System Management",
    "description": "Load modules. Swap environments. Save collections. Spider search. 10 tools for environment module management on HPC clusters.",
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
      "updated": "2026-02-19"
    },
    "platforms": [
      "claude",
      "cursor",
      "vscode"
    ],
    "slug": "lmod"
  },
  "ndp": {
    "name": "Ndp",
    "category": "Data Processing",
    "description": "List organizations. Search datasets. Get metadata. Discover research data through CKAN API. 3 tools for dataset discovery and exploration.",
    "icon": "\ud83d\udd27",
    "actions": [
      "list_organizations",
      "search_datasets",
      "get_dataset_details"
    ],
    "stats": {
      "version": "1.0.0",
      "updated": "2026-02-19"
    },
    "platforms": [
      "claude",
      "cursor",
      "vscode"
    ],
    "slug": "ndp"
  },
  "node_hardware": {
    "name": "Node-Hardware",
    "category": "Analysis & Visualization",
    "description": "CPU info. Memory stats. GPU details. Disk usage. Network metrics. 11 tools for hardware monitoring. Real-time system analysis.",
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
      "updated": "2026-02-19"
    },
    "platforms": [
      "claude",
      "cursor",
      "vscode"
    ],
    "slug": "node_hardware"
  },
  "pandas": {
    "name": "Pandas",
    "category": "Data Processing",
    "description": "Load CSV/Excel/Parquet. Statistical analysis. Data cleaning. Correlations. Groupby operations. Time series. 15 tools for tabular data. Pandas through natural language.",
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
      "updated": "2026-02-19"
    },
    "platforms": [
      "claude",
      "cursor",
      "vscode"
    ],
    "slug": "pandas"
  },
  "parallel_sort": {
    "name": "Parallel-Sort",
    "category": "Data Processing",
    "description": "Sort massive log files. Parallel processing. Pattern detection. Time-range filtering. Export JSON/CSV. 13 tools for large file operations.",
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
      "updated": "2026-02-19"
    },
    "platforms": [
      "claude",
      "cursor",
      "vscode"
    ],
    "slug": "parallel_sort"
  },
  "paraview": {
    "name": "Paraview",
    "category": "Analysis & Visualization",
    "description": "Load scientific data. Generate isosurfaces. Create data slices. Volume rendering. Flow streamlines. 12 tools for 3D scientific visualization with ADIOS2/BP5 support.",
    "icon": "\ud83d\udd27",
    "actions": [
      "load_scientific_data",
      "save_contour_as_stl",
      "create_geometric_shape",
      "generate_isosurface",
      "create_data_slice",
      "configure_volume_display",
      "toggle_visibility",
      "set_active_source",
      "get_active_source_names_by_type",
      "edit_volume_opacity",
      "set_color_map",
      "apply_field_coloring",
      "compute_surface_area",
      "set_color_map_preset",
      "set_representation_type",
      "get_pipeline",
      "get_available_arrays",
      "get_histogram",
      "generate_flow_streamlines",
      "take_viewport_screenshot",
      "show_screenshot_preview",
      "rotate_camera",
      "reset_camera",
      "plot_over_line",
      "warp_by_vector",
      "list_commands"
    ],
    "stats": {
      "version": "1.0.0",
      "updated": "2026-02-19"
    },
    "platforms": [
      "claude",
      "cursor",
      "vscode"
    ],
    "slug": "paraview"
  },
  "parquet": {
    "name": "Parquet",
    "category": "Data Processing",
    "description": "Read columnar data. Write Parquet files. Schema inspection. Pandas integration. Efficient for large datasets. Apache Parquet format operations.",
    "icon": "\ud83d\udccb",
    "actions": [
      "summarize_tool",
      "read_slice_tool",
      "get_column_preview_tool",
      "aggregate_column_tool"
    ],
    "stats": {
      "version": "1.0.0",
      "updated": "2026-02-19"
    },
    "platforms": [
      "claude",
      "cursor",
      "vscode"
    ],
    "slug": "parquet"
  },
  "plot": {
    "name": "Plot",
    "category": "Data Processing",
    "description": "Generate line plots. Create bar charts. Scatter visualizations. Histograms and heatmaps. 6 plotting tools for CSV data visualization through AI.",
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
      "version": "1.0.0",
      "updated": "2026-02-19"
    },
    "platforms": [
      "claude",
      "cursor",
      "vscode"
    ],
    "slug": "plot"
  },
  "slurm": {
    "name": "Slurm",
    "category": "System Management",
    "description": "Submit jobs. Check status. Allocate nodes. Read output. Full HPC cluster management through AI assistants. 13 tools for Slurm workload manager.",
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
      "updated": "2026-02-19"
    },
    "platforms": [
      "claude",
      "cursor",
      "vscode"
    ],
    "slug": "slurm"
  }
};

// Categories with counts and colors
export const categories = {
  "All": {
    "count": 16,
    "color": "#6b7280",
    "icon": "\ud83d\udd0d"
  },
  "Data Processing": {
    "count": 10,
    "color": "#3b82f6",
    "icon": "\ud83d\udcca"
  },
  "Utilities": {
    "count": 1,
    "color": "#ef4444",
    "icon": "\ud83d\udd27"
  },
  "Analysis & Visualization": {
    "count": 3,
    "color": "#10b981",
    "icon": "\ud83d\udcc8"
  },
  "System Management": {
    "count": 2,
    "color": "#f59e0b",
    "icon": "\ud83d\udda5\ufe0f"
  }
};

// Popular MCPs for featured section
export const popularMcps = [
  "jarvis",
  "hdf5",
  "paraview",
  "pandas",
  "arxiv",
  "parallel_sort"
];

// Category type mappings
export const categoryTypes = {
  "Data Processing": "data",
  "Analysis & Visualization": "analysis",
  "System Management": "system",
  "Utilities": "util"
};

// GitHub repository statistics
export const githubStats = {
  "stars": 0,
  "forks": 0,
  "watchers": 0,
  "url": "https://github.com/iowarp/clio-kit"
};

// MCP endorsements and badges
export const mcpEndorsement = {
  "hdf5": [
    "flagship",
    "v1.0"
  ],
  "slurm": [
    "hpc"
  ],
  "arxiv": [
    "research"
  ],
  "pandas": [
    "data"
  ]
};
