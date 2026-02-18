"""
ParaView MCP Server

This script runs as a standalone process and:
1. Connects to ParaView using its Python API over network
2. Exposes key ParaView functionality through the MCP protocol
3. Updates visualizations in the existing ParaView viewport

Usage:
1. Start pvserver with --multi-clients flag (e.g., pvserver --multi-clients --server-port=11111)
2. Start ParaView app and connect to the server
3. Configure Claude Desktop to use this script

"""

import os
import sys
import logging
import argparse
from typing import Optional, TYPE_CHECKING

from fastmcp import FastMCP
from fastmcp.exceptions import ToolError
from fastmcp.prompts import Message
from fastmcp.utilities.types import Image
from dotenv import load_dotenv

if TYPE_CHECKING:
    from .implementation.paraview_capabilities import VisualizationEngine

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# Default prompt that instructs Claude how to interact with ParaView
default_prompt = """
When using ParaView through this interface, please follow these guidelines:

1. IMPORTANT: Only call strictly necessary ParaView functions per reply (and please limit the total number of call per reply). This ensures operations execute in a more interative manner and no excessive calls to related but non-essential functions. 

2. The only execute multiple repeated function call when given a target goal (e.g., identify a specific object), where different parameters need to used (e.g., isosurface with different isovalue). Avoid repeated calling of color map function unless user specific ask for color map design.

3. Paraview will be connect to mcp server on starup so no need to connect first.


"""
# Initialize MCP server
mcp: FastMCP = FastMCP(
    "paraview",
    instructions=(
        "Controls ParaView for scientific visualization. "
        "Open data files, apply filters, create renderings, and manage visualization pipelines."
    ),
)

# ParaView manager will be initialized when needed
pv_manager: Optional["VisualizationEngine"] = None
server_host = "localhost"
server_port = 11111


def get_pv_manager() -> "VisualizationEngine":
    """Lazy initialization of ParaView manager with server connection"""
    global pv_manager, server_host, server_port
    if pv_manager is None:
        try:
            from .implementation.paraview_capabilities import VisualizationEngine

            pv_manager = VisualizationEngine(server_host, server_port)

            # Connect to the ParaView server
            logger.info(
                f"Connecting visualization engine to {server_host}:{server_port}"
            )
            success = pv_manager.connect(server_host, server_port)
            if not success:
                logger.error(
                    f"Failed to connect to ParaView server at {server_host}:{server_port}"
                )
                logger.error(
                    "Make sure pvserver is running with: pvserver --multi-clients --server-port=11111"
                )
                raise RuntimeError(
                    f"Could not connect to ParaView server at {server_host}:{server_port}"
                )
            else:
                logger.info("Successfully connected to ParaView server")

        except ImportError as e:
            logger.error(f"Failed to import ParaView: {e}")
            raise RuntimeError(f"ParaView not properly installed: {e}")
    assert pv_manager is not None
    return pv_manager


# ============================================================================
# MCP Tools for ParaView
# ============================================================================


@mcp.tool(
    name="load_scientific_data",
    description="Load scientific datasets (VTK, EXODUS, CSV, RAW, BP5) into ParaView with automatic format detection.",
    annotations={"readOnlyHint": False, "destructiveHint": False, "idempotentHint": False},
    tags={"paraview", "visualization"},
)
async def read_datafile_tool(file_path: str) -> str:
    """Load a data file into ParaView for visualization and analysis.

    Args:
        file_path: Absolute path to the data file.

    Returns:
        Status message with source registration name.
    """
    logger.info(f"Reading datafile from {file_path}")

    # Validate file path exists before attempting to load
    import os

    if not os.path.exists(file_path):
        raise ToolError(f"File not found at path '{file_path}'. Please verify the file path is correct and the file exists.")

    # Get file size for logging and diagnostics
    try:
        file_size = os.path.getsize(file_path)
        logger.info(f"File size: {file_size} bytes")
    except OSError as e:
        logger.warning(f"Could not determine file size: {e}")

    # Attempt to load the data with comprehensive error handling
    success, message, _, source_name = get_pv_manager().read_datafile(file_path)

    if success:
        return f"{message}. Source registered as '{source_name}'. Use this name for pipeline operations."
    else:
        # Provide enhanced error information
        file_ext = os.path.splitext(file_path)[1].lower()
        error_guidance = ""

        if file_ext in [".bp", ".bp5"]:
            error_guidance = "\nFor ADIOS2/BP5 files: Ensure ADIOS2 is installed and ParaView has ADIOS2 support enabled."
        elif file_ext == ".raw":
            error_guidance = "\nFor RAW files: Ensure filename follows format 'name_XxYxZ_datatype.raw' (e.g., 'volume_256x256x256_uint8.raw')."
        elif file_ext in [".vtk", ".vti", ".vtr", ".vts", ".vtu", ".vtp"]:
            error_guidance = "\nFor VTK files: Check if the file is corrupted or uses an unsupported VTK version."

        raise ToolError(f"{message}{error_guidance}")


