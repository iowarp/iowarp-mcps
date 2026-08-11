"""Tests for the per-package god-file size ratchet (campaign #362, Slice 1)."""

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

    result = check_file_size([src], rel_to=tmp_path, max_lines=800, baseline={})

    assert result.failures == []
    assert result.ratchet_downs == []


def test_new_file_over_default_cap_fails(tmp_path: Path) -> None:
    src = tmp_path / "pkg" / "src"
    _write_lines(src / "god_file.py", 801)

    result = check_file_size([src], rel_to=tmp_path, max_lines=800, baseline={})

    assert len(result.failures) == 1
    failure = result.failures[0]
    assert failure.rel == "pkg/src/god_file.py"
    assert failure.line_count == 801
    assert failure.kind == "new"
    assert failure.limit == 800


def test_baselined_file_at_recorded_count_passes(tmp_path: Path) -> None:
    src = tmp_path / "pkg" / "src"
    _write_lines(src / "legacy.py", 1000)
    baseline = {"pkg/src/legacy.py": 1000}

    result = check_file_size([src], rel_to=tmp_path, max_lines=800, baseline=baseline)

    assert result.failures == []
    assert result.ratchet_downs == []


def test_baselined_file_growing_past_recorded_count_fails(tmp_path: Path) -> None:
    """The sabotage case: growing a known-oversized file past its pin must fail."""
    src = tmp_path / "pkg" / "src"
    _write_lines(src / "legacy.py", 1005)
    baseline = {"pkg/src/legacy.py": 1000}

    result = check_file_size([src], rel_to=tmp_path, max_lines=800, baseline=baseline)

    assert len(result.failures) == 1
    failure = result.failures[0]
    assert failure.rel == "pkg/src/legacy.py"
    assert failure.line_count == 1005
    assert failure.kind == "regressed"
    assert failure.limit == 1000


def test_baselined_file_shrinking_is_an_advisory_ratchet_down(tmp_path: Path) -> None:
    """Shrinking never fails the build -- it's reported so the baseline can ratchet down."""
    src = tmp_path / "pkg" / "src"
    _write_lines(src / "legacy.py", 900)
    baseline = {"pkg/src/legacy.py": 1000}

    result = check_file_size([src], rel_to=tmp_path, max_lines=800, baseline=baseline)

    assert result.failures == []
    assert len(result.ratchet_downs) == 1
    ratchet_down = result.ratchet_downs[0]
    assert ratchet_down.rel == "pkg/src/legacy.py"
    assert ratchet_down.line_count == 900
    assert ratchet_down.baseline == 1000
    assert ratchet_down.under_cap is False


def test_baselined_file_shrinking_under_the_cap_flags_entry_removal(
    tmp_path: Path,
) -> None:
    src = tmp_path / "pkg" / "src"
    _write_lines(src / "legacy.py", 700)
    baseline = {"pkg/src/legacy.py": 1000}

    result = check_file_size([src], rel_to=tmp_path, max_lines=800, baseline=baseline)

    assert result.failures == []
    assert result.ratchet_downs[0].under_cap is True


def test_baseline_may_only_ratchet_down_never_silently_grow(tmp_path: Path) -> None:
    """A baseline higher than the file's real count is never rewarded silently."""
    src = tmp_path / "pkg" / "src"
    _write_lines(src / "legacy.py", 500)
    baseline = {"pkg/src/legacy.py": 1000}

    result = check_file_size([src], rel_to=tmp_path, max_lines=800, baseline=baseline)

    assert result.failures == []
    assert result.ratchet_downs[0].baseline == 1000
    assert result.ratchet_downs[0].line_count == 500


def test_test_files_are_never_ratchet_guarded(tmp_path: Path) -> None:
    """A huge test_*.py, or anything under a tests/ directory, is out of scope."""
    src = tmp_path / "pkg" / "src"
    _write_lines(src / "test_something.py", 5000)
    _write_lines(src / "tests" / "big_fixture.py", 5000)

    result = check_file_size([src], rel_to=tmp_path, max_lines=800, baseline={})

    assert result.failures == []


def test_multiple_scan_roots_are_all_checked(tmp_path: Path) -> None:
    src_a = tmp_path / "pkg_a" / "src"
    src_b = tmp_path / "pkg_b" / "src"
    _write_lines(src_a / "big.py", 900)
    _write_lines(src_b / "also_big.py", 900)

    result = check_file_size(
        [src_a, src_b], rel_to=tmp_path, max_lines=800, baseline={}
    )

    offending = sorted(failure.rel for failure in result.failures)
    assert offending == ["pkg_a/src/big.py", "pkg_b/src/also_big.py"]


def test_discover_package_src_roots_finds_pyproject_packages_and_agentic_search(
    tmp_path: Path,
) -> None:
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

    roots = discover_package_src_roots(tmp_path)

    assert (servers / "jarvis" / "src") in roots
    assert (tmp_path / "clio-agentic-search" / "src") in roots
    assert (servers / "not_a_package" / "src") not in roots
    assert len(roots) == 2


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
