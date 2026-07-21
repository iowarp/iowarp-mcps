"""Bounded lifecycle for the private MCP runtime cache.

The launcher builds one source-and-lock addressed child environment per embedded
server spec under ``mcp-environments`` and copies the server project under
``mcp-projects``.  Because both trees are keyed by the project content hash, every
version or lock change mints a *new* directory and the previous one is never
reclaimed.  On a heavy-use box this grew to tens of gigabytes: 72 full virtual
environments for 11 servers, each re-installing the same scientific stack, beside
a private ``uv-cache`` that hoarded every wheel ever downloaded.

This module turns that unbounded history into a bounded steady state.  After a
server environment is *successfully* rebuilt for a new spec, the older specs of
that same server are evicted (keep-newest-N), the private uv cache is pruned, and
every deletion is reported as a typed structured event.  Eviction is safe: it
never removes the environment just built, and it never removes an environment a
live server process still holds through the in-use marker.  A ``cache gc``
entrypoint applies the same invariant across all servers for boxes already
polluted, refusing to run while any served process is alive.

The one hard constraint the launcher imposes on this code: it runs *before* the
child MCP server inherits stdout, which is the JSON-RPC channel.  Nothing here
may write to stdout — every event and diagnostic goes to stderr.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from collections.abc import Callable, Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Final

CACHE_EVENT_SCHEMA: Final = "clio-kit.cache-event.v1"
ENVIRONMENTS_DIRNAME: Final = "mcp-environments"
PROJECTS_DIRNAME: Final = "mcp-projects"
UV_CACHE_DIRNAME: Final = "uv-cache"
LOCKS_DIRNAME: Final = ".locks"
_ENV_HASH_PREFIX_LENGTH: Final = 24
_HEX_DIGITS: Final = frozenset("0123456789abcdef")

# Configuration environment variables. The launcher's established configuration
# surface is process environment (see CLIO_KIT_CACHE_DIR), so these follow that
# convention rather than inventing a settings file.
KEEP_PER_SERVER_ENV: Final = "CLIO_KIT_ENV_KEEP"
EVICTION_ENABLED_ENV: Final = "CLIO_KIT_ENV_EVICTION"
PRUNE_ENABLED_ENV: Final = "CLIO_KIT_UV_CACHE_PRUNE"
CACHE_MAX_BYTES_ENV: Final = "CLIO_KIT_CACHE_MAX_BYTES"
_DEFAULT_KEEP_PER_SERVER: Final = 1

EmitEvent = Callable[[Mapping[str, object]], None]


def default_event_emitter(event: Mapping[str, object]) -> None:
    """Emit one structured cache event to stderr as a sorted JSON line.

    Stdout is reserved for the child server's JSON-RPC stream, so cache
    telemetry is confined to stderr.
    """
    payload = {"schema_version": CACHE_EVENT_SCHEMA, **event}
    sys.stderr.write(json.dumps(payload, sort_keys=True) + "\n")
    sys.stderr.flush()


@dataclass(frozen=True)
class CachePolicy:
    """Resolved, typed bounds for the private MCP runtime cache."""

    keep_per_server: int
    eviction_enabled: bool
    prune_enabled: bool
    max_cache_bytes: int | None

    @property
    def evict_count(self) -> int:
        """Return how many older specs, beyond the current, may be retained."""
        return max(0, self.keep_per_server - 1)


@dataclass(frozen=True)
class EvictedEnvironment:
    """One evicted server spec and the reclaimed footprint it represented."""

    server: str
    hash_prefix: str
    reason: str
    bytes_freed: int
    paths: tuple[str, ...]


@dataclass(frozen=True)
class SkippedEnvironment:
    """One retained-or-skipped spec, with the typed reason it was not evicted."""

    server: str
    hash_prefix: str
    reason: str


@dataclass(frozen=True)
class EvictionReport:
    """Structured outcome of a keep-newest eviction pass for a server set."""

    kept: tuple[SkippedEnvironment, ...] = ()
    evicted: tuple[EvictedEnvironment, ...] = ()
    skipped_in_use: tuple[SkippedEnvironment, ...] = ()

    @property
    def bytes_freed(self) -> int:
        """Return total bytes reclaimed across every evicted spec."""
        return sum(entry.bytes_freed for entry in self.evicted)


@dataclass(frozen=True)
class PruneReport:
    """Structured outcome of a private ``uv cache prune`` invocation."""

    ran: bool
    ok: bool
    reason: str
    cache_dir: str


@dataclass(frozen=True)
class BudgetReport:
    """Measured cache footprint against the optional configured budget."""

    total_bytes: int
    max_bytes: int | None
    over_budget: bool


@dataclass
class _EnvIdentity:
    """One server spec observed across the environment and project trees."""

    server: str
    hash_prefix: str
    env_dir: Path | None = None
    project_dirs: list[Path] = field(default_factory=list)

    def all_paths(self) -> list[Path]:
        paths: list[Path] = []
        if self.env_dir is not None:
            paths.append(self.env_dir)
        paths.extend(self.project_dirs)
        return paths

    def recency(self) -> float:
        """Return the newest mtime across this spec's on-disk directories."""
        times = [_safe_mtime(path) for path in self.all_paths()]
        return max(times) if times else 0.0