@mcp.tool(
    annotations={"readOnlyHint": False, "destructiveHint": False, "idempotentHint": False},
    tags={"paraview", "pipeline"},
)
def save_contour_as_stl(stl_filename: str = "contour.stl") -> str:
    """Save the active contour or surface as an STL file in the data directory.

    Args:
        stl_filename: The STL file name to use, defaults to 'contour.stl'.

    Returns:
        Status message.
    """
    success, message, path = get_pv_manager().save_contour_as_stl(stl_filename)
    if not success:
        raise ToolError(message)
    return message


@mcp.tool(
    name="create_geometric_shape",
    annotations={"readOnlyHint": False, "destructiveHint": False, "idempotentHint": False},
    tags={"paraview", "pipeline"},
)
def create_source(source_type: str) -> str:
    """Create a geometric source (Sphere, Cone, Cylinder, Plane, or Box).

    Args:
        source_type: Type of source to create.

    Returns:
        Status message with source name.
    """
    success, message, _, source_name = get_pv_manager().create_source(source_type)
    if success:
        return f"{message}. Source registered as '{source_name}'."
    else:
        raise ToolError(message)


@mcp.tool(
    name="generate_isosurface",
    annotations={"readOnlyHint": False, "destructiveHint": False, "idempotentHint": False},
    tags={"paraview", "pipeline"},
)
def create_isosurface(value: float, field: Optional[str] = None) -> str:
    """Create an isosurface visualization of the active source at the given isovalue.

    Args:
        value: Isovalue.
        field: Optional field name to contour by.

    Returns:
        Status message with filter name.
    """
    success, message, contour_obj, contour_name = get_pv_manager().create_isosurface(
        value, field
    )
    if success:
        return f"{message}. Filter registered as '{contour_name}'."
    else:
        raise ToolError(message)


@mcp.tool(
    name="create_data_slice",
    annotations={"readOnlyHint": False, "destructiveHint": False, "idempotentHint": False},
    tags={"paraview", "pipeline"},
)
def create_slice(
    origin_x: Optional[float] = None,
    origin_y: Optional[float] = None,
    origin_z: Optional[float] = None,
    normal_x: float = 0,
    normal_y: float = 0,
    normal_z: float = 1,
) -> str:
    """Create a slice plane through the loaded volume data.

    Args:
        origin_x, origin_y, origin_z: Slice origin coordinates (defaults to data center).
        normal_x, normal_y, normal_z: Normal vector for the slice plane (default [0, 0, 1]).

    Returns:
        Status message with pipeline name.
    """
    success, message, slice_filter, slice_name = get_pv_manager().create_slice(
        origin_x, origin_y, origin_z, normal_x, normal_y, normal_z
    )

    if success:
        return message
    else:
        raise ToolError(f"Error creating slice: {message}")


@mcp.tool(
    name="configure_volume_display",
    annotations={"readOnlyHint": False, "destructiveHint": False, "idempotentHint": False},
    tags={"paraview", "rendering"},
)
def toggle_volume_rendering(enable: bool = True) -> str:
    """Toggle volume rendering visibility for the active source.

    Args:
        enable: Whether to show (True) or hide (False) volume rendering.

    Returns:
        Status message with source name.
    """
    success, message, source_name = get_pv_manager().create_volume_rendering(enable)
    if success:
        return f"{message}. Source registered as '{source_name}'."
    else:
        raise ToolError(message)


