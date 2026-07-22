"""Admin JARVIS MCP entry point."""

from __future__ import annotations

import argparse
import os

from .server import (
    add_jarvis_root_argument,
    add_spack_command_argument,
    apply_tool_profile,
    configure_jarvis_root,
    configure_spack_command,
    mcp,
)

apply_tool_profile("admin")


def main() -> None:
    """Run the admin JARVIS MCP server."""
    parser = argparse.ArgumentParser(description="Jarvis admin MCP Server")
    parser.add_argument("--transport", choices=["stdio", "http"], default=None)
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--port", type=int, default=8000)
    add_jarvis_root_argument(parser)
    add_spack_command_argument(parser)
    args = parser.parse_args()
    configure_jarvis_root(args.jarvis_root)
    configure_spack_command(args.spack_command)
    transport = args.transport or os.getenv("MCP_TRANSPORT", "stdio")
    if transport == "http":
        mcp.run(transport="http", host=args.host, port=args.port)
    else:
        mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
