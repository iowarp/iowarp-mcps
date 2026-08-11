#!/usr/bin/env python3
"""Ratchet guard against god-files across clio-kit's packages.

Ported from clio-agent's ``scripts/check_file_size.py`` (iowarp/clio-agent,
#714/#767) for clio-kit campaign #362 ("server code health"), Slice 1. Walks
every package's ``src/`` tree -- one per ``clio-kit-mcp-servers/<name>``
(any directory with a ``pyproject.toml``) plus ``clio-agentic-search`` -- and
enforces a per-file line-count ratchet:

* A file **not** in :data:`RATCHET_BASELINE` may not exceed
  :data:`DEFAULT_MAX_LINES` -- a brand-new god-file fails the check.
* A file **in** :data:`RATCHET_BASELINE` (a known-oversized module awaiting
  decomposition) may not exceed its *recorded* line count -- it can shrink
  but never grow past where it is today.

The baseline may only ratchet DOWN. When a file is brought under the cap, or
merely shrinks, the check reports the ratchet-down and the same PR that
shrank it updates :data:`RATCHET_BASELINE` (lowering the number, or removing
the entry once the file is under ``DEFAULT_MAX_LINES``). Ratchet-down
reports are advisory: they do not fail the build.

Run as part of CI (blocking) and locally::

    uv run python scripts/check_file_size.py
    uv run python scripts/check_file_size.py --max 600
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import NamedTuple

# Default maximum number of lines a single *non-baselined* source module may
# contain. New files must stay under this cap.
DEFAULT_MAX_LINES = 800

# Per-file ratchet baseline: the known-oversized modules at their current line
# counts (measured on campaign/362-kit-health, 2026-08-10/11), recorded so
# they cannot regrow. These are the files awaiting further decomposition
# (clio-kit campaign #362, Slice 1). This mapping may only ratchet DOWN --
# when a file shrinks, lower its number here (or drop the entry once it falls
# under DEFAULT_MAX_LINES) in the same change. Paths are relative to the
# repository root and use forward slashes.
RATCHET_BASELINE: dict[str, int] = {
    # #362 wave 1: server.py's 44 model classes + package-discovery/search
    # helpers moved to owner modules (jarvis_mcp/models/*, package_discovery.py),
    # 3109 -> 1323. The remaining size is the `@mcp.tool` registration surface
    # for 30+ tools plus the CLI entry points; ratchets down with a further
    # per-concern tool-registration split if one is ever justified.
    "clio-kit-mcp-servers/jarvis/src/jarvis_mcp/server.py": 1323,
    # #362 wave 1: NOT split this wave (deferred -- see the wave-1 PR
    # description). Still the 6-class monolith measured at campaign kickoff.
    # Next wave: split into owner modules by concern (pipeline lifecycle,
    # execution/progress, artifacts) the same way server.py was split.
    "clio-kit-mcp-servers/jarvis/src/jarvis_mcp/capabilities/jarvis_handler.py": 3521,
    # #362: NOT split this wave -- out of wave-1 scope (jarvis-only). Flat
    # FastMCP function surface, no god-class; still needs an owner-module cut.
    "clio-kit-mcp-servers/hdf5/src/hdf5_mcp/server.py": 2415,
    # #362: NOT split this wave -- out of wave-1 scope. Single
    # VisualizationEngine god-class.
    "clio-kit-mcp-servers/paraview/src/paraview_mcp/implementation/paraview_capabilities.py": 2202,
    "clio-kit-mcp-servers/pandas/src/pandas_mcp/server.py": 1274,
    "clio-kit-mcp-servers/paraview/src/paraview_mcp/server.py": 1091,
    "clio-kit-mcp-servers/spack/src/spack_mcp/backend.py": 925,
    "clio-kit-mcp-servers/darshan/src/darshan_mcp/capabilities/darshan_parser.py": 857,
    "clio-kit-mcp-servers/parquet/src/parquet_mcp/capabilities/parquet_handler.py": 839,
    "clio-kit-mcp-servers/node-hardware/src/node_hardware_mcp/mcp_handlers.py": 819,
}

# Directory holding every MCP server package (one subdirectory per server).
MCP_SERVERS_ROOT = "clio-kit-mcp-servers"

# Additional package roots outside clio-kit-mcp-servers, checked for a `src/`
# tree the same way. clio-agentic-search is a standalone service (not an MCP
# server) but is still a first-class package in this repo's code-health scope.
EXTRA_PACKAGE_ROOTS = ("clio-agentic-search",)


class Failure(NamedTuple):
    """A file that breaks the ratchet (fails the check)."""

    rel: str
    line_count: int
    kind: str  # "new" (non-baselined over cap) or "regressed" (over recorded)
    limit: int  # the cap it broke (DEFAULT_MAX_LINES or the recorded baseline)


class RatchetDown(NamedTuple):
    """A baselined file that shrank -- advisory, not a failure."""

    rel: str
    line_count: int
    baseline: int
    under_cap: bool  # True once line_count <= max_lines (drop the entry entirely)


class Result(NamedTuple):
    """Outcome of a scan: failures fail the build, ratchet_downs are advisory."""

    failures: list[Failure]
    ratchet_downs: list[RatchetDown]


def _repo_root() -> Path:
    """Return the repository root (parent of the ``scripts`` directory)."""
    return Path(__file__).resolve().parent.parent


def _count_lines(path: Path) -> int:
    """Return the number of lines in ``path``."""
    with path.open("r", encoding="utf-8", errors="replace") as handle:
        return sum(1 for _ in handle)


def _is_test_file(path: Path) -> bool:
    """Return whether ``path`` is a test file (never ratchet-guarded)."""
    parts = path.parts
    if "tests" in parts or "test" in parts:
        return True
    return path.name.startswith("test_") or path.name.endswith("_test.py")


def discover_package_src_roots(repo_root: Path) -> list[Path]:
    """Discover every package's ``src/`` tree.

    One per ``clio-kit-mcp-servers/<name>`` directory that has a
    ``pyproject.toml`` (mirroring ``.github/workflows/quality_control.yml``'s
    ``discover-mcps`` step, minus its Chronolog exclusion -- this is a
    code-health scan, not a release gate, and Chronolog can grow a god-file
    same as any other package), plus any :data:`EXTRA_PACKAGE_ROOTS` that
    have a ``src/`` tree of their own.
    """
    roots: list[Path] = []
    servers_dir = repo_root / MCP_SERVERS_ROOT
    if servers_dir.is_dir():
        for pkg_dir in sorted(servers_dir.iterdir()):
            if not pkg_dir.is_dir() or not (pkg_dir / "pyproject.toml").is_file():
                continue
            src_dir = pkg_dir / "src"
            if src_dir.is_dir():
                roots.append(src_dir)
    for extra in EXTRA_PACKAGE_ROOTS:
        src_dir = repo_root / extra / "src"
        if src_dir.is_dir():
            roots.append(src_dir)
    return roots


def check_file_size(
    scan_roots: list[Path],
    *,
    rel_to: Path,
    max_lines: int = DEFAULT_MAX_LINES,
    baseline: dict[str, int] | None = None,
) -> Result:
    """Evaluate the per-file line-count ratchet under every root in ``scan_roots``.

    Args:
        scan_roots: Directory trees to walk for ``*.py`` files (one per
            package's ``src/`` directory).
        rel_to: Base directory used to compute the forward-slash relative
            path that keys into ``baseline`` (the repository root).
        max_lines: Cap applied to files not present in ``baseline``.
        baseline: Per-file recorded line counts. Defaults to
            :data:`RATCHET_BASELINE`.

    Returns:
        A :class:`Result` splitting build-failing offenders from advisory
        ratchet-down reports.
    """
    if baseline is None:
        baseline = RATCHET_BASELINE

    failures: list[Failure] = []
    ratchet_downs: list[RatchetDown] = []
    seen: set[str] = set()
    for scan_root in scan_roots:
        for path in sorted(scan_root.rglob("*.py")):
            if _is_test_file(path):
                continue
            rel = path.relative_to(rel_to).as_posix()
            if rel in seen:
                continue
            seen.add(rel)
            count = _count_lines(path)
            recorded = baseline.get(rel)
            if recorded is None:
                if count > max_lines:
                    failures.append(Failure(rel, count, "new", max_lines))
                continue
            if count > recorded:
                failures.append(Failure(rel, count, "regressed", recorded))
            elif count < recorded:
                ratchet_downs.append(
                    RatchetDown(rel, count, recorded, under_cap=count <= max_lines)
                )
    return Result(failures=failures, ratchet_downs=ratchet_downs)


def _print_report(result: Result, max_lines: int) -> None:
    """Print the ratchet report (failures then advisory ratchet-downs)."""
    for entry in result.ratchet_downs:
        if entry.under_cap:
            print(
                f"OK (ratchet down): {entry.rel} is now {entry.line_count} lines "
                f"(<= {max_lines}) -- remove it from RATCHET_BASELINE in "
                "scripts/check_file_size.py."
            )
        else:
            print(
                f"OK (ratchet down): {entry.rel} shrank {entry.baseline} -> "
                f"{entry.line_count} -- lower its RATCHET_BASELINE entry to "
                f"{entry.line_count} in scripts/check_file_size.py."
            )

    if not result.failures:
        print(
            f"OK: no package source file exceeds its ratchet baseline "
            f"(cap {max_lines} for new files)."
        )
        return

    print(f"FAIL: {len(result.failures)} file(s) break the size ratchet (#362):")
    for failure in result.failures:
        if failure.kind == "new":
            print(
                f"  {failure.rel}:{failure.line_count} "
                f"(new file exceeds cap {failure.limit})"
            )
        else:
            print(
                f"  {failure.rel}:{failure.line_count} "
                f"(regressed past recorded baseline {failure.limit})"
            )


def main(argv: list[str] | None = None) -> int:
    """CLI entry point. Return 0 if the ratchet holds, 1 on any failure."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--max",
        type=int,
        default=DEFAULT_MAX_LINES,
        help=f"Cap for non-baselined files (default: {DEFAULT_MAX_LINES}).",
    )
    args = parser.parse_args(argv)

    repo_root = _repo_root()
    scan_roots = discover_package_src_roots(repo_root)
    result = check_file_size(
        scan_roots,
        rel_to=repo_root,
        max_lines=args.max,
    )
    _print_report(result, args.max)
    return 1 if result.failures else 0


if __name__ == "__main__":
    sys.exit(main())