@mcp.tool(
    annotations={"readOnlyHint": False, "destructiveHint": False, "idempotentHint": False},
    tags={"paraview", "rendering"},
)
def toggle_visibility(enable: bool = True) -> str:
    """Toggle visibility for the active source.

    Args:
        enable: Whether to show (True) or hide (False) the active source.

    Returns:
        Status message with source name.
    """
    success, message, source_name = get_pv_manager().toggle_visibility(enable)
    if success:
        return f"{message}. Source registered as '{source_name}'."
    else:
        raise ToolError(message)


@mcp.tool(
    annotations={"readOnlyHint": False, "destructiveHint": False, "idempotentHint": False},
    tags={"paraview", "pipeline"},
)
def set_active_source(name: str) -> str:
    """Set the active pipeline object by its registered name.

    Args:
        name: The pipeline source name (e.g., 'Contour1').

    Returns:
        Status message.
    """
    success, message = get_pv_manager().set_active_source(name)
    if not success:
        raise ToolError(message)
    return message


@mcp.tool(
    annotations={"readOnlyHint": True, "destructiveHint": False, "idempotentHint": True},
    tags={"paraview", "pipeline"},
)
def get_active_source_names_by_type(source_type: Optional[str] = None) -> str:
    """List pipeline source names, optionally filtered by type.

    Args:
        source_type: Filter by type (e.g., 'Sphere', 'Contour'). None returns all.

    Returns:
        Formatted list of source names.
    """
    success, message, source_names = get_pv_manager().get_active_source_names_by_type(
        source_type
    )

    if success and source_names:
        sources_list = "\n- ".join(source_names)
        result = f"{message}:\n- {sources_list}"
        return result
    elif not success:
        raise ToolError(message)
    else:
        return message


# @mcp.tool()
# def edit_volume_opacity(field_name: str, opacity_points: list) -> str:
#     """
#     Edit ONLY the opacity transfer function for the specified field,
#     ensuring we pass only (value, alpha) pairs.

#     [Tips: only needed by volume rendering particularly finetuning the result, likely not needed when the color is ideal, usually the lower value should always have lower opacity]

#     Args:
#         field_name (str): The data array (field) name whose opacity we're adjusting.
#         opacity_points (list of [value, alpha] pairs):
#             Example: [[0.0, 0.0], [50.0, 0.3], [100.0, 1.0]]

#     Returns:
#         A status message (success or error)
#     """
#     success, message = pv_manager.edit_volume_opacity(field_name, opacity_points)
#     return message


@mcp.tool(
    annotations={"readOnlyHint": False, "destructiveHint": False, "idempotentHint": False},
    tags={"paraview", "rendering"},
)
def edit_volume_opacity(field_name: str, opacity_points: list[dict[str, float]]) -> str:
    """Edit the opacity transfer function for a scalar field.

    Args:
        field_name: The scalar field to modify.
        opacity_points: List of dicts like [{"value": 0.0, "alpha": 0.0}, ...].

    Returns:
        Status message.
    """
    formatted_points = [[pt["value"], pt["alpha"]] for pt in opacity_points]
    success, message = get_pv_manager().edit_volume_opacity(
        field_name, formatted_points
    )
    if not success:
        raise ToolError(message)
    return message


# @mcp.tool()
# def set_color_map(field_name: str, color_points: list) -> str:
#     """
#     Sets the color transfer function for the specified field.

#     [Tips: only volume rendering should be using the set_color_map function, the lower values range corresponds to lower density objects, whereas higher values indicate high physical density. When design the color mapping try to assess the object of interest's density first from the default colormap (low value assigned to blue, high value assigned to red) and re-assign customized color accordingly, the order of the color may need to be adjust based on the rendering result. The more solid object should have higher density (!high value range). And a screen_shot should always be taken once this function is called to assess how to adjust the color_map again.]

#     Args:
#         field_name (str): The name of the field/array (as it appears in ParaView).
#         color_points (list of [value, [r, g, b]]):
#             e.g., [[0.0, [0.0, 0.0, 1.0]], [50.0, [0.0, 1.0, 0.0]], [100.0, [1.0, 0.0, 0.0]]]
#             Each element is (value, (r, g, b)) with r,g,b in [0,1].

#     Returns:
#         A status message as a string (e.g., success or error).
#     """
#     success, message = pv_manager.set_color_map(field_name, color_points)
#     return message


