"""FastMCP surface for structured Spack discovery and installation."""

from __future__ import annotations

import argparse
import asyncio
import os
from collections.abc import Callable
from pathlib import Path
from typing import TypeVar

from fastmcp import FastMCP
from fastmcp.exceptions import ToolError
from fastmcp.prompts import Message

from spack_mcp.backend import (
    SpackBackendError,
    SpackEnvironmentResult,
    SpackFindResult,
    SpackInstallResult,
    SpackLocateResult,
    find_installed,
    install_spec,
    locate_installed,
    resolve_environment,
)

mcp: FastMCP = FastMCP(
    "spack",
    instructions=(
        "Discover, locate, and install Spack packages using structured results. "
        "This server never pretends that a shell-local `spack load` changes later "
        "agent or scheduler processes. Runtime environment materialization is an "
        "admin diagnostic; JARVIS should persist it inside jarvis_run."
    ),
)

USER_TOOLS = {"spack_find", "spack_locate", "spack_install"}
ADMIN_TOOLS = {"spack_environment"}
MCP_METADATA_PROFILE = "user"
ResultT = TypeVar("ResultT")


@mcp.tool(
    name="spack_find",
    description="List installed Spack packages matching an optional constraint.",
    annotations={
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": False,
    },
    tags={"spack", "packages", "user"},
)
async def spack_find_tool(query: str | None = None) -> SpackFindResult:
    """Return structured installed-package records."""
    return await _call_backend(find_installed, query)


@mcp.tool(
    name="spack_locate",
    description="Resolve one unique installed Spack spec and return its exact prefix.",
    annotations={
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": False,
    },
    tags={"spack", "packages", "user"},
)
async def spack_locate_tool(spec: str) -> SpackLocateResult:
    """Return one exact package identity and prefix or a protocol error."""
    return await _call_backend(locate_installed, spec)


@mcp.tool(
    name="spack_install",
    description="Install one Spack spec and verify that a matching install is observable.",
    annotations={
        "readOnlyHint": False,
        "destructiveHint": False,
        "idempotentHint": False,
        "openWorldHint": True,
    },
    tags={"spack", "packages", "user"},
)
async def spack_install_tool(
    spec: str,
    reuse: bool = True,
    timeout_seconds: int = 14_400,
) -> SpackInstallResult:
    """Install one spec with bounded output, timeout, and child cleanup."""
    return await _call_backend(
        install_spec,
        spec,
        reuse=reuse,
        timeout_seconds=timeout_seconds,
    )


@mcp.tool(
    name="spack_environment",
    description=(
        "Admin diagnostic: return a filtered structured environment for installed specs. "
        "This does not mutate the MCP server or any later process."
    ),
    annotations={
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": False,
    },
    tags={"spack", "environment", "admin"},
)
async def spack_environment_tool(specs: list[str]) -> SpackEnvironmentResult:
    """Return a filtered environment delta without exposing a fake load operation."""
    return await _call_backend(resolve_environment, specs)


@mcp.resource("spack://capabilities")
def spack_capabilities() -> dict[str, object]:
    """Describe the stateless Spack contract exposed by this server."""
    return {
        "operations": ["find", "locate", "install"],
        "admin_operations": ["environment"],
        "stateful_load_exposed": False,
        "runtime_owner": "jarvis_run",
    }


@mcp.prompt()
def prepare_spack_package(spec: str) -> list[Message]:
    """Guide an agent through deterministic package preparation."""
    return [
        Message(
            f"Prepare Spack package {spec!r}. First call spack_find, install only if "
            "needed, then call spack_locate. Pass the exact spec to jarvis_run via "
            "spack_specs so JARVIS persists the runtime environment."
        )
    ]


async def _call_backend(
    function: Callable[..., ResultT],
    *args: object,
    **kwargs: object,
) -> ResultT:
    try:
        return await asyncio.to_thread(function, *args, **kwargs)
    except SpackBackendError as exc:
        raise ToolError(exc.as_json()) from exc


def apply_tool_profile(profile: str) -> None:
    """Restrict the default server to the stable user-facing surface."""
    normalized = profile.strip().lower()
    if normalized == "all":
        return
    if normalized == "user":
        allowed = USER_TOOLS
    elif normalized == "admin":
        allowed = ADMIN_TOOLS
    else:
        raise ValueError("profile must be one of: all, user, admin")
    for tool_name in USER_TOOLS | ADMIN_TOOLS:
        if tool_name not in allowed:
            mcp.local_provider.remove_tool(tool_name)


def _spack_command_path(value: str) -> str:
    """Resolve and validate an operator-supplied Spack executable path."""
    candidate = Path(value).expanduser()
    try:
        resolved = candidate.resolve(strict=True)
    except (OSError, RuntimeError) as exc:
        raise argparse.ArgumentTypeError(f"Spack command does not exist: {candidate}") from exc
    if not resolved.is_file():
        raise argparse.ArgumentTypeError(f"Spack command is not a file: {resolved}")
    if os.name != "nt" and not os.access(resolved, os.X_OK):
        raise argparse.ArgumentTypeError(f"Spack command is not executable: {resolved}")
    return str(resolved)


def main() -> None:
    """Run the Spack MCP server over stdio or HTTP."""
    parser = argparse.ArgumentParser(description="Spack MCP Server")
    parser.add_argument("--transport", choices=["stdio", "http"], default=None)
    parser.add_argument("--profile", choices=["user", "admin", "all"], default=None)
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
    apply_tool_profile(args.profile or os.getenv("SPACK_MCP_PROFILE", "user"))
    transport = args.transport or os.getenv("MCP_TRANSPORT", "stdio")
    if transport == "http":
        mcp.run(transport="http", host=args.host, port=args.port)
    else:
        mcp.run(transport="stdio")


def admin_main() -> None:
    """Run only the internal structured-environment diagnostic surface."""
    os.environ.setdefault("SPACK_MCP_PROFILE", "admin")
    main()


if __name__ == "__main__":
    main()