def load_cache_policy(
    environ: Mapping[str, str] | None = None,
    *,
    emit: EmitEvent = default_event_emitter,
) -> CachePolicy:
    """Resolve the cache policy from configuration, reporting invalid values.

    Invalid configuration is never silently corrected: each rejected value emits
    a typed ``cache_config_rejected`` event before the documented default is used.
    """
    env = os.environ if environ is None else environ
    keep = _positive_int_config(
        env.get(KEEP_PER_SERVER_ENV),
        default=_DEFAULT_KEEP_PER_SERVER,
        name=KEEP_PER_SERVER_ENV,
        emit=emit,
    )
    max_bytes = _optional_positive_int_config(
        env.get(CACHE_MAX_BYTES_ENV),
        name=CACHE_MAX_BYTES_ENV,
        emit=emit,
    )
    return CachePolicy(
        keep_per_server=keep,
        eviction_enabled=_bool_config(env.get(EVICTION_ENABLED_ENV), default=True),
        prune_enabled=_bool_config(env.get(PRUNE_ENABLED_ENV), default=True),
        max_cache_bytes=max_bytes,
    )


def evict_superseded_environments(
    cache_root: Path,
    server: str,
    *,
    keep_current: str,
    policy: CachePolicy,
    emit: EmitEvent = default_event_emitter,
) -> EvictionReport:
    """Evict older specs of one server, keeping the current build and newest N.

    ``keep_current`` is the full ``project_sha256`` of the environment that was
    just built; it is retained unconditionally so a launch never deletes the
    environment it is about to run.  Additional specs up to the configured
    keep-count are retained by recency.  Any remaining spec that a live server
    still holds is skipped with a typed reason rather than deleted, because
    concurrent mutation of an in-use environment corrupts it.
    """
    if not policy.eviction_enabled:
        return EvictionReport(
            skipped_in_use=(),
            kept=(
                SkippedEnvironment(
                    server, keep_current[:_ENV_HASH_PREFIX_LENGTH], "eviction_disabled"
                ),
            ),
        )

    current_prefix = keep_current[:_ENV_HASH_PREFIX_LENGTH]
    identities = _discover_identities(cache_root, server)
    return _apply_keep_newest(
        cache_root,
        identities,
        retain_prefixes={current_prefix},
        keep_extra=policy.evict_count,
        reason="superseded",
        emit=emit,
    )


