"""In-memory MCP tests: the tools exist and run on real SAC fixtures."""

from __future__ import annotations

from pathlib import Path

import pytest
from fastmcp import Client
from fastmcp.exceptions import ToolError

from sac_mcp.server import mcp


@pytest.mark.asyncio
async def test_tools_registered() -> None:
    async with Client(mcp) as client:
        tools = {t.name for t in await client.list_tools()}
    assert {"inspect_archive", "compute_trace_statistics", "plot_traces"} <= tools


@pytest.mark.asyncio
async def test_resource_and_prompt_registered() -> None:
    async with Client(mcp) as client:
        resources = {str(r.uri) for r in await client.list_resources()}
        prompts = {p.name for p in await client.list_prompts()}
    assert "sac://capabilities" in resources
    assert "analyze_sac_archive" in prompts


@pytest.mark.asyncio
async def test_inspect_archive_on_archive(sac_archive: Path) -> None:
    async with Client(mcp) as client:
        result = await client.call_tool(
            "inspect_archive", {"filepath": str(sac_archive)}
        )
    data = result.data
    assert data["status"] == "success"
    assert data["sac_trace_count"] == 3  # notes.txt ignored
    assert "P" in data["phases"]
    assert "S" in data["phases"]


@pytest.mark.asyncio
async def test_inspect_archive_member_filter(sac_archive: Path) -> None:
    async with Client(mcp) as client:
        result = await client.call_tool(
            "inspect_archive", {"filepath": str(sac_archive), "member_filter": "bhn"}
        )
    assert result.data["sac_trace_count"] == 1


@pytest.mark.asyncio
async def test_inspect_single_sac_file(sac_file: Path) -> None:
    async with Client(mcp) as client:
        result = await client.call_tool("inspect_archive", {"filepath": str(sac_file)})
    assert result.data["sac_trace_count"] == 1
    assert result.data["sample_members"] == ["IU.ANMO.00.BHZ.sac"]


@pytest.mark.asyncio
async def test_compute_trace_statistics(sac_archive: Path) -> None:
    async with Client(mcp) as client:
        result = await client.call_tool(
            "compute_trace_statistics", {"filepath": str(sac_archive), "max_traces": 2}
        )
    data = result.data
    assert data["status"] == "success"
    assert data["sac_trace_count"] == 3
    assert data["traces_analyzed"] == 2
    assert data["traces_truncated"] is True
    first = data["traces"][0]
    for key in ("min", "max", "mean", "std", "peak_abs", "npts", "delta_s"):
        assert key in first
    assert first["peak_abs"] >= abs(first["max"]) - 1e-6


@pytest.mark.asyncio
async def test_compute_statistics_on_single_file(sac_file: Path) -> None:
    async with Client(mcp) as client:
        result = await client.call_tool(
            "compute_trace_statistics", {"filepath": str(sac_file)}
        )
    data = result.data
    assert data["traces_analyzed"] == 1
    assert data["traces"][0]["npts"] == 200
    assert data["traces"][0]["delta_s"] == pytest.approx(0.01, rel=1e-4)


@pytest.mark.asyncio
async def test_plot_traces(sac_archive: Path, tmp_path: Path) -> None:
    out = tmp_path / "traces.png"
    async with Client(mcp) as client:
        result = await client.call_tool(
            "plot_traces",
            {"filepath": str(sac_archive), "max_traces": 3, "output_path": str(out)},
        )
    data = result.data
    assert data["status"] == "success"
    assert data["traces_plotted"] == 3
    assert out.is_file() and out.stat().st_size > 0


@pytest.mark.asyncio
async def test_plot_traces_default_output(
    sac_file: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Run with cwd set to a temp dir so the default artifact path does not
    # pollute the server directory.
    monkeypatch.chdir(tmp_path)
    async with Client(mcp) as client:
        result = await client.call_tool("plot_traces", {"filepath": str(sac_file)})
    out = Path(result.data["output_path"])
    assert out.is_file() and out.stat().st_size > 0
    assert tmp_path in out.parents


@pytest.mark.asyncio
async def test_missing_file_raises_tool_error() -> None:
    async with Client(mcp) as client:
        with pytest.raises(ToolError):
            await client.call_tool("inspect_archive", {"filepath": "/no/such/file.sac"})


@pytest.mark.asyncio
async def test_filter_with_no_match_raises(sac_archive: Path) -> None:
    async with Client(mcp) as client:
        with pytest.raises(ToolError):
            await client.call_tool(
                "compute_trace_statistics",
                {"filepath": str(sac_archive), "member_filter": "zzz-nope"},
            )