@mcp.tool(
    annotations={"readOnlyHint": False, "destructiveHint": False, "idempotentHint": False},
    tags={"paraview", "rendering"},
)
def set_color_map(field_name: str, color_points: list[dict]) -> str:
    """Set a custom color transfer function for volume rendering.

    Args:
        field_name: The field/array name in ParaView.
        color_points: List of dicts: {"value": float, "rgb": [r, g, b]}.

    Returns:
        Status message.
    """
    try:
        formatted_points = [(pt["value"], tuple(pt["rgb"])) for pt in color_points]
    except Exception as e:
        raise ToolError(f"Invalid format for color_points: {e}")

    success, message = get_pv_manager().set_color_map(field_name, formatted_points)
    if not success:
        raise ToolError(message)
    return message


@mcp.tool(
    name="apply_field_coloring",
    annotations={"readOnlyHint": False, "destructiveHint": False, "idempotentHint": False},
    tags={"paraview", "rendering"},
)
def color_by(field: str, component: int = -1) -> str:
    """Color the active visualization by a specific data field.

    Args:
        field: Field name to color by.
        component: Component index (-1 for magnitude).

    Returns:
        Status message.
    """
    success, message = get_pv_manager().color_by(field, component)
    if not success:
        raise ToolError(message)
    return message


@mcp.tool(
    annotations={"readOnlyHint": True, "destructiveHint": False, "idempotentHint": True},
    tags={"paraview", "visualization"},
)
def compute_surface_area() -> str:
    """Compute the surface area of the active dataset (must be a surface mesh).

    Returns:
        Status message with area value.
    """
    success, message, area_value = get_pv_manager().compute_surface_area()
    if not success:
        raise ToolError(message)
    return message


@mcp.tool(
    annotations={"readOnlyHint": False, "destructiveHint": False, "idempotentHint": False},
    tags={"paraview", "rendering"},
)
def set_color_map_preset(preset_name: str = "Cool to Warm") -> str:
    """Apply a predefined color map preset (e.g., Viridis, Plasma, Cool to Warm).

    Args:
        preset_name: Name of the color map preset.

    Returns:
        Status message.
    """
    success, message = get_pv_manager().set_color_map_preset(preset_name)
    if not success:
        raise ToolError(message)
    return message


@mcp.tool(
    annotations={"readOnlyHint": False, "destructiveHint": False, "idempotentHint": False},
    tags={"paraview", "rendering"},
)
def set_representation_type(rep_type: str) -> str:
    """Set the representation type for the active source (Surface, Wireframe, Points, etc.).

    Args:
        rep_type: Representation type.

    Returns:
        Status message.
    """
    success, message = get_pv_manager().set_representation_type(rep_type)
    if not success:
        raise ToolError(message)
    return message


@mcp.tool(
    annotations={"readOnlyHint": True, "destructiveHint": False, "idempotentHint": True},
    tags={"paraview", "pipeline"},
)
def get_pipeline() -> str:
    """Get the current visualization pipeline structure.

    Returns:
        Description of the current pipeline.
    """
    success, message = get_pv_manager().get_pipeline()
    if not success:
        raise ToolError(message)
    return message


@mcp.tool(
    annotations={"readOnlyHint": True, "destructiveHint": False, "idempotentHint": True},
    tags={"paraview", "visualization"},
)
def get_available_arrays() -> str:
    """List available data arrays in the active source.

    Returns:
        List of available arrays.
    """
    success, message = get_pv_manager().get_available_arrays()
    if not success:
        raise ToolError(message)
    return message


