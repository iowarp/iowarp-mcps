#!/usr/bin/env python3
"""Ratchet guard against god-files across clio-kit's packages.

Ported from clio-agent's ``scripts/check_file_size.py`` (iowarp/clio-agent,
#714/#767) for clio-kit campaign #362 ("server code health"), Slice 1, and
then hardened past what that script enforces (PR #364 review finding 4):
clio-agent's version treats a baseline sitting ABOVE a file's real line count
as merely advisory (an "OK (ratchet down)" message, exit 0) -- which means a
single commit can grow a file AND raise its baseline to match, banking unused
headroom with zero build signal. This version does not tolerate that gap: a
baseline entry must be an EXACT mirror of reality at all times.

Walks every package's ``src/`` tree -- the root ``clio_kit`` package plus one
per ``clio-kit-mcp-servers/<name>`` (any directory with a ``pyproject.toml``)
plus ``clio-agentic-search`` -- and enforces a per-file line-count ratchet:

* A file **not** in :data:`RATCHET_BASELINE` may not exceed
  :data:`DEFAULT_MAX_LINES` -- a brand-new god-file fails the check.
* A file **in** :data:`RATCHET_BASELINE` (a known-oversized module awaiting
  decomposition) must match its recorded line count EXACTLY:

  - Grow past it ("regressed") -- FAILS.
  - Sit below it ("padded" -- the baseline claims more lines than the file
    actually has, whether from an un-recorded shrink or a same-commit
    baseline bump that outpaced the real growth) -- FAILS. There is no
    advisory-only path here; every gram of ratchet headroom must be spent
    the moment it's earned, never banked for later.
  - A baseline entry pointing at a file that no longer exists ("stale") --
    FAILS. A deleted or renamed file's old allowance must be removed in the
    same change, so nothing can later resurrect at that path and inherit
    unearned headroom.

The baseline may only ratchet DOWN, and every entry must be live and exact.
When a file shrinks, lower its :data:`RATCHET_BASELINE` number to match (or
drop the entry once it falls under :data:`DEFAULT_MAX_LINES`) in the SAME
change that shrank it -- the check fails until you do.

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

# Per-file ratchet baseline: the known-oversized modules at their EXACT
# current line counts (measured on campaign/362-kit-health, 2026-08-10/11),
# recorded so they cannot regrow. These are the files awaiting further
# decomposition (clio-kit campaign #362, Slice 1). Every entry must equal its
# file's real line count at all times -- the check fails on any mismatch in
# either direction (see the module docstring). Paths are relative to the
# repository root and use forward slashes.
RATCHET_BASELINE: dict[str, int] = {
    # #362 wave 1: server.py's 44 model classes + package-discovery/search
    # helpers moved to owner modules (jarvis_mcp/models/*, package_discovery.py),
    # 3109 -> 1323, then +259 (PR #364 review findings 1/3: the contract pins'
    # full tool-record capture plus the FULL backward-compatibility re-export
    # surface -- every name importable from the pre-split server.py, not a
    # hand-picked subset; see server.py's own header comment). The remaining
    # size is the `@mcp.tool` registration surface for 30+ tools, the CLI
    # entry points, and that compatibility re-export block; ratchets down
    # with a further per-concern tool-registration split if one is ever
    # justified (the re-export block would move with it).
    "clio-kit-mcp-servers/jarvis/src/jarvis_mcp/server.py": 1582,
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
    # clio-kit#370: SpackInstallResult + install_spec moved to a new owner
    # module (provisioning.py, real installs with a full on-disk build log
    # and typed recipe_not_found/build_failure/timed_out errors), shedding
    # this file to 890 lines. Not fully split below the cap this wave --
    # still the `find`/`locate`/`environment` backend plus the bounded
    # subprocess/Windows-job primitives every owner module composes with.
    "clio-kit-mcp-servers/spack/src/spack_mcp/backend.py": 890,
    # #362 (PR #364 review finding 5): discovery previously excluded the root
    # `clio_kit` package (the `clio-kit` launcher CLI itself) entirely --
    # these three were never scanned. Baselined at their measured counts, not
    # split this wave.
    "src/clio_kit/__init__.py": 958,
    # clio-kit#370: spack contract spec bumped to v2.2 (search/info tools
    # added to the curated surface) and a new historical-artifact entry
    # (spack-user-v2.1.json) recorded, 921 -> 930 (ruff-formatted). Fix round
    # (review kit-spack-review.md, R2): search gained repos_unreadable/
    # truncated fields, forcing v2.2 -> v2.3; one more historical-artifact
    # entry (spack-user-v2.2.json) recorded, 930 -> 931.
    "src/clio_kit/mcp_contracts.py": 931,
    "src/clio_kit/env_cache.py": 843,
    "clio-kit-mcp-servers/darshan/src/darshan_mcp/capabilities/darshan_parser.py": 857,
    "clio-kit-mcp-servers/parquet/src/parquet_mcp/capabilities/parquet_handler.py": 839,
    "clio-kit-mcp-servers/node-hardware/src/node_hardware_mcp/mcp_handlers.py": 819,
}

# Directory holding every MCP server package (one subdirectory per server).
MCP_SERVERS_ROOT = "clio-kit-mcp-servers"

# Additional package roots outside clio-kit-mcp-servers, checked for a `src/`
# tree the same way. clio-agentic-search is a standalone service (not an MCP
# server) but is still a first-class package in this repo's code-health
# scope; the repository root itself ships the `clio_kit` launcher package
# (its own `pyproject.toml` + `src/clio_kit/`) and was previously the one
# first-class package this scan silently skipped (PR #364 review finding 5).
EXTRA_PACKAGE_ROOTS = (".", "clio-agentic-search")


class Failure(NamedTuple):
    """A file (or baseline entry) that breaks the ratchet (fails the check)."""

    rel: str
    line_count: int | None  # None only for "stale" -- the file does not exist
    kind: str  # "new" | "regressed" | "padded" | "stale"
    limit: int | None  # the cap/baseline it broke; None only for "new" with no baseline


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

    The repository root's own ``src/`` (the ``clio_kit`` launcher package,
    if ``repo_root/pyproject.toml`` exists), one per
    ``clio-kit-mcp-servers/<name>`` directory that has a ``pyproject.toml``
    (mirroring ``.github/workflows/quality_control.yml``'s ``discover-mcps``
    step, minus its Chronolog exclusion -- this is a code-health scan, not a
    release gate, and Chronolog can grow a god-file same as any other
    package), plus any other :data:`EXTRA_PACKAGE_ROOTS` that have a
    ``src/`` tree of their own.
    """
    roots: list[Path] = []
    for extra in EXTRA_PACKAGE_ROOTS:
        pkg_dir = repo_root / extra
        if not (pkg_dir / "pyproject.toml").is_file():
            continue
        src_dir = pkg_dir / "src"
        if src_dir.is_dir():
            roots.append(src_dir)
    servers_dir = repo_root / MCP_SERVERS_ROOT
    if servers_dir.is_dir():
        for pkg_dir in sorted(servers_dir.iterdir()):
            if not pkg_dir.is_dir() or not (pkg_dir / "pyproject.toml").is_file():
                continue
            src_dir = pkg_dir / "src"
            if src_dir.is_dir():
                roots.append(src_dir)
    return roots


