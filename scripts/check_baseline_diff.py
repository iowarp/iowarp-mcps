#!/usr/bin/env python3
"""CI-only guard: catch same-commit ratchet-baseline inflation and rename laundering.

``scripts/check_file_size.py``'s static checker can only see ONE commit's
state -- the current ``RATCHET_BASELINE`` dict and the current file tree. It
cannot see whether a baseline entry moved because a review-worthy growth
happened. Two attacks slip past it silently (PR #364 review finding 4,
round 2):

1. Grow a file's line count AND bump its ``RATCHET_BASELINE`` entry to the
   exact new value in the same commit -- the static checker sees an exact
   match, not a change; nothing fails.
2. Rename an oversized file to a fresh path and mint a brand-new baseline
   entry at its current (grown) size -- the checker sees a "new" entry,
   which only fails if it lands above the cap; a value at or under the cap
   passes with zero history-aware signal, and the file's lineage (it used to
   be smaller, under a different name) is gone.

Neither is visible to a script that only ever reads one tree. This module
closes both by comparing the embedded ``RATCHET_BASELINE`` dict between two
versions of ``check_file_size.py`` -- in CI, the PR head and the merge-base
with the target branch -- and reporting a violation for any entry that
increased, or any brand-new entry above the cap. Decreases and removals are
never violations (a file leaving the baseline, or shrinking, is exactly what
the ratchet wants).

This is deliberately a SEPARATE module from ``check_file_size.py``: the
static checker stays a pure, single-tree, ref-independent check (usable
locally with no git history at all); this module is PR-context-only (it
needs two versions of the same file to diff) and is wired into CI as its own
guard, not folded into the static checker's own logic.

The cap a brand-new entry must stay under is read from ``DEFAULT_MAX_LINES``
in the BASE (merge-base) file's source, never imported from
``check_file_size.py`` live and never read from the head file (PR #364
review, round 3): a PR controls its own head content, so a PR that raised
its own ``DEFAULT_MAX_LINES`` alongside a brand-new over-cap baseline entry
must not get to grade its own homework with its own inflated cap.

If ``RATCHET_BASELINE`` did not exist at the base version at all (the target
branch has never had this file -- i.e. this PR is introducing the ratchet
system itself), there is no prior baseline to launder against; the CI step
that invokes this script skips calling it entirely in that case (see
``quality_control.yml``'s ``ratchet-baseline-diff-guard`` job), so this
module never has to special-case a base file that legitimately doesn't
exist -- ``base_file`` is always assumed to exist and parse correctly by the
time ``main`` runs.

Run as part of CI (PR-context only, blocking) or locally::

    uv run python scripts/check_baseline_diff.py base_check_file_size.py scripts/check_file_size.py
"""

from __future__ import annotations

import argparse
import ast
import sys
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class BaselineViolation:
    """One baseline entry that changed in a way the diff guard rejects."""

    rel: str
    kind: str  # "increased" | "new_over_cap"
    base_value: int | None  # None for "new_over_cap" (no prior entry existed)
    head_value: int


class MissingConstantError(ValueError):
    """A required top-level constant could not be found in checker source."""


def extract_baseline(source: str) -> dict[str, int]:
    """Parse the ``RATCHET_BASELINE`` dict literal out of checker source, safely.

    Uses ``ast`` (parse + ``literal_eval``), never ``exec``/``import``, so
    this is safe to run against untrusted historical file content. Raises
    :class:`MissingConstantError` if no such assignment is found -- a
    malformed edit, since the CI step never calls this for a base file that
    legitimately doesn't exist (see the module docstring).
    """
    tree = ast.parse(source)
    for node in ast.walk(tree):
        if not isinstance(node, ast.AnnAssign):
            continue
        target = node.target
        if isinstance(target, ast.Name) and target.id == "RATCHET_BASELINE":
            if node.value is None:
                break
            value = ast.literal_eval(node.value)
            if not isinstance(value, dict):
                break
            return {str(k): int(v) for k, v in value.items()}
    raise MissingConstantError(
        "RATCHET_BASELINE: dict[str, int] = {...} assignment not found"
    )


