"""Tests for the bounded MCP runtime cache lifecycle (issue #334)."""

from __future__ import annotations

import os
import subprocess
from pathlib import Path
from typing import Any

import pytest

import clio_kit
from clio_kit.env_cache import (
    BudgetReport,
    CacheInUseError,
    CachePolicy,
    EnvironmentInUseMarker,
    collect_cache_gc,
    evict_superseded_environments,
    load_cache_policy,
    maintain_after_build,
    measure_cache_budget,
    prune_uv_cache,
)

# A deterministic pool of 64-hex-char project hashes. Only the first 24 chars
# name the environment directory, so the fixtures keep distinct prefixes.
_HASHES = [f"{index:02x}" + "a" * 62 for index in range(1, 10)]


def _policy(**overrides: Any) -> CachePolicy:
    base = {
        "keep_per_server": 1,
        "eviction_enabled": True,
        "prune_enabled": True,
        "max_cache_bytes": None,
    }
    base.update(overrides)
    return CachePolicy(**base)  # type: ignore[arg-type]


def _seed_spec(
    cache_root: Path,
    server: str,
    full_hash: str,
    *,
    mtime: float,
    env_bytes: int = 4096,
) -> tuple[Path, Path]:
    """Create the environment and project directories for one server spec."""
    env_dir = cache_root / "mcp-environments" / f"{server}-{full_hash[:24]}"
    project_dir = cache_root / "mcp-projects" / server / full_hash
    (env_dir / "bin").mkdir(parents=True, exist_ok=True)
    project_dir.mkdir(parents=True, exist_ok=True)
    (env_dir / "bin" / "python").write_bytes(b"x" * env_bytes)
    (project_dir / "pyproject.toml").write_text("[project]\n", encoding="utf-8")
    for target in (env_dir, project_dir):
        os.utime(target, (mtime, mtime))
    return env_dir, project_dir


def _events_collector() -> tuple[list[dict[str, Any]], Any]:
    events: list[dict[str, Any]] = []

    def emit(event: Any) -> None:
        events.append(dict(event))

    return events, emit


def test_build_next_spec_evicts_previous_keeping_newest(tmp_path: Path) -> None:
    """Building spec N+1 must evict spec N when keep-per-server is 1."""
    events, emit = _events_collector()
    old_env, old_project = _seed_spec(tmp_path, "spack", _HASHES[0], mtime=1_000.0)
    new_env, new_project = _seed_spec(tmp_path, "spack", _HASHES[1], mtime=2_000.0)

    report = evict_superseded_environments(
        tmp_path,
        "spack",
        keep_current=_HASHES[1],
        policy=_policy(keep_per_server=1),
        emit=emit,
    )

    assert not old_env.exists()
    assert not old_project.exists()
    assert new_env.exists()
    assert new_project.exists()
    assert [entry.hash_prefix for entry in report.evicted] == [_HASHES[0][:24]]
    assert report.bytes_freed > 0
    assert any(
        event["event"] == "env_evicted" and event["reason"] == "superseded"
        for event in events
    )


def test_keep_n_knob_retains_that_many_specs(tmp_path: Path) -> None:
    """A keep-per-server of 2 must retain the current build plus one newest spec."""
    old_env, _ = _seed_spec(tmp_path, "jarvis", _HASHES[0], mtime=1_000.0)
    mid_env, _ = _seed_spec(tmp_path, "jarvis", _HASHES[1], mtime=2_000.0)
    new_env, _ = _seed_spec(tmp_path, "jarvis", _HASHES[2], mtime=3_000.0)

    report = evict_superseded_environments(
        tmp_path,
        "jarvis",
        keep_current=_HASHES[2],
        policy=_policy(keep_per_server=2),
        emit=lambda _event: None,
    )

    assert new_env.exists()  # current build
    assert mid_env.exists()  # newest of the remainder
    assert not old_env.exists()  # oldest evicted
    assert [entry.hash_prefix for entry in report.evicted] == [_HASHES[0][:24]]


