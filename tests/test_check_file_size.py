"""Tests for the per-package god-file size ratchet (campaign #362, Slice 1).

PR #364 review finding 4 hardened this checker past a straight port of
clio-agent's script: a baseline sitting ABOVE a file's real line count used
to be advisory-only (an "OK (ratchet down)" message, exit 0). These tests
prove that specific gap is closed: at any ONE tree, every baseline entry
must exactly mirror its file's real line count, in both directions, or the
check fails -- no padding/slack is tolerated even when it looks directionally
plausible (see test_exact_match_invariant_rejects_padding_even_when_it_looks_
like_a_legitimate_bump).

What this module's checker does NOT, and structurally cannot, prove on its
own: whether a baseline NUMBER rose between two real commits (grow a file
and bump its baseline to an exact new match in the same commit -- padding
never enters into it, so the exact-match invariant alone does not catch
this). That is a cross-commit question a single-tree checker has no way to
answer; scripts/check_baseline_diff.py (tests/test_check_baseline_diff.py)
closes it by diffing the baseline between two commits instead.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import ModuleType

import pytest


def _load_checker() -> ModuleType:
    """Load the CI checker from its repository script path."""
    script = Path(__file__).resolve().parents[1] / "scripts" / "check_file_size.py"
    spec = importlib.util.spec_from_file_location("clio_kit_check_file_size", script)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"could not load file-size checker: {script}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


_CHECKER = _load_checker()
check_file_size = _CHECKER.check_file_size
discover_package_src_roots = _CHECKER.discover_package_src_roots
main = _CHECKER.main


def _write_lines(path: Path, count: int) -> Path:
    """Write ``count`` trivial lines to ``path``, creating parent dirs."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("x = 1\n" * count, encoding="utf-8")
    return path


def test_clean_tree_with_no_baseline_passes(tmp_path: Path) -> None:
    src = tmp_path / "pkg" / "src"
    _write_lines(src / "small.py", 10)

    failures = check_file_size([src], rel_to=tmp_path, max_lines=800, baseline={})

    assert failures == []


def test_new_file_over_default_cap_fails(tmp_path: Path) -> None:
    src = tmp_path / "pkg" / "src"
    _write_lines(src / "god_file.py", 801)

    failures = check_file_size([src], rel_to=tmp_path, max_lines=800, baseline={})

    assert len(failures) == 1
    failure = failures[0]
    assert failure.rel == "pkg/src/god_file.py"
    assert failure.line_count == 801
    assert failure.kind == "new"
    assert failure.limit == 800


def test_baselined_file_at_recorded_count_passes(tmp_path: Path) -> None:
    src = tmp_path / "pkg" / "src"
    _write_lines(src / "legacy.py", 1000)
    baseline = {"pkg/src/legacy.py": 1000}

    failures = check_file_size([src], rel_to=tmp_path, max_lines=800, baseline=baseline)

    assert failures == []


def test_baselined_file_growing_past_recorded_count_fails(tmp_path: Path) -> None:
    """The sabotage case: growing a known-oversized file past its pin must fail."""
    src = tmp_path / "pkg" / "src"
    _write_lines(src / "legacy.py", 1005)
    baseline = {"pkg/src/legacy.py": 1000}

    failures = check_file_size([src], rel_to=tmp_path, max_lines=800, baseline=baseline)

    assert len(failures) == 1
    failure = failures[0]
    assert failure.rel == "pkg/src/legacy.py"
    assert failure.line_count == 1005
    assert failure.kind == "regressed"
    assert failure.limit == 1000


def test_baseline_may_only_ratchet_down_never_silently_grow(tmp_path: Path) -> None:
    """A baseline higher than the file's real count is NEVER rewarded silently.

    (PR #364 review finding 7: this test used to assert the opposite -- zero
    failures on an inflated baseline -- which blessed exactly the bypass its
    name claimed to prevent. Finding 4 closed the gap this test now proves:
    "padded" baselines fail the build, full stop, no advisory-only path.)
    """
    src = tmp_path / "pkg" / "src"
    _write_lines(src / "legacy.py", 500)
    baseline = {"pkg/src/legacy.py": 1000}

    failures = check_file_size([src], rel_to=tmp_path, max_lines=800, baseline=baseline)

    assert len(failures) == 1
    failure = failures[0]
    assert failure.rel == "pkg/src/legacy.py"
    assert failure.kind == "padded"
    assert failure.line_count == 500
    assert failure.limit == 1000


