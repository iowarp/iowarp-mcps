"""Tests for the dependency-free JUnit skip assertion."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import ModuleType

import pytest


def _load_validator() -> ModuleType:
    """Load the CI validator from its repository script path."""
    script = (
        Path(__file__).resolve().parents[1] / "scripts" / "assert_no_skipped_tests.py"
    )
    spec = importlib.util.spec_from_file_location("clio_kit_assert_no_skips", script)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"could not load JUnit validator: {script}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


_VALIDATOR = _load_validator()
JUnitReportError = _VALIDATOR.JUnitReportError
count_skipped_tests = _VALIDATOR.count_skipped_tests
main = _VALIDATOR.main


def _write_report(path: Path, test_cases: str) -> Path:
    """Write a minimal pytest-compatible JUnit report."""
    path.write_text(
        f'<testsuites><testsuite name="pytest">{test_cases}</testsuite></testsuites>',
        encoding="utf-8",
    )
    return path


def test_zero_skips_passes(tmp_path: Path) -> None:
    """A report containing only passing tests is accepted."""
    report = _write_report(tmp_path / "junit.xml", '<testcase name="passes" />')

    assert count_skipped_tests(report) == 0
    assert main([str(report)]) == 0


def test_skip_fails_even_with_an_xml_namespace(tmp_path: Path) -> None:
    """Skipped test cases are detected independently of XML namespaces."""
    report = tmp_path / "junit.xml"
    report.write_text(
        '<testsuites xmlns="urn:junit"><testsuite name="pytest">'
        '<testcase name="skipped"><skipped message="reason" /></testcase>'
        "</testsuite></testsuites>",
        encoding="utf-8",
    )

    assert count_skipped_tests(report) == 1
    assert main([str(report)]) == 1


def test_suite_summary_skip_fails_without_case_detail(tmp_path: Path) -> None:
    """The pytest suite summary remains authoritative if case detail is absent."""
    report = tmp_path / "junit.xml"
    report.write_text(
        '<testsuites><testsuite name="pytest" skipped="2" /></testsuites>',
        encoding="utf-8",
    )

    assert count_skipped_tests(report) == 2
    assert main([str(report)]) == 1


def test_missing_or_malformed_report_fails(tmp_path: Path) -> None:
    """Missing and malformed evidence cannot silently pass the assertion."""
    with pytest.raises(JUnitReportError, match="cannot read JUnit report"):
        count_skipped_tests(tmp_path / "missing.xml")

    malformed = tmp_path / "malformed.xml"
    malformed.write_text("<testsuite>", encoding="utf-8")
    with pytest.raises(JUnitReportError, match="cannot read JUnit report"):
        count_skipped_tests(malformed)
    assert main([str(malformed)]) == 1

    invalid_count = tmp_path / "invalid-count.xml"
    invalid_count.write_text(
        '<testsuites><testsuite skipped="unknown" /></testsuites>',
        encoding="utf-8",
    )
    with pytest.raises(JUnitReportError, match="non-integer skipped count"):
        count_skipped_tests(invalid_count)
