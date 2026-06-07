"""Network-mocked tests for the geo query_arcgis_features tool and helpers.

No real network is used: ``httpx.AsyncClient`` is replaced with a fake that
returns canned ArcGIS responses. All file output is confined to a tmp_path via
the ``CLIO_KIT_ARTIFACTS`` env var or an explicit absolute output_path.
"""

from __future__ import annotations

import json
from typing import Any

import httpx
import pytest
from fastmcp import Client
from fastmcp.exceptions import ToolError

from geo_mcp.implementation import arcgis
from geo_mcp.server import mcp

# A canned ArcGIS f=json response (esri attributes + esri geometry).
_ESRI_JSON: dict[str, Any] = {
    "geometryType": "esriGeometryPoint",
    "fields": [
        {"name": "OBJECTID", "type": "esriFieldTypeOID"},
        {"name": "name", "type": "esriFieldTypeString"},
        {"name": "start_date", "type": "esriFieldTypeDate"},
    ],
    "features": [
        {
            "attributes": {"OBJECTID": 1, "name": "A", "start_date": 1_600_000_000_000},
            "geometry": {"x": -118.2, "y": 34.1},
        },
        {
            "attributes": {"OBJECTID": 2, "name": "B", "start_date": 1_600_100_000_000},
            "geometry": {"x": -117.9, "y": 34.3},
        },
    ],
}

# A canned native GeoJSON response (ArcGIS f=geojson).
_GEOJSON: dict[str, Any] = {
    "type": "FeatureCollection",
    "features": [
        {
            "type": "Feature",
            "properties": {"OBJECTID": 1, "name": "A"},
            "geometry": {"type": "Point", "coordinates": [-118.2, 34.1]},
        },
        {
            "type": "Feature",
            "properties": {"OBJECTID": 2, "name": "B"},
            "geometry": {"type": "Point", "coordinates": [-117.9, 34.3]},
        },
    ],
}


class _FakeResponse:
    def __init__(self, payload: Any, url: str) -> None:
        self._payload = payload
        self.url = url

    def raise_for_status(self) -> None:
        return None

    def json(self) -> Any:
        return self._payload


class _FakeAsyncClient:
    """Stand-in for httpx.AsyncClient that returns canned payloads by f= param.

    Records every request URL+params so tests can assert on what was sent.
    """

    calls: list[tuple[str, dict[str, Any]]] = []
    json_payload: Any = _ESRI_JSON
    geojson_payload: Any = _GEOJSON
    geojson_raises: Exception | None = None

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        pass

    async def __aenter__(self) -> _FakeAsyncClient:
        return self

    async def __aexit__(self, *exc: Any) -> None:
        return None

    async def get(self, url: str, params: dict[str, Any] | None = None) -> _FakeResponse:
        params = params or {}
        type(self).calls.append((url, params))
        if params.get("f") == "geojson":
            if type(self).geojson_raises is not None:
                raise type(self).geojson_raises
            return _FakeResponse(type(self).geojson_payload, f"{url}?f=geojson")
        # Build a representative final URL with the where clause for assertions.
        final = f"{url}?f=json&where={params.get('where')}"
        return _FakeResponse(type(self).json_payload, final)


@pytest.fixture
def fake_http(monkeypatch: pytest.MonkeyPatch) -> type[_FakeAsyncClient]:
    """Patch httpx.AsyncClient (in the arcgis module) with the fake client."""
    _FakeAsyncClient.calls = []
    _FakeAsyncClient.json_payload = _ESRI_JSON
    _FakeAsyncClient.geojson_payload = _GEOJSON
    _FakeAsyncClient.geojson_raises = None
    monkeypatch.setattr(arcgis.httpx, "AsyncClient", _FakeAsyncClient)
    return _FakeAsyncClient