def prune_uv_cache(
    cache_root: Path,
    *,
    policy: CachePolicy,
    uv_executable: str,
    emit: EmitEvent = default_event_emitter,
    run: Callable[..., subprocess.CompletedProcess[bytes]] | None = None,
) -> PruneReport:
    """Prune the private uv cache so wheel retention tracks live environments.

    Failure is tolerated: the launch must proceed even when pruning cannot run,
    and every outcome — skipped, pruned, or failed — is reported as a typed
    event with its reason.
    """
    run_command = subprocess.run if run is None else run
    cache_dir = (cache_root / UV_CACHE_DIRNAME).resolve()
    if not policy.prune_enabled:
        report = PruneReport(
            ran=False, ok=True, reason="prune_disabled", cache_dir=str(cache_dir)
        )
        emit(
            {
                "event": "uv_cache_prune",
                "ran": False,
                "ok": True,
                "reason": report.reason,
                "cache_dir": report.cache_dir,
            }
        )
        return report
    if not cache_dir.is_dir():
        report = PruneReport(
            ran=False, ok=True, reason="cache_absent", cache_dir=str(cache_dir)
        )
        emit(
            {
                "event": "uv_cache_prune",
                "ran": False,
                "ok": True,
                "reason": report.reason,
                "cache_dir": report.cache_dir,
            }
        )
        return report
    try:
        completed = run_command(
            [uv_executable, "cache", "prune", "--cache-dir", str(cache_dir)],
            capture_output=True,
            check=False,
        )
    except OSError as exc:
        report = PruneReport(
            ran=True,
            ok=False,
            reason=f"prune_spawn_failed: {exc}",
            cache_dir=str(cache_dir),
        )
        emit(
            {
                "event": "uv_cache_prune",
                "ran": True,
                "ok": False,
                "reason": report.reason,
                "cache_dir": report.cache_dir,
            }
        )
        return report
    if completed.returncode != 0:
        detail = _decode_stream_tail(completed.stderr) or _decode_stream_tail(
            completed.stdout
        )
        report = PruneReport(
            ran=True,
            ok=False,
            reason=f"prune_exit_{completed.returncode}: {detail}".strip(),
            cache_dir=str(cache_dir),
        )
        emit(
            {
                "event": "uv_cache_prune",
                "ran": True,
                "ok": False,
                "reason": report.reason,
                "cache_dir": report.cache_dir,
            }
        )
        return report
    report = PruneReport(ran=True, ok=True, reason="pruned", cache_dir=str(cache_dir))
    emit(
        {
            "event": "uv_cache_prune",
            "ran": True,
            "ok": True,
            "reason": report.reason,
            "cache_dir": report.cache_dir,
        }
    )
    return report


def measure_cache_budget(
    cache_root: Path,
    *,
    policy: CachePolicy,
    emit: EmitEvent = default_event_emitter,
) -> BudgetReport:
    """Measure the cache footprint and report a typed over-budget event.

    The bound is advisory: uv owns wheel pruning, so this asserts the invariant
    for monitoring and CI rather than deleting arbitrary cache entries.
    """
    total = _dir_size(cache_root)
    over = policy.max_cache_bytes is not None and total > policy.max_cache_bytes
    if over:
        emit(
            {
                "event": "cache_over_budget",
                "cache_root": str(cache_root),
                "total_bytes": total,
                "max_bytes": policy.max_cache_bytes,
            }
        )
    return BudgetReport(
        total_bytes=total, max_bytes=policy.max_cache_bytes, over_budget=over
    )


def maintain_after_build(
    cache_root: Path,
    server: str,
    *,
    project_sha256: str,
    uv_executable: str,
    policy: CachePolicy | None = None,
    emit: EmitEvent = default_event_emitter,
) -> tuple[EvictionReport, PruneReport, BudgetReport]:
    """Run the full post-build steady-state pass: evict, prune, measure.

    This is the single entry point the launcher calls after a server's
    environment is confirmed built.  Every step is best-effort with a typed
    report; a maintenance failure must never prevent the server from launching.
    """
    resolved_policy = policy or load_cache_policy(emit=emit)
    eviction = evict_superseded_environments(
        cache_root,
        server,
        keep_current=project_sha256,
        policy=resolved_policy,
        emit=emit,
    )
    prune = prune_uv_cache(
        cache_root,
        policy=resolved_policy,
        uv_executable=uv_executable,
        emit=emit,
    )
    budget = measure_cache_budget(cache_root, policy=resolved_policy, emit=emit)
    return eviction, prune, budget


class CacheInUseError(RuntimeError):
    """Raised when a bulk cache operation is refused because a server is live."""


