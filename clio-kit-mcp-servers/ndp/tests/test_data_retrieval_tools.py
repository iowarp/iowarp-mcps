"""Tests for the generic data-retrieval tools ported from clio-agent.

These tools (stage_resource, query_arcgis_features, profile_csv_resource,
plot_csv_timeseries) are exercised through the in-memory FastMCP client with all
network access mocked, so no real HTTP/OSDF traffic occurs.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import httpx
import pytest
from fastmcp import Client

from ndp_mcp import server
from ndp_mcp.server import mcp


def _parse_result(result: Any) -> dict[str, Any]:
    data = result.data
    if isinstance(data, dict):
        return data
    if isinstance(data, str):
        return json.loads(data)
    return {"raw": str(data)}


@pytest.fixture(autouse=True)
def _artifacts_root(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Confine all artifact writes to the pytest temp dir."""
    root = tmp_path / "artifacts"
    monkeypatch.setenv("CLIO_KIT_ARTIFACTS", str(root))
    return root


# ---------------------------------------------------------------------------
# stage_resource
# ---------------------------------------------------------------------------


class _FakeStreamResponse:
    """Minimal async stand-in for an httpx streaming response."""

    def __init__(self, *, chunks: list[bytes], headers: dict[str, str]) -> None:
        self._chunks = chunks
        self.headers = headers
        self.url = "https://example.test/sample.csv"

    async def __aenter__(self) -> _FakeStreamResponse:
        return self

    async def __aexit__(self, *args: Any) -> None:
        return None

    def raise_for_status(self) -> None:
        return None

    async def aiter_bytes(self, chunk_size: int):
        del chunk_size
        for chunk in self._chunks:
            yield chunk


class _FakeAsyncClient:
    """Async client stub returning a preconfigured streaming response."""

    def __init__(self, response: _FakeStreamResponse) -> None:
        self._response = response

    async def __aenter__(self) -> _FakeAsyncClient:
        return self

    async def __aexit__(self, *args: Any) -> None:
        return None

    def stream(self, method: str, url: str):
        del method, url
        return self._response


@pytest.mark.asyncio
async def test_stage_resource_http_writes_file_and_shape(
    monkeypatch: pytest.MonkeyPatch,
    _artifacts_root: Path,
) -> None:
    """An HTTP(S) resource is streamed to a local file with the expected shape."""
    payload = b"time,east,north,up\n1,0.1,0.2,0.3\n"
    response = _FakeStreamResponse(
        chunks=[payload],
        headers={"content-length": str(len(payload)), "content-type": "text/csv"},
    )

    def fake_client(*args: Any, **kwargs: Any) -> _FakeAsyncClient:
        return _FakeAsyncClient(response)

    monkeypatch.setattr(server.httpx, "AsyncClient", fake_client)

    async with Client(mcp) as client:
        result = await client.call_tool(
            "stage_resource",
            {"url": "https://example.test/sample.csv"},
        )

    data = _parse_result(result)
    assert data["ok"] is True
    assert data["content_type"] == "text/csv"
    assert data["size_bytes"] == len(payload)
    assert data["method"] == "http"
    local_path = Path(data["local_path"])
    assert local_path.exists()
    assert local_path.read_bytes() == payload
    # File must live under the configured artifacts root, not a hardcoded path.
    assert str(local_path).startswith(str(_artifacts_root.resolve()))
    assert local_path.name == "sample.csv"