def check_file_size(
    scan_roots: list[Path],
    *,
    rel_to: Path,
    max_lines: int = DEFAULT_MAX_LINES,
    baseline: dict[str, int] | None = None,
) -> list[Failure]:
    """Evaluate the per-file line-count ratchet under every root in ``scan_roots``.

    Args:
        scan_roots: Directory trees to walk for ``*.py`` files (one per
            package's ``src/`` directory).
        rel_to: Base directory used to compute the forward-slash relative
            path that keys into ``baseline`` (the repository root).
        max_lines: Cap applied to files not present in ``baseline``.
        baseline: Per-file EXACT recorded line counts. Defaults to
            :data:`RATCHET_BASELINE`.

    Returns:
        Every offense: a brand-new god-file, a baselined file that grew past
        its recorded count, a baselined file that no longer matches its
        recorded count exactly (in either direction), or a baseline entry
        whose file no longer exists. Empty means the ratchet holds.
    """
    if baseline is None:
        baseline = RATCHET_BASELINE

    failures: list[Failure] = []
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
                failures.append(Failure(rel, count, "padded", recorded))
            # count == recorded: the baseline is exact -- no failure.

    for rel, recorded in baseline.items():
        if rel not in seen:
            failures.append(Failure(rel, None, "stale", recorded))

    return failures


def _print_report(failures: list[Failure], max_lines: int) -> None:
    """Print the ratchet report."""
    if not failures:
        print(
            "OK: every ratchet baseline entry exactly matches its file's real "
            f"line count, and no new file exceeds the cap ({max_lines})."
        )
        return

    print(f"FAIL: {len(failures)} file(s) break the size ratchet (#362):")
    for failure in failures:
        if failure.kind == "new":
            print(
                f"  {failure.rel}:{failure.line_count} "
                f"(new file exceeds cap {failure.limit})"
            )
        elif failure.kind == "regressed":
            print(
                f"  {failure.rel}:{failure.line_count} "
                f"(regressed past recorded baseline {failure.limit})"
            )
        elif failure.kind == "padded":
            assert failure.line_count is not None
            if failure.line_count <= max_lines:
                print(
                    f"  {failure.rel}:{failure.line_count} (baseline claims "
                    f"{failure.limit} but the file is only {failure.line_count} "
                    f"lines, under the {max_lines} cap -- remove its "
                    "RATCHET_BASELINE entry in scripts/check_file_size.py)"
                )
            else:
                print(
                    f"  {failure.rel}:{failure.line_count} (baseline claims "
                    f"{failure.limit} but the file is only {failure.line_count} "
                    f"lines -- lower its RATCHET_BASELINE entry to "
                    f"{failure.line_count} in scripts/check_file_size.py)"
                )
        elif failure.kind == "stale":
            print(
                f"  {failure.rel} (baselined at {failure.limit} lines but the "
                "file no longer exists -- remove its RATCHET_BASELINE entry "
                "in scripts/check_file_size.py)"
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
    failures = check_file_size(
        scan_roots,
        rel_to=repo_root,
        max_lines=args.max,
    )
    _print_report(failures, args.max)
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
