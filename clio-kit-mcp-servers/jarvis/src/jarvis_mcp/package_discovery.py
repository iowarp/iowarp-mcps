"""Package inventory discovery, bounded search, and agent-visible settings.

Split out of ``jarvis_mcp.server`` (clio-kit campaign #362, Slice 1). This
module owns everything about turning a registered JARVIS-CD repository into
the agent-visible package contract: inventory discovery, the bounded
``package_search`` page (with its opaque, revision-bound cursor), and one
package's full description (settings + versioned deployment contract).

``_discover_package_inventory`` needs the process-local JARVIS manager
singleton, which lives in ``server.py``. It imports ``get_manager`` lazily
(inside the function body, not at module load time) for two reasons: it
breaks what would otherwise be an import cycle (``server`` imports this
module's discovery/search functions; this module would need ``server``'s
manager back), and it re-resolves ``jarvis_mcp.server.get_manager`` fresh on
every call, so ``unittest.mock.patch("jarvis_mcp.server.get_manager", ...)``
in tests keeps working exactly as it did when this function lived in
``server.py``.
"""

from __future__ import annotations

import base64
import binascii
import hashlib
import json
import re
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from fastmcp.exceptions import ToolError
from pydantic import BaseModel, ValidationError

from .models.packages import (
    PACKAGE_DEPLOYMENT_SCHEMA,
    PACKAGE_DESCRIPTION_SCHEMA,
    JarvisConfigurationInputBindingDocument,
    JarvisPackageDeploymentDocument,
    _PackageAgentMetadata,
    _PackageInventoryEntry,
)

PACKAGE_SEARCH_SCHEMA = "jarvis.package-search.v1"
PACKAGE_SEARCH_CURSOR_SCHEMA = "clio-kit.jarvis-package-search-cursor.v1"
PACKAGE_SEARCH_DEFAULT_PAGE_SIZE = 10
PACKAGE_SEARCH_MAX_PAGE_SIZE = 25
PACKAGE_SEARCH_MAX_RESULT_BYTES = 64 * 1024
PACKAGE_SEARCH_MAX_CURSOR_LENGTH = 1024
_PACKAGE_SEARCH_CURSOR_TEXT = re.compile(r"^[A-Za-z0-9_-]+$")
_PACKAGE_SEARCH_SHA256 = re.compile(r"^[0-9a-f]{64}$")


def _discover_packages() -> list[dict[str, Any]]:
    """Return the legacy exhaustive package descriptions with full settings."""

    return [
        _package_description_from_inventory(entry)
        for entry in _discover_package_inventory()
    ]


def _discover_package_inventory() -> list[_PackageInventoryEntry]:
    """Discover lightweight package identities without importing package classes."""

    from .server import get_manager

    packages: list[_PackageInventoryEntry] = []
    seen: set[str] = set()
    try:
        manager = get_manager()
        repos = [Path(str(repo)) for repo in manager.list_repos()]
    except Exception:
        repos = []
    for repo in repos:
        if not repo.exists():
            continue
        package_files = sorted(
            (*repo.rglob("pkg.py"), *repo.rglob("package.py")),
            key=lambda path: (path.parent.as_posix(), path.name != "pkg.py"),
        )
        for pkg_file in package_files:
            package = _package_inventory_entry(repo, pkg_file)
            name = package.name
            if not name or name in seen:
                continue
            seen.add(name)
            packages.append(package)
    return sorted(packages, key=lambda package: (package.name.casefold(), package.name))


def _find_package_description(package_name: str) -> dict[str, Any] | None:
    """Resolve one exact canonical or short name and load only its settings."""

    normalized = package_name.strip().casefold()
    inventory = _discover_package_inventory()
    canonical = next(
        (package for package in inventory if package.name.casefold() == normalized),
        None,
    )
    if canonical is not None:
        return _package_description_from_inventory(canonical)

    short_matches = [
        package for package in inventory if package.short_name.casefold() == normalized
    ]
    if len(short_matches) == 1:
        return _package_description_from_inventory(short_matches[0])
    if len(short_matches) > 1:
        candidates = ", ".join(package.name for package in short_matches)
        raise ToolError(
            f"package short name is ambiguous: {package_name}; use one of: {candidates}"
        )
    return None