@pytest.mark.asyncio
async def test_stage_resource_http_size_cap_raises(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Advertised content-length over max_bytes raises a ToolError (no partial file)."""
    response = _FakeStreamResponse(
        chunks=[b"x" * 100],
        headers={"content-length": "100"},
    )

    def fake_client(*args: Any, **kwargs: Any) -> _FakeAsyncClient:
        return _FakeAsyncClient(response)

    monkeypatch.setattr(server.httpx, "AsyncClient", fake_client)

    async with Client(mcp) as client:
        with pytest.raises(Exception) as excinfo:
            await client.call_tool(
                "stage_resource",
                {"url": "https://example.test/big.bin", "max_bytes": 10},
            )

    assert "staging limit" in str(excinfo.value)


@pytest.mark.asyncio
async def test_stage_resource_rejects_unsupported_scheme() -> None:
    """Non HTTP(S)/OSDF URLs are rejected."""
    async with Client(mcp) as client:
        with pytest.raises(Exception) as excinfo:
            await client.call_tool("stage_resource", {"url": "ftp://example.test/x"})
    assert "Unsupported resource URL scheme" in str(excinfo.value)


@pytest.mark.asyncio
async def test_stage_resource_osdf_requires_pelican(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """OSDF resources fail clearly when the pelican CLI is unavailable."""
    monkeypatch.setattr(server.shutil, "which", lambda name: None)

    async with Client(mcp) as client:
        with pytest.raises(Exception) as excinfo:
            await client.call_tool(
                "stage_resource",
                {"url": "osdf:///ndp/public/data/object.bin"},
            )
    assert "pelican" in str(excinfo.value).lower()


# ---------------------------------------------------------------------------
# query_arcgis_features
# ---------------------------------------------------------------------------


class _FakeArcGISClient:
    """Async client stub serving ArcGIS json then geojson responses by ``f`` param."""

    def __init__(self, json_payload: dict[str, Any], geojson_payload: dict[str, Any]) -> None:
        self._json = json_payload
        self._geojson = geojson_payload
        self.calls: list[dict[str, Any]] = []

    async def __aenter__(self) -> _FakeArcGISClient:
        return self

    async def __aexit__(self, *args: Any) -> None:
        return None

    async def get(self, url: str, params: dict[str, Any] | None = None):
        params = params or {}
        self.calls.append({"url": url, "params": params})
        body = self._geojson if params.get("f") == "geojson" else self._json
        request = httpx.Request("GET", url, params=params)
        return httpx.Response(200, json=body, request=request)


@pytest.mark.asyncio
async def test_query_arcgis_features_writes_geojson_and_shape(
    monkeypatch: pytest.MonkeyPatch,
    _artifacts_root: Path,
) -> None:
    """ArcGIS features are returned compactly and persisted as native GeoJSON."""
    json_payload = {
        "geometryType": "esriGeometryPoint",
        "fields": [
            {"name": "IncidentName"},
            {"name": "DailyAcres"},
            {"name": "Updated"},
        ],
        "features": [
            {
                "attributes": {
                    "IncidentName": "TEST",
                    "DailyAcres": 12.5,
                    "Updated": 1780550400000,
                    "Start": 1780546800000,
                },
                "geometry": {"x": -117.1, "y": 32.8},
            }
        ],
    }
    geojson_payload = {
        "type": "FeatureCollection",
        "features": [
            {
                "type": "Feature",
                "properties": {"IncidentName": "TEST", "DailyAcres": 12.5},
                "geometry": {"type": "Point", "coordinates": [-117.1, 32.8]},
            }
        ],
    }

    fake_client = _FakeArcGISClient(json_payload, geojson_payload)

    def make_client(*args: Any, **kwargs: Any) -> _FakeArcGISClient:
        return fake_client

    monkeypatch.setattr(server.httpx, "AsyncClient", make_client)

    async with Client(mcp) as client:
        result = await client.call_tool(
            "query_arcgis_features",
            {
                "feature_service_url": "https://example.test/MyService/FeatureServer",
                "layer_id": 0,
                "where": "DailyAcres > 0",
                "min_lon": -118,
                "min_lat": 32,
                "max_lon": -116,
                "max_lat": 34,
            },
        )

    data = _parse_result(result)
    assert data["ok"] is True
    assert data["feature_count"] == 1
    assert data["geometry_type"] == "esriGeometryPoint"
    assert data["features"][0]["geometry"] == {"x": -117.1, "y": 32.8}
    # Date fields get ISO companions while raw values are preserved.
    assert data["features"][0]["properties"]["Updated"] == 1780550400000
    assert data["features"][0]["properties"]["Updated_iso"] == "2026-06-04T05:20:00Z"
    assert data["features"][0]["properties"]["Start_iso"] == "2026-06-04T04:20:00Z"

    # The saved file is native GeoJSON written under the artifacts root.
    output_path = Path(data["output_path"])
    assert output_path.exists()
    assert str(output_path).startswith(str(_artifacts_root.resolve()))
    saved = json.loads(output_path.read_text(encoding="utf-8"))
    assert saved["type"] == "FeatureCollection"
    assert saved["features"][0]["geometry"]["type"] == "Point"

    # Auto-named from the service segment, and the json query carried the bbox.
    assert output_path.name == "myservice.geojson"
    first_call = fake_client.calls[0]
    assert first_call["url"] == "https://example.test/MyService/FeatureServer/0/query"
    assert first_call["params"]["where"] == "DailyAcres > 0"
    assert first_call["params"]["geometryType"] == "esriGeometryEnvelope"


@pytest.mark.asyncio
async def test_query_arcgis_features_respects_explicit_output_path(
    monkeypatch: pytest.MonkeyPatch,
    _artifacts_root: Path,
) -> None:
    """An explicit output_path filename is honored (relocated under artifacts root)."""
    json_payload = {
        "geometryType": "esriGeometryPoint",
        "fields": [{"name": "name"}],
        "features": [{"attributes": {"name": "a"}, "geometry": {"x": 1.0, "y": 2.0}}],
    }
    geojson_payload = {"type": "FeatureCollection", "features": []}
    fake_client = _FakeArcGISClient(json_payload, geojson_payload)
    monkeypatch.setattr(server.httpx, "AsyncClient", lambda *a, **k: fake_client)

    async with Client(mcp) as client:
        result = await client.call_tool(
            "query_arcgis_features",
            {
                "feature_service_url": "https://example.test/svc/FeatureServer/0/query",
                "output_path": "/nonexistent/dir/perimeters.geojson",
            },
        )

    data = _parse_result(result)
    output_path = Path(data["output_path"])
    assert output_path.name == "perimeters.geojson"
    assert str(output_path).startswith(str(_artifacts_root.resolve()))
    assert output_path.exists()


@pytest.mark.asyncio
async def test_query_arcgis_features_surfaces_arcgis_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """An ArcGIS error payload raises a ToolError."""
    error_payload = {"error": {"code": 400, "message": "Invalid where clause"}}
    fake_client = _FakeArcGISClient(error_payload, {"type": "FeatureCollection", "features": []})
    monkeypatch.setattr(server.httpx, "AsyncClient", lambda *a, **k: fake_client)

    async with Client(mcp) as client:
        with pytest.raises(Exception) as excinfo:
            await client.call_tool(
                "query_arcgis_features",
                {"feature_service_url": "https://example.test/svc/FeatureServer/0/query"},
            )
    assert "ArcGIS returned an error" in str(excinfo.value)


# ---------------------------------------------------------------------------
# profile_csv_resource
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_profile_csv_resource_reports_numeric_state(tmp_path: Path) -> None:
    """CSV profiling returns columns, samples, numeric ranges, and missing counts."""
    csv_path = tmp_path / "weather.csv"
    csv_path.write_text(
        "Date,Hour,Air Temp (C),Wind Speed (m/s),Station\n"
        "6/1/2026,0100,18.5,2.0,Fresno\n"
        "6/1/2026,0200,20.5,3.5,Fresno\n"
        "6/1/2026,0300,,4.5,Fresno\n",
        encoding="utf-8",
    )

    async with Client(mcp) as client:
        result = await client.call_tool(
            "profile_csv_resource",
            {"filepath": str(csv_path), "max_rows": 10},
        )

    data = _parse_result(result)
    assert data["ok"] is True
    assert data["columns"] == ["Date", "Hour", "Air Temp (C)", "Wind Speed (m/s)", "Station"]
    assert data["rows_examined"] == 3
    assert data["rows_profiled"] == 3
    assert data["missing_values"]["Air Temp (C)"] == 1
    assert data["numeric_summary"]["Air Temp (C)"]["count"] == 2
    assert data["numeric_summary"]["Air Temp (C)"]["max"] == 20.5
    assert data["numeric_summary"]["Wind Speed (m/s)"]["mean"] == pytest.approx(10.0 / 3.0)
    assert data["sample_rows"][0]["Station"] == "Fresno"


@pytest.mark.asyncio
async def test_profile_csv_resource_missing_file_raises() -> None:
    """Profiling a non-existent file raises a ToolError."""
    async with Client(mcp) as client:
        with pytest.raises(Exception) as excinfo:
            await client.call_tool(
                "profile_csv_resource",
                {"filepath": "/does/not/exist.csv"},
            )
    assert "does not exist" in str(excinfo.value)


# ---------------------------------------------------------------------------
# plot_csv_timeseries
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_plot_csv_timeseries_writes_png(
    tmp_path: Path,
    _artifacts_root: Path,
) -> None:
    """Plotting numeric columns produces a PNG under the artifacts root."""
    csv_path = tmp_path / "series.csv"
    csv_path.write_text(
        "time,east,north,up\n1,0.1,0.2,0.3\n2,0.4,0.5,0.6\n3,0.7,0.8,0.9\n",
        encoding="utf-8",
    )

    async with Client(mcp) as client:
        result = await client.call_tool(
            "plot_csv_timeseries",
            {
                "filepath": str(csv_path),
                "x_column": "time",
                "y_columns": ["east", "north"],
            },
        )

    data = _parse_result(result)
    assert data["ok"] is True
    assert data["y_columns"] == ["east", "north"]
    assert data["rows_plotted"] == 3
    output = Path(data["output_path"])
    assert output.exists()
    assert output.suffix == ".png"
    assert output.stat().st_size > 0
    assert str(output).startswith(str(_artifacts_root.resolve()))


@pytest.mark.asyncio
async def test_plot_csv_timeseries_accepts_comma_separated_columns(
    tmp_path: Path,
) -> None:
    """y_columns may be supplied as a comma-separated string."""
    csv_path = tmp_path / "series.csv"
    csv_path.write_text(
        "time,east,north\n1,0.1,0.2\n2,0.4,0.5\n",
        encoding="utf-8",
    )

    async with Client(mcp) as client:
        result = await client.call_tool(
            "plot_csv_timeseries",
            {"filepath": str(csv_path), "x_column": "time", "y_columns": "east, north"},
        )

    data = _parse_result(result)
    assert data["y_columns"] == ["east", "north"]


@pytest.mark.asyncio
async def test_plot_csv_timeseries_unknown_column_raises(tmp_path: Path) -> None:
    """Requesting a missing column raises a ToolError."""
    csv_path = tmp_path / "series.csv"
    csv_path.write_text("time,east\n1,0.1\n", encoding="utf-8")

    async with Client(mcp) as client:
        with pytest.raises(Exception) as excinfo:
            await client.call_tool(
                "plot_csv_timeseries",
                {"filepath": str(csv_path), "x_column": "time", "y_columns": ["nope"]},
            )
    assert "not present" in str(excinfo.value)
