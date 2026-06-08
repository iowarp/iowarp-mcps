"""Network-mocked tests for the geo geocode tool and helpers.

No real network is used: ``httpx.AsyncClient`` is replaced with a fake that
returns a canned Nominatim search response. Tests assert lat/lon are parsed as
floats, the Nominatim ``boundingbox`` ([min_lat, max_lat, min_lon, max_lon]) is
REORDERED to [min_lon, min_lat, max_lon, max_lat], provenance is set, the
mandated User-Agent header is sent, and ToolError/GeocodeError are raised on
empty or error responses.
"""

from __future__ import annotations

from typing import Any

import httpx
import pytest
from fastmcp import Client
from fastmcp.exceptions import ToolError

# The package __init__ re-exports the ``geocode`` function, which shadows the
# submodule attribute on ``geo_mcp.implementation``. Resolve the real submodule
# via importlib so we can patch ``httpx`` and reach the private helpers.
import importlib

from geo_mcp.server import mcp

geocode_impl = importlib.import_module("geo_mcp.implementation.geocode")

# A canned Nominatim format=json response for a sample query. Nominatim returns
# boundingbox as [min_lat, max_lat, min_lon, max_lon] (strings).
_NOMINATIM_JSON: list[dict[str, Any]] = [
    {
        "place_id": 1,
        "display_name": "Boulder, Boulder County, Colorado, United States",
        "lat": "40.0149856",
        "lon": "-105.2705456",
        "boundingbox": ["39.9542650", "40.0945850", "-105.3017759", "-105.1781000"],
        "type": "city",
        "importance": 0.71,
    },
    {
        "place_id": 2,
        "display_name": "Boulder, Montana, United States",
        "lat": "46.2370986",
        "lon": "-112.1180864",
        "boundingbox": ["46.2270986", "46.2470986", "-112.1280864", "-112.1080864"],
        "type": "town",
        "importance": 0.45,
    },
]


class _FakeResponse:
    def __init__(self, payload: Any, url: str) -> None:
        self._payload = payload
        self.url = url

    def raise_for_status(self) -> None:
        return None

    def json(self) -> Any:
        return self._payload


class _FakeAsyncClient:
    """Stand-in for httpx.AsyncClient returning a canned Nominatim payload.

    Records every request URL, params, and headers so tests can assert on the
    User-Agent and query parameters sent.
    """

    calls: list[tuple[str, dict[str, Any], dict[str, Any]]] = []
    payload: Any = _NOMINATIM_JSON
    raises: Exception | None = None

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        pass

    async def __aenter__(self) -> _FakeAsyncClient:
        return self

    async def __aexit__(self, *exc: Any) -> None:
        return None

    async def get(
        self,
        url: str,
        params: dict[str, Any] | None = None,
        headers: dict[str, Any] | None = None,
    ) -> _FakeResponse:
        type(self).calls.append((url, params or {}, headers or {}))
        if type(self).raises is not None:
            raise type(self).raises
        return _FakeResponse(type(self).payload, f"{url}?q={(params or {}).get('q')}")


@pytest.fixture
def fake_http(monkeypatch: pytest.MonkeyPatch) -> type[_FakeAsyncClient]:
    """Patch httpx.AsyncClient (in the geocode module) with the fake client."""
    _FakeAsyncClient.calls = []
    _FakeAsyncClient.payload = _NOMINATIM_JSON
    _FakeAsyncClient.raises = None
    monkeypatch.setattr(geocode_impl.httpx, "AsyncClient", _FakeAsyncClient)
    return _FakeAsyncClient


# --------------------------------------------------------------------------- #
# Pure-helper tests (no network)
# --------------------------------------------------------------------------- #


def test_reorder_bbox_to_lon_lat_order() -> None:
    # Nominatim order: [min_lat, max_lat, min_lon, max_lon]
    bbox = geocode_impl._reorder_bbox(["39.95", "40.09", "-105.30", "-105.17"])
    # Reordered to [min_lon, min_lat, max_lon, max_lat]
    assert bbox == [-105.30, 39.95, -105.17, 40.09]


def test_reorder_bbox_handles_malformed() -> None:
    assert geocode_impl._reorder_bbox(None) is None
    assert geocode_impl._reorder_bbox(["1", "2", "3"]) is None
    assert geocode_impl._reorder_bbox(["a", "b", "c", "d"]) is None


def test_map_match_parses_floats_and_provenance() -> None:
    match = geocode_impl._map_match(_NOMINATIM_JSON[0])
    assert match is not None
    assert isinstance(match["lat"], float)
    assert isinstance(match["lon"], float)
    assert match["lat"] == pytest.approx(40.0149856)
    assert match["lon"] == pytest.approx(-105.2705456)
    assert match["provenance"] == "osm_nominatim"
    assert match["type"] == "city"
    assert match["importance"] == pytest.approx(0.71)


