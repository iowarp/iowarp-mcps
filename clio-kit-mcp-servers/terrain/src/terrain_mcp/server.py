#!/usr/bin/env python3
"""Terrain MCP server.

Generic terrain-analysis tools: analyze a Digital Elevation Model (DEM) for
elevation, slope, aspect, and site suitability; and read an x/y/z point cloud,
gridding it into a DEM-like surface for downstream analysis.

Base formats (CSV / NPY / NPZ) work with only numpy installed. GeoTIFF DEMs
need the optional ``rasterio`` extra and LAS/LAZ point clouds need the optional
``laspy`` extra; both are handled gracefully with an actionable error message.
"""

import logging
from typing import Annotated, Any

from dotenv import load_dotenv
from fastmcp import FastMCP
from fastmcp.exceptions import ToolError
from fastmcp.prompts import Message
from pydantic import Field

from .implementation import (
    DependencyMissingError,
    TerrainError,
    analyze_dem,
    read_point_cloud,
)

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

load_dotenv()

mcp: FastMCP = FastMCP(
    "terrain",
    instructions=(
        "Generic terrain analysis over gridded elevation data and point clouds. "
        "Use dem_terrain to analyze a Digital Elevation Model for elevation, slope, "
        "aspect, and site suitability against elevation/slope criteria. Use "
        "pointcloud_read to read an x/y/z point cloud and grid it into a DEM-like "
        "surface (optionally writing a CSV DEM you can then feed to dem_terrain). "
        "Base CSV/NPY/NPZ formats always work; GeoTIFF and LAS/LAZ need optional extras."
    ),
)


@mcp.tool(
    name="dem_terrain",
    title="Analyze DEM",
    description=(
        "Analyze a Digital Elevation Model grid for elevation, slope, aspect, and "
        "site suitability. Accepts CSV numeric grids, NPY, and NPZ (with a 'dem' "
        "array); GeoTIFF requires the optional rasterio extra. Returns grid shape, "
        "summary statistics, suitability counts, and representative suitable cells."
    ),
    annotations={
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
    },
    tags={"terrain", "dem", "slope", "suitability"},
)
async def dem_terrain_tool(
    filepath: Annotated[
        str,
        Field(description="Path to the DEM (CSV/NPY/NPZ, or GeoTIFF with rasterio)."),
    ],
    cell_size: Annotated[
        float, Field(description="Ground distance between grid cells. Must be > 0.")
    ] = 1.0,
    elevation_min: Annotated[
        float | None,
        Field(description="Minimum elevation for a cell to count as suitable."),
    ] = None,
    elevation_max: Annotated[
        float | None,
        Field(description="Maximum elevation for a cell to count as suitable."),
    ] = None,
    slope_max_degrees: Annotated[
        float | None,
        Field(description="Maximum slope (degrees) for a cell to count as suitable."),
    ] = None,
    nodata: Annotated[
        float | None,
        Field(description="Sentinel value to treat as no-data (set to NaN)."),
    ] = None,
) -> dict[str, Any]:
    """Analyze a DEM for elevation, slope, aspect, and suitability. See description for formats."""
    try:
        return analyze_dem(
            filepath,
            cell_size=cell_size,
            elevation_min=elevation_min,
            elevation_max=elevation_max,
            slope_max_degrees=slope_max_degrees,
            nodata=nodata,
        )
    except DependencyMissingError as exc:
        raise ToolError(str(exc)) from exc
    except TerrainError as exc:
        raise ToolError(str(exc)) from exc
    except Exception as exc:  # noqa: BLE001 - surface any failure as a tool error
        logger.exception("dem_terrain failed")
        raise ToolError(f"DEM analysis failed: {exc}") from exc


@mcp.tool(
    name="pointcloud_read",
    title="Grid Points",
    description=(
        "Read an x/y/z point cloud and grid it into a DEM-like surface by averaging "
        "z per cell. Accepts CSV with x,y,z columns, NPY, and NPZ; LAS/LAZ requires "
        "the optional laspy extra. Optionally writes the gridded surface to a CSV DEM "
        "for downstream dem_terrain analysis. Returns point/grid stats and bounds."
    ),
    annotations={
        "readOnlyHint": False,
        "destructiveHint": False,
        "idempotentHint": True,
    },
    tags={"terrain", "pointcloud", "gridding", "dem"},
)
async def pointcloud_read_tool(
    filepath: Annotated[
        str,
        Field(
            description="Path to the point cloud (CSV/NPY/NPZ, or LAS/LAZ with laspy)."
        ),
    ],
    grid_cell_size: Annotated[
        float, Field(description="Size of each output grid cell. Must be > 0.")
    ] = 1.0,
    max_points: Annotated[
        int, Field(description="Maximum points to read (capped at 500000).")
    ] = 100_000,
    output_dem_path: Annotated[
        str | None,
        Field(description="Optional path to write the gridded surface as a CSV DEM."),
    ] = None,
) -> dict[str, Any]:
    """Read an x/y/z point cloud and grid it into a DEM-like surface. See description for formats."""
    try:
        return read_point_cloud(
            filepath,
            grid_cell_size=grid_cell_size,
            max_points=max_points,
            output_dem_path=output_dem_path,
        )
    except DependencyMissingError as exc:
        raise ToolError(str(exc)) from exc
    except TerrainError as exc:
        raise ToolError(str(exc)) from exc
    except Exception as exc:  # noqa: BLE001 - surface any failure as a tool error
        logger.exception("pointcloud_read failed")
        raise ToolError(f"Point-cloud read failed: {exc}") from exc


@mcp.resource("terrain://capabilities")
def terrain_capabilities() -> dict[str, Any]:
    """Supported input formats, tools, and safety limits for terrain analysis."""
    return {
        "tools": ["dem_terrain", "pointcloud_read"],
        "dem_formats": {
            "always_available": ["csv", "npy", "npz"],
            "optional": {"geotiff": "requires the 'geotiff' extra (rasterio)"},
        },
        "pointcloud_formats": {
            "always_available": ["csv", "npy", "npz"],
            "optional": {"las_laz": "requires the 'laz' extra (laspy)"},
        },
        "limits": {
            "max_dem_cells": 2_000_000,
            "max_point_cloud_points": 500_000,
        },
        "outputs": [
            "elevation/slope/aspect summary statistics",
            "site-suitability mask counts and representative cells",
            "gridded DEM-like surface from point clouds (optional CSV export)",
        ],
    }


@mcp.prompt()
def terrain_suitability_workflow(filepath: str) -> list[Message]:
    """Guided workflow for assessing site suitability from terrain data."""
    return [
        Message(
            f"I need to assess site suitability from the terrain data at {filepath}. "
            "If it is a point cloud (CSV/NPY/NPZ or LAS/LAZ), first use pointcloud_read "
            "to grid it into a DEM, writing the gridded surface to a CSV via "
            "output_dem_path. Then run dem_terrain on the DEM with my elevation and "
            "slope_max_degrees criteria, and summarize the suitable area fraction, the "
            "elevation/slope/aspect statistics, and a few representative suitable cells."
        ),
    ]


def main() -> None:
    """Entry point for the terrain MCP server."""
    import argparse
    import os

    parser = argparse.ArgumentParser(description="Terrain MCP Server")
    parser.add_argument("--transport", choices=["stdio", "http"], default=None)
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--port", type=int, default=8000)
    args = parser.parse_args()
    transport = args.transport or os.getenv("MCP_TRANSPORT", "stdio")
    if transport == "http":
        mcp.run(transport="http", host=args.host, port=args.port)
    else:
        mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
