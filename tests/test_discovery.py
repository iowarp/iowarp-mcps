"""Server discovery: what the kit ships and how each server starts.

Discovery decides which servers exist at all, so a server it cannot see is a
server nobody can run. The descriptor replaced a string match over
``pyproject.toml`` that could be won by any unrelated line and could never see
a non-Python server.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from clio_kit.discovery import (
    discover_servers_in,
    is_servers_root,
    read_server_descriptor,
)

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]


def _write_server(
    root: Path, name: str, descriptor: str | None, pyproject: str
) -> Path:
    server_dir = root / name
    server_dir.mkdir(parents=True)
    (server_dir / "pyproject.toml").write_text(pyproject, encoding="utf-8")
    if descriptor is not None:
        (server_dir / "clio-server.toml").write_text(descriptor, encoding="utf-8")
    return server_dir


def test_descriptor_states_what_discovery_used_to_infer(tmp_path: Path) -> None:
    server = _write_server(
        tmp_path,
        "hdf5",
        'name = "hdf5"\nruntime = "python"\nlock = "uv.lock"\nentry = "hdf5-mcp"\n',
        "[project]\nname = 'x'\n",
    )

    assert read_server_descriptor(server) == {
        "name": "hdf5",
        "runtime": "python",
        "entry": "hdf5-mcp",
    }


def test_descriptor_rejects_a_runtime_nothing_can_start(tmp_path: Path) -> None:
    """An unsupported runtime must fail by its own name, not as a missing file."""
    server = _write_server(
        tmp_path,
        "crystal",
        'name = "crystal"\nruntime = "haskell"\nentry = "crystal"\n',
        "[project]\nname = 'x'\n",
    )

    with pytest.raises(ValueError, match="runtime 'haskell'"):
        read_server_descriptor(server)


def test_a_stray_mcp_assignment_no_longer_wins(tmp_path: Path) -> None:
    """The old discovery took the FIRST line containing ``-mcp =``, anywhere.

    A dependency pin or a comment mentioning one was enough to name the server
    after it. The fallback now parses the document and reads project.scripts.
    """
    _write_server(
        tmp_path,
        "hdf5",
        None,
        "[project]\n"
        "name = 'hdf5-mcp'\n"
        "dependencies = ['some-other-mcp == 1.0']\n"
        "\n"
        "[project.scripts]\n"
        'hdf5-mcp = "hdf5_mcp.server:main"\n',
    )

    entry_commands, directories = discover_servers_in(tmp_path)

    assert entry_commands == {"hdf5": "hdf5-mcp"}
    assert directories == {"hdf5": "hdf5"}


def test_a_hyphenated_name_survives_the_fallback(tmp_path: Path) -> None:
    """The old code carried explicit no-op branches for these two names."""
    for name in ("node-hardware", "parallel-sort"):
        _write_server(
            tmp_path,
            name,
            None,
            f"[project]\nname = '{name}'\n\n[project.scripts]\n"
            f'{name}-mcp = "x:main"\n',
        )

    entry_commands, _ = discover_servers_in(tmp_path)

    assert entry_commands == {
        "node-hardware": "node-hardware-mcp",
        "parallel-sort": "parallel-sort-mcp",
    }


def test_one_malformed_descriptor_does_not_hide_the_others(tmp_path: Path) -> None:
    """A broken server must cost only itself, not the whole catalogue."""
    _write_server(tmp_path, "broken", 'runtime = "python"\n', "[project]\nname='b'\n")
    _write_server(
        tmp_path,
        "hdf5",
        'name = "hdf5"\nruntime = "python"\nentry = "hdf5-mcp"\n',
        "[project]\nname='h'\n",
    )

    entry_commands, _ = discover_servers_in(tmp_path)

    assert set(entry_commands) == {"hdf5"}


def test_a_servers_root_may_hold_only_descriptors(tmp_path: Path) -> None:
    """A non-Python server has no pyproject.toml to be recognised by."""
    root = tmp_path / "servers"
    server = root / "crystal"
    server.mkdir(parents=True)
    (server / "clio-server.toml").write_text(
        'name = "crystal"\nruntime = "node"\nentry = "crystal"\n', encoding="utf-8"
    )

    assert is_servers_root(root)
    assert not is_servers_root(tmp_path / "nothing-here")


def test_every_shipped_server_describes_itself() -> None:
    """A shipped server with no descriptor falls back; one with a wrong one lies."""
    servers_root = REPOSITORY_ROOT / "clio-kit-mcp-servers"
    shipped = sorted(path.parent for path in servers_root.glob("*/pyproject.toml"))
    assert shipped

    for server_dir in shipped:
        descriptor = read_server_descriptor(server_dir)
        assert descriptor is not None, f"{server_dir.name} has no clio-server.toml"
        assert descriptor["name"] == server_dir.name
        assert descriptor["runtime"] == "python"
        assert (server_dir / "uv.lock").is_file()

    entry_commands, directories = discover_servers_in(servers_root)
    assert set(entry_commands) == {server.name for server in shipped}
    assert all(directories[name] == name for name in entry_commands)