def test_disabled_eviction_retains_all_specs(tmp_path: Path) -> None:
    """The sabotage twin: disabling eviction must leave every stale spec on disk.

    This proves the keep-newest tests are load-bearing — if eviction silently
    became a no-op, ``test_build_next_spec_evicts_previous`` would fail while this
    test would pass, so the pair pins the real behavior in both directions.
    """
    old_env, old_project = _seed_spec(tmp_path, "spack", _HASHES[0], mtime=1_000.0)
    _seed_spec(tmp_path, "spack", _HASHES[1], mtime=2_000.0)

    report = evict_superseded_environments(
        tmp_path,
        "spack",
        keep_current=_HASHES[1],
        policy=_policy(eviction_enabled=False),
        emit=lambda _event: None,
    )

    assert old_env.exists()
    assert old_project.exists()
    assert report.evicted == ()


def test_in_use_environment_is_skipped_with_typed_reason(tmp_path: Path) -> None:
    """An environment held by a live launcher must be skipped, not deleted."""
    events, emit = _events_collector()
    old_env, old_project = _seed_spec(tmp_path, "slurm", _HASHES[0], mtime=1_000.0)
    _seed_spec(tmp_path, "slurm", _HASHES[1], mtime=2_000.0)

    with EnvironmentInUseMarker(tmp_path, old_env.name):
        report = evict_superseded_environments(
            tmp_path,
            "slurm",
            keep_current=_HASHES[1],
            policy=_policy(keep_per_server=1),
            emit=emit,
        )

    assert old_env.exists()
    assert old_project.exists()
    assert report.evicted == ()
    assert [entry.reason for entry in report.skipped_in_use] == ["in_use"]
    assert any(
        event["event"] == "env_evict_skipped" and event["reason"] == "in_use"
        for event in events
    )


def test_released_marker_no_longer_blocks_eviction(tmp_path: Path) -> None:
    """Once a holder exits, its environment becomes a normal eviction candidate."""
    old_env, _ = _seed_spec(tmp_path, "slurm", _HASHES[0], mtime=1_000.0)
    _seed_spec(tmp_path, "slurm", _HASHES[1], mtime=2_000.0)

    with EnvironmentInUseMarker(tmp_path, old_env.name):
        pass  # acquire then release

    report = evict_superseded_environments(
        tmp_path,
        "slurm",
        keep_current=_HASHES[1],
        policy=_policy(keep_per_server=1),
        emit=lambda _event: None,
    )

    assert not old_env.exists()
    assert [entry.hash_prefix for entry in report.evicted] == [_HASHES[0][:24]]


def test_prune_invoked_on_success(tmp_path: Path) -> None:
    """A successful prune must be reported as run and ok with a typed event."""
    (tmp_path / "uv-cache").mkdir(parents=True)
    events, emit = _events_collector()
    calls: list[list[str]] = []

    def fake_run(cmd: list[str], **_kwargs: Any) -> subprocess.CompletedProcess[bytes]:
        calls.append(cmd)
        return subprocess.CompletedProcess(cmd, 0, b"", b"")

    report = prune_uv_cache(
        tmp_path,
        policy=_policy(),
        uv_executable="uv",
        emit=emit,
        run=fake_run,
    )

    assert report.ran and report.ok
    assert calls and calls[0][:3] == ["uv", "cache", "prune"]
    assert any(event["event"] == "uv_cache_prune" and event["ok"] for event in events)


