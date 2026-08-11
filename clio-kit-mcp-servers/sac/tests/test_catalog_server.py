"""In-memory MCP tests: the tools exist and run on real synthetic catalogs.

The seismic science (Mc, b-value, Omori decay) is verified on synthetic
catalogs; the data-vs-verdict separation is asserted; and rendering is exercised
on disk. Nothing here touches the network.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from fastmcp import Client
from fastmcp.exceptions import ToolError

from sac_mcp.implementation import (
    _b_value,
    _magnitude_of_completeness,
    _omori_decay,
)
from sac_mcp.server import mcp

from .conftest import gr_magnitudes, mainshock_aftershock_events


# ----------------------------- wiring ------------------------------------


@pytest.mark.asyncio
async def test_tools_registered() -> None:
    async with Client(mcp) as client:
        tools = {t.name for t in await client.list_tools()}
    assert {"analyze_sequence", "plot_sequence"} <= tools


@pytest.mark.asyncio
async def test_query_catalog_is_gone() -> None:
    async with Client(mcp) as client:
        tools = {t.name for t in await client.list_tools()}
    assert "query_catalog" not in tools


@pytest.mark.asyncio
async def test_resource_and_prompt_registered() -> None:
    async with Client(mcp) as client:
        resources = {str(r.uri) for r in await client.list_resources()}
        prompts = {p.name for p in await client.list_prompts()}
    assert "sac://capabilities" in resources
    assert "characterize_sequence" in prompts


# ----------------------------- science -----------------------------------


def test_b_value_recovers_known_slope() -> None:
    mags = gr_magnitudes(b=1.0, mc=2.0)
    stats = _b_value(mags, mc=2.0)
    assert stats["b_value"] is not None
    assert 0.85 <= stats["b_value"] <= 1.15, stats


def test_b_value_declines_on_too_few_events() -> None:
    assert _b_value([5.0, 5.1, 5.2], mc=4.5)["b_value"] is None


def test_mc_estimates_near_true_completeness() -> None:
    mags = gr_magnitudes(b=1.0, mc=2.0)
    mc = _magnitude_of_completeness(mags)
    assert mc is not None and abs(mc - 2.0) <= 0.4, mc


def test_omori_decay_is_monotonic_for_aftershocks() -> None:
    events = mainshock_aftershock_events()
    t0 = max(events, key=lambda e: e["mag"])["time_ms"]
    decay = _omori_decay(events, t0)
    rates = [b["rate_per_day"] for b in decay["rate_buckets"][:5]]
    assert rates[0] > rates[-1]  # decaying
    assert decay["omori_p_estimate"] is not None and decay["omori_p_estimate"] > 0


# ----------------- analyze_sequence (data, not verdict) ------------------


@pytest.mark.asyncio
async def test_analyze_returns_stats_not_classification(
    aftershock_geojson: Path,
) -> None:
    async with Client(mcp) as client:
        result = await client.call_tool(
            "analyze_sequence", {"catalog_path": str(aftershock_geojson)}
        )
    res = result.data
    st = res["statistics"]
    # data is present
    assert st["largest_event"]["magnitude"] == 6.5
    assert st["bath_gap"] is not None and st["bath_gap"] > 1.0
    assert st["fraction_after_largest"] == 1.0  # mainshock first, all after
    assert st["temporal_decay"]["omori_p_estimate"] is not None
    # the tool must NOT make the judgment
    blob = json.dumps(res).lower()
    assert "sequence_type" not in blob
    assert "classification" not in blob
    assert "aftershock" not in blob and "swarm" not in blob


@pytest.mark.asyncio
async def test_analyze_reads_feature_collection(
    aftershock_feature_collection: Path,
) -> None:
    async with Client(mcp) as client:
        result = await client.call_tool(
            "analyze_sequence", {"catalog_path": str(aftershock_feature_collection)}
        )
    assert result.data["statistics"]["largest_event"]["magnitude"] == 6.5


@pytest.mark.asyncio
async def test_analyze_reads_csv(aftershock_csv: Path) -> None:
    async with Client(mcp) as client:
        result = await client.call_tool(
            "analyze_sequence", {"catalog_path": str(aftershock_csv)}
        )
    res = result.data
    assert res["event_count"] == 25
    assert res["statistics"]["largest_event"]["magnitude"] == 6.5


@pytest.mark.asyncio
async def test_analyze_recovers_b_value_from_gr_catalog(gr_geojson: Path) -> None:
    async with Client(mcp) as client:
        result = await client.call_tool(
            "analyze_sequence", {"catalog_path": str(gr_geojson)}
        )
    st = result.data["statistics"]
    assert st["b_value"] is not None and 0.85 <= st["b_value"] <= 1.15


@pytest.mark.asyncio
async def test_analyze_empty_catalog_is_graceful(empty_geojson: Path) -> None:
    async with Client(mcp) as client:
        result = await client.call_tool(
            "analyze_sequence", {"catalog_path": str(empty_geojson)}
        )
    res = result.data
    assert res["ok"] and res["event_count"] == 0 and "statistics" not in res


@pytest.mark.asyncio
async def test_analyze_missing_file_raises_tool_error() -> None:
    async with Client(mcp) as client:
        with pytest.raises(ToolError):
            await client.call_tool(
                "analyze_sequence", {"catalog_path": "/no/such/catalog.json"}
            )


@pytest.mark.asyncio
async def test_analyze_unsupported_extension_raises(tmp_path: Path) -> None:
    bad = tmp_path / "catalog.txt"
    bad.write_text("not a catalog", encoding="utf-8")
    async with Client(mcp) as client:
        with pytest.raises(ToolError):
            await client.call_tool("analyze_sequence", {"catalog_path": str(bad)})


# ----------------------------- plot_sequence -----------------------------


@pytest.mark.asyncio
async def test_plot_renders_figure(aftershock_geojson: Path, tmp_path: Path) -> None:
    out = tmp_path / "seq.png"
    async with Client(mcp) as client:
        result = await client.call_tool(
            "plot_sequence",
            {
                "catalog_path": str(aftershock_geojson),
                "title": "t",
                "mc": 3.0,
                "b_value": 1.0,
                "output_path": str(out),
            },
        )
    res = result.data
    assert res["ok"] and out.stat().st_size > 5000
    assert res["panels"] == ["epicenter_map", "gutenberg_richter", "temporal_evolution"]


@pytest.mark.asyncio
async def test_plot_default_output(
    aftershock_csv: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    async with Client(mcp) as client:
        result = await client.call_tool(
            "plot_sequence", {"catalog_path": str(aftershock_csv)}
        )
    out = Path(result.data["figure_path"])
    assert out.is_file() and out.stat().st_size > 5000
    assert tmp_path in out.parents


@pytest.mark.asyncio
async def test_plot_rejects_empty_catalog(empty_geojson: Path) -> None:
    async with Client(mcp) as client:
        with pytest.raises(ToolError):
            await client.call_tool(
                "plot_sequence", {"catalog_path": str(empty_geojson)}
            )