def test_map_match_skips_entries_without_coords() -> None:
    assert geocode_impl._map_match({"display_name": "no coords"}) is None
    assert geocode_impl._map_match({"lat": "x", "lon": "y"}) is None
    assert geocode_impl._map_match("not-a-dict") is None


# --------------------------------------------------------------------------- #
# geocode (network mocked)
# --------------------------------------------------------------------------- #


@pytest.mark.asyncio
async def test_geocode_parses_match(fake_http) -> None:
    matches = await geocode_impl.geocode("Boulder, CO", limit=2)
    assert len(matches) == 2
    first = matches[0]
    assert first["lat"] == pytest.approx(40.0149856)
    assert first["lon"] == pytest.approx(-105.2705456)
    assert first["display_name"].startswith("Boulder")
    assert first["provenance"] == "osm_nominatim"


@pytest.mark.asyncio
async def test_geocode_reorders_bbox(fake_http) -> None:
    matches = await geocode_impl.geocode("Boulder, CO", limit=1)
    # Canonical [min_lon, min_lat, max_lon, max_lat] order.
    assert matches[0]["bbox"] == [
        pytest.approx(-105.3017759),
        pytest.approx(39.9542650),
        pytest.approx(-105.1781000),
        pytest.approx(40.0945850),
    ]


@pytest.mark.asyncio
async def test_geocode_sends_user_agent_and_params(fake_http) -> None:
    await geocode_impl.geocode("Boulder, CO", limit=3, countrycodes="us")
    url, params, headers = fake_http.calls[0]
    assert url == geocode_impl._NOMINATIM_SEARCH_URL
    assert params["q"] == "Boulder, CO"
    assert params["format"] == "json"
    assert params["limit"] == 3
    assert params["countrycodes"] == "us"
    # Nominatim mandates a descriptive User-Agent header.
    assert headers["User-Agent"] == geocode_impl._USER_AGENT
    assert "clio-kit" in headers["User-Agent"]


@pytest.mark.asyncio
async def test_geocode_caps_limit(fake_http) -> None:
    await geocode_impl.geocode("Boulder, CO", limit=99999)
    _, params, _ = fake_http.calls[0]
    assert params["limit"] == geocode_impl._MAX_RESULTS


@pytest.mark.asyncio
async def test_geocode_omits_countrycodes_when_blank(fake_http) -> None:
    await geocode_impl.geocode("Boulder, CO", countrycodes="   ")
    _, params, _ = fake_http.calls[0]
    assert "countrycodes" not in params


@pytest.mark.asyncio
async def test_geocode_raises_on_blank_query(fake_http) -> None:
    with pytest.raises(geocode_impl.GeocodeError, match="non-empty"):
        await geocode_impl.geocode("   ")


@pytest.mark.asyncio
async def test_geocode_raises_on_empty_result(fake_http) -> None:
    fake_http.payload = []
    with pytest.raises(geocode_impl.GeocodeError, match="No matching location"):
        await geocode_impl.geocode("Nowheresville XYZ")


@pytest.mark.asyncio
async def test_geocode_raises_on_http_error(fake_http) -> None:
    fake_http.raises = httpx.HTTPError("boom")
    with pytest.raises(geocode_impl.GeocodeError, match="Could not complete"):
        await geocode_impl.geocode("Boulder, CO")


@pytest.mark.asyncio
async def test_geocode_raises_on_bad_json_shape(fake_http) -> None:
    fake_http.payload = {"unexpected": "object"}
    with pytest.raises(geocode_impl.GeocodeError, match="unexpected response"):
        await geocode_impl.geocode("Boulder, CO")


# --------------------------------------------------------------------------- #
# Tool surface (in-memory MCP client, network mocked)
# --------------------------------------------------------------------------- #


@pytest.mark.asyncio
async def test_tool_registered() -> None:
    async with Client(mcp) as client:
        tools = {t.name for t in await client.list_tools()}
    assert "geocode" in tools


@pytest.mark.asyncio
async def test_tool_runs_in_memory(fake_http) -> None:
    async with Client(mcp) as client:
        result = await client.call_tool("geocode", {"query": "Boulder, CO", "limit": 1})
    matches = result.data
    assert isinstance(matches, list)
    assert matches[0]["provenance"] == "osm_nominatim"
    assert matches[0]["bbox"] == [
        pytest.approx(-105.3017759),
        pytest.approx(39.9542650),
        pytest.approx(-105.1781000),
        pytest.approx(40.0945850),
    ]


@pytest.mark.asyncio
async def test_tool_maps_empty_result_to_toolerror(fake_http) -> None:
    fake_http.payload = []
    async with Client(mcp) as client:
        with pytest.raises(ToolError):
            await client.call_tool("geocode", {"query": "Nowheresville XYZ"})


@pytest.mark.asyncio
async def test_tool_maps_http_error_to_toolerror(fake_http) -> None:
    fake_http.raises = httpx.HTTPError("boom")
    async with Client(mcp) as client:
        with pytest.raises(ToolError):
            await client.call_tool("geocode", {"query": "Boulder, CO"})