def _package_from_pkg_file(repo: Path, pkg_file: Path) -> dict[str, Any]:
    """Build one full package description from a repository source file."""

    return _package_description_from_inventory(_package_inventory_entry(repo, pkg_file))


def _package_inventory_entry(repo: Path, pkg_file: Path) -> _PackageInventoryEntry:
    """Build one lightweight package inventory entry from its source location."""

    relative = pkg_file.relative_to(repo)
    parts = list(relative.parts[:-1])
    short_name = parts[-1] if parts else repo.name
    dotted = ".".join(parts) if parts else short_name
    description = _first_docstring_or_comment(pkg_file)
    repository = parts[0] if parts else repo.name
    return _PackageInventoryEntry(
        name=dotted,
        short_name=short_name,
        repository=repository,
        description=description,
        repo=repo,
        package_file=pkg_file,
    )


def _package_description_from_inventory(
    entry: _PackageInventoryEntry,
) -> dict[str, Any]:
    """Load one selected package's path-free agent contract."""

    metadata = _package_agent_metadata(entry.name)
    package: dict[str, Any] = {
        "schema_version": PACKAGE_DESCRIPTION_SCHEMA,
        "name": entry.name,
        "short_name": entry.short_name,
        "description": entry.description,
        "deployment": metadata.deployment,
    }
    if metadata.settings is not None:
        package["settings"] = metadata.settings
    return package


def _search_packages(
    *,
    query: str,
    page_size: int = PACKAGE_SEARCH_DEFAULT_PAGE_SIZE,
    cursor: str | None = None,
) -> dict[str, Any]:
    """Return a bounded, summary-only page from the registered package inventory."""

    normalized_query = " ".join(query.split())
    if not normalized_query:
        raise ToolError("package_search query must not be blank")
    if (
        isinstance(page_size, bool)
        or not isinstance(page_size, int)
        or not 1 <= page_size <= PACKAGE_SEARCH_MAX_PAGE_SIZE
    ):
        raise ToolError(
            "package_search page_size must be between 1 and "
            f"{PACKAGE_SEARCH_MAX_PAGE_SIZE}"
        )

    inventory = _discover_package_inventory()
    # The declared configuration contract is part of what ranks and pages this
    # search, so it is also part of the revision the cursor is bound to: a menu
    # that changes between pages must invalidate the cursor exactly as a
    # changed docstring already does.
    configuration_texts = {
        package.name: _package_configuration_search_text(package.name)
        for package in inventory
    }
    inventory_revision = _package_inventory_revision(inventory, configuration_texts)
    query_sha256 = hashlib.sha256(
        normalized_query.casefold().encode("utf-8")
    ).hexdigest()
    ranked = sorted(
        (
            (rank, package)
            for package in inventory
            if (
                rank := _package_search_rank(
                    package,
                    normalized_query,
                    configuration_texts.get(package.name, ""),
                )
            )
            is not None
        ),
        key=lambda item: (item[0], item[1].name.casefold(), item[1].name),
    )
    matches = [package for _, package in ranked]

    start = 0
    if cursor is not None:
        decoded = _decode_package_search_cursor(cursor)
        if decoded["query_sha256"] != query_sha256:
            raise ToolError("package_search cursor does not match the requested query")
        if decoded["inventory_revision"] != inventory_revision:
            raise ToolError(
                "package_search cursor is stale because the package inventory changed"
            )
        anchor = decoded["after_package_name"]
        try:
            start = next(
                index + 1
                for index, package in enumerate(matches)
                if package.name == anchor
            )
        except StopIteration as exc:
            raise ToolError(
                "package_search cursor is stale because its package anchor disappeared"
            ) from exc

    page = [package.summary() for package in matches[start : start + page_size]]
    while True:
        has_more = start + len(page) < len(matches)
        next_cursor = None
        if has_more and page:
            next_cursor = _encode_package_search_cursor(
                after_package_name=str(page[-1]["name"]),
                query_sha256=query_sha256,
                inventory_revision=inventory_revision,
            )
        result: dict[str, Any] = {
            "schema_version": PACKAGE_SEARCH_SCHEMA,
            "target": "package_search",
            "query": normalized_query,
            "inventory_revision": inventory_revision,
            "packages": page,
            "total_matches": len(matches),
            "returned_count": len(page),
            "next_cursor": next_cursor,
        }
        if len(_package_search_json_bytes(result)) <= PACKAGE_SEARCH_MAX_RESULT_BYTES:
            return result
        if len(page) <= 1:
            raise ToolError(
                "one package_search result exceeded the response byte limit"
            )
        page.pop()