def test_prune_failure_is_tolerated_with_reason(tmp_path: Path) -> None:
    """A non-zero prune exit must be tolerated and reported, never raised."""
    (tmp_path / "uv-cache").mkdir(parents=True)
    events, emit = _events_collector()

    def failing_run(
        cmd: list[str], **_kwargs: Any
    ) -> subprocess.CompletedProcess[bytes]:
        return subprocess.CompletedProcess(cmd, 3, b"", b"disk error")

    report = prune_uv_cache(
        tmp_path,
        policy=_policy(),
        uv_executable="uv",
        emit=emit,
        run=failing_run,
    )

    assert report.ran and not report.ok
    assert "prune_exit_3" in report.reason
    assert any(
        event["event"] == "uv_cache_prune" and not event["ok"] for event in events
    )


def test_prune_spawn_failure_is_tolerated(tmp_path: Path) -> None:
    """A missing uv binary during prune must not raise out of maintenance."""
    (tmp_path / "uv-cache").mkdir(parents=True)

    def raising_run(cmd: list[str], **_kwargs: Any) -> Any:
        raise OSError("uv not found")

    report = prune_uv_cache(
        tmp_path,
        policy=_policy(),
        uv_executable="uv",
        emit=lambda _event: None,
        run=raising_run,
    )

    assert report.ran and not report.ok
    assert "prune_spawn_failed" in report.reason


