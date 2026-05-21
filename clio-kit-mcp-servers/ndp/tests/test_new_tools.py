"""Tests for the 7 new NDP MCP tools added on top of the upstream 3.

Covered:
  Registration (4): register_dataset, register_kafka_topic,
                    register_s3_resource, register_url_resource
  Resource search (1): search_resources
  Status / user (2): get_jupyter_details, get_user_info

All tests mock NDPClient._make_request — no live HTTP. Live integration
checks belong in the dedicated `tests/test_live.py` (run with -m live).
"""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

import ndp_mcp.server as srv


# ── Tool-registration sanity check ──────────────────────────────────────

EXPECTED_TOOLS = {
    "list_organizations",
    "search_datasets",
    "get_dataset_details",
    "register_dataset",
    "register_kafka_topic",
    "register_s3_resource",
    "register_url_resource",
    "search_resources",
    "get_jupyter_details",
    "get_user_info",
    # 4 streaming / kafka tools (EarthScope GNSS UI pattern)
    "list_kafka_streams",
    "get_kafka_details",
    "get_system_metrics",
    "register_derived_stream",
}


@pytest.mark.asyncio
async def test_all_ten_tools_registered():
    tools = await srv.mcp.list_tools()
    names = {getattr(t, "name", str(t)) for t in tools} if not isinstance(tools, dict) else set(tools.keys())
    missing = EXPECTED_TOOLS - names
    assert not missing, f"missing tools: {missing}"


# ── Registration tools ──────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_register_dataset_minimal():
    with patch.object(srv.ndp_client, "_make_request", new=AsyncMock(return_value={"id": "abc123"})) as m:
        out = await srv.register_dataset(name="my-ds", title="My DS", owner_org="org1")
        assert out["registration"] == {"id": "abc123"}
        assert out["_meta"]["tool"] == "register_dataset"
        # body matched
        kwargs = m.call_args.kwargs
        assert kwargs["json_data"]["name"] == "my-ds"
        assert kwargs["json_data"]["title"] == "My DS"
        assert kwargs["json_data"]["owner_org"] == "org1"
        # defaults: not included unless explicitly passed
        assert "notes" not in kwargs["json_data"]
        # server query param
        assert kwargs["params"] == {"server": "local"}


@pytest.mark.asyncio
async def test_register_dataset_full():
    with patch.object(srv.ndp_client, "_make_request", new=AsyncMock(return_value={"id": "x"})) as m:
        await srv.register_dataset(
            name="env-data",
            title="Environmental Data",
            owner_org="ucsd",
            notes="hourly snapshots",
            tags=["climate", "hourly"],
            license_id="cc-by",
            private=False,
            server="pre_ckan",
        )
        body = m.call_args.kwargs["json_data"]
        assert body["tags"] == ["climate", "hourly"]
        assert body["license_id"] == "cc-by"
        assert body["private"] is False
        assert m.call_args.kwargs["params"]["server"] == "pre_ckan"


@pytest.mark.asyncio
async def test_register_kafka_topic_required_fields():
    with patch.object(srv.ndp_client, "_make_request", new=AsyncMock(return_value={})) as m:
        await srv.register_kafka_topic(
            dataset_name="quake-stream",
            dataset_title="Earthquake Stream",
            owner_org="usgs",
            kafka_topic="quakes",
            kafka_host="kafka.example.org",
            kafka_port=9092,
        )
        body = m.call_args.kwargs["json_data"]
        assert body["kafka_topic"] == "quakes"
        assert body["kafka_port"] == 9092


@pytest.mark.asyncio
async def test_register_s3_resource_basic():
    with patch.object(srv.ndp_client, "_make_request", new=AsyncMock(return_value={"ok": True})) as m:
        out = await srv.register_s3_resource(
            resource_name="snapshot-2024",
            resource_title="Snapshot 2024",
            owner_org="lab",
            resource_s3="s3://my-bucket/data/snapshot.csv",
        )
        assert out["s3_url"] == "s3://my-bucket/data/snapshot.csv"
        body = m.call_args.kwargs["json_data"]
        assert body["resource_s3"] == "s3://my-bucket/data/snapshot.csv"


@pytest.mark.asyncio
async def test_register_url_resource_with_filetype():
    with patch.object(srv.ndp_client, "_make_request", new=AsyncMock(return_value={"ok": True})) as m:
        await srv.register_url_resource(
            resource_name="hourly-csv",
            resource_title="Hourly CSV",
            owner_org="lab",
            resource_url="https://example.com/data.csv",
            file_type="CSV",
        )
        body = m.call_args.kwargs["json_data"]
        assert body["file_type"] == "CSV"


# ── Search resources ────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_search_resources_basic():
    with patch.object(
        srv.ndp_client,
        "_make_request",
        new=AsyncMock(return_value=[{"name": "a"}, {"name": "b"}]),
    ) as m:
        out = await srv.search_resources(q="earthquake", limit=10)
        assert out["count"] == 2
        assert m.call_args.kwargs["params"]["q"] == "earthquake"
        assert m.call_args.kwargs["params"]["limit"] == 10


@pytest.mark.asyncio
async def test_search_resources_dict_response():
    """API may return {resources: [...]} instead of a bare list."""
    with patch.object(
        srv.ndp_client,
        "_make_request",
        new=AsyncMock(return_value={"resources": [{"name": "a"}]}),
    ):
        out = await srv.search_resources(format="NetCDF")
        assert out["count"] == 1