def _package_configuration_search_text(package_name: str) -> str:
    """Return one package's declared agent-visible configuration as search text.

    Discovery ranks over what a package DECLARES, not only over the module
    docstring that ``_first_docstring_or_comment`` scrapes. A caller looking
    for a package that accepts a *staged local input* has no other way to find
    one: the bounded search summary carries identity only, and a setting's
    ``input_binding`` -- the single authoritative staging signal -- lives in
    the package's configure menu, which search never consulted. Every term
    here is package-declared (setting names, setting prose, and the binding's
    own ``kind``/``structure`` vocabulary); nothing about specific packages is
    encoded in this function.

    Loading is best-effort by design and mirrors
    :func:`_package_agent_metadata`'s existing treatment of an unloadable
    menu: a package that cannot be imported contributes no configuration text
    and stays rankable by identity exactly as before, so one broken package in
    a registered repository can never fail a whole search.
    """

    try:
        from jarvis_cd.core.pkg import Pkg  # type: ignore[import-untyped]

        pkg = Pkg.load_standalone(package_name)
        settings = [
            _setting_from_menu_item(item)
            for item in pkg.configure_menu()
            if _setting_is_agent_visible(item)
        ]
    except Exception:
        return ""

    terms: list[str] = []
    for setting in settings:
        for field in ("name", "description"):
            value = setting.get(field)
            if isinstance(value, str) and value:
                terms.append(value)
        binding = setting.get("input_binding")
        if isinstance(binding, dict):
            terms.append("input_binding")
            for field in ("kind", "structure"):
                value = binding.get(field)
                if isinstance(value, str) and value:
                    terms.append(value)
    return " ".join(terms)


def _package_search_rank(
    package: _PackageInventoryEntry,
    query: str,
    configuration_text: str = "",
) -> int | None:
    """Return a deterministic relevance rank, or ``None`` when no field matches.

    Ranks 0-4 are identity and docstring matches and are unchanged. Ranks 5
    and 6 are the package's own declared configuration contract, which ranks
    below every identity match so an exact name never loses to a setting that
    merely mentions the query.
    """

    folded_query = query.casefold()
    folded_name = package.name.casefold()
    folded_short_name = package.short_name.casefold()
    if folded_query in {folded_name, folded_short_name}:
        return 0
    if folded_name.startswith(folded_query) or folded_short_name.startswith(
        folded_query
    ):
        return 1
    if folded_query in folded_name or folded_query in folded_short_name:
        return 2
    folded_description = (package.description or "").casefold()
    if folded_query in folded_description:
        return 3

    normalized_query = _package_search_terms(folded_query)
    if not normalized_query:
        return None
    identity_terms = _package_search_terms(
        " ".join(
            (
                package.name,
                package.short_name,
                package.description or "",
            )
        ).casefold()
    )
    if all(term in identity_terms for term in normalized_query):
        return 4

    folded_configuration = configuration_text.casefold()
    if folded_configuration and folded_query in folded_configuration:
        return 5
    searchable = identity_terms + _package_search_terms(folded_configuration)
    if all(term in searchable for term in normalized_query):
        return 6
    return None


def _package_search_terms(value: str) -> list[str]:
    """Tokenize package names and prose without locale-dependent behavior."""

    return [term for term in re.split(r"[^a-z0-9]+", value) if term]


def _package_inventory_revision(
    inventory: list[_PackageInventoryEntry],
    configuration_texts: Mapping[str, str] | None = None,
) -> str:
    """Hash the full inventory used to rank and page package search."""

    texts = configuration_texts or {}
    hasher = hashlib.sha256()
    hasher.update(b"clio-kit.jarvis-package-inventory.v1\0")
    for package in inventory:
        encoded = _package_search_json_bytes(
            {
                "name": package.name,
                "short_name": package.short_name,
                "repository": package.repository,
                "description": package.description,
                "configuration": texts.get(package.name, ""),
            }
        )
        hasher.update(len(encoded).to_bytes(8, "big"))
        hasher.update(encoded)
    return hasher.hexdigest()


