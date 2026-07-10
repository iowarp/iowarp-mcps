"""User-facing JARVIS MCP entry point."""

from __future__ import annotations

import argparse
import os

from .server import apply_tool_profile, mcp

apply_tool_profile("user")


def main() -> None:
    """Run the compact user-facing JARVIS MCP server."""
    parser = argparse.ArgumentParser(description="Jarvis user MCP Server")
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
