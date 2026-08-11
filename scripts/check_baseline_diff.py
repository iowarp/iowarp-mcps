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
   which only fails if it lands above :data:`DEFAULT_MAX_LINES`; a value at
   or under the cap passes with zero history-aware signal, and the file's
   lineage (it used to be smaller, under a different name) is gone.

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

If ``RATCHET_BASELINE`` did not exist at the base version at all (the target
branch has never had this file -- i.e. this PR is introducing the ratchet
system itself), there is no prior baseline to launder against, so
:func:`extract_baseline` simply returns an empty dict for a base file that
doesn't parse as containing the assignment because it's missing entirely;
see the CLI's ``--base-missing-ok`` handling below for the exact contract
the CI step relies on.

Run as part of CI (PR-context only, blocking) or locally::

    uv run python scripts/check_baseline_diff.py base_check_file_size.py scripts/check_file_size.py
"""

from __future__ import annotations

import argparse
import ast
import sys
from dataclasses import dataclass
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from check_file_size import DEFAULT_MAX_LINES  # noqa: E402


@dataclass(frozen=True)
class BaselineViolation:
    """One baseline entry that changed in a way the diff guard rejects."""

    rel: str
    kind: str  # "increased" | "new_over_cap"
    base_value: int | None  # None for "new_over_cap" (no prior entry existed)
    head_value: int


class MissingRatchetBaselineError(ValueError):
    """``RATCHET_BASELINE`` could not be found in a file that does exist."""


def extract_baseline(source: str) -> dict[str, int]:
    """Parse the ``RATCHET_BASELINE`` dict literal out of checker source, safely.

    Uses ``ast`` (parse + ``literal_eval``), never ``exec``/``import``, so
    this is safe to run against untrusted historical file content. Raises
    :class:`MissingRatchetBaselineError` if no such assignment is found --
    callers decide whether a missing assignment is a hard failure (a
    malformed edit) or an expected "file didn't exist yet" case (handled
    before ever calling this, by the CLI's missing-file branch).
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
    raise MissingRatchetBaselineError(
        "RATCHET_BASELINE: dict[str, int] = {...} assignment not found"
    )


def diff_baselines(
    base: dict[str, int], head: dict[str, int], *, cap: int = DEFAULT_MAX_LINES
) -> list[BaselineViolation]:
    """Compare two baseline dicts and report every same-commit-inflation violation.

    Args:
        base: The baseline as it stood at the merge-base with the target branch.
        head: The baseline as it stands at the PR head (or the tree under test).
        cap: The line-count cap a brand-new entry must stay at or under.

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
        "inflation or rename laundering (#364 review finding 4, round 2):"
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
        default=DEFAULT_MAX_LINES,
        help=f"Cap a brand-new baseline entry must stay under (default: {DEFAULT_MAX_LINES}).",
    )
    args = parser.parse_args(argv)

    base = extract_baseline(args.base_file.read_text(encoding="utf-8"))
    head = extract_baseline(args.head_file.read_text(encoding="utf-8"))
    violations = diff_baselines(base, head, cap=args.cap)
    _print_report(violations, args.cap)
    return 1 if violations else 0


if __name__ == "__main__":
    sys.exit(main())