def _encode_package_search_cursor(
    *,
    after_package_name: str,
    query_sha256: str,
    inventory_revision: str,
) -> str:
    """Encode an opaque cursor bound to one query and inventory revision."""

    payload = _package_search_json_bytes(
        {
            "schema_version": PACKAGE_SEARCH_CURSOR_SCHEMA,
            "after_package_name": after_package_name,
            "query_sha256": query_sha256,
            "inventory_revision": inventory_revision,
        }
    )
    cursor = base64.urlsafe_b64encode(payload).decode("ascii").rstrip("=")
    if len(cursor) > PACKAGE_SEARCH_MAX_CURSOR_LENGTH:
        raise ToolError("package_search cursor exceeded its byte limit")
    return cursor


def _decode_package_search_cursor(cursor: str) -> dict[str, str]:
    """Decode and strictly validate one package-search cursor."""

    if (
        not cursor
        or len(cursor) > PACKAGE_SEARCH_MAX_CURSOR_LENGTH
        or _PACKAGE_SEARCH_CURSOR_TEXT.fullmatch(cursor) is None
    ):
        raise ToolError("package_search cursor is invalid")
    padding = "=" * (-len(cursor) % 4)
    try:
        payload = base64.b64decode(
            cursor + padding,
            altchars=b"-_",
            validate=True,
        )
        if len(payload) > PACKAGE_SEARCH_MAX_CURSOR_LENGTH:
            raise ToolError("package_search cursor exceeded its byte limit")
        value = json.loads(
            payload.decode("utf-8"),
            object_pairs_hook=_reject_package_search_duplicate_keys,
        )
    except ToolError:
        raise
    except (
        binascii.Error,
        UnicodeDecodeError,
        json.JSONDecodeError,
        ValueError,
    ) as exc:
        raise ToolError("package_search cursor is invalid") from exc
    expected_fields = {
        "schema_version",
        "after_package_name",
        "query_sha256",
        "inventory_revision",
    }
    if not isinstance(value, dict) or set(value) != expected_fields:
        raise ToolError("package_search cursor schema is invalid")
    if value.get("schema_version") != PACKAGE_SEARCH_CURSOR_SCHEMA:
        raise ToolError("package_search cursor schema is unsupported")
    after_package_name = value.get("after_package_name")
    query_sha256 = value.get("query_sha256")
    inventory_revision = value.get("inventory_revision")
    if (
        not isinstance(after_package_name, str)
        or not after_package_name
        or not isinstance(query_sha256, str)
        or _PACKAGE_SEARCH_SHA256.fullmatch(query_sha256) is None
        or not isinstance(inventory_revision, str)
        or _PACKAGE_SEARCH_SHA256.fullmatch(inventory_revision) is None
    ):
        raise ToolError("package_search cursor fields are invalid")
    return {
        "after_package_name": after_package_name,
        "query_sha256": query_sha256,
        "inventory_revision": inventory_revision,
    }


