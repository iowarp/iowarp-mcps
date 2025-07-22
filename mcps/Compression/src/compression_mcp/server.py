#!/usr/bin/env python3
"""
Compression MCP Server implementation using Model Context Protocol.
Provides file compression capabilities through MCP tools.
"""
import os
import sys
import json
from fastmcp import FastMCP
from dotenv import load_dotenv
import logging

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Add current directory to path for relative imports
sys.path.insert(0, os.path.dirname(__file__))

# Load environment variables
load_dotenv()

from . import mcp_handlers

# Initialize MCP server
mcp = FastMCP("CompressionMCP")

@mcp.tool(
    name="compress_file",
    description="Compress a file using gzip compression."
)
async def compress_file_tool(file_path: str) -> dict:
    """
    Compress a file using gzip compression with detailed statistics and performance analytics. Supports all file types with comprehensive error handling.

    Args:
        file_path (str): Absolute path to the file to compress

    Returns:
        dict: Dictionary containing compression results with detailed statistics including original size, compressed size, compression ratio, and output file path.
    """
    logger.info(f"Compressing file: {file_path}")
    return await mcp_handlers.compress_file_handler(file_path)


def main():
    """
    Main entry point for the Compression MCP server.
    Supports both stdio and SSE transports based on environment variables.
    """
    try:
        logger.info("Starting Compression MCP Server")
        
        # Determine which transport to use
        transport = os.getenv("MCP_TRANSPORT", "stdio").lower()
        if transport == "sse":
            # SSE transport for web-based clients
            host = os.getenv("MCP_SSE_HOST", "0.0.0.0")
            port = int(os.getenv("MCP_SSE_PORT", "8000"))
            logger.info(f"Starting SSE transport on {host}:{port}")
            print(json.dumps({"message": f"Starting SSE on {host}:{port}"}), file=sys.stderr)
            mcp.run(transport="sse", host=host, port=port)
        else:
            # Default stdio transport
            logger.info("Starting stdio transport")
            print(json.dumps({"message": "Starting stdio transport"}), file=sys.stderr)
            mcp.run(transport="stdio")

    except Exception as e:
        logger.error(f"Server error: {e}")
        print(json.dumps({"error": str(e)}), file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    main()