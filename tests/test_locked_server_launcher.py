"""Tests for reproducible embedded MCP server launches."""

import hashlib
import tempfile
from pathlib import Path

import click
import pytest

import clio_kit
from clio_kit import (
    LOCKED_SERVER_LAUNCH_SCHEMA,
    get_servers_path,
    locked_server_command,
    locked_server_environment,
    locked_server_project_identity,
    materialize_locked_server_project,
)


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]


def test_source_checkout_precedes_stale_installed_shared_data(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Editable development must launch repository server bytes, not stale data."""
    repository_root = tmp_path / "checkout"
    module_dir = repository_root / "src" / "clio_kit"
    source_servers = repository_root / "clio-kit-mcp-servers"
    installed_servers = tmp_path / "environment" / "clio-kit-mcp-servers"
    module_dir.mkdir(parents=True)
    for root, name in (
        (source_servers, "current-mcp"),
        (installed_servers, "stale-mcp"),
    ):
        project = root / name
        project.mkdir(parents=True)
        (project / "pyproject.toml").write_text(
            f"[project]\nname = '{name}'\nversion = '1.0.0'\n",
            encoding="utf-8",
        )

    monkeypatch.setattr(clio_kit, "MODULE_DIR", module_dir)
    monkeypatch.setattr(
        clio_kit,
        "_distribution_shared_data_roots",
        lambda _shared_name: [installed_servers],
    )

    assert get_servers_path().resolve() == source_servers.resolve()


def test_locked_server_command_uses_immutable_frozen_project(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The launcher must resolve child dependencies only from the shipped lock."""
    server_path = tmp_path / "jarvis"
    server_path.mkdir()
    (server_path / "uv.lock").write_text("version = 1\n", encoding="utf-8")
    monkeypatch.setattr("clio_kit.uv_command", lambda: "/opt/uv/bin/uv")

    command = locked_server_command(server_path, "jarvis-mcp")

    assert command == [
        "/opt/uv/bin/uv",
        "run",
        "--no-dev",
        "--no-editable",
        "--frozen",
        "--project",
        str(server_path),
        "jarvis-mcp",
    ]


def test_locked_server_command_rejects_missing_lock(tmp_path: Path) -> None:
    """An embedded server without a lock must fail closed."""
    server_path = tmp_path / "spack"
    server_path.mkdir()

    with pytest.raises(click.ClickException, match="refusing an unpinned"):
        locked_server_command(server_path, "spack-mcp")


def test_every_embedded_server_ships_a_lock() -> None:
    """A clean source checkout must contain every lock required by the launcher."""
    servers_root = REPOSITORY_ROOT / "clio-kit-mcp-servers"
    projects = sorted(
        path.parent for path in servers_root.glob("*/pyproject.toml") if path.is_file()
    )

    assert projects
    assert [
        project.name for project in projects if not (project / "uv.lock").is_file()
    ] == []


def test_locked_server_environment_is_source_and_lock_addressed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Changing server code or its lock must select a different cached environment."""
    server_path = tmp_path / "jarvis"
    source_path = server_path / "src" / "jarvis_mcp"
    source_path.mkdir(parents=True)
    (server_path / "pyproject.toml").write_text(
        "[project]\nname = 'jarvis-mcp'\nversion = '1.0.0'\n",
        encoding="utf-8",
    )
    (server_path / "uv.lock").write_text("version = 1\n", encoding="utf-8")
    module_path = source_path / "server.py"
    module_path.write_text("VALUE = 1\n", encoding="utf-8")
    monkeypatch.setenv("CLIO_KIT_CACHE_DIR", str(tmp_path / "cache"))

    first = locked_server_environment(server_path)
    first_identity = locked_server_project_identity(server_path)
    module_path.write_text("VALUE = 2\n", encoding="utf-8")
    second = locked_server_environment(server_path)
    second_identity = locked_server_project_identity(server_path)

    assert first.parent == (tmp_path / "cache" / "mcp-environments").resolve()
    assert first.name.startswith("jarvis-")
    assert first != second
    assert LOCKED_SERVER_LAUNCH_SCHEMA == "clio-kit.locked-server.v4"
    assert first_identity["schema_version"] == LOCKED_SERVER_LAUNCH_SCHEMA
    assert first_identity["server_name"] == "jarvis"
    assert len(first_identity["project_sha256"]) == 64
    assert len(first_identity["lock_sha256"]) == 64
    assert first_identity["project_sha256"] != second_identity["project_sha256"]
    assert first_identity["lock_sha256"] == second_identity["lock_sha256"]


def test_project_identity_frames_file_boundaries_without_structural_collision(
    tmp_path: Path,
) -> None:
    """A file record cannot be confused with bytes appended to a prior file."""
    collapsed = tmp_path / "collapsed"
    separated = tmp_path / "separated"
    collapsed.mkdir()
    separated.mkdir()
    base = b"[project]\nname='collision-fixture'\n"
    payload = b"VALUE = 1\n"
    framed_source = len(b"src.py").to_bytes(8, "big") + b"src.py" + payload
    for project in (collapsed, separated):
        (project / "uv.lock").write_bytes(b"version = 1\n")
    (collapsed / "pyproject.toml").write_bytes(base + framed_source)
    (separated / "pyproject.toml").write_bytes(base)
    (separated / "src.py").write_bytes(payload)

    assert _legacy_v3_project_digest(collapsed) == _legacy_v3_project_digest(separated)
    assert (
        locked_server_project_identity(collapsed)["project_sha256"]
        != (locked_server_project_identity(separated)["project_sha256"])
    )


def test_embedded_project_is_atomically_materialized_outside_archive_cache(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A uvx archive project is copied to a verified content-addressed root."""
    server_path = tmp_path / "uv-cache" / "archive-v0" / "entry" / "spack"
    source_path = server_path / "src" / "spack_mcp"
    source_path.mkdir(parents=True)
    (server_path / "pyproject.toml").write_text(
        "[project]\nname = 'spack-mcp'\nversion = '1.0.0'\n",
        encoding="utf-8",
    )
    (server_path / "uv.lock").write_text("version = 1\n", encoding="utf-8")
    (server_path / "README.md").write_text("Spack MCP\n", encoding="utf-8")
    (source_path / "server.py").write_text("VALUE = 1\n", encoding="utf-8")
    ignored = server_path / "tests"
    ignored.mkdir()
    (ignored / "test_server.py").write_text("assert False\n", encoding="utf-8")
    cache_root = tmp_path / "clio-cache"
    monkeypatch.setenv("CLIO_KIT_CACHE_DIR", str(cache_root))

    identity = locked_server_project_identity(server_path)
    materialized = materialize_locked_server_project(
        server_path,
        identity=identity,
    )

    assert materialized.is_relative_to(cache_root / "mcp-projects")
    assert not materialized.is_relative_to(tmp_path / "uv-cache")
    assert (materialized / "src" / "spack_mcp" / "server.py").is_file()
    assert (materialized / "README.md").is_file()
    assert not (materialized / "tests").exists()
    assert materialize_locked_server_project(server_path, identity=identity) == (
        materialized
    )

    (materialized / "src" / "spack_mcp" / "server.py").write_text(
        "VALUE = 2\n",
        encoding="utf-8",
    )
    with pytest.raises(click.ClickException, match="identity verification"):
        materialize_locked_server_project(server_path, identity=identity)


def test_materialization_does_not_repeat_content_hash_in_temporary_path(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Transient paths stay short while the verified destination keeps its full hash."""
    server_path = tmp_path / "source" / "geo"
    source_path = server_path / "src" / "geo_mcp"
    source_path.mkdir(parents=True)
    (server_path / "pyproject.toml").write_text(
        "[project]\nname = 'geo-mcp'\nversion = '1.0.0'\n",
        encoding="utf-8",
    )
    (server_path / "uv.lock").write_text("version = 1\n", encoding="utf-8")
    (source_path / "server.py").write_text("VALUE = 1\n", encoding="utf-8")
    cache_root = tmp_path / "clio-cache"
    monkeypatch.setenv("CLIO_KIT_CACHE_DIR", str(cache_root))
    created_paths: list[Path] = []
    original_mkdtemp = tempfile.mkdtemp

    def record_mkdtemp(*args: object, **kwargs: object) -> str:
        created = Path(original_mkdtemp(*args, **kwargs))
        created_paths.append(created)
        return str(created)

    monkeypatch.setattr(tempfile, "mkdtemp", record_mkdtemp)

    identity = locked_server_project_identity(server_path)
    materialized = materialize_locked_server_project(server_path, identity=identity)

    assert materialized.name == identity["project_sha256"]
    assert len(created_paths) == 1
    assert created_paths[0].name.startswith(".tmp-")
    assert identity["project_sha256"] not in created_paths[0].name


def _legacy_v3_project_digest(project: Path) -> str:
    """Reproduce the ambiguous v3 stream for the structural-collision fixture."""
    digest = hashlib.sha256()
    policy = b"uv-run:materialized:frozen:no-editable:no-dev:v2"
    digest.update(len(policy).to_bytes(8, "big"))
    digest.update(policy)
    for path in sorted(project.iterdir(), key=lambda item: item.as_posix()):
        relative_path = path.relative_to(project).as_posix().encode("utf-8")
        digest.update(len(relative_path).to_bytes(8, "big"))
        digest.update(relative_path)
        digest.update(path.read_bytes())
    return digest.hexdigest()