@pytest.fixture(autouse=True)
def artifacts_in_tmp(monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
    """Confine all artifact writes to tmp_path."""
    monkeypatch.setenv("CLIO_KIT_ARTIFACTS", str(tmp_path))


# --------------------------------------------------------------------------- #
# Pure-helper tests (no network)
# --------------------------------------------------------------------------- #


def test_layer_query_url_for_service_root() -> None:
    url = arcgis._arcgis_layer_query_url("https://x/arcgis/rest/services/S/FeatureServer", 3)
    assert url == "https://x/arcgis/rest/services/S/FeatureServer/3/query"


def test_layer_query_url_defaults_layer_zero() -> None:
    url = arcgis._arcgis_layer_query_url("https://x/S/FeatureServer", None)
    assert url.endswith("/FeatureServer/0/query")


def test_layer_query_url_for_layer_url() -> None:
    url = arcgis._arcgis_layer_query_url("https://x/S/FeatureServer/2", None)
    assert url == "https://x/S/FeatureServer/2/query"


def test_layer_query_url_passthrough_query() -> None:
    url = arcgis._arcgis_layer_query_url("https://x/S/FeatureServer/2/query", None)
    assert url == "https://x/S/FeatureServer/2/query"


def test_layer_query_url_rejects_non_http() -> None:
    with pytest.raises(ValueError, match="HTTP"):
        arcgis._arcgis_layer_query_url("ftp://x/FeatureServer", 0)


def test_layer_query_url_rejects_non_numeric_layer() -> None:
    with pytest.raises(ValueError, match="numeric"):
        arcgis._arcgis_layer_query_url("https://x/S/FeatureServer", "abc")


def test_bbox_geometry_empty_when_partial() -> None:
    assert arcgis._arcgis_bbox_geometry(min_lon=1, min_lat=2, max_lon=3, max_lat=None) == {}


def test_bbox_geometry_builds_envelope() -> None:
    geom = arcgis._arcgis_bbox_geometry(min_lon=-119, min_lat=33, max_lon=-117, max_lat=35)
    assert geom["geometryType"] == "esriGeometryEnvelope"
    env = json.loads(geom["geometry"])
    assert env["xmin"] == -119 and env["ymax"] == 35


def test_bbox_geometry_rejects_inverted() -> None:
    with pytest.raises(ValueError, match="min_lon"):
        arcgis._arcgis_bbox_geometry(min_lon=10, min_lat=0, max_lon=1, max_lat=5)


def test_epoch_to_iso_for_millis() -> None:
    assert arcgis._arcgis_epoch_to_iso(1_600_000_000_000) == "2020-09-13T12:26:40Z"


def test_epoch_to_iso_rejects_garbage() -> None:
    assert arcgis._arcgis_epoch_to_iso("not-a-number") is None
    assert arcgis._arcgis_epoch_to_iso(0) is None


def test_normalize_attributes_adds_iso_companion() -> None:
    norm = arcgis._normalize_arcgis_attributes({"start_date": 1_600_000_000_000, "name": "x"})
    assert norm["start_date_iso"] == "2020-09-13T12:26:40Z"
    assert norm["name"] == "x"


def test_compact_geometry_point_and_rings() -> None:
    assert arcgis._compact_arcgis_geometry({"x": 1, "y": 2}) == {"x": 1, "y": 2}
    summary = arcgis._compact_arcgis_geometry({"rings": [[[0, 0], [1, 1], [2, 0]]]})
    assert summary["bbox"] == [0, 0, 2, 1]
    assert summary["point_count_sampled"] == 3


# --------------------------------------------------------------------------- #
# query_arcgis_features (network mocked)
# --------------------------------------------------------------------------- #


@pytest.mark.asyncio
async def test_query_writes_native_geojson(fake_http, tmp_path) -> None:
    out = tmp_path / "layer.geojson"
    result = await arcgis.query_arcgis_features(
        "https://x/arcgis/rest/services/Sites/FeatureServer/0",
        output_path=str(out),
    )
    assert result["ok"] is True
    assert result["feature_count"] == 2
    assert result["geometry_type"] == "esriGeometryPoint"
    assert result["fields"] == ["OBJECTID", "name", "start_date"]
    assert result["output_path"] == str(out)
    assert out.is_file()
    saved = json.loads(out.read_text())
    # The saved file is the native f=geojson FeatureCollection.
    assert saved["type"] == "FeatureCollection"
    assert saved["features"][0]["geometry"]["type"] == "Point"


@pytest.mark.asyncio
async def test_query_returns_compact_features_with_iso(fake_http, tmp_path) -> None:
    result = await arcgis.query_arcgis_features(
        "https://x/S/FeatureServer/0", output_path=str(tmp_path / "o.geojson")
    )
    props = result["features"][0]["properties"]
    assert props["start_date_iso"] == "2020-09-13T12:26:40Z"
    assert result["features"][0]["geometry"] == {"x": -118.2, "y": 34.1}


@pytest.mark.asyncio
async def test_query_auto_names_output(fake_http, tmp_path) -> None:
    result = await arcgis.query_arcgis_features(
        "https://x/arcgis/rest/services/MySites/FeatureServer/0"
    )
    assert result["output_path"].endswith("mysites.geojson")
    assert result["output_path"].startswith(str(tmp_path))


@pytest.mark.asyncio
async def test_query_passes_bbox_and_where(fake_http) -> None:
    await arcgis.query_arcgis_features(
        "https://x/S/FeatureServer/0",
        where="POP > 100",
        max_features=5,
        min_lon=-119,
        min_lat=33,
        max_lon=-117,
        max_lat=35,
    )
    first_url, first_params = fake_http.calls[0]
    assert first_url == "https://x/S/FeatureServer/0/query"
    assert first_params["where"] == "POP > 100"
    assert first_params["resultRecordCount"] == 5
    assert first_params["geometryType"] == "esriGeometryEnvelope"


@pytest.mark.asyncio
async def test_query_falls_back_when_geojson_fails(fake_http, tmp_path) -> None:
    # If the f=geojson fetch errors, the compact collection is written instead.
    fake_http.geojson_raises = httpx.HTTPError("boom")
    out = tmp_path / "fallback.geojson"
    result = await arcgis.query_arcgis_features("https://x/S/FeatureServer/0", output_path=str(out))
    assert result["ok"] is True
    saved = json.loads(out.read_text())
    # Fallback writes the compact (esri-geometry summary) collection.
    assert saved["features"][0]["geometry"] == {"x": -118.2, "y": 34.1}


@pytest.mark.asyncio
async def test_query_raises_on_arcgis_error(fake_http, tmp_path) -> None:
    fake_http.json_payload = {"error": {"code": 400, "message": "bad"}}
    with pytest.raises(arcgis.ArcGISQueryError, match="ArcGIS returned an error"):
        await arcgis.query_arcgis_features(
            "https://x/S/FeatureServer/0", output_path=str(tmp_path / "e.geojson")
        )


@pytest.mark.asyncio
async def test_query_raises_on_missing_features(fake_http, tmp_path) -> None:
    fake_http.json_payload = {"geometryType": "esriGeometryPoint"}
    with pytest.raises(arcgis.ArcGISQueryError, match="no feature list"):
        await arcgis.query_arcgis_features(
            "https://x/S/FeatureServer/0", output_path=str(tmp_path / "e.geojson")
        )


@pytest.mark.asyncio
async def test_query_raises_on_bad_url() -> None:
    with pytest.raises(arcgis.ArcGISQueryError, match="HTTP"):
        await arcgis.query_arcgis_features("ftp://nope/FeatureServer/0")


@pytest.mark.asyncio
async def test_query_caps_max_features(fake_http, tmp_path) -> None:
    await arcgis.query_arcgis_features(
        "https://x/S/FeatureServer/0",
        max_features=99999,
        output_path=str(tmp_path / "c.geojson"),
    )
    _, params = fake_http.calls[0]
    assert params["resultRecordCount"] == arcgis._MAX_ARCGIS_FEATURES


# --------------------------------------------------------------------------- #
# Tool surface (in-memory MCP client, network mocked)
# --------------------------------------------------------------------------- #


@pytest.mark.asyncio
async def test_tool_registered() -> None:
    async with Client(mcp) as client:
        tools = {t.name for t in await client.list_tools()}
    assert "query_arcgis_features" in tools


@pytest.mark.asyncio
async def test_tool_runs_in_memory(fake_http, tmp_path) -> None:
    out = tmp_path / "tool.geojson"
    async with Client(mcp) as client:
        result = await client.call_tool(
            "query_arcgis_features",
            {
                "feature_service_url": "https://x/S/FeatureServer/0",
                "output_path": str(out),
            },
        )
    assert result.data["ok"] is True
    assert result.data["feature_count"] == 2
    assert out.is_file()


@pytest.mark.asyncio
async def test_tool_maps_query_error_to_toolerror(fake_http, tmp_path) -> None:
    fake_http.json_payload = {"error": {"message": "nope"}}
    async with Client(mcp) as client:
        with pytest.raises(ToolError):
            await client.call_tool(
                "query_arcgis_features",
                {
                    "feature_service_url": "https://x/S/FeatureServer/0",
                    "output_path": str(tmp_path / "e.geojson"),
                },
            )