def test_baselined_file_shrinking_still_over_cap_fails_as_padded(
    tmp_path: Path,
) -> None:
    """Shrinking but staying over the cap: still fails until the baseline is lowered."""
    src = tmp_path / "pkg" / "src"
    _write_lines(src / "legacy.py", 900)
    baseline = {"pkg/src/legacy.py": 1000}

    failures = check_file_size([src], rel_to=tmp_path, max_lines=800, baseline=baseline)

    assert len(failures) == 1
    assert failures[0].kind == "padded"
    assert failures[0].line_count == 900
    assert failures[0].limit == 1000


def test_baselined_file_shrinking_under_cap_fails_until_entry_removed(
    tmp_path: Path,
) -> None:
    src = tmp_path / "pkg" / "src"
    _write_lines(src / "legacy.py", 700)
    baseline = {"pkg/src/legacy.py": 1000}

    failures = check_file_size([src], rel_to=tmp_path, max_lines=800, baseline=baseline)

    assert len(failures) == 1
    assert failures[0].kind == "padded"
    assert failures[0].line_count == 700


def test_stale_baseline_entry_for_a_deleted_file_fails(tmp_path: Path) -> None:
    """A baseline entry for a file that no longer exists must be removed, not linger.

    Closes the resurrect-below-old-allowance gap (PR #364 review finding 4b):
    without this, deleting a baselined file leaves its old headroom
    unclaimed in RATCHET_BASELINE, and a LATER, unrelated file created at
    that same path would silently inherit an allowance it never earned.
    """
    src = tmp_path / "pkg" / "src"
    src.mkdir(parents=True)
    baseline = {"pkg/src/gone.py": 1200}

    failures = check_file_size([src], rel_to=tmp_path, max_lines=800, baseline=baseline)

    assert len(failures) == 1
    failure = failures[0]
    assert failure.rel == "pkg/src/gone.py"
    assert failure.kind == "stale"
    assert failure.line_count is None
    assert failure.limit == 1200


def test_exact_match_invariant_rejects_padding_even_when_it_looks_like_a_legitimate_bump(
    tmp_path: Path,
) -> None:
    """What the STATIC checker (this module) actually guarantees, precisely:
    at any ONE (file, baseline) snapshot, a baseline entry must equal the
    file's real line count EXACTLY -- never "at or above". This function has
    no concept of "before" or "after" at all; each call here is an
    independent, self-contained check of one (file-on-disk, baseline-dict)
    pair, not a simulated commit sequence.

    The baseline used below (1600, for a file that happens to be 1500 lines)
    is deliberately chosen to LOOK like a plausible bump -- growth is the
    direction a file's size usually moves in, so a reader could mistake a
    passing result here for "the checker tolerates a baseline that's ahead of
    the file, as long as the file might catch up." It does not: 1600 != 1500
    fails as "padded" on this single snapshot alone, for the same reason
    500 (under the file's real count) would also fail -- the invariant is
    EXACT match, full stop, with no directional exception.

    What this test does NOT and CANNOT prove: that a baseline NUMBER rising
    between two real commits (the same-commit "grow the file and its
    baseline together" attack, PR #364 review finding 4) is caught. That is
    a CROSS-COMMIT question -- it requires comparing the baseline dict as it
    stood at a PRIOR commit against its current value, which a checker that
    only ever reads one tree structurally cannot do. That protection lives
    in scripts/check_baseline_diff.py instead; see
    tests/test_check_baseline_diff.py, in particular
    test_same_commit_inflation_is_caught_even_when_the_static_checker_would_pass
    and the CLI meta-test test_cli_ignores_a_head_side_cap_increase.
    """
    src = tmp_path / "pkg" / "src"
    _write_lines(src / "legacy.py", 1500)

    padded_baseline = {"pkg/src/legacy.py": 1600}
    failures = check_file_size(
        [src], rel_to=tmp_path, max_lines=800, baseline=padded_baseline
    )

    assert len(failures) == 1
    failure = failures[0]
    assert failure.kind == "padded"
    assert failure.line_count == 1500
    assert failure.limit == 1600

    # The only baseline that passes for THIS snapshot is the exact real count.
    exact_baseline = {"pkg/src/legacy.py": 1500}
    assert (
        check_file_size([src], rel_to=tmp_path, max_lines=800, baseline=exact_baseline)
        == []
    )


def test_test_files_are_never_ratchet_guarded(tmp_path: Path) -> None:
    """A huge test_*.py, or anything under a tests/ directory, is out of scope."""
    src = tmp_path / "pkg" / "src"
    _write_lines(src / "test_something.py", 5000)
    _write_lines(src / "tests" / "big_fixture.py", 5000)

    failures = check_file_size([src], rel_to=tmp_path, max_lines=800, baseline={})

    assert failures == []


