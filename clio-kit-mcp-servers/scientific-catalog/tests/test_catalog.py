"""Tests for the production scientific catalog contract."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, cast

import pytest
from fastmcp import Client

from scientific_catalog_mcp.backend import CatalogError, CatalogStore
from scientific_catalog_mcp.models import (
    DatasetDescribeResult,
    DatasetDescriptor,
    canonical_sha256,
)
from scientific_catalog_mcp.server import configure_catalog, mcp


def _descriptor(dataset_id: str, member: str) -> dict[str, Any]:
    descriptor: dict[str, Any] = {
        "schema_version": "jarvis.dataset-descriptor.v1",
        "dataset_id": dataset_id,
        "kind": "temporal-volume",
        "format": "vti",
        "members": [
            {"index": 0, "location": f"/site/data/{member}-000.vti", "timestep": 0.0},
            {"index": 1, "location": f"/site/data/{member}-001.vti", "timestep": 1.0},
        ],
        "arrays": [{"name": "density", "association": "point", "components": 1}],
        "bounds": [0.0, 1.0, 0.0, 1.0, 0.0, 1.0],
        "source_artifact": None,
    }
    descriptor["fingerprint"] = {
        "algorithm": "sha256",
        "digest": canonical_sha256(descriptor),
    }
    return descriptor


def _catalog(*, revision: str = "one") -> dict[str, Any]:
    asteroid = _descriptor("deep-water-impact-2018", "asteroid")
    redsea = _descriptor("red-sea-eddies-2020", "redsea")
    return {
        "schema_version": "clio-kit.scientific-dataset-catalog.v1",
        "site_id": "test-site",
        "revision": revision,
        "datasets": [
            {
                "dataset_id": "deep-water-impact-2018",
                "title": "2018 Deep Water Impact",
                "summary": "Temporal asteroid impact volume used for scientific review.",
                "tags": ["asteroid", "impact", "volume"],
                "descriptor": asteroid,
            },
            {
                "dataset_id": "red-sea-eddies-2020",
                "title": "Red Sea Eddies",
                "summary": "Temporal ocean circulation volume.",
                "tags": ["ocean", "red-sea", "volume"],
                "descriptor": redsea,
            },
        ],
    }


def _write_catalog(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(json.dumps(payload), encoding="utf-8")


def test_descriptor_rejects_visualization_recipe_fields() -> None:
    payload = {**_descriptor("dataset", "frame"), "camera": {"preset": "close-up"}}
    with pytest.raises(ValueError, match="Extra inputs are not permitted"):
        DatasetDescriptor.model_validate(payload)


def test_descriptor_rejects_unrecomputable_fingerprint() -> None:
    payload = _descriptor("dataset", "frame")
    cast(dict[str, Any], payload["fingerprint"])["digest"] = "9" * 64
    with pytest.raises(ValueError, match="fingerprint field omitted"):
        DatasetDescriptor.model_validate(payload)


def test_descriptor_fingerprint_matches_jarvis_optional_field_omission() -> None:
    """Null optional member/array fields cannot change JARVIS identity bytes."""
    payload = _descriptor("dataset", "frame")
    cast(dict[str, Any], cast(list[Any], payload["members"])[0])["timestep"] = None
    cast(dict[str, Any], cast(list[Any], payload["arrays"])[0])["units"] = None
    intrinsic = {key: value for key, value in payload.items() if key != "fingerprint"}
    cast(list[dict[str, Any]], intrinsic["members"])[0].pop("timestep")
    cast(list[dict[str, Any]], intrinsic["arrays"])[0].pop("units")
    cast(dict[str, Any], payload["fingerprint"])["digest"] = canonical_sha256(intrinsic)

    descriptor = DatasetDescriptor.model_validate(payload)

    rendered = descriptor.model_dump(mode="json")
    assert "timestep" not in cast(list[dict[str, Any]], rendered["members"])[0]
    assert "units" not in cast(list[dict[str, Any]], rendered["arrays"])[0]


def test_search_and_describe_return_stable_intrinsic_contracts(tmp_path: Path) -> None:
    path = tmp_path / "catalog.json"
    _write_catalog(path, _catalog())
    store = CatalogStore(path)

    result = store.search(query="asteroid volume", page_size=10)
    assert result.schema_version == "clio-kit.scientific-dataset-search.v1"
    assert result.total_matches == 1
    assert result.datasets[0].dataset_id == "deep-water-impact-2018"
    assert result.datasets[0].member_count == 2

    described = store.describe("deep-water-impact-2018")
    assert described.schema_version == "clio-kit.scientific-dataset-description.v1"
    assert described.dataset.descriptor.schema_version == "jarvis.dataset-descriptor.v1"
    assert described.dataset_descriptor == described.dataset.descriptor
    assert described.descriptor_sha256 == canonical_sha256(
        described.dataset_descriptor.model_dump(mode="json")
    )


def test_describe_result_rejects_a_divergent_handoff(tmp_path: Path) -> None:
    """Catalog metadata and the explicit JARVIS handoff cannot silently diverge."""
    path = tmp_path / "catalog.json"
    _write_catalog(path, _catalog())
    store = CatalogStore(path)
    asteroid = store.describe("deep-water-impact-2018")
    red_sea = store.describe("red-sea-eddies-2020")
    payload = asteroid.model_dump(mode="json")
    payload["dataset_descriptor"] = red_sea.dataset_descriptor.model_dump(mode="json")
    payload["descriptor_sha256"] = red_sea.descriptor_sha256

    with pytest.raises(ValueError, match="must match dataset.descriptor"):
        DatasetDescribeResult.model_validate(payload)


def test_pagination_cursor_is_bound_to_catalog_revision(tmp_path: Path) -> None:
    path = tmp_path / "catalog.json"
    _write_catalog(path, _catalog())
    store = CatalogStore(path)
    first = store.search(page_size=1)
    assert first.next_cursor is not None

    changed = _catalog(revision="two-with-different-size")
    _write_catalog(path, changed)
    with pytest.raises(CatalogError, match="different catalog revision"):
        store.search(cursor=first.next_cursor, page_size=1)


def test_duplicate_json_keys_are_rejected(tmp_path: Path) -> None:
    path = tmp_path / "catalog.json"
    path.write_text(
        '{"schema_version":"clio-kit.scientific-dataset-catalog.v1",'
        '"site_id":"one","site_id":"two","revision":"one","datasets":[]}',
        encoding="utf-8",
    )
    with pytest.raises(CatalogError, match="duplicate JSON key"):
        CatalogStore(path).search()


def test_catalog_and_descriptor_identities_must_match(tmp_path: Path) -> None:
    path = tmp_path / "catalog.json"
    payload = _catalog()
    dataset = cast(dict[str, Any], cast(list[Any], payload["datasets"])[0])
    dataset["dataset_id"] = "substituted-id"
    _write_catalog(path, payload)
    with pytest.raises(CatalogError, match="dataset_id values must match"):
        CatalogStore(path).search()


@pytest.mark.asyncio
async def test_mcp_surface_has_two_agent_oriented_tools(tmp_path: Path) -> None:
    path = tmp_path / "catalog.json"
    _write_catalog(path, _catalog())
    configure_catalog(path)

    async with Client(mcp) as client:
        tools = await client.list_tools()
        assert {tool.name for tool in tools} == {
            "scientific_dataset_search",
            "scientific_dataset_describe",
        }
        search_tool = next(tool for tool in tools if tool.name == "scientific_dataset_search")
        assert "file_path" not in search_tool.inputSchema.get("properties", {})
        assert "camera" not in search_tool.inputSchema.get("properties", {})
        result = await client.call_tool(
            "scientific_dataset_search",
            {"query": "red sea", "page_size": 10},
        )
        described = await client.call_tool(
            "scientific_dataset_describe",
            {"dataset_id": "red-sea-eddies-2020"},
        )
    content = cast(dict[str, Any], result.structured_content)
    assert content["total_matches"] == 1
    assert content["datasets"][0]["dataset_id"] == "red-sea-eddies-2020"
    described_content = cast(dict[str, Any], described.structured_content)
    dataset = cast(dict[str, Any], described_content["dataset"])
    assert described_content["dataset_descriptor"] == dataset["descriptor"]
    assert described_content["dataset_descriptor"]["schema_version"] == (
        "jarvis.dataset-descriptor.v1"
    )


@pytest.mark.asyncio
async def test_discover_prompt_preserves_search_describe_boundary() -> None:
    """The generic prompt must guide discovery without smuggling scene semantics."""
    async with Client(mcp) as client:
        prompts = {prompt.name for prompt in await client.list_prompts()}
        rendered = await client.get_prompt(
            "discover_scientific_dataset",
            {"query": "asteroid impact volume"},
        )

    assert "discover_scientific_dataset" in prompts
    assert rendered.messages
    text = rendered.messages[0].content.text
    assert "asteroid impact volume" in text
    assert "scientific_dataset_search" in text
    assert "scientific_dataset_describe" in text
    assert "dataset_descriptor unchanged" in text
    assert "Do not invent camera, colormap, filter, scheduler" in text
