"""Admin-only Spack MCP entry point."""

from __future__ import annotations

import argparse
import os

from spack_mcp.server import _spack_command_path, apply_tool_profile, mcp

apply_tool_profile("admin")


def main() -> None:
    """Run only the internal Spack environment-diagnostic surface."""
    parser = argparse.ArgumentParser(description="Spack admin MCP Server")
    parser.add_argument("--transport", choices=["stdio", "http"], default=None)
    parser.add_argument(
        "--spack-command",
        type=_spack_command_path,
        default=None,
        help="Absolute or user-relative path to the audited Spack executable.",
    )
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--port", type=int, default=8000)
    args = parser.parse_args()
    if args.spack_command is not None:
        os.environ["SPACK_MCP_COMMAND"] = args.spack_command
    transport = args.transport or os.getenv("MCP_TRANSPORT", "stdio")
    if transport == "http":
        mcp.run(transport="http", host=args.host, port=args.port)
    else:
        mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