@mcp.tool(
    annotations={"readOnlyHint": True, "destructiveHint": False, "idempotentHint": True},
    tags={"paraview", "visualization"},
)
def get_histogram(
    field: Optional[str] = None, num_bins: int = 256, data_location: str = "POINTS"
) -> str:
    """Compute histogram data for a field in the active source.

    Args:
        field: Field name (auto-selected if only one exists).
        num_bins: Number of bins (default: 256).
        data_location: 'POINTS' or 'CELLS'.

    Returns:
        Formatted histogram data.
    """
    success, message, histogram_data = get_pv_manager().get_histogram(
        field, num_bins, data_location
    )

    if success and histogram_data:
        # Format histogram data for display
        hist_summary = f"{message}\n\nHistogram data ({len(histogram_data)} bins):\n"
        # Show first few and last few bins for preview
        preview_count = min(5, len(histogram_data))
        for i in range(preview_count):
            bin_center, frequency = histogram_data[i]
            hist_summary += (
                f"  Bin {i + 1}: value={bin_center:.2f}, count={frequency}\n"
            )

        if len(histogram_data) > preview_count * 2:
            hist_summary += (
                f"  ... ({len(histogram_data) - preview_count * 2} bins omitted) ...\n"
            )
            for i in range(len(histogram_data) - preview_count, len(histogram_data)):
                bin_center, frequency = histogram_data[i]
                hist_summary += (
                    f"  Bin {i + 1}: value={bin_center:.2f}, count={frequency}\n"
                )

        return hist_summary
    else:
        raise ToolError(message)


@mcp.tool(
    name="generate_flow_streamlines",
    annotations={"readOnlyHint": False, "destructiveHint": False, "idempotentHint": False},
    tags={"paraview", "pipeline"},
)
def create_streamline(
    seed_point_number: int,
    vector_field: Optional[str] = None,
    integration_direction: str = "BOTH",
    max_steps: int = 1000,
    initial_step: float = 0.1,
    maximum_step: float = 50.0,
) -> str:
    """Create streamlines from a vector volume using the StreamTracer filter.

    Args:
        seed_point_number: Number of seed points to generate.
        vector_field: Vector field name (auto-detected if None).
        integration_direction: 'FORWARD', 'BACKWARD', or 'BOTH'.
        max_steps: Maximum integration steps.
        initial_step: Initial step length.
        maximum_step: Maximum streamline length.

    Returns:
        Status message with tube name.
    """
    success, message, streamline, tube_name = get_pv_manager().create_stream_tracer(
        vector_field=vector_field,
        base_source=None,
        point_center=None,
        integration_direction=integration_direction,
        initial_step_length=initial_step,
        maximum_stream_length=maximum_step,
        number_of_streamlines=seed_point_number,
    )

    if success:
        return f"{message} Tube registered as '{tube_name}'."
    else:
        raise ToolError(message)


@mcp.tool(
    name="take_viewport_screenshot",
    description="Capture a screenshot of the current ParaView viewport and save it as a timestamped PNG.",
    annotations={"readOnlyHint": True, "destructiveHint": False, "idempotentHint": True},
    tags={"paraview", "rendering"},
)
async def get_screenshot_tool() -> str:
    """Capture a screenshot of the current viewport and save to the working directory.

    Returns:
        File path information.
    """
    import os

    logger.info("Capturing ParaView viewport screenshot")

    current_dir = os.getcwd()
    logger.info(f"Screenshot will be saved to: {current_dir}")

    success, message, img_path = get_pv_manager().get_screenshot()

    if not success:
        logger.error(f"Screenshot capture failed: {message}")
        raise ToolError(f"Screenshot failed: {message}")
    else:
        filename = os.path.basename(img_path)
        logger.info(f"Screenshot saved successfully: {filename}")

        return f"{message}\nSaved in: {current_dir}\nFilename: {filename}"


@mcp.tool(
    name="show_screenshot_preview",
    description="Capture a screenshot with inline preview using temporary files.",
    annotations={"readOnlyHint": True, "destructiveHint": False, "idempotentHint": True},
    tags={"paraview", "rendering"},
)
async def show_screenshot_preview() -> str:
    """Capture a screenshot with inline preview handling.

    Returns:
        Screenshot preview with file path information.
    """
    import os
    import shutil
    import tempfile
    import threading
    import time

    logger.info("Capturing ParaView viewport screenshot with improved preview")

    current_dir = os.getcwd()
    success, message, img_path = get_pv_manager().get_screenshot()

    if not success:
        logger.error(f"Screenshot capture failed: {message}")
        raise ToolError(f"Screenshot failed: {message}")
    else:
        filename = os.path.basename(img_path)
        logger.info(f"Screenshot saved: {filename}")

        temp_preview_path = None
        try:
            with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as temp_file:
                temp_preview_path = temp_file.name

            shutil.copy2(img_path, temp_preview_path)

            def cleanup_preview() -> None:
                time.sleep(30)
                try:
                    if temp_preview_path and os.path.exists(temp_preview_path):
                        os.remove(temp_preview_path)
                        logger.debug(
                            f"Cleaned up preview temp file: {temp_preview_path}"
                        )
                except Exception as e:
                    logger.warning(f"Failed to cleanup preview temp: {e}")

            threading.Thread(target=cleanup_preview, daemon=True).start()

            result = f"Screenshot Preview\nSaved as: {filename}\nLocation: {current_dir}\n\n"
            result += str(Image(path=temp_preview_path))

            return result

        except Exception as e:
            logger.error(f"Failed to create preview: {e}")
            return f"Screenshot saved: {filename}\nLocation: {current_dir}\nPreview failed: {e}"