def collect_cache_gc(
    cache_root: Path,
    *,
    policy: CachePolicy,
    uv_executable: str,
    emit: EmitEvent = default_event_emitter,
    dry_run: bool = False,
) -> tuple[EvictionReport, PruneReport]:
    """Apply keep-newest-N across every server for an already-polluted box.

    This mirrors the per-launch invariant but has no "current build" to anchor
    on, so it keeps the newest N specs per server by recency.  It refuses (typed)
    to touch anything while any environment is still held by a live server,
    because bulk deletion during an active spawn corrupts the cache.
    """
    servers = discover_servers(cache_root)
    live = [
        identity
        for identity in _all_identities(cache_root, servers)
        if _identity_in_use(cache_root, identity)
    ]
    if live:
        held = sorted(f"{item.server}-{item.hash_prefix}" for item in live)
        emit(
            {
                "event": "cache_gc_refused",
                "reason": "environments_in_use",
                "in_use": held,
            }
        )
        raise CacheInUseError(
            "refusing cache gc while these environments are in use: " + ", ".join(held)
        )

    aggregate = EvictionReport()
    for server in sorted(servers):
        identities = _discover_identities(cache_root, server)
        report = _apply_keep_newest(
            cache_root,
            identities,
            retain_prefixes=set(),
            keep_extra=max(0, policy.keep_per_server),
            reason="gc_superseded",
            emit=emit,
            dry_run=dry_run,
        )
        aggregate = _merge_reports(aggregate, report)

    if dry_run:
        prune = PruneReport(
            ran=False,
            ok=True,
            reason="dry_run",
            cache_dir=str((cache_root / UV_CACHE_DIRNAME).resolve()),
        )
        emit(
            {
                "event": "uv_cache_prune",
                "ran": False,
                "ok": True,
                "reason": prune.reason,
                "cache_dir": prune.cache_dir,
            }
        )
    else:
        prune = prune_uv_cache(
            cache_root, policy=policy, uv_executable=uv_executable, emit=emit
        )
    return aggregate, prune


def discover_servers(cache_root: Path) -> set[str]:
    """Return every server name known to the on-disk project and env trees."""
    servers: set[str] = set()
    projects_root = cache_root / PROJECTS_DIRNAME
    if projects_root.is_dir():
        servers.update(
            child.name for child in projects_root.iterdir() if child.is_dir()
        )
    return servers


# --- in-use marker -------------------------------------------------------


class EnvironmentInUseMarker:
    """A per-process lock proving a live launcher holds one environment.

    The marker is a lock file named for the holding process id under a locks
    registry sibling to the environment tree.  Concurrent launches of the same
    spec never contend, because each locks only its own pid file; a checker
    detecting *any* pid file it cannot lock knows a live holder exists, while a
    crashed holder's file is lockable and reclaimed.  The registry lives outside
    the environment directory so acquiring it never perturbs environment mtimes
    or the environment contents uv manages.
    """

    def __init__(self, cache_root: Path, env_dir_name: str) -> None:
        self._lock_dir = _locks_dir(cache_root, env_dir_name)
        self._handle: _FileLock | None = None

    def __enter__(self) -> "EnvironmentInUseMarker":
        try:
            self._lock_dir.mkdir(parents=True, exist_ok=True)
            lock_path = self._lock_dir / f"{os.getpid()}.lock"
            handle = _FileLock(lock_path)
            handle.acquire()
            self._handle = handle
        except OSError:
            # Best-effort: an unwritable registry must not block a launch. The
            # current environment is never a deletion candidate regardless.
            self._handle = None
        return self

    def __exit__(self, *_exc: object) -> None:
        if self._handle is not None:
            self._handle.release()
            self._handle = None


def _identity_in_use(cache_root: Path, identity: _EnvIdentity) -> bool:
    env_dir_name = (
        identity.env_dir.name
        if identity.env_dir is not None
        else f"{identity.server}-{identity.hash_prefix}"
    )
    return _env_dir_in_use(cache_root, env_dir_name)


def _env_dir_in_use(cache_root: Path, env_dir_name: str) -> bool:
    """Return whether any live launcher currently holds this environment."""
    lock_dir = _locks_dir(cache_root, env_dir_name)
    if not lock_dir.is_dir():
        return False
    in_use = False
    for lock_path in lock_dir.glob("*.lock"):
        probe = _FileLock(lock_path)
        if probe.try_acquire():
            # No live holder: reclaim the stale marker.
            probe.release()
            try:
                lock_path.unlink()
            except OSError:
                pass
        else:
            in_use = True
    return in_use