def extract_default_max_lines(source: str) -> int:
    """Parse ``DEFAULT_MAX_LINES = <int>`` out of checker source, safely.

    Callers must pass the BASE (merge-base) file's source here, never the
    head file's -- see the module docstring for why the cap must come from
    history the PR itself cannot have edited.
    """
    tree = ast.parse(source)
    for node in ast.walk(tree):
        if not isinstance(node, ast.Assign):
            continue
        if any(
            isinstance(target, ast.Name) and target.id == "DEFAULT_MAX_LINES"
            for target in node.targets
        ):
            value = ast.literal_eval(node.value)
            if isinstance(value, int):
                return value
    raise MissingConstantError("DEFAULT_MAX_LINES = <int> assignment not found")


def diff_baselines(
    base: dict[str, int], head: dict[str, int], *, cap: int
) -> list[BaselineViolation]:
    """Compare two baseline dicts and report every same-commit-inflation violation.

    Args:
        base: The baseline as it stood at the merge-base with the target branch.
        head: The baseline as it stands at the PR head (or the tree under test).
        cap: The line-count cap a brand-new entry must stay at or under. Callers
            must derive this from the BASE side (see :func:`extract_default_max_lines`),
            never from head -- there is no safe default here on purpose.

    Returns:
        One :class:`BaselineViolation` per offending entry, sorted by path.
        An entry that decreased, was removed, or is new and at/under the cap
        produces no violation.
    """
    violations: list[BaselineViolation] = []
    for rel in sorted(head):
        head_value = head[rel]
        base_value = base.get(rel)
        if base_value is None:
            if head_value > cap:
                violations.append(
                    BaselineViolation(rel, "new_over_cap", None, head_value)
                )
            continue
        if head_value > base_value:
            violations.append(
                BaselineViolation(rel, "increased", base_value, head_value)
            )
    return violations


def _print_report(violations: list[BaselineViolation], cap: int) -> None:
    if not violations:
        print(
            "OK: no RATCHET_BASELINE entry increased, and no new entry landed "
            f"above the cap ({cap}), since the merge-base."
        )
        return
    print(
        f"FAIL: {len(violations)} RATCHET_BASELINE change(s) look like same-commit "
        "inflation or rename laundering (#364 review finding 4):"
    )
    for violation in violations:
        if violation.kind == "increased":
            print(
                f"  {violation.rel}: baseline raised {violation.base_value} -> "
                f"{violation.head_value} in this PR. A baseline entry may only "
                "ratchet down; if the file genuinely needs to be larger, that "
                "growth needs its own reviewed justification, not a same-commit "
                "bump to match."
            )
        else:
            print(
                f"  {violation.rel}: new RATCHET_BASELINE entry at "
                f"{violation.head_value} lines, above the cap ({cap}). If this "
                "path is a rename of a file that was already baselined, that "
                "history is invisible to this diff -- split the file (or lower "
                f"this entry to <= {cap} and drop it) instead of re-baselining "
                "it under a new name."
            )


def main(argv: list[str] | None = None) -> int:
    """CLI entry point. Return 0 if the diff guard holds, 1 on any violation."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "base_file", type=Path, help="check_file_size.py content at the merge-base"
    )
    parser.add_argument(
        "head_file", type=Path, help="check_file_size.py content at the PR head"
    )
    parser.add_argument(
        "--cap",
        type=int,
        default=None,
        help=(
            "Override the cap a brand-new entry must stay under. Defaults to "
            "DEFAULT_MAX_LINES read from base_file (the merge-base version) -- "
            "NEVER head_file -- so a PR cannot raise its own cap and bless its "
            "own brand-new over-cap baseline entry."
        ),
    )
    args = parser.parse_args(argv)

    base_source = args.base_file.read_text(encoding="utf-8")
    head_source = args.head_file.read_text(encoding="utf-8")
    base = extract_baseline(base_source)
    head = extract_baseline(head_source)
    cap = args.cap if args.cap is not None else extract_default_max_lines(base_source)
    violations = diff_baselines(base, head, cap=cap)
    _print_report(violations, cap)
    return 1 if violations else 0


if __name__ == "__main__":
    sys.exit(main())
