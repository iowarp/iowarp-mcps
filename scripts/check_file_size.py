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
    # #376 (v3.7.2 mint): jarvis_add_step_tool and append_pkg_tool both gain
    # the `target` parameter (interceptor target-binding) plus its Field
    # description; 1582 -> 1605 (real count via `wc -l`).
    "clio-kit-mcp-servers/jarvis/src/jarvis_mcp/server.py": 1605,
    # #362 wave 1: NOT split this wave (deferred -- see the wave-1 PR
    # description). Still the 6-class monolith measured at campaign kickoff.
    # Next wave: split into owner modules by concern (pipeline lifecycle,
    # execution/progress, artifacts) the same way server.py was split.
    # gating fix (2026-08-12): jarvis_get_execution's artifact page gained a
    # bounded role="log" content read (content_max_bytes) -- the substantial
    # logic (path resolution, tail read, per-item error typing) went into a
    # NEW owner module (artifact_content.py), not here; this file only grew
    # by the trivial call-site wiring inside get_execution() that has to live
    # where get_execution() itself lives, 3521 -> 3529.
    # release/2.10.2 (#252 + v3.7.1 mint): terminal execution-output
    # declaration wiring merged in alongside the content-read call site above
    # -- both land in get_execution()'s call site, 3529 -> 3548 (real count,
    # not guessed -- verified via `wc -l` against the merged tree, after
    # de-duplicating the execution_root_from_record collision below).
    # #376 (v3.7.2 mint): interceptor target-binding -- append_pkg gains the
    # `target` parameter plus two new helpers (_is_interceptor_step,
    # _bind_interceptor_target) that thread it to JARVIS-CD's native
    # interceptors-list mechanism, and defer an interceptor's
    # configure_package() call (the find_library ordering defect) to when
    # JARVIS-CD itself needs it -- never, per Pipeline.start(). Kept in this
    # file rather than a new owner module: the logic is tightly coupled to
    # (and sits directly beside) _get_package/_package_config/
    # _kwargs_to_config_args, the same abstraction level as
    # _normalize_package_config_request just below it. 3548 -> 3659 (real
    # count via `wc -l`).
    "clio-kit-mcp-servers/jarvis/src/jarvis_mcp/capabilities/jarvis_handler.py": 3659,
    # #362: NOT split this wave -- out of wave-1 scope (jarvis-only). Flat
    # FastMCP function surface, no god-class; still needs an owner-module cut.
    "clio-kit-mcp-servers/hdf5/src/hdf5_mcp/server.py": 2415,
    # #362: NOT split this wave -- out of wave-1 scope. Single
    # VisualizationEngine god-class.
    "clio-kit-mcp-servers/paraview/src/paraview_mcp/implementation/paraview_capabilities.py": 2202,
    "clio-kit-mcp-servers/pandas/src/pandas_mcp/server.py": 1274,
    "clio-kit-mcp-servers/paraview/src/paraview_mcp/server.py": 1091,
    "clio-kit-mcp-servers/spack/src/spack_mcp/backend.py": 925,
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
    # gating fix (2026-08-12): jarvis contract spec bumped v3.6 -> v3.7
    # (jarvis_get_execution's artifacts filter gained content_max_bytes, a
    # deliberate wire-visible additive change); one more historical-artifact
    # entry (jarvis-user-v3.6.json) recorded on the develop line this
    # cherry-picked from, 931 -> 932.
    # release/2.10.2: cherry-picked the v3.7 mint onto release/2.10.2 (built
    # off main, not full develop -- the unrelated spack/scheduler commits
    # ahead of it on develop were deliberately left out of this release), then
    # v3.7.1 mint (execution-output declarations, #252) added one more
    # historical-artifact entry (jarvis-user-v3.7.json). Real count on THIS
    # tree verified via `wc -l`, not carried over from develop's number: 923.
    # #376 (v3.7.2 mint): one more historical-artifact entry
    # (jarvis-user-v3.7.1.json) as v3.7.1 retires to historical; 923 -> 924.
    "src/clio_kit/mcp_contracts.py": 924,
    # release/2.10.2: merging fix/execution-output-artifacts (#252 --
    # execution_output_artifact_events/_hash_regular_file, terminal
    # execution-output declarations) alongside the v3.7 content-read mint's
    # own inline wiring in artifact_query_page/_validate_query_filters (the
    # substantial content-read LOGIC lives in artifact_content.py, imported
    # here, not duplicated) push this past the default new-file threshold for
    # the first time. Both branches had independently defined
    # execution_root_from_record (artifact_content.py's grounded-in-jarvis-cd
    # version vs. this file's script_path-fallback version) -- consolidated
    # to one definition owned by artifact_content.py (extended with the
    # script_path fallback) so the two call sites in jarvis_handler.py no
    # longer silently resolve to whichever import happened to shadow the
    # other. Real count verified via `wc -l`: 846.
    "clio-kit-mcp-servers/jarvis/src/jarvis_mcp/artifacts.py": 846,
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