def _locks_dir(cache_root: Path, env_dir_name: str) -> Path:
    return cache_root / ENVIRONMENTS_DIRNAME / LOCKS_DIRNAME / env_dir_name


class _FileLock:
    """A cross-platform advisory lock on a single sentinel file."""

    def __init__(self, path: Path) -> None:
        self._path = path
        self._fd: int | None = None

    def acquire(self) -> None:
        if not self.try_acquire():
            raise OSError(f"could not acquire lock: {self._path}")

    def try_acquire(self) -> bool:
        fd = os.open(self._path, os.O_RDWR | os.O_CREAT, 0o644)
        try:
            os.write(fd, b"\0")
            os.lseek(fd, 0, os.SEEK_SET)
            _lock_region(fd)
        except OSError:
            os.close(fd)
            return False
        self._fd = fd
        return True

    def release(self) -> None:
        if self._fd is None:
            return
        try:
            _unlock_region(self._fd)
        except OSError:
            pass
        finally:
            os.close(self._fd)
            self._fd = None


if sys.platform == "win32":
    import msvcrt

    def _lock_region(fd: int) -> None:
        msvcrt.locking(fd, msvcrt.LK_NBLCK, 1)

    def _unlock_region(fd: int) -> None:
        os.lseek(fd, 0, os.SEEK_SET)
        msvcrt.locking(fd, msvcrt.LK_UNLCK, 1)
else:
    import fcntl

    def _lock_region(fd: int) -> None:
        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)

    def _unlock_region(fd: int) -> None:
        fcntl.flock(fd, fcntl.LOCK_UN)


# --- internals -----------------------------------------------------------


def _apply_keep_newest(
    cache_root: Path,
    identities: Sequence[_EnvIdentity],
    *,
    retain_prefixes: set[str],
    keep_extra: int,
    reason: str,
    emit: EmitEvent,
    dry_run: bool = False,
) -> EvictionReport:
    """Retain forced + newest specs; evict the rest, skipping in-use ones."""
    forced = [item for item in identities if item.hash_prefix in retain_prefixes]
    others = sorted(
        (item for item in identities if item.hash_prefix not in retain_prefixes),
        key=lambda item: item.recency(),
        reverse=True,
    )
    retained = forced + others[:keep_extra]
    candidates = others[keep_extra:]

    kept = tuple(
        SkippedEnvironment(item.server, item.hash_prefix, "retained")
        for item in retained
    )
    evicted: list[EvictedEnvironment] = []
    skipped: list[SkippedEnvironment] = []
    for identity in candidates:
        if _identity_in_use(cache_root, identity):
            skipped.append(
                SkippedEnvironment(identity.server, identity.hash_prefix, "in_use")
            )
            emit(
                {
                    "event": "env_evict_skipped",
                    "server": identity.server,
                    "hash_prefix": identity.hash_prefix,
                    "reason": "in_use",
                }
            )
            continue
        paths = identity.all_paths()
        freed = sum(_dir_size(path) for path in paths)
        if not dry_run:
            for path in paths:
                _remove_tree(path)
            _remove_tree(
                _locks_dir(cache_root, f"{identity.server}-{identity.hash_prefix}")
            )
        evicted.append(
            EvictedEnvironment(
                server=identity.server,
                hash_prefix=identity.hash_prefix,
                reason=reason,
                bytes_freed=freed,
                paths=tuple(str(path) for path in paths),
            )
        )
        emit(
            {
                "event": "env_evicted",
                "server": identity.server,
                "hash_prefix": identity.hash_prefix,
                "reason": reason,
                "bytes_freed": freed,
                "paths": [str(path) for path in paths],
                "dry_run": dry_run,
            }
        )
    return EvictionReport(
        kept=kept, evicted=tuple(evicted), skipped_in_use=tuple(skipped)
    )