@mcp.tool(
    annotations={"readOnlyHint": False, "destructiveHint": False, "idempotentHint": False},
    tags={"paraview", "rendering"},
)
def rotate_camera(azimuth: float = 30.0, elevation: float = 0.0) -> str:
    """Rotate the camera by azimuth and elevation angles in degrees.

    Args:
        azimuth: Rotation around vertical axis.
        elevation: Rotation around horizontal axis.

    Returns:
        Status message.
    """
    success, message = get_pv_manager().rotate_camera(azimuth, elevation)
    if not success:
        raise ToolError(message)
    return message


@mcp.tool(
    annotations={"readOnlyHint": False, "destructiveHint": False, "idempotentHint": True},
    tags={"paraview", "rendering"},
)
def reset_camera() -> str:
    """Reset the camera to show all data in the viewport.

    Returns:
        Status message.
    """
    success, message = get_pv_manager().reset_camera()
    if not success:
        raise ToolError(message)
    return message


# @mcp.tool()
# def plot_over_line(point1: list = None, point2: list = None, resolution: int = 100) -> str:
#     """
#     Create a 'Plot Over Line' filter to sample data along a line between two points.

#     Args:
#         point1 (list, optional): The [x, y, z] coordinates of the start point. If None, will use data bounds.
#         point2 (list, optional): The [x, y, z] coordinates of the end point. If None, will use data bounds.
#         resolution (int, optional): Number of sample points along the line (default: 100).

#     Returns:
#         Status message
#     """
#     success, message, plot_filter = pv_manager.plot_over_line(point1, point2, resolution)
#     return message


@mcp.tool(
    annotations={"readOnlyHint": False, "destructiveHint": False, "idempotentHint": False},
    tags={"paraview", "pipeline"},
)
def plot_over_line(
    point1: Optional[list[float]] = None,
    point2: Optional[list[float]] = None,
    resolution: int = 100,
) -> str:
    """Create a 'Plot Over Line' filter to sample data between two points.

    Args:
        point1: Start [x, y, z] coordinates (defaults to data bounds).
        point2: End [x, y, z] coordinates (defaults to data bounds).
        resolution: Number of sample points (default: 100).

    Returns:
        Status message.
    """
    success, message, plot_filter = get_pv_manager().plot_over_line(
        point1, point2, resolution
    )
    if not success:
        raise ToolError(message)
    return message


@mcp.tool(
    annotations={"readOnlyHint": False, "destructiveHint": False, "idempotentHint": False},
    tags={"paraview", "pipeline"},
)
def warp_by_vector(
    vector_field: Optional[str] = None, scale_factor: float = 1.0
) -> str:
    """Apply a 'Warp By Vector' filter to the active source.

    Args:
        vector_field: Vector field name (auto-detected if None).
        scale_factor: Scale factor for the warp.

    Returns:
        Status message.
    """
    success, message, warp_filter = get_pv_manager().warp_by_vector(
        vector_field, scale_factor
    )
    if not success:
        raise ToolError(message)
    return message


