#!/usr/bin/env python3
"""SAC MCP server.

Analyzes SAC seismic-waveform files the user already has on disk: inspect a
``.sac`` file or a TAR archive of SAC files, compute per-trace amplitude
statistics, and plot traces to a PNG. It retrieves nothing - it only reads
local files.
"""

import logging
from typing import Annotated, Any

from dotenv import load_dotenv
from fastmcp import FastMCP
from fastmcp.exceptions import ToolError
from fastmcp.prompts import Message
from pydantic import Field

from .implementation import (
    SacAnalysisError,
    compute_trace_statistics,
    inspect_archive,
    plot_traces,
)

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

load_dotenv()

mcp: FastMCP = FastMCP(
    "sac",
    instructions=(
        "Analyzes SAC seismic-waveform files that already exist on disk. Accepts a "
        "single .sac file or a .tar/.tar.gz/.tgz archive containing SAC files. Use "
        "inspect_archive first to list members, stations, and phases; "
        "compute_trace_statistics for per-trace min/max/mean/std/peak amplitudes; "
        "and plot_traces to render normalized traces to a PNG. This server does not "
        "fetch or download data - point it at files you already have."
    ),
)


@mcp.tool(
    name="inspect_archive",
    title="inspect(archive)",
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
    title="stats(traces)",
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
    title="plot(traces)",
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


@mcp.resource("sac://capabilities")
def sac_capabilities() -> dict[str, Any]:
    """What this server can do and the inputs it accepts."""
    return {
        "tools": ["inspect_archive", "compute_trace_statistics", "plot_traces"],
        "accepted_inputs": [".sac", ".tar", ".tar.gz", ".tgz"],
        "header_format": "SAC binary, 632-byte header, little/big-endian auto-detected",
        "limits": {
            "max_sac_bytes_per_trace": 8 * 1024 * 1024,
            "max_members_listed": 100,
            "max_traces_statistics": 25,
            "max_traces_plotted": 8,
        },
        "notes": "Read-only file analysis; no data retrieval or remote access.",
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
