"""Read outside contributions to the CLIO Kit marketplace.

Entries here are *indexed*, not vendored: each names a repository or package
this project does not own, so the contributor keeps their code and their
release cadence and this repository holds one pointer. Their updates reach
users on the next ``/plugin marketplace update`` without a release here, which
is both the whole benefit and the whole risk -- so the shape of an entry is
checked hard even though its content is not ours to check.

Lives in the launcher package rather than beside the generator so the same
reader backs both manifest generation and the contributor-facing validation
that will check a submission before it becomes a pull request.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, cast

# Where the federated catalogue is published, in preference order.
#
# LIVE: a file shipped inside the marketplace itself. It travels with the
# marketplace, so `claude plugin marketplace update` refreshes it and a new
# referral reaches users without a clio-kit release -- which is the whole point
# of indexing rather than vendoring. It sits beside marketplace.json rather
# than inside it because a custom key under the manifest's own `metadata`
# fails `claude plugin validate --strict` with "Unknown field".
#
# BAKED: a snapshot inside the wheel, written at generation time. This is the
# fallback for an installation that has never added the marketplace, or a
# client whose layout we cannot read.
LIVE_FEDERATED_FILE = "federated-marketplaces.json"
FEDERATED_DATA_FILE = "_federated_marketplaces.json"

# Claude Code records every added marketplace here, including where it put the
# checkout. This is a client-internal file, so every read of it is best-effort:
# a missing file, an unexpected shape or an unreadable path falls back to the
# baked snapshot rather than failing.
KNOWN_MARKETPLACES = ("plugins", "known_marketplaces.json")

try:
    import tomllib
except ImportError:  # pragma: no cover - Python 3.10 fallback
    import tomli as tomllib  # type: ignore[import-not-found,no-redef]


# Source shapes an outside contribution may declare, and the fields each one
# needs. Everything here points at a repository or package we do not own: the
# contributor keeps their code and their release cadence, and this repository
# holds one entry. `npm` is what makes a TypeScript or Go plugin listable
# without living here at all.
COMMUNITY_SOURCE_FIELDS: dict[str, tuple[tuple[str, ...], tuple[str, ...]]] = {
    "github": (("repo",), ("ref", "sha")),
    "git-subdir": (("url", "path"), ("ref", "sha")),
    "npm": (("package",), ("version", "registry")),
    "url": (("url",), ("ref", "sha")),
}

# What an entry points at. A `plugin` is installable and rides in
# marketplace.json beside our own. A `marketplace` is somebody else's whole
# catalogue.
#
# The two cannot be published the same way, and the reason is a client
# constraint rather than a preference: Claude Code has no nested-marketplace
# concept. A marketplace is added with `claude plugin marketplace add`, one at
# a time, and an entry carrying an unrecognised field is reported as
# "Unknown field 'kind'. Claude Code ignores it at load time" -- so writing a
# marketplace into `plugins` would publish something that either fails to
# install or silently resolves to the wrong thing.
#
# A federated marketplace is therefore carried as a *referral*: recorded here,
# listed by `clio-kit marketplaces`, and added by the user with one command
# that we print. Their catalogue stays under their control, which is the
# property the entry existed to provide; what it does not do is appear inline
# inside ours, because no client we ship to can render that.
COMMUNITY_KINDS: tuple[str, ...] = ("plugin", "marketplace")

# A marketplace is fetched by the client as a whole repository, so only the
# source types that name one qualify. `npm` publishes a package and
# `git-subdir` a directory; neither is something `marketplace add` accepts.
MARKETPLACE_SOURCE_TYPES: frozenset[str] = frozenset({"github", "url"})


def read_community_entries(repo_root: Path) -> list[dict[str, Any]]:
    """Read the installable outside contributions, name-sorted.

    These are indexed, not vendored. Their updates reach users on the next
    ``/plugin marketplace update`` without a release here, which is the whole
    benefit and the whole risk -- so the shape is checked hard even though the
    content is not ours.

    Only ``kind = "plugin"`` entries come back, already shaped for
    ``marketplace.json``. Federated marketplaces are returned by
    :func:`read_federated_marketplaces` instead, because the client cannot
    render one inline.
    """
    return [entry for kind, entry in _read_entries(repo_root) if kind == "plugin"]


def read_federated_marketplaces(repo_root: Path) -> list[dict[str, Any]]:
    """Read the entries that point at somebody else's whole catalogue.

    Each carries the exact command a user runs to add it, because that is the
    only way a client we ship to can consume another marketplace.
    """
    federated: list[dict[str, Any]] = []
    for kind, entry in _read_entries(repo_root):
        if kind != "marketplace":
            continue
        referral = dict(entry)
        referral["add_command"] = marketplace_add_command(entry["source"])
        federated.append(referral)
    return federated


def marketplace_add_command(source: dict[str, Any]) -> str:
    """Return the one command that adds a federated marketplace."""
    target = source["repo"] if source["source"] == "github" else source["url"]
    return f"claude plugin marketplace add {target}"


def write_shipped_marketplaces(
    package_dir: Path, federated: list[dict[str, Any]]
) -> None:
    """Bake the federated catalogue into the package for the installed CLI."""
    payload = {
        "schema": "clio-kit.federated-marketplaces.v1",
        "marketplaces": federated,
    }
    path = package_dir / FEDERATED_DATA_FILE
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def read_shipped_marketplaces() -> list[dict[str, Any]]:
    """Return the federated catalogue baked into this installation."""
    return _read_federated_file(Path(__file__).resolve().parent / FEDERATED_DATA_FILE)


def _read_federated_file(path: Path) -> list[dict[str, Any]]:
    """Read one federated catalogue file, or nothing if it is unusable."""
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return []
    marketplaces = payload.get("marketplaces") if isinstance(payload, dict) else None
    if not isinstance(marketplaces, list):
        return []
    return cast(list[dict[str, Any]], marketplaces)


def _claude_config_dir() -> Path:
    """Return the client's configuration directory."""
    configured = os.getenv("CLAUDE_CONFIG_DIR")
    if configured:
        return Path(configured).expanduser()
    return Path.home() / ".claude"


