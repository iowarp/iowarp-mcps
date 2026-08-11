"""Tests for the published scope the launcher groups its server listing by."""

import json
from pathlib import Path

from click.testing import CliRunner

import clio_kit
from clio_kit import main
from clio_kit.server_scope import (
    DEFAULT_SERVER_SCOPE,
    SERVER_SCOPE_ORDER,
    group_by_scope,
    read_server_scope,
)


def test_every_shipped_server_declares_a_known_scope() -> None:
    """Scope travels with the server project, not with the repository."""
    servers_root = clio_kit.get_servers_path()
    manifests = sorted(servers_root.glob("*/server.json"))

    assert manifests, "no shipped server manifests were discovered"
    for manifest in manifests:
        scope = json.loads(manifest.read_text(encoding="utf-8")).get("scope")
        assert scope in SERVER_SCOPE_ORDER, f"{manifest.parent.name} scope: {scope!r}"


def test_listing_groups_general_servers_apart_from_scientific_ones() -> None:
    """The grouping is what a user reads to tell the two surfaces apart."""
    grouped = group_by_scope(
        {"web": "general", "hdf5": "scientific", "compression": "general"}
    )

    assert grouped == {"scientific": ["hdf5"], "general": ["compression", "web"]}
    assert list(grouped) == ["scientific", "general"]


def test_scope_filter_lists_only_the_requested_surface() -> None:
    """`--scope` is the subset a config generator would consume."""
    result = CliRunner().invoke(main, ["mcp-servers", "--scope", "general"])

    assert result.exit_code == 0
    assert "General purpose:" in result.output
    assert "Scientific:" not in result.output
    assert "- web" in result.output
    assert "- hdf5" not in result.output


def test_unreadable_manifest_degrades_to_the_scientific_default(
    tmp_path: Path,
) -> None:
    """Listing must not fail because one manifest is missing or malformed."""
    (tmp_path / "server.json").write_text("{ not json", encoding="utf-8")

    assert read_server_scope(tmp_path) == DEFAULT_SERVER_SCOPE
    assert read_server_scope(tmp_path / "absent") == DEFAULT_SERVER_SCOPE
