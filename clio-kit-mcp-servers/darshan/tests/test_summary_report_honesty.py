"""The summary report must not claim success when nothing was analysed."""

from __future__ import annotations

from typing import Any

import pytest

from darshan_mcp.capabilities import darshan_parser


@pytest.mark.asyncio
async def test_report_fails_when_every_section_failed(monkeypatch) -> None:
    """A machine without darshan-parser must not get a clean-looking report.

    Every section fails independently there. Reporting success anyway hands
    back an empty executive summary, no findings and no recommendations under
    a top-level success, which reads as a finished analysis of a job with no
    problems rather than as an analysis that never ran.
    """
    failure: dict[str, Any] = {
        "success": False,
        "error": "darshan-parser command not found. Is Darshan installed?",
    }

    async def fail(*_args: Any, **_kwargs: Any) -> dict[str, Any]:
        return dict(failure)

    for name in (
        "get_job_summary",
        "analyze_file_access_patterns",
        "get_io_performance_metrics",
        "identify_io_bottlenecks",
    ):
        monkeypatch.setattr(darshan_parser, name, fail)

    report = await darshan_parser.generate_io_summary_report("/tmp/not-a-darshan-log")

    assert report["success"] is False
    # The per-section errors stay visible, so a caller can see WHY nothing ran.
    sections = report["detailed_analysis"]
    assert all(section["success"] is False for section in sections.values())
    assert "darshan-parser command not found" in sections["job_summary"]["error"]
    assert report["executive_summary"] == {}
    assert report["key_findings"] == []


@pytest.mark.asyncio
async def test_report_succeeds_when_any_section_succeeded(monkeypatch) -> None:
    """A partial result is still a result, so one working section is enough."""

    async def ok(*_args: Any, **_kwargs: Any) -> dict[str, Any]:
        return {
            "success": True,
            "total_io_volume": 1024,
            "runtime_seconds": 60,
            "nprocs": 4,
        }

    async def fail(*_args: Any, **_kwargs: Any) -> dict[str, Any]:
        return {"success": False, "error": "unavailable"}

    monkeypatch.setattr(darshan_parser, "get_job_summary", ok)
    for name in (
        "analyze_file_access_patterns",
        "get_io_performance_metrics",
        "identify_io_bottlenecks",
    ):
        monkeypatch.setattr(darshan_parser, name, fail)

    report = await darshan_parser.generate_io_summary_report("/tmp/log")

    assert report["success"] is True
    assert report["executive_summary"]["process_count"] == 4
