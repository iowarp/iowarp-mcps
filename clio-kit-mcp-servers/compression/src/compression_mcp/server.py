#!/usr/bin/env python3
"""Compression MCP Server — gzip file compression and decompression."""

import logging
import os
from typing import Annotated

from fastmcp import FastMCP
from fastmcp.prompts import Message
from pydantic import Field

from . import mcp_handlers

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

mcp: FastMCP = FastMCP(
    "compression",
    instructions=(
        "Provides gzip file compression and decompression. "
        "Use compress_file to reduce file size, decompress_file to restore originals."
    ),
)


@mcp.tool(
    title="Compress",
    annotations={
        "readOnlyHint": False,
        "destructiveHint": False,
        "idempotentHint": True,
    },
    tags={"compression", "file-io"},
)
async def compress_file_tool(
    file_path: Annotated[
        str, Field(description="Absolute path to the file to compress")
    ],
) -> dict:
    """Compress a file using gzip. Returns original/compressed sizes and compression ratio."""
    logger.info(f"Compressing file: {file_path}")
    return await mcp_handlers.compress_file_handler(file_path)


@mcp.tool(
    title="Decompress",
    annotations={
        "readOnlyHint": False,
        "destructiveHint": False,
        "idempotentHint": True,
    },
    tags={"decompression", "file-io"},
)
async def decompress_file_tool(
    file_path: Annotated[
        str, Field(description="Absolute path to the .gz file to decompress")
    ],
) -> dict:
    """Decompress a gzip-compressed (.gz) file back to its original form."""
    logger.info(f"Decompressing file: {file_path}")
    return await mcp_handlers.decompress_file_handler(file_path)


@mcp.resource("compression://capabilities")
def compression_capabilities() -> dict:
    """Supported compression formats and their capabilities."""
    return {
        "formats": {
            "gzip": {
                "extension": ".gz",
                "mime_type": "application/gzip",
                "description": "GNU zip compression",
                "operations": ["compress", "decompress"],
            }
        },
        "max_file_size": "No limit (streaming)",
    }


@mcp.prompt()
def compress_workflow(file_path: str) -> list[Message]:
    """Guided workflow for compressing a file and verifying the result."""
    return [
        Message(
            f"I need to compress the file at {file_path}. "
            "Please compress it, then verify the output exists and report the compression ratio."
        ),
    ]


def main() -> None:
    """Main entry point for the compression MCP server."""
    import argparse

    parser = argparse.ArgumentParser(description="Compression MCP Server")
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
