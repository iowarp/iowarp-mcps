# ParaView MCP Server

[![License: BSD-3-Clause](https://img.shields.io/badge/License-BSD--3--Clause-blue.svg)](https://opensource.org/licenses/BSD-3-Clause)
[![PyPI version](https://img.shields.io/pypi/v/paraview-mcp.svg)](https://pypi.org/project/paraview-mcp/)
[![Python](https://img.shields.io/badge/Python-3.10%2B-blue)](https://www.python.org/)

**Part of [CLIO Kit](https://toolkit.iowarp.ai/) - Gnosis Research Center**

ParaView MCP is a Model Context Protocol server that enables LLMs to create scientific 3D visualizations using ParaView through natural language commands. Features autonomous visualization, native ADIOS2/BP5 support, visual feedback, and no programming required.

## Quick Start

```bash
uvx clio-kit mcp-server paraview
```

---

## 🛠️ Installation

### Requirements

- Python 3.10 or higher
- [uv](https://docs.astral.sh/uv/) package manager (recommended)
- ParaView installation

<details>
<summary><b>Install in Cursor</b></summary>

Go to: `Settings` -> `Cursor Settings` -> `MCP` -> `Add new global MCP server`

Pasting the following configuration into your Cursor `~/.cursor/mcp.json` file is the recommended approach. You may also install in a specific project by creating `.cursor/mcp.json` in your project folder. See [Cursor MCP docs](https://docs.cursor.com/context/model-context-protocol) for more info.

```json
{
  "mcpServers": {
    "paraview-mcp": {
      "command": "uvx",
      "args": ["clio-kit", "mcp-server", "paraview"]
    }
  }
}
```

</details>

<details>
<summary><b>Install in VS Code</b></summary>

Add this to your VS Code MCP config file. See [VS Code MCP docs](https://code.visualstudio.com/docs/copilot/chat/mcp-servers) for more info.

```json
"mcp": {
  "servers": {
    "paraview-mcp": {
      "type": "stdio",
      "command": "uvx",
      "args": ["clio-kit", "mcp-server", "paraview"]
    }
  }
}
```

</details>

<details>
<summary><b>Install in Claude Code</b></summary>

Run this command. See [Claude Code MCP docs](https://docs.anthropic.com/en/docs/agents-and-tools/claude-code/tutorials#set-up-model-context-protocol-mcp) for more info.

```sh
claude mcp add paraview-mcp -- uvx clio-kit mcp-server paraview
```

</details>

<details>
<summary><b>Install in Claude Desktop</b></summary>

Add this to your Claude Desktop `claude_desktop_config.json` file. See [Claude Desktop MCP docs](https://modelcontextprotocol.io/quickstart/user) for more info.

```json
{
  "mcpServers": {
    "paraview-mcp": {
      "command": "uvx",
      "args": ["clio-kit", "mcp-server", "paraview"]
    }
  }
}
```

</details>

<details>
<summary><b>Manual Setup</b></summary>

**Linux/macOS:**
```bash
CLONE_DIR=$(pwd)
git clone https://github.com/iowarp/clio-kit.git
uv --directory=$CLONE_DIR/clio-kit/clio-kit-mcp-servers/paraview run paraview-mcp --help
```

**Windows CMD:**
```cmd
set CLONE_DIR=%cd%
git clone https://github.com/iowarp/clio-kit.git
uv --directory=%CLONE_DIR%\clio-kit\clio-kit-mcp-servers\paraview run paraview-mcp --help
```

**Windows PowerShell:**
```powershell
$env:CLONE_DIR=$PWD
git clone https://github.com/iowarp/clio-kit.git
uv --directory=$env:CLONE_DIR\clio-kit\clio-kit-mcp-servers\paraview run paraview-mcp --help
```

</details>

## How to Install ParaView

### Option 1: Automated Installation

```bash
# One-command setup - installs and configures everything
uv run automate-setup
```

This automatically installs system dependencies, builds ParaView with ADIOS2 support, configures Python integration, and verifies installation.

**Time:** ~1-2 hours (mostly automated)

### Option 2: Quick Install with Conda

```bash
# Install ParaView and ADIOS2 via conda
conda install -c conda-forge paraview adios2
uv run configure-paraview
```

### Option 3: System Packages

```bash
# Ubuntu/Debian
sudo apt install paraview python3-paraview libadios2-dev
uv run configure-paraview
```

## How to Run ParaView Server

### Find Your ParaView Installation
```bash
find ~ -name "pvserver" -type f 2>/dev/null | head -5
find ~ -name "paraview" -type f 2>/dev/null | head -5
```

### Start ParaView Server
```bash
# Method 1: Using project scripts (recommended)
uv run paraview-server

# Method 2: Direct command (replace with your actual path)
PARAVIEW_PATH=$(find ~ -name "pvserver" -type f 2>/dev/null | head -1)
$(dirname "$PARAVIEW_PATH")/pvserver --multi-clients --server-port=11111
```

**Expected output:** `Waiting for client...` and `Accepting connection(s): hostname:11111`

## How to Run ParaView GUI

### Start ParaView GUI
```bash
# Method 1: Using project scripts (recommended)
uv run paraview-gui

# Method 2: Direct command (replace with your actual path)
PARAVIEW_GUI=$(find ~ -name "paraview" -type f 2>/dev/null | head -1)
$PARAVIEW_GUI
```

### Connect GUI to Server
1. Open ParaView GUI
2. Go to **File** → **Connect**
3. Select **Add Server**
4. Name: `localhost`, Host: `localhost`, Port: `11111`
5. Click **Connect**

## Capabilities

### `load_scientific_data`
**Description**: Load scientific datasets (VTK, EXODUS, CSV, RAW, BP5) into ParaView with automatic format detection.
**Tags**: paraview, visualization

### `save_contour_as_stl`
**Description**: Save the active contour or surface as an STL file in the data directory.

Args:
    stl_filename: The STL file name to use, defaults to 'contour.stl'.

Returns:
    Status message.
**Tags**: paraview, pipeline

### `create_geometric_shape`
**Description**: Create a geometric source (Sphere, Cone, Cylinder, Plane, or Box).

Args:
    source_type: Type of source to create.

Returns:
    Status message with source name.
**Tags**: paraview, pipeline

### `generate_isosurface`
**Description**: Create an isosurface visualization of the active source at the given isovalue.

Args:
    value: Isovalue.
    field: Optional field name to contour by.

Returns:
    Status message with filter name.
**Tags**: paraview, pipeline

### `create_data_slice`
**Description**: Create a slice plane through the loaded volume data.

Args:
    origin_x, origin_y, origin_z: Slice origin coordinates (defaults to data center).
    normal_x, normal_y, normal_z: Normal vector for the slice plane (default [0, 0, 1]).

Returns:
    Status message with pipeline name.
**Tags**: paraview, pipeline

### `configure_volume_display`
**Description**: Toggle volume rendering visibility for the active source.

Args:
    enable: Whether to show (True) or hide (False) volume rendering.

Returns:
    Status message with source name.
**Tags**: paraview, rendering

### `toggle_visibility`
**Description**: Toggle visibility for the active source.

Args:
    enable: Whether to show (True) or hide (False) the active source.

Returns:
    Status message with source name.
**Tags**: paraview, rendering

### `set_active_source`
**Description**: Set the active pipeline object by its registered name.

Args:
    name: The pipeline source name (e.g., 'Contour1').

Returns:
    Status message.
**Tags**: paraview, pipeline

### `get_active_source_names_by_type`
**Description**: List pipeline source names, optionally filtered by type.

Args:
    source_type: Filter by type (e.g., 'Sphere', 'Contour'). None returns all.

Returns:
    Formatted list of source names.
**Hints**: read-only, idempotent
**Tags**: paraview, pipeline

### `edit_volume_opacity`
**Description**: Edit the opacity transfer function for a scalar field.

Args:
    field_name: The scalar field to modify.
    opacity_points: List of dicts like [{"value": 0.0, "alpha": 0.0}, ...].

Returns:
    Status message.
**Tags**: paraview, rendering

### `set_color_map`
**Description**: Set a custom color transfer function for volume rendering.

Args:
    field_name: The field/array name in ParaView.
    color_points: List of dicts: {"value": float, "rgb": [r, g, b]}.

Returns:
    Status message.
**Tags**: paraview, rendering

### `apply_field_coloring`
**Description**: Color the active visualization by a specific data field.

Args:
    field: Field name to color by.
    component: Component index (-1 for magnitude).

Returns:
    Status message.
**Tags**: paraview, rendering

### `compute_surface_area`
**Description**: Compute the surface area of the active dataset (must be a surface mesh).

Returns:
    Status message with area value.
**Hints**: read-only, idempotent
**Tags**: paraview, visualization

### `set_color_map_preset`
**Description**: Apply a predefined color map preset (e.g., Viridis, Plasma, Cool to Warm).

Args:
    preset_name: Name of the color map preset.

Returns:
    Status message.
**Tags**: paraview, rendering

### `set_representation_type`
**Description**: Set the representation type for the active source (Surface, Wireframe, Points, etc.).

Args:
    rep_type: Representation type.

Returns:
    Status message.
**Tags**: paraview, rendering

### `get_pipeline`
**Description**: Get the current visualization pipeline structure.

Returns:
    Description of the current pipeline.
**Hints**: read-only, idempotent
**Tags**: paraview, pipeline

### `get_available_arrays`
**Description**: List available data arrays in the active source.

Returns:
    List of available arrays.
**Hints**: read-only, idempotent
**Tags**: paraview, visualization

### `get_histogram`
**Description**: Compute histogram data for a field in the active source.

Args:
    field: Field name (auto-selected if only one exists).
    num_bins: Number of bins (default: 256).
    data_location: 'POINTS' or 'CELLS'.

Returns:
    Formatted histogram data.
**Hints**: read-only, idempotent
**Tags**: paraview, visualization

### `generate_flow_streamlines`
**Description**: Create streamlines from a vector volume using the StreamTracer filter.

Args:
    seed_point_number: Number of seed points to generate.
    vector_field: Vector field name (auto-detected if None).
    integration_direction: 'FORWARD', 'BACKWARD', or 'BOTH'.
    max_steps: Maximum integration steps.
    initial_step: Initial step length.
    maximum_step: Maximum streamline length.

Returns:
    Status message with tube name.
**Tags**: paraview, pipeline

### `take_viewport_screenshot`
**Description**: Capture a screenshot of the current ParaView viewport and save it as a timestamped PNG.
**Hints**: read-only, idempotent
**Tags**: paraview, rendering

### `show_screenshot_preview`
**Description**: Capture a screenshot with inline preview using temporary files.
**Hints**: read-only, idempotent
**Tags**: paraview, rendering

### `rotate_camera`
**Description**: Rotate the camera by azimuth and elevation angles in degrees.

Args:
    azimuth: Rotation around vertical axis.
    elevation: Rotation around horizontal axis.

Returns:
    Status message.
**Tags**: paraview, rendering

### `reset_camera`
**Description**: Reset the camera to show all data in the viewport.

Returns:
    Status message.
**Hints**: idempotent
**Tags**: paraview, rendering

### `plot_over_line`
**Description**: Create a 'Plot Over Line' filter to sample data between two points.

Args:
    point1: Start [x, y, z] coordinates (defaults to data bounds).
    point2: End [x, y, z] coordinates (defaults to data bounds).
    resolution: Number of sample points (default: 100).

Returns:
    Status message.
**Tags**: paraview, pipeline

### `warp_by_vector`
**Description**: Apply a 'Warp By Vector' filter to the active source.

Args:
    vector_field: Vector field name (auto-detected if None).
    scale_factor: Scale factor for the warp.

Returns:
    Status message.
**Tags**: paraview, pipeline

### `list_commands`
**Description**: List all available commands in this ParaView MCP server.

Returns:
    List of available commands.
**Hints**: read-only, idempotent
**Tags**: paraview, visualization

### Resources

- `paraview://capabilities` - ParaView visualization capabilities and supported formats.

### Prompts

- **visualize_data**: Guided workflow for creating a ParaView visualization.
## Claude Code

```bash
claude mcp add clio-paraview -- uvx clio-kit paraview
```

Or install via the CLIO Kit plugin marketplace:

```
/plugin marketplace add iowarp/clio-kit
/plugin install clio-paraview@iowarp-clio-kit
```
## Claude Desktop

Add to your Claude Desktop config (`claude_desktop_config.json`):

```json
{
  "mcpServers": {
    "clio-paraview": {
      "command": "uvx",
      "args": [
        "clio-kit",
        "paraview"
      ]
    }
  }
}
```
## Gemini CLI

Add to `~/.gemini/settings.json`:

```json
{
  "mcpServers": {
    "clio-paraview": {
      "command": "uvx",
      "args": [
        "clio-kit",
        "paraview"
      ]
    }
  }
}
```

Or install the CLIO Kit extension:

```bash
gemini extensions install https://github.com/iowarp/clio-kit
```
## Examples

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

---

## Credits and Attribution

### Original Inspiration
This project builds upon concepts from the original LLNL ParaView MCP work:

**Original work**: [LLNL ParaView MCP](https://github.com/LLNL/paraview_mcp)  
**Authors**: Shusen Liu, Haichao Miao (LLNL)

### Dependencies
- **ParaView**: [Kitware ParaView](https://www.paraview.org/) - Open-source scientific visualization
- **ADIOS2**: [ORNL ADIOS2](https://adios2.readthedocs.io/) - Adaptable I/O System
- **FastMCP**: [FastMCP Framework](https://github.com/jlowin/fastmcp) - Model Context Protocol implementation

## Documentation

- **Full Documentation**: [CLIO Kit Website](https://toolkit.iowarp.ai/)
- **Installation Guide**: See [INSTALLATION.md](../../../CLAUDE.md#setup--installation)
- **Contributing**: See [Contribution Guide](https://github.com/iowarp/clio-kit/wiki/Contribution)
- **Detailed Setup**: See [USAGE_README.md](./USAGE_README.md) for complete ParaView installation and configuration

## License

BSD-3-Clause with proper attribution to original LLNL work
