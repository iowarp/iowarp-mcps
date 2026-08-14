"""The `clio-kit cache` command group over the private MCP runtime cache.

Split out of the launcher module, which the size ratchet holds at a fixed line
count precisely because it had grown into the place every new command landed.
The commands here read and reclaim the content-addressed environment tree that
:mod:`clio_kit.env_cache` maintains; the launcher keeps only the code that
actually starts a server.
"""

from __future__ import annotations

import dataclasses
import json
import os
from pathlib import Path

import click

from clio_kit.env_cache import (
    CacheInUseError,
    collect_cache_gc,
    discover_servers,
    load_cache_policy,
    measure_cache_budget,
)


def clio_cache_root() -> Path:
    """Return the operator-configurable cache root used by child runtimes."""
    configured_cache = os.getenv("CLIO_KIT_CACHE_DIR")
    if configured_cache:
        return Path(configured_cache).expanduser().resolve()
    return (
        Path(os.getenv("XDG_CACHE_HOME", str(Path.home() / ".cache"))).expanduser()
        / "clio-kit"
    ).resolve()


@click.group("cache")
def cache_group() -> None:
    """Inspect and reclaim the private MCP runtime cache."""


@cache_group.command("gc")
@click.option(
    "--keep",
    type=int,
    default=None,
    help="Environments to keep per server (overrides CLIO_KIT_ENV_KEEP).",
)
@click.option(
    "--dry-run",
    is_flag=True,
    help="Report what would be evicted without deleting anything.",
)
def cache_gc(keep: int | None, dry_run: bool) -> None:
    """Collapse every server to its newest N specs and prune the uv cache.

    This is the manual reclaim path for a box already polluted by unbounded
    environment history. It refuses to run while any environment is held by a
    live server, because deleting an environment mid-spawn corrupts the cache.
    """
    # Imported here rather than at module scope: the launcher imports this
    # module to register the group, so a top-level import would cycle.
    from clio_kit import uv_command

    cache_root = clio_cache_root()
    policy = load_cache_policy()
    if keep is not None:
        if keep < 1:
            raise click.ClickException("--keep must be >= 1")
        policy = dataclasses.replace(policy, keep_per_server=keep)
    try:
        eviction, prune = collect_cache_gc(
            cache_root,
            policy=policy,
            uv_executable=uv_command(),
            dry_run=dry_run,
        )
    except CacheInUseError as exc:
        raise click.ClickException(str(exc)) from exc
    budget = measure_cache_budget(cache_root, policy=policy)
    click.echo(
        json.dumps(
            {
                "dry_run": dry_run,
                "keep_per_server": policy.keep_per_server,
                "evicted": [
                    {
                        "server": entry.server,
                        "hash_prefix": entry.hash_prefix,
                        "bytes_freed": entry.bytes_freed,
                    }
                    for entry in eviction.evicted
                ],
                "skipped_in_use": [
                    {"server": entry.server, "hash_prefix": entry.hash_prefix}
                    for entry in eviction.skipped_in_use
                ],
                "bytes_freed": eviction.bytes_freed,
                "uv_cache_prune": {
                    "ran": prune.ran,
                    "ok": prune.ok,
                    "reason": prune.reason,
                },
                "cache_total_bytes": budget.total_bytes,
                "over_budget": budget.over_budget,
            },
            sort_keys=True,
        )
    )


@cache_group.command("status")
def cache_status() -> None:
    """Print a machine-readable summary of the private runtime cache footprint."""
    cache_root = clio_cache_root()
    policy = load_cache_policy()
    budget = measure_cache_budget(cache_root, policy=policy)
    environments_root = cache_root / "mcp-environments"
    per_server: dict[str, int] = {}
    if environments_root.is_dir():
        for server in sorted(discover_servers(cache_root)):
            token = f"{server}-"
            per_server[server] = sum(
                1
                for child in environments_root.iterdir()
                if child.is_dir() and child.name.startswith(token)
            )
    click.echo(
        json.dumps(
            {
                "cache_root": str(cache_root),
                "total_bytes": budget.total_bytes,
                "max_bytes": budget.max_bytes,
                "over_budget": budget.over_budget,
                "keep_per_server": policy.keep_per_server,
                "environments_per_server": per_server,
            },
            sort_keys=True,
        )
    )


CACHE_GROUP = cache_group
