"""Fail CI when a pytest JUnit report contains skipped tests."""

from __future__ import annotations

import argparse
import sys
import xml.etree.ElementTree as ET
from collections.abc import Sequence
from pathlib import Path


class JUnitReportError(RuntimeError):
    """Raised when a JUnit report cannot prove that no tests were skipped."""


def _local_name(tag: str) -> str:
    """Return an XML tag name without its optional namespace."""
    return tag.rsplit("}", maxsplit=1)[-1]


def count_skipped_tests(report: Path) -> int:
    """Return the number of skipped test cases in a pytest JUnit report."""
    try:
        root = ET.parse(report).getroot()
    except (OSError, ET.ParseError) as exc:
        raise JUnitReportError(f"cannot read JUnit report {report}: {exc}") from exc

    skipped_cases = 0
    for test_case in root.iter():
        if _local_name(test_case.tag) != "testcase":
            continue
        if any(_local_name(child.tag) == "skipped" for child in test_case):
            skipped_cases += 1

    skipped_by_suite = 0
    for test_suite in root.iter():
        if _local_name(test_suite.tag) != "testsuite":
            continue
        if any(_local_name(child.tag) == "testsuite" for child in test_suite):
            continue
        raw_skipped = test_suite.get("skipped")
        if raw_skipped is None:
            continue
        try:
            suite_skipped = int(raw_skipped)
        except ValueError as exc:
            raise JUnitReportError(
                f"JUnit report {report} has a non-integer skipped count"
            ) from exc
        if suite_skipped < 0:
            raise JUnitReportError(
                f"JUnit report {report} has a negative skipped count"
            )
        skipped_by_suite += suite_skipped
    return max(skipped_cases, skipped_by_suite)


def main(argv: Sequence[str] | None = None) -> int:
    """Validate one pytest JUnit report and return a process exit status."""
    parser = argparse.ArgumentParser(
        description="Require a pytest JUnit report to contain zero skipped tests."
    )
    parser.add_argument("report", type=Path, help="Path to the pytest JUnit XML report")
    args = parser.parse_args(argv)

    try:
        skipped = count_skipped_tests(args.report)
    except JUnitReportError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    if skipped:
        print(
            f"error: {args.report} reports {skipped} skipped test(s); skips fail CI",
            file=sys.stderr,
        )
        return 1
    print(f"PASS: {args.report} reports zero skipped tests")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
