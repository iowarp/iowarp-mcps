"""A retired server name must point at its successor, not fail like a typo."""

from click.testing import CliRunner

from clio_kit import main
from clio_kit.retired_servers import (
    RETIRED_SERVERS,
    retirement_notice,
    unknown_server_lines,
)


def test_every_retired_name_points_at_a_shipped_server() -> None:
    """A signpost pointing nowhere is worse than no signpost."""
    from clio_kit import list_available_servers

    shipped = set(list_available_servers())
    for retired, (successor, _) in RETIRED_SERVERS.items():
        assert retired not in shipped, f"{retired} still ships; it is not retired"
        assert successor in shipped, f"{retired} points at missing '{successor}'"


def test_retired_name_explains_where_the_capability_went() -> None:
    notice = retirement_notice("geojson")

    assert notice is not None
    assert "geo" in notice
    assert "inspect_geojson" in notice
    assert "clio-kit mcp-server geo" in notice


def test_unretired_unknown_name_still_lists_what_is_available() -> None:
    lines = unknown_server_lines("nonsense", {"geo": "geo-mcp", "sac": "sac-mcp"})

    assert lines[0] == "Error: Unknown server 'nonsense'"
    assert lines[1] == "Available servers: geo, sac"


def test_launcher_prints_the_notice_and_exits_nonzero() -> None:
    result = CliRunner().invoke(main, ["mcp-server", "seismic"])

    assert result.exit_code == 1
    assert "merged into 'sac'" in result.output
    assert "analyze_sequence" in result.output