def _package_search_json_bytes(value: object) -> bytes:
    """Serialize bounded search state using a deterministic UTF-8 encoding."""

    return json.dumps(
        value,
        allow_nan=False,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")


def _reject_package_search_duplicate_keys(
    pairs: list[tuple[str, Any]],
) -> dict[str, Any]:
    """Reject ambiguous JSON objects inside opaque package-search cursors."""

    value: dict[str, Any] = {}
    for key, item in pairs:
        if key in value:
            raise ValueError(f"duplicate package_search cursor key: {key}")
        value[key] = item
    return value


def _first_docstring_or_comment(path: Path) -> str | None:
    try:
        lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        return None
    in_docstring = False
    docstring_quote: str | None = None
    collected: list[str] = []
    for raw_line in lines[:80]:
        line = raw_line.strip()
        if not line:
            continue
        if line.startswith("#"):
            comment = line.lstrip("#").strip()
            if comment:
                return comment
            continue
        if in_docstring and docstring_quote is not None:
            if line.endswith(docstring_quote):
                line = line[: -len(docstring_quote)]
                if line:
                    collected.append(line.strip())
                return " ".join(collected).strip() or None
            collected.append(line)
            continue
        if line.startswith(('"""', "'''")):
            docstring_quote = line[:3]
            remainder = line[3:]
            if remainder.endswith(docstring_quote):
                remainder = remainder[:-3]
                return remainder.strip() or None
            in_docstring = True
            if remainder:
                collected.append(remainder.strip())
            continue
        return None
    return " ".join(collected).strip() or None


def _step_snapshot(
    pipeline_snapshot: dict[str, Any], step_id: str
) -> dict[str, Any] | None:
    for package in pipeline_snapshot.get("packages", []):
        if not isinstance(package, dict):
            continue
        identifiers = {
            str(package.get("pkg_id", "")),
            str(package.get("global_id", "")),
        }
        if step_id in identifiers:
            return package
    return None


def _package_agent_metadata(package_name: str) -> _PackageAgentMetadata:
    """Load package-owned configuration and deployment metadata once.

    Older JARVIS packages do not implement ``describe_deployment`` and are
    represented with ``deployment=None``. If a package advertises the method,
    however, its document must match the versioned, path-free contract instead
    of being silently downgraded to legacy behavior.
    """

    try:
        from jarvis_cd.core.pkg import Pkg  # type: ignore[import-untyped]

        pkg = Pkg.load_standalone(package_name)
    except Exception:
        return _PackageAgentMetadata(settings=None, deployment=None)

    try:
        menu = pkg.configure_menu()
        settings = [
            _setting_from_menu_item(item)
            for item in menu
            if _setting_is_agent_visible(item)
        ]
    except Exception:
        settings = None

    describe_deployment = getattr(pkg, "describe_deployment", None)
    if not callable(describe_deployment):
        return _PackageAgentMetadata(settings=settings, deployment=None)
    try:
        raw_deployment = describe_deployment()
    except Exception:
        raise ToolError(
            f"package '{package_name}' failed to describe its deployment contract"
        ) from None
    if raw_deployment is None:
        return _PackageAgentMetadata(settings=settings, deployment=None)
    if isinstance(raw_deployment, BaseModel):
        raw_deployment = raw_deployment.model_dump(mode="json")
    if not isinstance(raw_deployment, dict):
        raise ToolError(
            f"package '{package_name}' returned an invalid deployment contract"
        )
    try:
        deployment = json.loads(
            json.dumps(
                raw_deployment,
                allow_nan=False,
                ensure_ascii=False,
                separators=(",", ":"),
                sort_keys=True,
            )
        )
    except (TypeError, ValueError):
        raise ToolError(
            f"package '{package_name}' returned a non-JSON deployment contract"
        ) from None
    try:
        validated = JarvisPackageDeploymentDocument.model_validate(deployment)
    except ValidationError:
        raise ToolError(
            f"package '{package_name}' returned an invalid deployment contract"
        ) from None
    if (
        validated.schema_version != PACKAGE_DEPLOYMENT_SCHEMA
        or validated.package != package_name
    ):
        raise ToolError(
            f"package '{package_name}' returned an invalid deployment contract"
        )
    return _PackageAgentMetadata(settings=settings, deployment=deployment)


def _setting_from_menu_item(item: dict[str, Any]) -> dict[str, Any]:
    setting: dict[str, Any] = {
        "name": item.get("name"),
        "description": item.get("msg"),
        "required": bool(item.get("required", False)),
        "nullable": _setting_accepts_null(item),
    }
    kind = item.get("type")
    if isinstance(kind, type):
        setting["type"] = kind.__name__
    elif kind is not None:
        setting["type"] = str(kind)
    if "default" in item:
        setting["default"] = item["default"]
    choices = item.get("choices")
    if isinstance(choices, (list, tuple)):
        setting["choices"] = list(choices)
    aliases = item.get("aliases")
    if isinstance(aliases, (list, tuple)) and all(
        isinstance(alias, str) and alias for alias in aliases
    ):
        setting["aliases"] = list(aliases)
    if "input_binding" in item:
        try:
            input_binding = JarvisConfigurationInputBindingDocument.model_validate(
                item["input_binding"]
            )
        except ValidationError as error:
            raise ValueError("invalid package configuration input binding") from error
        setting["input_binding"] = input_binding.model_dump(mode="json")
    return {
        key: value
        for key, value in setting.items()
        if value is not None or key == "default"
    }


def _setting_is_agent_visible(item: dict[str, Any]) -> bool:
    """Return whether package metadata exposes a setting to user agents."""

    return item.get("agent_visible", True) is not False


def _setting_accepts_null(item: dict[str, Any]) -> bool:
    """Return whether the structured add-step path accepts explicit null."""

    return "default" in item and item["default"] is None