@mcp.tool(
    annotations={"readOnlyHint": True, "destructiveHint": False, "idempotentHint": True},
    tags={"paraview", "visualization"},
)
def list_commands() -> str:
    """List all available commands in this ParaView MCP server.

    Returns:
        List of available commands.
    """
    commands = [
        "load_scientific_data: Load scientific datasets from various file formats (VTK, EXODUS, CSV, RAW, BP5, etc.)",
        "create_geometric_shape: Create geometric sources (Sphere, Cone, etc.)",
        "generate_isosurface: Create isosurface visualizations",
        "create_data_slice: Create slices through volume data",
        "configure_volume_display: Enable or disable volume rendering",
        "toggle_visibility: Enable or disable visibility for the active source",
        "set_active_source: Set the active pipeline object by name",
        "get_active_source_names_by_type: Get a list of sources filtered by type",
        "apply_field_coloring: Color the visualization by a field",
        "set_color_map_preset: Apply predefined color schemes (Viridis, Plasma, Cool to Warm, etc.)",
        "set_representation_type: Set the representation type (Surface, Wireframe, etc.)",
        "edit_volume_opacity: Edit the opacity transfer function",
        "set_color_map: Set custom color transfer function for volume rendering",
        "get_pipeline: Get the current pipeline structure",
        "get_available_arrays: Get available data arrays",
        "get_histogram: Compute histogram data for a field in the active source",
        "generate_flow_streamlines: Create streamline visualizations",
        "compute_surface_area: Compute the surface area of the active surface",
        "save_contour_as_stl: Save the active surface as STL",
        "take_viewport_screenshot: Capture screenshot and save to current directory (recommended)",
        "show_screenshot_preview: Capture screenshot with improved inline preview (fixed closing issues)",
        "rotate_camera: Rotate the camera view",
        "reset_camera: Reset the camera to show all data",
        "plot_line: Plot a line through the data",
        "warp_by_vector: Warp the active source by a vector field",
    ]

    return "Available ParaView commands:\n\n" + "\n".join(commands)


@mcp.resource("paraview://capabilities")
def paraview_capabilities() -> dict:
    """ParaView visualization capabilities and supported formats."""
    return {
        "supported_formats": ["VTK", "VTU", "VTS", "PVD", "STL", "OBJ", "PLY"],
        "operations": ["open", "filter", "render", "screenshot", "pipeline management"],
    }


@mcp.prompt()
def visualize_data(file_path: str) -> list[Message]:
    """Guided workflow for creating a ParaView visualization."""
    return [
        Message(
            f"I need to visualize the data file at {file_path}. "
            "Open it in ParaView, apply appropriate filters, create a rendering, "
            "and save a screenshot."
        ),
    ]


def main():
    """
    Main entry point for the ParaView MCP server.
    Supports both stdio and SSE transports based on environment variables.
    """
    # Handle 'help' command (without dashes) by converting to --help
    if len(sys.argv) > 1 and sys.argv[1] == "help":
        sys.argv[1] = "--help"

    parser = argparse.ArgumentParser(
        description="ParaView MCP Server - Scientific visualization server with comprehensive ParaView capabilities",
        prog="paraview-mcp",
    )
    parser.add_argument(
        "--version", action="version", version="ParaView MCP Server v1.0.0"
    )
    parser.add_argument(
        "--transport",
        choices=["stdio", "http"],
        default=None,
        help="Transport type to use (default: stdio)",
    )
    parser.add_argument(
        "--host", default="0.0.0.0", help="Host for HTTP transport (default: 0.0.0.0)"
    )
    parser.add_argument(
        "--port", type=int, default=8000, help="Port for HTTP transport (default: 8000)"
    )
    parser.add_argument(
        "--server",
        type=str,
        default="localhost",
        help="ParaView server hostname (default: localhost)",
    )
    parser.add_argument(
        "--pv-port",
        type=int,
        default=11111,
        help="ParaView server port (default: 11111)",
    )
    parser.add_argument(
        "--paraview_package_path",
        type=str,
        help="Path to the ParaView Python package",
        default=None,
    )

    args = parser.parse_args()

    try:
        logger.info("Starting ParaView MCP Server")

        # Add the ParaView package path to sys.path
        if args.paraview_package_path:
            sys.path.append(args.paraview_package_path)

        # Set ParaView server connection parameters
        global server_host, server_port
        server_host = args.server
        server_port = args.pv_port
        logger.info(f"ParaView server configured: {server_host}:{server_port}")

        # Note: ParaView connection will be established when first tool is called

        transport = args.transport or os.getenv("MCP_TRANSPORT", "stdio")
        if transport == "http":

            mcp.run(transport=transport, host=args.host, port=args.port)

        else:

            mcp.run(transport=transport)

    except Exception as e:
        logger.error(f"Server error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