def read_live_marketplaces() -> list[dict[str, Any]]:
    """Return the federated catalogue from an added marketplace, if there is one.

    Reads the client's own record of where each marketplace was checked out, so
    the answer reflects the last ``marketplace update`` rather than the version
    of clio-kit that happens to be installed. Every step is best-effort: this
    reads a client-internal file, and an unreadable or unexpected one means the
    caller falls back to the baked snapshot.
    """
    known = _claude_config_dir().joinpath(*KNOWN_MARKETPLACES)
    try:
        entries = json.loads(known.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return []
    if not isinstance(entries, dict):
        return []

    for record in entries.values():
        if not isinstance(record, dict):
            continue
        location = record.get("installLocation")
        if not isinstance(location, str) or not location:
            continue
        found = _read_federated_file(
            Path(location) / ".claude-plugin" / LIVE_FEDERATED_FILE
        )
        if found:
            return found
    return []


def write_live_marketplaces(repo_root: Path, federated: list[dict[str, Any]]) -> None:
    """Publish the federated catalogue inside the marketplace itself."""
    payload = {
        "schema": "clio-kit.federated-marketplaces.v1",
        "marketplaces": federated,
    }
    path = repo_root / ".claude-plugin" / LIVE_FEDERATED_FILE
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def _read_entries(repo_root: Path) -> list[tuple[str, dict[str, Any]]]:
    """Parse every entry file, returning (kind, marketplace-shaped entry)."""
    entries_dir = repo_root / "community" / "entries"
    if not entries_dir.is_dir():
        return []

    entries: list[tuple[str, dict[str, Any]]] = []
    for path in sorted(entries_dir.glob("*.toml")):
        with open(path, "rb") as f:
            data = tomllib.load(f)

        name = data.get("name")
        if not isinstance(name, str) or not name:
            raise ValueError(f"{path} needs a name")
        if name != path.stem:
            raise ValueError(f"{path} declares name {name!r}; rename the file to match")
        if name.startswith("clio-"):
            raise ValueError(
                f"{path} may not claim the clio- prefix, which is generated from "
                "this repository's own servers, bundles and skills"
            )
        description = data.get("description")
        if not isinstance(description, str) or not description:
            raise ValueError(f"{path} needs a description")

        kind = data.get("kind", "plugin")
        if kind not in COMMUNITY_KINDS:
            raise ValueError(
                f"{path} has kind {kind!r}; expected one of {sorted(COMMUNITY_KINDS)}"
            )

        source = data.get("source")
        if not isinstance(source, dict):
            raise ValueError(f"{path} needs a [source] table")
        source_type = source.get("type")
        if source_type not in COMMUNITY_SOURCE_FIELDS:
            raise ValueError(
                f"{path} has source type {source_type!r}; "
                f"expected one of {sorted(COMMUNITY_SOURCE_FIELDS)}"
            )
        if kind == "marketplace" and source_type not in MARKETPLACE_SOURCE_TYPES:
            raise ValueError(
                f"{path} is a marketplace, so its source must name a whole "
                f"repository -- {source_type!r} cannot be passed to "
                f"`claude plugin marketplace add`; "
                f"expected one of {sorted(MARKETPLACE_SOURCE_TYPES)}"
            )
        required, optional = COMMUNITY_SOURCE_FIELDS[cast(str, source_type)]
        unexpected = sorted(set(source) - {"type", *required, *optional})
        if unexpected:
            raise ValueError(f"{path} source has unexpected fields: {unexpected}")
        missing = sorted(field for field in required if not source.get(field))
        if missing:
            raise ValueError(f"{path} source of type {source_type!r} needs {missing}")

        marketplace_source: dict[str, Any] = {"source": source_type}
        for field in (*required, *optional):
            if source.get(field):
                marketplace_source[field] = source[field]

        entry: dict[str, Any] = {
            "name": name,
            "source": marketplace_source,
            "description": description,
            "category": data.get("category", "community"),
            "keywords": list(data.get("keywords", [])),
        }
        # Recorded so a stale entry has someone to ask, and surfaced in the
        # catalogue so a user can see this is indexed rather than maintained
        # here. Claude Code ignores `metadata`, which is what makes it safe to
        # carry provenance in.
        maintainer = data.get("maintainer")
        if maintainer:
            entry["metadata"] = {"maintainer": maintainer, "indexed": True}
        entries.append((kind, entry))

    names = [entry["name"] for _, entry in entries]
    if len(set(names)) != len(names):
        raise ValueError("community entries contain duplicate names")
    return entries
