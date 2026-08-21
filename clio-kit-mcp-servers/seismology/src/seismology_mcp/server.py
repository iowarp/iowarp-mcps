#!/usr/bin/env python3
"""Seismology MCP server: waveforms and earthquake catalogs already on disk.

Two families of tool. Waveforms: inspect a ``.sac`` file or a TAR archive of
SAC files, compute per-trace amplitude statistics, and plot traces to a PNG.
Earthquake catalogs: compute sequence statistics (Mc, Gutenberg-Richter
b-value, Bath gap, Omori decay) and render the three-panel sequence figure --
ported from the seismic MCP server when it merged in (clio-kit #357).

It retrieves nothing; it only reads local files.
"""

import logging
from typing import Annotated, Any

from dotenv import load_dotenv
from fastmcp import FastMCP
from fastmcp.exceptions import ToolError
from fastmcp.prompts import Message
from pydantic import Field

from .implementation import (
    CatalogError,
    SacAnalysisError,
    analyze_sequence,
    compute_trace_statistics,
    inspect_archive,
    plot_sequence,
    plot_traces,
)

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

load_dotenv()

mcp: FastMCP = FastMCP(
    "seismology",
    instructions=(
        "Analyzes SAC seismic-waveform files that already exist on disk. Accepts a "
        "single .sac file or a .tar/.tar.gz/.tgz archive containing SAC files. Use "
        "inspect_archive first to list members, stations, and phases; "
        "compute_trace_statistics for per-trace min/max/mean/std/peak amplitudes; "
        "and plot_traces to render normalized traces to a PNG. For earthquake "
        "CATALOGS rather than waveforms, use analyze_sequence for descriptive "
        "statistics (completeness magnitude, Gutenberg-Richter b-value, Bath "
        "gap, Omori decay) and plot_sequence for the three-panel sequence "
        "figure; those accept a .geojson/.json/.csv catalog, not SAC files. "
        "This server does not fetch or download data - point it at files you "
        "already have."
    ),
)


@mcp.tool(
    name="inspect_archive",
    title="Inspect Archive",
    description=(
        "Inspect a staged SAC file or TAR archive and summarize its SAC waveform "
        "members: count, a sample of member names and sizes, and the inferred "
        "stations and phases. Read-only; a good first step before computing "
        "statistics or plotting."
    ),
    annotations={
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
    },
    tags={"seismic", "sac", "inspect", "waveform"},
)
async def inspect_archive_tool(
    filepath: Annotated[
        str,
        Field(
            description="Path to a .sac file or a .tar/.tar.gz/.tgz archive of SAC files."
        ),
    ],
    member_filter: Annotated[
        str | None,
        Field(
            description="Optional case-insensitive substring filter on member names."
        ),
    ] = None,
    max_members: Annotated[
        int, Field(description="Maximum number of members/sizes to list (1-100).")
    ] = 12,
) -> dict[str, Any]:
    """Summarize the SAC members of a file or archive. See tool description."""
    try:
        return inspect_archive(
            filepath, member_filter=member_filter, max_members=max_members
        )
    except SacAnalysisError as exc:
        raise ToolError(str(exc)) from exc
    except Exception as exc:  # noqa: BLE001 - surface unexpected failures as tool errors
        logger.exception("inspect_archive failed")
        raise ToolError(f"Could not inspect SAC archive: {exc}") from exc


@mcp.tool(
    name="compute_trace_statistics",
    title="Trace Statistics",
    description=(
        "Compute per-trace amplitude statistics (min, max, mean, std, peak_abs) "
        "plus header metadata (npts, delta_s, begin_s, end_s) for SAC traces in a "
        "file or archive. Read-only; bounded by max_traces."
    ),
    annotations={
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
    },
    tags={"seismic", "sac", "statistics", "waveform"},
)
async def compute_trace_statistics_tool(
    filepath: Annotated[
        str,
        Field(
            description="Path to a .sac file or a .tar/.tar.gz/.tgz archive of SAC files."
        ),
    ],
    member_filter: Annotated[
        str | None,
        Field(
            description="Optional case-insensitive substring filter on member names."
        ),
    ] = None,
    max_traces: Annotated[
        int, Field(description="Maximum number of traces to analyze (1-25).")
    ] = 6,
) -> dict[str, Any]:
    """Compute per-trace statistics for SAC traces. See tool description."""
    try:
        return compute_trace_statistics(
            filepath, member_filter=member_filter, max_traces=max_traces
        )
    except SacAnalysisError as exc:
        raise ToolError(str(exc)) from exc
    except Exception as exc:  # noqa: BLE001 - surface unexpected failures as tool errors
        logger.exception("compute_trace_statistics failed")
        raise ToolError(f"Could not compute SAC trace statistics: {exc}") from exc


