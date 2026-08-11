"""Tests for the PR-context ratchet-baseline diff guard (#364 review finding 4).

scripts/check_file_size.py's static checker can only ever see ONE tree; these
tests are the meta-test the review asked for on the CROSS-COMMIT half of the
guard: growing a file and its baseline entry together, or renaming an
oversized file into a fresh baseline entry, only becomes visible when two
versions of the baseline are diffed against each other -- which is what
scripts/check_baseline_diff.py does and what this file proves. Round 3 added
the cap-provenance meta-test: the cap must come from the BASE (merge-base)
file, never the head file, so a PR cannot raise its own cap alongside a
brand-new over-cap entry and have the guard bless it.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import ModuleType

import pytest


def _load_module() -> ModuleType:
    script = Path(__file__).resolve().parents[1] / "scripts" / "check_baseline_diff.py"
    spec = importlib.util.spec_from_file_location(
        "clio_kit_check_baseline_diff", script
    )
    if spec is None or spec.loader is None:
        raise RuntimeError(f"could not load baseline-diff guard: {script}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


_GUARD = _load_module()
BaselineViolation = _GUARD.BaselineViolation
MissingConstantError = _GUARD.MissingConstantError
diff_baselines = _GUARD.diff_baselines
extract_baseline = _GUARD.extract_baseline
extract_default_max_lines = _GUARD.extract_default_max_lines
main = _GUARD.main


def _checker_source(entries: dict[str, int], *, default_max_lines: int = 800) -> str:
    """Render a minimal check_file_size.py-shaped source with the given baseline."""
    lines = "\n".join(f'    "{rel}": {count},' for rel, count in entries.items())
    return (
        f"DEFAULT_MAX_LINES = {default_max_lines}\n\n"
        f"RATCHET_BASELINE: dict[str, int] = {{\n{lines}\n}}\n"
    )


# --- diff_baselines: the pure comparison logic -----------------------------


def test_no_changes_is_clean() -> None:
    base = {"pkg/a.py": 1000}
    head = {"pkg/a.py": 1000}
    assert diff_baselines(base, head, cap=800) == []


def test_increased_entry_is_a_violation() -> None:
    base = {"pkg/a.py": 1000}
    head = {"pkg/a.py": 1200}

    violations = diff_baselines(base, head, cap=800)

    assert violations == [BaselineViolation("pkg/a.py", "increased", 1000, 1200)]


def test_same_commit_inflation_is_caught_even_when_the_static_checker_would_pass() -> (
    None
):
    """The exact attack finding 4 named: grow the file AND its baseline together
    to a matching value. The static checker sees base==actual and is happy;
    this diff guard only looks at the baseline NUMBER moving, so it still
    catches it.
    """
    base = {"pkg/legacy.py": 1000}
    head = {"pkg/legacy.py": 1500}  # baseline bumped to match a grown file

    violations = diff_baselines(base, head, cap=800)

    assert len(violations) == 1
    assert violations[0].kind == "increased"
    assert violations[0].base_value == 1000
    assert violations[0].head_value == 1500


def test_decreased_entry_is_not_a_violation() -> None:
    base = {"pkg/a.py": 1000}
    head = {"pkg/a.py": 900}
    assert diff_baselines(base, head, cap=800) == []


def test_removed_entry_is_not_a_violation() -> None:
    base = {"pkg/a.py": 1000}
    head: dict[str, int] = {}
    assert diff_baselines(base, head, cap=800) == []


def test_new_entry_at_or_under_cap_is_not_a_violation() -> None:
    base: dict[str, int] = {}
    head = {"pkg/new.py": 800}
    assert diff_baselines(base, head, cap=800) == []


def test_new_entry_over_cap_is_a_violation() -> None:
    base: dict[str, int] = {}
    head = {"pkg/new.py": 801}

    violations = diff_baselines(base, head, cap=800)

    assert violations == [BaselineViolation("pkg/new.py", "new_over_cap", None, 801)]


def test_rename_laundering_is_caught_as_a_new_over_cap_entry() -> None:
    """The other attack finding 4 named: rename an oversized file and mint a
    fresh baseline entry, shedding its lineage. From the diff's point of
    view this is "old key removed" (fine) + "new key added over cap" (caught).
    """
    base = {"pkg/old_name.py": 1200}
    head = {"pkg/new_name.py": 1200}  # same size, different path -- a rename

    violations = diff_baselines(base, head, cap=800)

    assert violations == [
        BaselineViolation("pkg/new_name.py", "new_over_cap", None, 1200)
    ]


def test_multiple_entries_each_evaluated_independently() -> None:
    base = {"a.py": 1000, "b.py": 900, "c.py": 1100}
    head = {
        "a.py": 1000,  # unchanged
        "b.py": 700,  # decreased, fine
        # c.py removed, fine
        "d.py": 850,  # new, over cap, violation
    }

    violations = diff_baselines(base, head, cap=800)

    assert violations == [BaselineViolation("d.py", "new_over_cap", None, 850)]


# --- extract_baseline: parsing real check_file_size.py-shaped source -------


def test_extract_baseline_parses_a_real_shaped_source() -> None:
    source = _checker_source({"pkg/a.py": 1000, "pkg/b.py": 900})
    assert extract_baseline(source) == {"pkg/a.py": 1000, "pkg/b.py": 900}


def test_extract_baseline_handles_an_empty_dict() -> None:
    source = "RATCHET_BASELINE: dict[str, int] = {}\n"
    assert extract_baseline(source) == {}


def test_extract_baseline_raises_when_assignment_is_absent() -> None:
    with pytest.raises(MissingConstantError):
        extract_baseline("DEFAULT_MAX_LINES = 800\n")


def test_extract_baseline_does_not_execute_the_source() -> None:
    """ast.literal_eval, never exec/import -- a hostile historical revision
    of this file must not be able to run code just by being diffed.
    """
    hostile = (
        "import os\n"
        "os.environ['PWNED'] = '1'\n"
        "RATCHET_BASELINE: dict[str, int] = {'a.py': 900}\n"
    )
    assert extract_baseline(hostile) == {"a.py": 900}
    import os as _os

    assert "PWNED" not in _os.environ


# --- extract_default_max_lines: the cap must come from the BASE file -------


def test_extract_default_max_lines_parses_a_real_shaped_source() -> None:
    source = _checker_source({}, default_max_lines=800)
    assert extract_default_max_lines(source) == 800


def test_extract_default_max_lines_parses_a_non_default_value() -> None:
    source = _checker_source({}, default_max_lines=650)
    assert extract_default_max_lines(source) == 650


def test_extract_default_max_lines_raises_when_assignment_is_absent() -> None:
    with pytest.raises(MissingConstantError):
        extract_default_max_lines("RATCHET_BASELINE: dict[str, int] = {}\n")


# --- CLI end-to-end ----------------------------------------------------------


def test_cli_passes_on_a_clean_diff(tmp_path: Path) -> None:
    base_file = tmp_path / "base.py"
    head_file = tmp_path / "head.py"
    base_file.write_text(_checker_source({"a.py": 1000}), encoding="utf-8")
    head_file.write_text(_checker_source({"a.py": 900}), encoding="utf-8")

    assert main([str(base_file), str(head_file)]) == 0


def test_cli_fails_on_same_commit_inflation(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    base_file = tmp_path / "base.py"
    head_file = tmp_path / "head.py"
    base_file.write_text(_checker_source({"a.py": 1000}), encoding="utf-8")
    head_file.write_text(_checker_source({"a.py": 1500}), encoding="utf-8")

    assert main([str(base_file), str(head_file)]) == 1
    out = capsys.readouterr().out
    assert "a.py" in out
    assert "1000" in out and "1500" in out


def test_cli_fails_on_rename_laundering(tmp_path: Path) -> None:
    base_file = tmp_path / "base.py"
    head_file = tmp_path / "head.py"
    base_file.write_text(_checker_source({"old.py": 1200}), encoding="utf-8")
    head_file.write_text(_checker_source({"new.py": 1200}), encoding="utf-8")

    assert main([str(base_file), str(head_file)]) == 1


def test_cli_respects_custom_cap(tmp_path: Path) -> None:
    base_file = tmp_path / "base.py"
    head_file = tmp_path / "head.py"
    base_file.write_text(_checker_source({}), encoding="utf-8")
    head_file.write_text(_checker_source({"a.py": 500}), encoding="utf-8")

    assert main([str(base_file), str(head_file), "--cap", "400"]) == 1
    assert main([str(base_file), str(head_file), "--cap", "600"]) == 0


def test_cli_ignores_a_head_side_cap_increase(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """The meta-test PR #364 review round 3 asked for: a PR that raises its
    OWN DEFAULT_MAX_LINES alongside a brand-new, over-(old-)cap baseline
    entry must not get to grade its own homework. The cap is read from
    base_file (DEFAULT_MAX_LINES=800, the merge-base's real cap), never from
    head_file (DEFAULT_MAX_LINES=999999, the PR's own inflated one) -- so the
    new entry at 5000 lines still fails even though it's comfortably under
    the PR's self-raised cap.
    """
    base_file = tmp_path / "base.py"
    head_file = tmp_path / "head.py"
    base_file.write_text(_checker_source({}, default_max_lines=800), encoding="utf-8")
    head_file.write_text(
        _checker_source({"pkg/new_god_file.py": 5000}, default_max_lines=999999),
        encoding="utf-8",
    )

    assert main([str(base_file), str(head_file)]) == 1
    out = capsys.readouterr().out
    assert "pkg/new_god_file.py" in out
    assert "800" in out  # the cap actually applied is the base's, not 999999