# ── Status / user ───────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_get_jupyter_details_returns_payload():
    payload = {"url": "https://jhub.example.org", "kernels": ["python3"]}
    with patch.object(srv.ndp_client, "_make_request", new=AsyncMock(return_value=payload)):
        out = await srv.get_jupyter_details()
        assert out["jupyter"] == payload
        assert out["_meta"]["tool"] == "get_jupyter_details"


@pytest.mark.asyncio
async def test_get_user_info_returns_payload():
    payload = {"sub": "alice", "email": "alice@example.org"}
    with patch.object(srv.ndp_client, "_make_request", new=AsyncMock(return_value=payload)):
        out = await srv.get_user_info()
        assert out["user"] == payload


# ── Error handling — all tools surface ToolError ────────────────────────


@pytest.mark.asyncio
async def test_register_dataset_wraps_http_error():
    with patch.object(
        srv.ndp_client, "_make_request", new=AsyncMock(side_effect=Exception("HTTP 401"))
    ):
        with pytest.raises(srv.ToolError):
            await srv.register_dataset(name="x", title="X", owner_org="org")


@pytest.mark.asyncio
async def test_search_resources_wraps_http_error():
    with patch.object(
        srv.ndp_client, "_make_request", new=AsyncMock(side_effect=Exception("boom"))
    ):
        with pytest.raises(srv.ToolError):
            await srv.search_resources(q="anything")


# ── Streaming / kafka tools ─────────────────────────────────────────────


@pytest.mark.asyncio
async def test_list_kafka_streams_parses_description_json():
    """Each kafka resource's `description` is itself JSON with host/port/topic;
    the tool should unpack it into compact rows."""
    backend_resp = {
        "count": 1,
        "results": [{
            "name": "earthscope_kafka_gnss_observations",
            "url": "kafka://broker.example.org:9196/some-topic",
            "description": (
                '{"description": "Kafka GNSS observations from EarthScope",'
                ' "host": "broker.example.org", "port": 9196,'
                ' "topic": "public.gnss.positions"}'
            ),
        }]
    }
    with patch.object(srv.ndp_client, "_make_request",
                       new=AsyncMock(return_value=backend_resp)) as m:
        out = await srv.list_kafka_streams(name="gnss", limit=10)
    assert out["count"] == 1
    stream = out["streams"][0]
    assert stream["topic"] == "public.gnss.positions"
    assert stream["host"] == "broker.example.org"
    assert stream["port"] == 9196
    # Params: server defaults to 'local' (the one that doesn't need auth),
    # format=kafka is auto-set
    params = m.call_args.kwargs["params"]
    assert params["format"] == "kafka"
    assert params["server"] == "local"
    assert params["name"] == "gnss"


@pytest.mark.asyncio
async def test_list_kafka_streams_handles_bare_list_response():
    """Older backend revisions sometimes return a bare list."""
    with patch.object(srv.ndp_client, "_make_request",
                       new=AsyncMock(return_value=[
                           {"name": "topic-a", "description": "not json"},
                       ])):
        out = await srv.list_kafka_streams()
    assert out["count"] == 1
    assert out["streams"][0]["name"] == "topic-a"


@pytest.mark.asyncio
async def test_get_kafka_details_returns_payload():
    payload = {"bootstrap_servers": ["b1:9092"], "consumer_group_hint": "ndp-ep"}
    with patch.object(srv.ndp_client, "_make_request",
                       new=AsyncMock(return_value=payload)):
        out = await srv.get_kafka_details()
    assert out["kafka"] == payload


@pytest.mark.asyncio
async def test_get_system_metrics_returns_payload():
    payload = {"cpu": 12.3, "mem": 4.2, "msg_rate": 100}
    with patch.object(srv.ndp_client, "_make_request",
                       new=AsyncMock(return_value=payload)):
        out = await srv.get_system_metrics()
    assert out["metrics"] == payload


@pytest.mark.asyncio
async def test_register_derived_stream_records_filter_in_mapping():
    with patch.object(srv.ndp_client, "_make_request",
                       new=AsyncMock(return_value={"id": "derived-1"})) as m:
        out = await srv.register_derived_stream(
            dataset_name="gnss-agmt",
            dataset_title="GNSS AGMT.CI.LY.20 only",
            owner_org="earthscope",
            source_topic="public.gnss.positions",
            dest_topic="derived.gnss.agmt",
            dest_host="derived.broker.example.org",
            dest_port=9092,
            sncl_filter="AGMT.CI.LY.20",
        )
    body = m.call_args.kwargs["json_data"]
    assert body["kafka_topic"] == "derived.gnss.agmt"
    assert body["mapping"]["source_topic"] == "public.gnss.positions"
    assert body["mapping"]["sncl_filter"] == "AGMT.CI.LY.20"
    assert "Derived from public.gnss.positions" in body["dataset_description"]
    assert out["derived_topic"] == "derived.gnss.agmt"


@pytest.mark.asyncio
async def test_list_kafka_streams_wraps_http_error():
    with patch.object(srv.ndp_client, "_make_request",
                       new=AsyncMock(side_effect=Exception("boom"))):
        with pytest.raises(srv.ToolError):
            await srv.list_kafka_streams()
