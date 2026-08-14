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

from pathlib import Path
from typing import Any, cast

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


def read_community_entries(repo_root: Path) -> list[dict[str, Any]]:
    """Read outside contributions, one TOML per contributor, name-sorted.

    These are indexed, not vendored. Their updates reach users on the next
    ``/plugin marketplace update`` without a release here, which is the whole
    benefit and the whole risk -- so the shape is checked hard even though the
    content is not ours.
    """
    entries_dir = repo_root / "community" / "entries"
    if not entries_dir.is_dir():
        return []

    entries: list[dict[str, Any]] = []
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

        source = data.get("source")
        if not isinstance(source, dict):
            raise ValueError(f"{path} needs a [source] table")
        source_type = source.get("type")
        if source_type not in COMMUNITY_SOURCE_FIELDS:
            raise ValueError(
                f"{path} has source type {source_type!r}; "
                f"expected one of {sorted(COMMUNITY_SOURCE_FIELDS)}"
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
        entries.append(entry)

    names = [entry["name"] for entry in entries]
    if len(set(names)) != len(names):
        raise ValueError("community entries contain duplicate names")
    return entries
