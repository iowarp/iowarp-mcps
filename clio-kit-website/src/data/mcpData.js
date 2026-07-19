// MCP data structure for tile-based showcase
export const mcpData = {
  "agentic_search": {
    "name": "Agentic Search",
    "category": "Search & Retrieval",
    "description": "Hybrid retrieval engine. Lexical, vector, graph, and scientific search over namespaced document corpora. DuckDB storage. FastAPI service with async job queue.",
    "icon": "\ud83d\udd0d",
    "actions": [
      "query",
      "index",
      "list_documents",
      "submit_index_job",
      "get_job_status",
      "cancel_job",
      "health",
      "metrics"
    ],
    "stats": {
      "version": "1.0.0",
      "updated": "2026-02-23"
    },
    "platforms": [
      "claude",
      "cursor",
      "vscode"
    ],
    "slug": "agentic_search",
    "docPath": "/docs/agentic-search"
  },
  "adios": {
    "name": "Adios",
    "category": "Data Processing",
    "description": "Fetch and analyze BP5 data files using ADIOS2. Access scientific data, metadata, and attributes for research and analysis purposes.",
    "icon": "\ud83d\udcca",
    "actions": [
      "list_bp5",
      "inspect_variables",
      "inspect_variables_at_step",
      "inspect_attributes",
      "read_variable_at_step"
    ],
    "stats": {
      "version": "2.2.3",
      "updated": "2026-07-18"
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
    "description": "ArXiv MCP server implementation using Model Context Protocol",
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
      "version": "2.2.3",
      "updated": "2026-07-18"
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
    "description": "ChronoLog MCP server implementation using Model Context Protocol",
    "icon": "\u23f0",
    "actions": [
      "start_chronolog",
      "record_interaction",
      "stop_chronolog",
      "retrieve_interaction"
    ],
    "stats": {
      "version": "2.0.1",
      "updated": "2026-07-18"
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
    "description": "Compression MCP server implementation using Model Context Protocol",
    "icon": "\ud83d\udddc\ufe0f",
    "actions": [
      "compress_file_tool",
      "decompress_file_tool"
    ],
    "stats": {
      "version": "2.2.3",
      "updated": "2026-07-18"
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
    "description": "Darshan I/O profiler MCP server for analyzing I/O trace files",
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
      "version": "2.2.3",
      "updated": "2026-07-18"
    },
    "platforms": [
      "claude",
      "cursor",
      "vscode"
    ],
    "slug": "darshan"
  },
  "geo": {
    "name": "Geo",
    "category": "Data Processing",
    "description": "MCP server for rendering GeoJSON vector layers into map images with basemaps",
    "icon": "\ud83d\udd27",
    "actions": [
      "render_feature_map",
      "points_in_polygons",
      "bounding_box",
      "query_arcgis_features",
      "geocode",
      "filter_points_by_radius"
    ],
    "stats": {
      "version": "2.2.3",
      "updated": "2026-07-18"
    },
    "platforms": [
      "claude",
      "cursor",
      "vscode"
    ],
    "slug": "geo"
  },
  "geojson": {
    "name": "Geojson",
    "category": "Utilities",
    "description": "MCP server for inspecting, validating, and summarizing GeoJSON documents (stdlib only)",
    "icon": "\ud83d\udd27",
    "actions": [
      "inspect_geojson",
      "validate_geojson",
      "summarize_geojson",
      "feature_bbox"
    ],
    "stats": {
      "version": "2.2.3",
      "updated": "2026-07-18"
    },
    "platforms": [
      "claude",
      "cursor",
      "vscode"
    ],
    "slug": "geojson"
  },
  "hdf5": {
    "name": "Hdf5",
    "category": "Data Processing",
    "description": "HDF5 FastMCP - Scientific Data Access for AI Agents | CLIO Kit MCP Server",
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
      "version": "2.2.3",
      "updated": "2026-07-18"
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
    "description": "JARVIS-CD MCP with a compact user pipeline contract and explicit admin compatibility profiles",
    "icon": "\ud83e\udd16",
    "actions": [
      "jarvis_create_pipeline",
      "jarvis_describe",
      "jarvis_add_step",
      "jarvis_edit_step",
      "jarvis_run",
      "jarvis_get_execution"
    ],
    "stats": {
      "version": "3.5.2",
      "updated": "2026-07-18"
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
    "description": "Lmod MCP - Environment Module Management for LLMs with comprehensive module operations",
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
      "version": "2.2.3",
      "updated": "2026-07-18"
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
    "description": "National Data Platform (NDP) MCP server for searching and discovering datasets across multiple CKAN instances",
    "icon": "\ud83d\udd27",
    "actions": [
      "list_organizations",
      "search_datasets",
      "get_dataset_details",
      "stage_resource"
    ],
    "stats": {
      "version": "2.2.3",
      "updated": "2026-07-18"
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
    "description": "Node Hardware MCP - Comprehensive Hardware Monitoring and System Analysis for LLMs with real-time performance metrics",
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
      "version": "2.2.3",
      "updated": "2026-07-18"
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
    "description": "Pandas MCP - Advanced Data Analysis for LLMs with comprehensive pandas operations",
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
      "profile_data",
      "profile_csv"
    ],
    "stats": {
      "version": "2.2.3",
      "updated": "2026-07-18"
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
    "description": "Parallel Sort MCP - High-Performance Log File Processing for LLMs with advanced sorting and analysis",
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
      "version": "2.2.3",
      "updated": "2026-07-18"
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
    "description": "MCP server for ParaView scientific visualization",
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
      "version": "2.2.3",
      "updated": "2026-07-18"
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
    "description": "MCP server for Apache Parquet files",
    "icon": "\ud83d\udccb",
    "actions": [
      "summarize_tool",
      "read_slice_tool",
      "get_column_preview_tool",
      "aggregate_column_tool"
    ],
    "stats": {
      "version": "2.2.3",
      "updated": "2026-07-18"
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
    "description": "MCP server for advanced data visualization and plotting operations",
    "icon": "\ud83d\udcc8",
    "actions": [
      "line_plot",
      "bar_plot",
      "scatter_plot",
      "histogram_plot",
      "heatmap_plot",
      "plot_timeseries",
      "data_info"
    ],
    "stats": {
      "version": "2.2.3",
      "updated": "2026-07-18"
    },
    "platforms": [
      "claude",
      "cursor",
      "vscode"
    ],
    "slug": "plot"
  },
  "sac": {
    "name": "Sac",
    "category": "Analysis & Visualization",
    "description": "MCP server for analyzing SAC seismic-waveform files and TAR archives: inspect members, compute per-trace statistics, and plot traces",
    "icon": "\ud83d\udd27",
    "actions": [
      "inspect_archive",
      "compute_trace_statistics",
      "plot_traces"
    ],
    "stats": {
      "version": "2.2.3",
      "updated": "2026-07-18"
    },
    "platforms": [
      "claude",
      "cursor",
      "vscode"
    ],
    "slug": "sac"
  },
  "scientific_catalog": {
    "name": "Scientific-Catalog",
    "category": "Data Processing",
    "description": "Operator-owned scientific dataset discovery for remote agents",
    "icon": "\ud83d\udd27",
    "actions": [
      "scientific_dataset_search",
      "scientific_dataset_describe"
    ],
    "stats": {
      "version": "1.1.2",
      "updated": "2026-07-18"
    },
    "platforms": [
      "claude",
      "cursor",
      "vscode"
    ],
    "slug": "scientific_catalog"
  },
  "seismic": {
    "name": "Seismic",
    "category": "Analysis & Visualization",
    "description": "MCP server for earthquake-sequence analysis on saved catalogs: completeness magnitude, Gutenberg-Richter b-value, Bath gap, Omori decay, and a three-panel figure",
    "icon": "\ud83d\udd27",
    "actions": [
      "analyze_sequence",
      "plot_sequence"
    ],
    "stats": {
      "version": "2.2.3",
      "updated": "2026-07-18"
    },
    "platforms": [
      "claude",
      "cursor",
      "vscode"
    ],
    "slug": "seismic"
  },
  "slurm": {
    "name": "Slurm",
    "category": "System Management",
    "description": "MCP server for Slurm workload management and HPC job scheduling",
    "icon": "\ud83d\udda5\ufe0f",
    "actions": [
      "slurm_submit",
      "slurm_list",
      "slurm_describe",
      "slurm_cluster",
      "slurm_cancel"
    ],
    "stats": {
      "version": "3.0.0",
      "updated": "2026-07-18"
    },
    "platforms": [
      "claude",
      "cursor",
      "vscode"
    ],
    "slug": "slurm"
  },
  "spack": {
    "name": "Spack",
    "category": "Utilities",
    "description": "Structured Spack discovery and installation tools for scientific agents",
    "icon": "\ud83d\udd27",
    "actions": [
      "spack_find",
      "spack_locate",
      "spack_install"
    ],
    "stats": {
      "version": "2.1.0",
      "updated": "2026-07-18"
    },
    "platforms": [
      "claude",
      "cursor",
      "vscode"
    ],
    "slug": "spack"
  },
  "terrain": {
    "name": "Terrain",
    "category": "Analysis & Visualization",
    "description": "MCP server for terrain analysis: DEM slope/aspect/suitability and point-cloud reading/gridding",
    "icon": "\ud83d\udd27",
    "actions": [
      "dem_terrain",
      "pointcloud_read"
    ],
    "stats": {
      "version": "2.2.3",
      "updated": "2026-07-18"
    },
    "platforms": [
      "claude",
      "cursor",
      "vscode"
    ],
    "slug": "terrain"
  }
};

// Categories with counts and colors
export const categories = {
  "All": {
    "count": 24,
    "color": "#6b7280",
    "icon": "\ud83d\udd0d"
  },
  "Analysis & Visualization": {
    "count": 6,
    "color": "#10b981",
    "icon": "\ud83d\udcc8"
  },
  "Data Processing": {
    "count": 12,
    "color": "#3b82f6",
    "icon": "\ud83d\udcca"
  },
  "Search & Retrieval": {
    "count": 1,
    "color": "#6366f1",
    "icon": "\ud83d\udd0d"
  },
  "System Management": {
    "count": 2,
    "color": "#f59e0b",
    "icon": "\ud83d\udda5\ufe0f"
  },
  "Utilities": {
    "count": 3,
    "color": "#ef4444",
    "icon": "\ud83d\udd27"
  }
};

// Popular MCPs for featured section
export const popularMcps = [
  "hdf5",
  "paraview",
  "pandas",
  "arxiv",
  "parallel_sort",
  "node_hardware"
];

// Category type mappings
export const categoryTypes = {
  "Data Processing": "data",
  "Analysis & Visualization": "analysis",
  "Search & Retrieval": "search",
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
