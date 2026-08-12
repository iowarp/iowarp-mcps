"""FastMCP surface for structured Spack discovery and installation."""

from __future__ import annotations

import argparse
import asyncio
import os
from collections.abc import Callable
from pathlib import Path
from typing import Annotated, TypeVar

from fastmcp import FastMCP
from fastmcp.exceptions import ToolError
from fastmcp.prompts import Message
from pydantic import Field

from spack_mcp.backend import (
    SpackBackendError,
    SpackEnvironmentResult,
    SpackFindResult,
    SpackLocateResult,
    find_installed,
    locate_installed,
    resolve_environment,
)
from spack_mcp.discovery import (
    SpackInfoResult,
    SpackSearchResult,
    describe_package,
    enrich_not_installed,
    search_packages,
)
from spack_mcp.provisioning import SpackInstallResult, install_spec

mcp: FastMCP = FastMCP(
    "spack",
    instructions=(
        "Discover, locate, search, describe, and install Spack packages using "
        "structured results. A find with no installed matches succeeds with "
        "count=0 and packages=[]; locating an absent package returns the "
        "structured not_installed error, enriched with whether a recipe is "
        "available to install. Search answers recipe AVAILABILITY across every "
        "registered repo -- broader than find/locate, which only see what is "
        "already installed. This server never pretends that a shell-local "
        "`spack load` changes later agent or scheduler processes. Runtime "
        "environment materialization is an admin diagnostic. Copy "
        "spack_locate.output.load_spec (or spack_install.output.load_spec) "
        "unchanged into jarvis_run.input.spack_specs so JARVIS persists the "
        "runtime environment."
    ),
)

USER_TOOLS = {"spack_find", "spack_locate", "spack_search", "spack_info", "spack_install"}
ADMIN_TOOLS = {"spack_environment"}
MCP_METADATA_PROFILE = "user"
ResultT = TypeVar("ResultT")


@mcp.tool(
    name="spack_find",
    title="Find Packages",
    description=(
        "List installed Spack packages matching an optional constraint. "
        "No matches is a successful result with count=0 and packages=[]."
    ),
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
    title="Locate Package",
    description=(
        "Resolve one unique installed Spack spec. Copy "
        "spack_locate.output.load_spec unchanged into one element of "
        "jarvis_run.input.spack_specs; do not derive or pass an executable path from "
        "the returned prefix. An absent package returns the structured not_installed "
        "error, whose detail now says whether a recipe is available to install "
        "(call spack_install) or exists in no registered repo at all."
    ),
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
    return await _call_backend(
        locate_installed,
        spec,
        enrich_error=lambda error: enrich_not_installed(error, spec),
    )


@mcp.tool(
    name="spack_search",
    title="Search Recipes",
    description=(
        "Search recipe AVAILABILITY across every registered Spack repo -- broader "
        "than spack_find/spack_locate, which only see what is already installed. "
        "Answers 'does a recipe exist', 'in which repo', and 'is it already "
        "installed' in one call. No matches is a successful result with count=0."
    ),
    annotations={
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": False,
    },
    tags={"spack", "packages", "user"},
)
async def spack_search_tool(query: str) -> SpackSearchResult:
    """Return fuzzy-matched recipe candidates with repo and install state."""
    return await _call_backend(search_packages, query)


@mcp.tool(
    name="spack_info",
    title="Describe Recipe",
    description=(
        "Describe one recipe: versions, variants, and description. Probes "
        "`spack info` first; if that subcommand is unavailable or fails on this "
        "deployment, falls back to statically parsing the recipe's package.py and "
        "marks the result degraded=true with degraded_reason explaining why -- "
        "never silently. A package absent from every registered repo returns the "
        "structured recipe_not_found error."
    ),
    annotations={
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": False,
    },
    tags={"spack", "packages", "user"},
)
async def spack_info_tool(package: str) -> SpackInfoResult:
    """Return one recipe's versions/variants/description, degraded-flagged."""
    return await _call_backend(describe_package, package)


@mcp.tool(
    name="spack_install",
    title="Install Package",
    description=(
        "Install one Spack spec with explicit reusable or fresh concretization. "
        "Runs synchronously (streaming/task augmentation is deferred to the kit "
        "tasks-semantics slice, SEP-2663) with a configurable timeout; captures the "
        "full build log to disk and returns its path plus a bounded tail, and the "
        "install prefix on success. A missing recipe, a failed build, and a timeout "
        "are distinct typed errors (recipe_not_found / build_failure / timed_out), "
        "each naming the recovery affordance (searched repos / log tail / log path)."
    ),
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
    reuse: Annotated[
        bool,
        Field(
            description=(
                "Choose Spack concretization explicitly: true passes --reuse and may "
                "reuse compatible installed packages or buildcaches; false passes "
                "--fresh and excludes them while concretizing."
            )
        ),
    ] = True,
    timeout_seconds: int = 14_400,
) -> SpackInstallResult:
    """Install one spec with explicit concretization, timeout, and child cleanup."""
    return await _call_backend(
        install_spec,
        spec,
        reuse=reuse,
        timeout_seconds=timeout_seconds,
    )


@mcp.tool(
    name="spack_environment",
    title="Diff Environment",
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
        "operations": ["find", "locate", "search", "info", "install"],
        "admin_operations": ["environment"],
        "stateful_load_exposed": False,
        "runtime_owner": "jarvis_run",
    }


@mcp.prompt()
def prepare_spack_package(spec: str) -> list[Message]:
    """Guide an agent through the provisioning loop: locate, search, install."""
    return [
        Message(
            f"Prepare Spack package {spec!r}. First call spack_find (or spack_locate) "
            "to check whether it is already installed. If not, call spack_search to "
            "confirm a recipe exists and spack_info to see its versions/variants "
            "before proposing an install. Install only after that check (and any "
            "required approval), then call spack_locate. Copy "
            "spack_locate.output.load_spec (or spack_install.output.load_spec) "
            "unchanged into jarvis_run.input.spack_specs so JARVIS persists the "
            "runtime environment."
        )
    ]


async def _call_backend(
    function: Callable[..., ResultT],
    *args: object,
    enrich_error: Callable[[SpackBackendError], SpackBackendError] | None = None,
    **kwargs: object,
) -> ResultT:
    try:
        return await asyncio.to_thread(function, *args, **kwargs)
    except SpackBackendError as exc:
        if enrich_error is not None:
            exc = await asyncio.to_thread(enrich_error, exc)
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