@mcp.tool(
    name="plot_traces",
    title="Plot Traces",
    description=(
        "Plot selected SAC traces from a file or archive to a PNG artifact. Traces "
        "are amplitude-normalized and vertically offset. Writes a file; returns the "
        "output path, plotted member names, and render duration."
    ),
    annotations={
        "readOnlyHint": False,
        "destructiveHint": True,
        "idempotentHint": True,
    },
    tags={"seismic", "sac", "plot", "visualization", "waveform"},
)
async def plot_traces_tool(
    filepath: Annotated[
        str,
        Field(
            description="Path to a .sac file or a .tar/.tar.gz/.tgz archive of SAC files."
        ),
    ],
    member_filter: Annotated[
        str | None,
        Field(
            description="Optional case-insensitive substring filter on member names."
        ),
    ] = None,
    max_traces: Annotated[
        int, Field(description="Maximum number of traces to plot (1-8).")
    ] = 3,
    output_path: Annotated[
        str,
        Field(
            description="Destination PNG path. Empty uses a default under the working dir."
        ),
    ] = "",
) -> dict[str, Any]:
    """Plot SAC traces to a PNG. See tool description."""
    try:
        return plot_traces(
            filepath,
            member_filter=member_filter,
            max_traces=max_traces,
            output_path=output_path,
        )
    except SacAnalysisError as exc:
        raise ToolError(str(exc)) from exc
    except Exception as exc:  # noqa: BLE001 - surface unexpected failures as tool errors
        logger.exception("plot_traces failed")
        raise ToolError(f"Could not plot SAC traces: {exc}") from exc


@mcp.tool(
    name="analyze_sequence",
    title="Analyze Sequence",
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
    title="Plot Sequence",
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


@mcp.resource("seismology://capabilities")
def seismology_capabilities() -> dict[str, Any]:
    """What this server can do and the inputs it accepts."""
    return {
        "waveform_tools": [
            "inspect_archive",
            "compute_trace_statistics",
            "plot_traces",
        ],
        "catalog_tools": ["analyze_sequence", "plot_sequence"],
        "accepted_inputs": [".sac", ".tar", ".tar.gz", ".tgz"],
        "accepted_catalog_inputs": [".geojson", ".json", ".csv"],
        "catalog_formats": {
            "geojson": "GeoJSON FeatureCollection or {'events': [...]} wrapper",
            "csv": "columns mag/time/lon/lat (+optional depth/place/id)",
        },
        "header_format": "SAC binary, 632-byte header, little/big-endian auto-detected",
        "catalog_statistics": [
            "completeness_mc",
            "b_value",
            "b_uncertainty",
            "bath_gap",
            "spatial_extent_km",
            "omori_p_estimate",
        ],
        "figure_panels": ["epicenter_map", "gutenberg_richter", "temporal_evolution"],
        "limits": {
            "max_sac_bytes_per_trace": 8 * 1024 * 1024,
            "max_members_listed": 100,
            "max_traces_statistics": 25,
            "max_traces_plotted": 8,
        },
        "notes": (
            "Read/compute/plot only; no data retrieval or remote access. The "
            "waveform tools read SAC files; the catalog tools read saved "
            "earthquake catalogs and return statistics, not a classification."
        ),
    }


@mcp.prompt()
def analyze_sac_archive(filepath: str) -> list[Message]:
    """Guided workflow for inspecting and analyzing a SAC file or archive."""
    return [
        Message(
            f"I have a SAC seismic file or archive at {filepath}. "
            "First call inspect_archive to list its SAC members, stations, and phases. "
            "Then call compute_trace_statistics to summarize per-trace amplitudes, and "
            "finally call plot_traces to render the traces to a PNG. Report the member "
            "count, notable peak amplitudes, and the path to the generated plot."
        ),
    ]


def main() -> None:
    """Entry point for the SAC MCP server."""
    import argparse
    import os

    parser = argparse.ArgumentParser(description="SAC MCP Server")
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