def test_prune_skips_while_another_server_environment_is_live(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A live MCP must not make a second launch wait on uv's cache lock."""

    (tmp_path / "uv-cache").mkdir(parents=True)
    calls: list[list[str]] = []
    real_pid = os.getpid()

    def fake_run(cmd: list[str], **_kwargs: Any) -> subprocess.CompletedProcess[bytes]:
        calls.append(cmd)
        return subprocess.CompletedProcess(cmd, 0, b"", b"")

    with EnvironmentInUseMarker(tmp_path, "adios-" + _HASHES[0][:24]):
        monkeypatch.setattr(os, "getpid", lambda: real_pid + 1)
        report = prune_uv_cache(
            tmp_path,
            policy=_policy(),
            uv_executable="uv",
            emit=lambda _event: None,
            run=fake_run,
        )

    assert report.ran is False
    assert report.reason == "prune_skipped_in_use"
    assert calls == []


def test_prune_timeout_is_tolerated(tmp_path: Path) -> None:
    """An unmarked uv cache lock cannot delay an MCP launch indefinitely."""

    (tmp_path / "uv-cache").mkdir(parents=True)

    def timing_out_run(cmd: list[str], **kwargs: Any) -> Any:
        raise subprocess.TimeoutExpired(cmd, kwargs["timeout"])

    report = prune_uv_cache(
        tmp_path,
        policy=_policy(),
        uv_executable="uv",
        emit=lambda _event: None,
        run=timing_out_run,
    )

    assert report.ran is True
    assert report.ok is False
    assert report.reason == "prune_timeout_10s"


def test_gc_refuses_when_any_environment_is_in_use(tmp_path: Path) -> None:
    """Bulk gc must refuse entirely while any environment is held, deleting none."""
    events, emit = _events_collector()
    held_env, _ = _seed_spec(tmp_path, "spack", _HASHES[0], mtime=1_000.0)
    other_env, _ = _seed_spec(tmp_path, "spack", _HASHES[1], mtime=2_000.0)

    with EnvironmentInUseMarker(tmp_path, held_env.name):
        with pytest.raises(CacheInUseError):
            collect_cache_gc(
                tmp_path,
                policy=_policy(keep_per_server=1),
                uv_executable="uv",
                emit=emit,
            )

    assert held_env.exists()
    assert other_env.exists()
    assert any(event["event"] == "cache_gc_refused" for event in events)


def test_gc_collapses_every_server_to_keep_n(tmp_path: Path) -> None:
    """With nothing in use, gc must collapse each server to its newest N specs."""
    spack_old, _ = _seed_spec(tmp_path, "spack", _HASHES[0], mtime=1_000.0)
    spack_new, _ = _seed_spec(tmp_path, "spack", _HASHES[1], mtime=2_000.0)
    jarvis_old, _ = _seed_spec(tmp_path, "jarvis", _HASHES[2], mtime=1_500.0)
    jarvis_new, _ = _seed_spec(tmp_path, "jarvis", _HASHES[3], mtime=2_500.0)
    (tmp_path / "uv-cache").mkdir(parents=True)

    eviction, prune = collect_cache_gc(
        tmp_path,
        policy=_policy(keep_per_server=1),
        uv_executable="uv",
        emit=lambda _event: None,
        dry_run=False,
    )

    assert spack_new.exists() and jarvis_new.exists()
    assert not spack_old.exists() and not jarvis_old.exists()
    assert {entry.server for entry in eviction.evicted} == {"spack", "jarvis"}
    # prune is attempted against the real uv; tolerate whatever the box reports.
    assert prune.ran or prune.reason in {"cache_absent", "prune_disabled"}


def test_gc_dry_run_reports_without_deleting(tmp_path: Path) -> None:
    """A dry-run gc must enumerate eviction candidates but delete nothing."""
    old_env, _ = _seed_spec(tmp_path, "spack", _HASHES[0], mtime=1_000.0)
    _seed_spec(tmp_path, "spack", _HASHES[1], mtime=2_000.0)

    eviction, prune = collect_cache_gc(
        tmp_path,
        policy=_policy(keep_per_server=1),
        uv_executable="uv",
        emit=lambda _event: None,
        dry_run=True,
    )

    assert old_env.exists()  # nothing removed
    assert [entry.hash_prefix for entry in eviction.evicted] == [_HASHES[0][:24]]
    assert not prune.ran and prune.reason == "dry_run"


def test_load_cache_policy_reads_configuration(tmp_path: Path) -> None:
    """Configuration knobs must be honored from the process environment."""
    policy = load_cache_policy(
        {
            "CLIO_KIT_ENV_KEEP": "3",
            "CLIO_KIT_ENV_EVICTION": "0",
            "CLIO_KIT_UV_CACHE_PRUNE": "off",
            "CLIO_KIT_CACHE_MAX_BYTES": "1048576",
        },
        emit=lambda _event: None,
    )

    assert policy.keep_per_server == 3
    assert policy.eviction_enabled is False
    assert policy.prune_enabled is False
    assert policy.max_cache_bytes == 1_048_576


def test_load_cache_policy_rejects_invalid_values_typed() -> None:
    """Invalid knobs must fall back to defaults with a typed rejection event."""
    events, emit = _events_collector()

    policy = load_cache_policy(
        {"CLIO_KIT_ENV_KEEP": "0", "CLIO_KIT_CACHE_MAX_BYTES": "huge"},
        emit=emit,
    )

    assert policy.keep_per_server == 1  # default
    assert policy.max_cache_bytes is None
    reasons = {
        (event["name"], event["reason"])
        for event in events
        if event["event"] == "cache_config_rejected"
    }
    assert ("CLIO_KIT_ENV_KEEP", "below_minimum") in reasons
    assert ("CLIO_KIT_CACHE_MAX_BYTES", "not_an_integer") in reasons


def test_measure_cache_budget_flags_over_budget(tmp_path: Path) -> None:
    """The advisory budget must emit a typed over-budget event when exceeded."""
    events, emit = _events_collector()
    _seed_spec(tmp_path, "spack", _HASHES[0], mtime=1_000.0, env_bytes=8192)

    report = measure_cache_budget(
        tmp_path, policy=_policy(max_cache_bytes=1), emit=emit
    )

    assert report.over_budget
    assert report.measured is True
    assert report.total_bytes >= 8192
    assert any(event["event"] == "cache_over_budget" for event in events)


def test_maintain_after_build_evicts_and_prunes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The post-build pass must evict stale specs and attempt a prune together."""
    (tmp_path / "uv-cache").mkdir(parents=True)
    old_env, _ = _seed_spec(tmp_path, "spack", _HASHES[0], mtime=1_000.0)
    _seed_spec(tmp_path, "spack", _HASHES[1], mtime=2_000.0)
    prune_calls: list[list[str]] = []

    def fake_run(cmd: list[str], **_kwargs: Any) -> subprocess.CompletedProcess[bytes]:
        prune_calls.append(cmd)
        return subprocess.CompletedProcess(cmd, 0, b"", b"")

    monkeypatch.setattr("clio_kit.env_cache.subprocess.run", fake_run)

    eviction, prune, budget = maintain_after_build(
        tmp_path,
        "spack",
        project_sha256=_HASHES[1],
        uv_executable="uv",
        policy=_policy(keep_per_server=1),
        emit=lambda _event: None,
    )

    assert not old_env.exists()
    assert eviction.bytes_freed > 0
    assert prune.ran and prune.ok
    assert prune_calls and prune_calls[0][1:3] == ["cache", "prune"]
    assert budget.measured is False
    assert budget.over_budget is False


def test_maintain_after_build_skips_unconfigured_budget_walk(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Server launch must not scan the whole cache when no budget is configured."""
    events, emit = _events_collector()
    current = _HASHES[0]
    _seed_spec(tmp_path, "geo", current, mtime=1_000.0)

    def fail_measure(*_args: Any, **_kwargs: Any) -> BudgetReport:
        raise AssertionError("unconfigured launch must not measure the cache")

    monkeypatch.setattr("clio_kit.env_cache.measure_cache_budget", fail_measure)

    _eviction, _prune, budget = maintain_after_build(
        tmp_path,
        "geo",
        project_sha256=current,
        uv_executable="uv",
        policy=_policy(eviction_enabled=False, prune_enabled=False),
        emit=emit,
    )

    assert budget == BudgetReport(
        total_bytes=0,
        max_bytes=None,
        over_budget=False,
        measured=False,
    )
    assert any(
        event.get("event") == "cache_budget_measurement"
        and event.get("reason") == "budget_unconfigured"
        for event in events
    )


def test_launcher_local_server_evicts_stale_sibling(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """End-to-end wiring: launching a server evicts an older spec of that server."""
    server_path = tmp_path / "servers" / "spack"
    (server_path / "src").mkdir(parents=True)
    (server_path / "pyproject.toml").write_text(
        "[project]\nname = 'spack-mcp'\nversion = '1.0.0'\n", encoding="utf-8"
    )
    (server_path / "uv.lock").write_text("version = 1\n", encoding="utf-8")
    (server_path / "src" / "server.py").write_text("VALUE = 1\n", encoding="utf-8")

    cache_root = tmp_path / "cache"
    monkeypatch.setenv("CLIO_KIT_CACHE_DIR", str(cache_root))
    monkeypatch.setattr(clio_kit, "uv_command", lambda: "uv")

    identity = clio_kit.locked_server_project_identity(server_path)
    current_env = clio_kit._locked_server_environment_path(
        server_path, project_sha256=identity["project_sha256"]
    )
    # Pre-seed a stale sibling spec for the same server.
    stale_env, stale_project = _seed_spec(
        cache_root, "spack", _HASHES[8], mtime=1_000.0
    )
    sync_environments: list[dict[str, str]] = []

    def fake_run(cmd: list[str], **kwargs: Any) -> subprocess.CompletedProcess[bytes]:
        # The build (uv sync) must materialize the current environment directory.
        if "sync" in cmd:
            sync_environments.append(kwargs["env"])
            current_env.mkdir(parents=True, exist_ok=True)
            (current_env / "bin").mkdir(parents=True, exist_ok=True)
        return subprocess.CompletedProcess(cmd, 0, b"", b"")

    monkeypatch.setattr(clio_kit.subprocess, "run", fake_run)

    clio_kit._run_locked_local_server(server_path, "spack-mcp", (), os.environ.copy())

    assert current_env.exists()
    assert sync_environments[0]["UV_PRERELEASE"] == "allow"
    assert not stale_env.exists()
    assert not stale_project.exists()
