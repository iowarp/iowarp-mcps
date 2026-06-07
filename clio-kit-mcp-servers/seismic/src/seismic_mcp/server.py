#!/usr/bin/env python3
"""Seismic MCP server.

Characterizes an earthquake sequence from a catalog the user already has on disk
(GeoJSON or CSV): it computes the descriptive statistics a seismologist reads -
completeness magnitude (Mc), the Gutenberg-Richter b-value, the Bath-law
magnitude gap, and Omori-style rate decay - and renders a three-panel figure. It
retrieves nothing: acquisition is a separate retrieval MCP's job.

Design rule (do not break): these tools produce *data*. They compute the
statistics and draw the figure. They do NOT decide whether the activity is an
aftershock sequence, a swarm, or background, and they do NOT declare which event
is "the mainshock". That classification is the agent's judgment, made by
reasoning over the statistics these tools return.
"""

import logging
from typing import Annotated, Any

from dotenv import load_dotenv
from fastmcp import FastMCP
from fastmcp.exceptions import ToolError
from fastmcp.prompts import Message
from pydantic import Field

from .implementation import CatalogError, analyze_sequence, plot_sequence

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

load_dotenv()

mcp: FastMCP = FastMCP(
    "seismic",
    instructions=(
        "Characterizes an earthquake sequence from a catalog you already have on "
        "disk - a GeoJSON FeatureCollection (or saved {'events': [...]} wrapper) "
        "or a CSV with mag/time/lon/lat columns. Use analyze_sequence to get the "
        "descriptive statistics (completeness magnitude Mc, Gutenberg-Richter "
        "b-value, Bath-law magnitude gap, Omori rate decay, spatial extent), and "
        "plot_sequence to render a three-panel figure (epicenter map, "
        "Gutenberg-Richter distribution, temporal evolution). These tools return "
        "statistics and figures only - they do NOT classify the sequence as "
        "aftershocks/swarm/background; that is your judgment. This server does not "
        "fetch or download data - point it at a catalog you already have."
    ),
)


@mcp.tool(
    name="analyze_sequence",
    description=(
        "Compute the descriptive statistics of a saved earthquake catalog: "
        "completeness magnitude (Mc), the Gutenberg-Richter b-value with "
        "uncertainty, the largest event, the Bath-law magnitude gap to the "
        "second-largest, the share of events before vs after the largest, the "
        "spatial extent, and the Omori post-event rate decay. Returns statistics "
        "ONLY - it does not classify the sequence."
    ),
    annotations={
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
    },
    tags={"seismic", "earthquake", "statistics", "gutenberg-richter", "omori"},
)
async def analyze_sequence_tool(
    catalog_path: Annotated[
        str,
        Field(
            description=(
                "Path to a saved earthquake catalog: a .geojson/.json GeoJSON "
                "FeatureCollection (or {'events': [...]} wrapper) or a .csv with "
                "mag/time/lon/lat columns."
            )
        ),
    ],
    mag_bin: Annotated[
        float,
        Field(
            description="Magnitude bin width for Mc and the b-value MLE (default 0.1)."
        ),
    ] = 0.1,
) -> dict[str, Any]:
    """Compute sequence statistics from a saved catalog. See tool description."""
    try:
        return analyze_sequence(catalog_path, mag_bin=mag_bin)
    except CatalogError as exc:
        raise ToolError(str(exc)) from exc
    except Exception as exc:  # noqa: BLE001 - surface unexpected failures as tool errors
        logger.exception("analyze_sequence failed")
        raise ToolError(f"Could not analyze sequence: {exc}") from exc


@mcp.tool(
    name="plot_sequence",
    description=(
        "Render the three-panel earthquake-sequence figure from a saved catalog: "
        "(1) an epicenter map sized by magnitude and coloured by time, (2) the "
        "Gutenberg-Richter magnitude-frequency distribution with an optional "
        "b-value fit line, and (3) the cumulative count over time. Writes a PNG "
        "and returns its path; pass mc/b_value to draw the G-R fit line."
    ),
    annotations={
        "readOnlyHint": False,
        "destructiveHint": True,
        "idempotentHint": True,
    },
    tags={"seismic", "earthquake", "plot", "visualization", "gutenberg-richter"},
)
async def plot_sequence_tool(
    catalog_path: Annotated[
        str,
        Field(
            description=(
                "Path to a saved earthquake catalog (.geojson/.json/.csv), same "
                "forms as analyze_sequence."
            )
        ),
    ],
    title: Annotated[str | None, Field(description="Optional figure title.")] = None,
    mc: Annotated[
        float | None,
        Field(description="Optional completeness magnitude for the G-R fit line."),
    ] = None,
    b_value: Annotated[
        float | None,
        Field(description="Optional Gutenberg-Richter b-value for the G-R fit line."),
    ] = None,
    output_path: Annotated[
        str,
        Field(
            description="Destination PNG path. Empty uses a default under the working dir."
        ),
    ] = "",
) -> dict[str, Any]:
    """Render the three-panel sequence figure. See tool description."""
    try:
        return plot_sequence(
            catalog_path,
            title=title,
            mc=mc,
            b_value=b_value,
            output_path=output_path,
        )
    except CatalogError as exc:
        raise ToolError(str(exc)) from exc
    except Exception as exc:  # noqa: BLE001 - surface unexpected failures as tool errors
        logger.exception("plot_sequence failed")
        raise ToolError(f"Could not plot sequence: {exc}") from exc


@mcp.resource("seismic://capabilities")
def seismic_capabilities() -> dict[str, Any]:
    """What this server can do and the inputs it accepts."""
    return {
        "tools": ["analyze_sequence", "plot_sequence"],
        "accepted_inputs": [".geojson", ".json", ".csv"],
        "catalog_formats": {
            "geojson": "GeoJSON FeatureCollection or {'events': [...]} wrapper",
            "csv": "columns mag/time/lon/lat (+optional depth/place/id)",
        },
        "statistics": [
            "completeness_mc",
            "b_value",
            "b_uncertainty",
            "bath_gap",
            "spatial_extent_km",
            "omori_p_estimate",
        ],
        "figure_panels": ["epicenter_map", "gutenberg_richter", "temporal_evolution"],
        "notes": (
            "Read/compute/plot only; no data retrieval or remote access. Tools "
            "return statistics and figures, not a sequence classification."
        ),
    }


@mcp.prompt()
def characterize_sequence(catalog_path: str) -> list[Message]:
    """Guided workflow for characterizing a saved earthquake catalog."""
    return [
        Message(
            f"I have a saved earthquake catalog at {catalog_path}. "
            "First call analyze_sequence to get the descriptive statistics - "
            "completeness magnitude (Mc), the Gutenberg-Richter b-value, the "
            "largest event and the Bath-law gap to the second-largest, the share "
            "of events after the largest, and the Omori rate decay. Then reason "
            "over those numbers to classify the activity (mainshock-aftershock "
            "sequence, swarm, or background) - the tool does not classify it for "
            "you. Finally call plot_sequence with the Mc and b-value you found to "
            "render the three-panel figure, and report the classification and the "
            "path to the generated figure."
        ),
    ]


def main() -> None:
    """Entry point for the seismic MCP server."""
    import argparse
    import os

    parser = argparse.ArgumentParser(description="Seismic MCP Server")
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