def _discover_identities(cache_root: Path, server: str) -> list[_EnvIdentity]:
    """Group one server's specs across the environment and project trees."""
    by_prefix: dict[str, _EnvIdentity] = {}

    def identity_for(prefix: str) -> _EnvIdentity:
        existing = by_prefix.get(prefix)
        if existing is None:
            existing = _EnvIdentity(server=server, hash_prefix=prefix)
            by_prefix[prefix] = existing
        return existing

    env_root = cache_root / ENVIRONMENTS_DIRNAME
    if env_root.is_dir():
        prefix_token = f"{server}-"
        for child in env_root.iterdir():
            if child.name == LOCKS_DIRNAME or not child.is_dir():
                continue
            if not child.name.startswith(prefix_token):
                continue
            remainder = child.name[len(prefix_token) :]
            if _is_env_hash_prefix(remainder):
                identity_for(remainder).env_dir = child

    project_root = cache_root / PROJECTS_DIRNAME / server
    if project_root.is_dir():
        for child in project_root.iterdir():
            if not child.is_dir():
                continue
            if len(child.name) >= _ENV_HASH_PREFIX_LENGTH and _is_hex(child.name):
                identity_for(child.name[:_ENV_HASH_PREFIX_LENGTH]).project_dirs.append(
                    child
                )

    return list(by_prefix.values())


def _all_identities(cache_root: Path, servers: Iterable[str]) -> list[_EnvIdentity]:
    identities: list[_EnvIdentity] = []
    for server in servers:
        identities.extend(_discover_identities(cache_root, server))
    return identities


def _merge_reports(left: EvictionReport, right: EvictionReport) -> EvictionReport:
    return EvictionReport(
        kept=left.kept + right.kept,
        evicted=left.evicted + right.evicted,
        skipped_in_use=left.skipped_in_use + right.skipped_in_use,
    )


def _is_env_hash_prefix(value: str) -> bool:
    return len(value) == _ENV_HASH_PREFIX_LENGTH and _is_hex(value)


def _is_hex(value: str) -> bool:
    return bool(value) and all(character in _HEX_DIGITS for character in value)


def _safe_mtime(path: Path) -> float:
    try:
        return path.stat().st_mtime
    except OSError:
        return 0.0


def _dir_size(path: Path) -> int:
    if not path.exists():
        return 0
    total = 0
    for current_root, _dirs, files in os.walk(path):
        base = Path(current_root)
        for name in files:
            try:
                total += (base / name).stat().st_size
            except OSError:
                continue
    return total


def _remove_tree(path: Path) -> None:
    shutil.rmtree(path, ignore_errors=True)


def _decode_stream_tail(data: bytes | None, *, limit: int = 2_000) -> str:
    if not data:
        return ""
    return data[-limit:].decode("utf-8", errors="replace").strip()


def _positive_int_config(
    raw: str | None,
    *,
    default: int,
    name: str,
    emit: EmitEvent,
) -> int:
    if raw is None or raw.strip() == "":
        return default
    try:
        value = int(raw)
    except ValueError:
        emit(
            {
                "event": "cache_config_rejected",
                "name": name,
                "value": raw,
                "reason": "not_an_integer",
                "using_default": default,
            }
        )
        return default
    if value < 1:
        emit(
            {
                "event": "cache_config_rejected",
                "name": name,
                "value": raw,
                "reason": "below_minimum",
                "using_default": default,
            }
        )
        return default
    return value


def _optional_positive_int_config(
    raw: str | None,
    *,
    name: str,
    emit: EmitEvent,
) -> int | None:
    if raw is None or raw.strip() == "":
        return None
    try:
        value = int(raw)
    except ValueError:
        emit(
            {
                "event": "cache_config_rejected",
                "name": name,
                "value": raw,
                "reason": "not_an_integer",
                "using_default": None,
            }
        )
        return None
    if value < 1:
        emit(
            {
                "event": "cache_config_rejected",
                "name": name,
                "value": raw,
                "reason": "below_minimum",
                "using_default": None,
            }
        )
        return None
    return value


def _bool_config(raw: str | None, *, default: bool) -> bool:
    if raw is None or raw.strip() == "":
        return default
    normalized = raw.strip().lower()
    if normalized in {"1", "true", "yes", "on"}:
        return True
    if normalized in {"0", "false", "no", "off"}:
        return False
    return default