def test_multiple_scan_roots_are_all_checked(tmp_path: Path) -> None:
    src_a = tmp_path / "pkg_a" / "src"
    src_b = tmp_path / "pkg_b" / "src"
    _write_lines(src_a / "big.py", 900)
    _write_lines(src_b / "also_big.py", 900)

    failures = check_file_size(
        [src_a, src_b], rel_to=tmp_path, max_lines=800, baseline={}
    )

    offending = sorted(failure.rel for failure in failures)
    assert offending == ["pkg_a/src/big.py", "pkg_b/src/also_big.py"]


def test_discover_package_src_roots_finds_repo_root_pyproject_packages_and_agentic_search(
    tmp_path: Path,
) -> None:
    """PR #364 review finding 5: the repo root's own `src/` (the `clio_kit`
    launcher package) must be scanned too, not just clio-kit-mcp-servers/*.
    """
    (tmp_path / "pyproject.toml").write_text("", encoding="utf-8")
    (tmp_path / "src").mkdir()

    servers = tmp_path / "clio-kit-mcp-servers"
    (servers / "jarvis" / "src").mkdir(parents=True)
    (servers / "jarvis" / "pyproject.toml").write_text("", encoding="utf-8")
    # A directory without pyproject.toml is not a package and must be skipped.
    (servers / "not_a_package" / "src").mkdir(parents=True)
    # A package without a src/ tree contributes no root.
    (servers / "no_src_pkg" / "pyproject.toml").parent.mkdir(
        parents=True, exist_ok=True
    )
    (servers / "no_src_pkg" / "pyproject.toml").write_text("", encoding="utf-8")
    (tmp_path / "clio-agentic-search" / "src").mkdir(parents=True)
    (tmp_path / "clio-agentic-search" / "pyproject.toml").write_text(
        "", encoding="utf-8"
    )

    roots = discover_package_src_roots(tmp_path)

    assert (tmp_path / "src") in roots
    assert (servers / "jarvis" / "src") in roots
    assert (tmp_path / "clio-agentic-search" / "src") in roots
    assert (servers / "not_a_package" / "src") not in roots
    assert len(roots) == 3


def test_discover_package_src_roots_skips_repo_root_without_pyproject(
    tmp_path: Path,
) -> None:
    """A bare src/ at the repo root with no pyproject.toml is not a package."""
    (tmp_path / "src").mkdir()

    roots = discover_package_src_roots(tmp_path)

    assert roots == []


def test_cli_main_exit_code_reflects_the_ratchet(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """Sabotage the CLI end-to-end: a fresh god-file must fail, then revert to pass."""
    src = tmp_path / "clio-kit-mcp-servers" / "widget" / "src"
    (tmp_path / "clio-kit-mcp-servers" / "widget" / "pyproject.toml").parent.mkdir(
        parents=True, exist_ok=True
    )
    (tmp_path / "clio-kit-mcp-servers" / "widget" / "pyproject.toml").write_text(
        "", encoding="utf-8"
    )
    target = _write_lines(src / "server.py", 10)

    monkeypatch.setattr(_CHECKER, "_repo_root", lambda: tmp_path)
    monkeypatch.setattr(_CHECKER, "RATCHET_BASELINE", {})

    assert main([]) == 0
    capsys.readouterr()

    _write_lines(target, 801)
    assert main([]) == 1
    out = capsys.readouterr().out
    assert "clio-kit-mcp-servers/widget/src/server.py" in out

    _write_lines(target, 10)
    assert main([]) == 0


def test_real_tree_holds_at_recorded_baseline() -> None:
    """The live repository tree passes at the checked-in, exact baseline.

    Mirrors clio-agent's test_check_file_size.py::test_real_tree_holds_at_
    recorded_baseline -- a regression pin over the ACTUAL repo, not a
    synthetic fixture, run in addition to (never instead of) the synthetic
    cases above.
    """
    repo_root = Path(__file__).resolve().parents[1]
    scan_roots = discover_package_src_roots(repo_root)
    failures = check_file_size(scan_roots, rel_to=repo_root)
    assert failures == [], failures


def test_baseline_entries_all_exist_and_are_exact() -> None:
    """Every baselined path must point at a real file whose count matches exactly.

    Mirrors clio-agent's test_baseline_entries_all_exist -- extended (per PR
    #364 review finding 4) to check the count is EXACT, not merely that the
    file exists, since this checker no longer tolerates any drift.
    """
    repo_root = Path(__file__).resolve().parents[1]
    missing = [
        rel for rel in _CHECKER.RATCHET_BASELINE if not (repo_root / rel).is_file()
    ]
    assert not missing, missing

    mismatched = {}
    for rel, recorded in _CHECKER.RATCHET_BASELINE.items():
        actual = _CHECKER._count_lines(repo_root / rel)
        if actual != recorded:
            mismatched[rel] = {"recorded": recorded, "actual": actual}
    assert not mismatched, mismatched
