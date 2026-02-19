---
title: Paraview MCP
description: "ParaView MCP v1.0.0 - Part of CLIO Kit (IoWarp Platform). 29 tools for scientific 3D visualization: load scientific data, generate isosurfaces, create slices, volume rendering, flow streamlines, color mapping, histogram analysis, ADIOS2/BP5 support. Enables AI agents to create autonomous scientif..."
---

import MCPDetail from '@site/src/components/MCPDetail';

<MCPDetail 
  name="Paraview"
  icon="🔧"
  category="Analysis & Visualization"
  description="ParaView MCP v1.0.0 - Part of CLIO Kit (IoWarp Platform). 29 tools for scientific 3D visualization: load scientific data, generate isosurfaces, create slices, volume rendering, flow streamlines, color mapping, histogram analysis, ADIOS2/BP5 support. Enables AI agents to create autonomous scientific visualizations."
  version="1.0.0"
  actions={["load_scientific_data", "save_contour_as_stl", "create_geometric_shape", "generate_isosurface", "create_data_slice", "configure_volume_display", "toggle_visibility", "set_active_source", "get_active_source_names_by_type", "edit_volume_opacity", "set_color_map", "apply_field_coloring", "compute_surface_area", "set_color_map_preset", "set_representation_type", "get_pipeline", "get_available_arrays", "get_histogram", "generate_flow_streamlines", "take_viewport_screenshot", "show_screenshot_preview", "rotate_camera", "reset_camera", "plot_over_line", "warp_by_vector", "list_commands"]}
  platforms={["claude", "cursor", "vscode"]}
  keywords={["MCP", "ParaView", "visualization", "scientific", "3D"]}
  license="BSD-3-Clause"
  tools={[{"name": "load_scientific_data", "description": "Load scientific datasets (VTK, EXODUS, CSV, RAW, BP5) into ParaView with automatic format detection.", "function_name": "load_scientific_data"}, {"name": "save_contour_as_stl", "description": "Save the active contour or surface as an STL file in the data directory.\n\nArgs:\n    stl_filename: The STL file name to use, defaults to 'contour.stl'.\n\nReturns:\n    Status message.", "function_name": "save_contour_as_stl"}, {"name": "create_geometric_shape", "description": "Create a geometric source (Sphere, Cone, Cylinder, Plane, or Box).\n\nArgs:\n    source_type: Type of source to create.\n\nReturns:\n    Status message with source name.", "function_name": "create_geometric_shape"}, {"name": "generate_isosurface", "description": "Create an isosurface visualization of the active source at the given isovalue.\n\nArgs:\n    value: Isovalue.\n    field: Optional field name to contour by.\n\nReturns:\n    Status message with filter name.", "function_name": "generate_isosurface"}, {"name": "create_data_slice", "description": "Create a slice plane through the loaded volume data.\n\nArgs:\n    origin_x, origin_y, origin_z: Slice origin coordinates (defaults to data center).\n    normal_x, normal_y, normal_z: Normal vector for the slice plane (default [0, 0, 1]).\n\nReturns:\n    Status message with pipeline name.", "function_name": "create_data_slice"}, {"name": "configure_volume_display", "description": "Toggle volume rendering visibility for the active source.\n\nArgs:\n    enable: Whether to show (True) or hide (False) volume rendering.\n\nReturns:\n    Status message with source name.", "function_name": "configure_volume_display"}, {"name": "toggle_visibility", "description": "Toggle visibility for the active source.\n\nArgs:\n    enable: Whether to show (True) or hide (False) the active source.\n\nReturns:\n    Status message with source name.", "function_name": "toggle_visibility"}, {"name": "set_active_source", "description": "Set the active pipeline object by its registered name.\n\nArgs:\n    name: The pipeline source name (e.g., 'Contour1').\n\nReturns:\n    Status message.", "function_name": "set_active_source"}, {"name": "get_active_source_names_by_type", "description": "List pipeline source names, optionally filtered by type.\n\nArgs:\n    source_type: Filter by type (e.g., 'Sphere', 'Contour'). None returns all.\n\nReturns:\n    Formatted list of source names.", "function_name": "get_active_source_names_by_type"}, {"name": "edit_volume_opacity", "description": "Edit the opacity transfer function for a scalar field.\n\nArgs:\n    field_name: The scalar field to modify.\n    opacity_points: List of dicts like [{\"value\": 0.0, \"alpha\": 0.0}, ...].\n\nReturns:\n    Status message.", "function_name": "edit_volume_opacity"}, {"name": "set_color_map", "description": "Set a custom color transfer function for volume rendering.\n\nArgs:\n    field_name: The field/array name in ParaView.\n    color_points: List of dicts: {\"value\": float, \"rgb\": [r, g, b]}.\n\nReturns:\n    Status message.", "function_name": "set_color_map"}, {"name": "apply_field_coloring", "description": "Color the active visualization by a specific data field.\n\nArgs:\n    field: Field name to color by.\n    component: Component index (-1 for magnitude).\n\nReturns:\n    Status message.", "function_name": "apply_field_coloring"}, {"name": "compute_surface_area", "description": "Compute the surface area of the active dataset (must be a surface mesh).\n\nReturns:\n    Status message with area value.", "function_name": "compute_surface_area"}, {"name": "set_color_map_preset", "description": "Apply a predefined color map preset (e.g., Viridis, Plasma, Cool to Warm).\n\nArgs:\n    preset_name: Name of the color map preset.\n\nReturns:\n    Status message.", "function_name": "set_color_map_preset"}, {"name": "set_representation_type", "description": "Set the representation type for the active source (Surface, Wireframe, Points, etc.).\n\nArgs:\n    rep_type: Representation type.\n\nReturns:\n    Status message.", "function_name": "set_representation_type"}, {"name": "get_pipeline", "description": "Get the current visualization pipeline structure.\n\nReturns:\n    Description of the current pipeline.", "function_name": "get_pipeline"}, {"name": "get_available_arrays", "description": "List available data arrays in the active source.\n\nReturns:\n    List of available arrays.", "function_name": "get_available_arrays"}, {"name": "get_histogram", "description": "Compute histogram data for a field in the active source.\n\nArgs:\n    field: Field name (auto-selected if only one exists).\n    num_bins: Number of bins (default: 256).\n    data_location: 'POINTS' or 'CELLS'.\n\nReturns:\n    Formatted histogram data.", "function_name": "get_histogram"}, {"name": "generate_flow_streamlines", "description": "Create streamlines from a vector volume using the StreamTracer filter.\n\nArgs:\n    seed_point_number: Number of seed points to generate.\n    vector_field: Vector field name (auto-detected if None).\n    integration_direction: 'FORWARD', 'BACKWARD', or 'BOTH'.\n    max_steps: Maximum integration steps.\n    initial_step: Initial step length.\n    maximum_step: Maximum streamline length.\n\nReturns:\n    Status message with tube name.", "function_name": "generate_flow_streamlines"}, {"name": "take_viewport_screenshot", "description": "Capture a screenshot of the current ParaView viewport and save it as a timestamped PNG.", "function_name": "take_viewport_screenshot"}, {"name": "show_screenshot_preview", "description": "Capture a screenshot with inline preview using temporary files.", "function_name": "show_screenshot_preview"}, {"name": "rotate_camera", "description": "Rotate the camera by azimuth and elevation angles in degrees.\n\nArgs:\n    azimuth: Rotation around vertical axis.\n    elevation: Rotation around horizontal axis.\n\nReturns:\n    Status message.", "function_name": "rotate_camera"}, {"name": "reset_camera", "description": "Reset the camera to show all data in the viewport.\n\nReturns:\n    Status message.", "function_name": "reset_camera"}, {"name": "plot_over_line", "description": "Create a 'Plot Over Line' filter to sample data between two points.\n\nArgs:\n    point1: Start [x, y, z] coordinates (defaults to data bounds).\n    point2: End [x, y, z] coordinates (defaults to data bounds).\n    resolution: Number of sample points (default: 100).\n\nReturns:\n    Status message.", "function_name": "plot_over_line"}, {"name": "warp_by_vector", "description": "Apply a 'Warp By Vector' filter to the active source.\n\nArgs:\n    vector_field: Vector field name (auto-detected if None).\n    scale_factor: Scale factor for the warp.\n\nReturns:\n    Status message.", "function_name": "warp_by_vector"}, {"name": "list_commands", "description": "List all available commands in this ParaView MCP server.\n\nReturns:\n    List of available commands.", "function_name": "list_commands"}]}
>

### Basic Scientific Data Visualization
```
Load /data/simulation_output.vtk with temperature data, create an isosurface at temperature 300, 
apply Blue to Red color map preset, and take a high-resolution screenshot.
```

### Volume Visualization with Flow Analysis
```
Using /data/fluid_dynamics.bp5, create volume rendering of pressure field with Rainbow color map,
add streamlines to visualize flow patterns, and adjust opacity for better visibility.
```

### Multi-Slice Data Exploration
```
Load /data/medical_scan.vti, get array info to identify density field, create three orthogonal slices 
through the center, color by density field using Viridis preset, and export slices to VTK format.
```

### Advanced ADIOS2/BP5 Analysis
```
Query metadata from /data/checkpoint.bp5 to list available timesteps and variables, 
convert to VTK format, create histogram of temperature distribution, apply threshold filter 
to extract hot regions (>500K), and visualize with appropriate color mapping.
```

### Interactive Camera Control
```
Load /data/molecule.vtk, create isosurface of electron density, rotate camera 45 degrees around Y axis,
zoom in to focus on binding site, set camera position for optimal viewing angle, and save multiple viewpoints.
```

</MCPDetail>

