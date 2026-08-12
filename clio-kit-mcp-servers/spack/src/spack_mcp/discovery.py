"""Recipe discovery across registered Spack repos: search, info, availability.

New owner module (clio-kit#370) rather than growth of the ratcheted
``backend.py``. The curated spack surface could previously only answer "is X
*installed*" (``spack_locate``/``spack_find``); this module answers "does a
*recipe* for X exist at all, in which repo, with which versions/variants" --
the missing half of the provisioning loop (typed not-installed -> lookup ->
HITL-approved install).

Critical implementation constraint (learned live against the ares spack
clone, 2026-08-11): ``spack list`` is broken on that deployment -- it dies
with "cannot unpack non-iterable NoneType object", the same internal bug as
its ``spack load``. Recipe discovery here never shells out to ``spack list``.
Instead it uses ``spack repo list`` (confirmed working) to enumerate
registered repos, then walks each repo's ``packages/`` directory directly: a
recipe is a subdirectory containing a ``package.py``. ``package.py`` files
are only ever statically parsed with :mod:`ast` -- never imported or
executed -- so an untrusted or malformed recipe cannot run code in this
process.
"""

from __future__ import annotations

import ast
import difflib
import re
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Final, Literal

from pydantic import BaseModel, ConfigDict, Field

from spack_mcp import backend
from spack_mcp.backend import (
    SPACK_RESULT_SCHEMA,
    SpackBackendError,
    SpackPackage,
    find_installed,
)

_MAX_SEARCH_MATCHES: Final = 25
_MAX_PACKAGE_ENTRIES_PER_REPO: Final = 20_000
_FUZZY_CUTOFF: Final = 0.6
_SPEC_NAME_BOUNDARY: Final = re.compile(r"[\s@%+~^/]")
_INFO_SECTION_HEADERS: Final = {
    "description",
    "homepage",
    "safe versions",
    "preferred version",
    "deprecated versions",
    "variants",
}
_VERSION_TOKEN: Final = re.compile(r"^[0-9][A-Za-z0-9_.\-]*")
_VARIANT_NAME: Final = re.compile(r"^([A-Za-z0-9_+.-]+)\s*\[")


class SpackPackageMatch(BaseModel):
    """One catalog recipe matched by a search query."""

    model_config = ConfigDict(extra="forbid")

    name: str
    repos: list[str] = Field(description="Registered repo namespaces that declare this recipe.")
    installed: bool
    installed_packages: list[SpackPackage] = Field(default_factory=list)


class SpackSearchResult(BaseModel):
    """Recipe availability across every registered repo, not just installs."""

    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["spack.mcp.result.v1"] = SPACK_RESULT_SCHEMA
    operation: Literal["search"] = "search"
    query: str
    repos_searched: list[str]
    matches: list[SpackPackageMatch]
    count: int


class SpackInfoResult(BaseModel):
    """Recipe detail: versions, variants, description, and how it was read."""

    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["spack.mcp.result.v1"] = SPACK_RESULT_SCHEMA
    operation: Literal["info"] = "info"
    package: str
    repo: str | None = None
    description: str | None = None
    versions: list[str] = Field(default_factory=list)
    variants: list[str] = Field(default_factory=list)
    source: Literal["spack_info", "package_py"]
    degraded: bool
    degraded_reason: str | None = None


@dataclass(frozen=True)
class SpackRepoRef:
    """One registered Spack package repository."""

    name: str
    path: Path


@dataclass(frozen=True)
class RecipeAvailability:
    """Whether a recipe exists in any registered repo, and where."""

    available: bool
    repo: str | None
    repos_searched: list[str]
    message: str


def base_package_name(spec: str) -> str:
    """Return the leading package-name token of a Spack spec string.

    ``"hdf5@1.14.3 +mpi"`` -> ``"hdf5"``. Best-effort: used only to look a
    recipe up in the catalog, never to concretize or execute anything.
    """
    match = _SPEC_NAME_BOUNDARY.search(spec)
    return spec[: match.start()] if match else spec


def list_registered_repos() -> list[SpackRepoRef]:
    """Enumerate registered package repos via ``spack repo list``.

    Deliberately not ``spack list`` (broken on the ares clone, see module
    docstring); ``spack repo list`` was confirmed working there.
    """
    result = backend._run_spack(["repo", "list"], operation="search", timeout_seconds=60)
    repos = _parse_repo_list(result.stdout)
    if not repos:
        raise SpackBackendError(
            "no_repos_registered",
            "spack repo list returned no registered package repositories",
            operation="search",
        )
    return repos


def _parse_repo_list(output: str) -> list[SpackRepoRef]:
    """Parse ``spack repo list``'s tabular ``namespace  path`` output.

    Tolerant of the ``==> N package repositories`` banner line, a
    ``Namespace``/``Path`` header, and a dashed separator row -- none of
    which are portable across Spack versions, so they are recognized
    heuristically rather than assumed to be absent or present.
    """
    repos: list[SpackRepoRef] = []
    for line in output.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("==>"):
            continue
        if stripped.lower().startswith("namespace"):
            continue
        if set(stripped) <= {"-", " ", "="}:
            continue
        parts = stripped.split(None, 1)
        if len(parts) != 2:
            continue
        name, path = parts
        repos.append(SpackRepoRef(name=name, path=Path(path)))
    return repos


def _repo_packages(repo: SpackRepoRef) -> dict[str, Path]:
    """Return ``{package_name: package.py path}`` for one repo's recipes."""
    packages_dir = repo.path / "packages"
    if not packages_dir.is_dir():
        return {}
    entries: dict[str, Path] = {}
    count = 0
    for entry in packages_dir.iterdir():
        count += 1
        if count > _MAX_PACKAGE_ENTRIES_PER_REPO:
            raise SpackBackendError(
                "response_too_large",
                f"repo {repo.name!r} exposes more than "
                f"{_MAX_PACKAGE_ENTRIES_PER_REPO} package directories",
                operation="search",
            )
        if not entry.is_dir():
            continue
        package_py = entry / "package.py"
        if package_py.is_file():
            entries[entry.name] = package_py
    return entries


def _catalog(repos: list[SpackRepoRef]) -> dict[str, list[SpackRepoRef]]:
    """Return ``{package_name: [repos declaring it]}`` across every repo."""
    catalog: dict[str, list[SpackRepoRef]] = defaultdict(list)
    for repo in repos:
        for name in _repo_packages(repo):
            catalog[name].append(repo)
    return catalog


def _fuzzy_match(query: str, candidates: list[str]) -> list[str]:
    """Rank candidate recipe names by exact, prefix, substring, then typo distance."""
    lowered_query = query.lower()
    exact: list[str] = []
    prefix: list[str] = []
    substring: list[str] = []
    for name in candidates:
        lowered = name.lower()
        if lowered == lowered_query:
            exact.append(name)
        elif lowered.startswith(lowered_query):
            prefix.append(name)
        elif lowered_query in lowered:
            substring.append(name)
    ranked = sorted(exact) + sorted(prefix) + sorted(substring)
    if len(ranked) < _MAX_SEARCH_MATCHES:
        lowered_to_name = {name.lower(): name for name in candidates}
        seen = {name.lower() for name in ranked}
        close = difflib.get_close_matches(
            lowered_query,
            lowered_to_name.keys(),
            n=_MAX_SEARCH_MATCHES,
            cutoff=_FUZZY_CUTOFF,
        )
        for lowered_name in close:
            if lowered_name not in seen:
                ranked.append(lowered_to_name[lowered_name])
                seen.add(lowered_name)
    return ranked[:_MAX_SEARCH_MATCHES]


def search_packages(query: str) -> SpackSearchResult:
    """Search recipe availability across every registered repo.

    Composes with the existing locate/find mechanism: one call answers
    "does a recipe exist", "in which repo", and "is it already installed".
    """
    normalized_query = query.strip()
    if not normalized_query:
        raise SpackBackendError("invalid_query", "query must not be empty", operation="search")
    repos = list_registered_repos()
    catalog = _catalog(repos)
    matched_names = _fuzzy_match(normalized_query, list(catalog))
    installed_by_name: dict[str, list[SpackPackage]] = defaultdict(list)
    for package in find_installed().packages:
        installed_by_name[package.name].append(package)
    matches = [
        SpackPackageMatch(
            name=name,
            repos=sorted(repo.name for repo in catalog[name]),
            installed=name in installed_by_name,
            installed_packages=installed_by_name.get(name, []),
        )
        for name in matched_names
    ]
    return SpackSearchResult(
        query=normalized_query,
        repos_searched=sorted(repo.name for repo in repos),
        matches=matches,
        count=len(matches),
    )


def classify_recipe_availability(base_name: str) -> RecipeAvailability:
    """Answer "does a recipe exist for this package, and where" for error text.

    Never raises: repo-discovery failure is reported as an honest
    ``message`` (no silent fallback) rather than masking the caller's
    original error or hiding the reason a recipe couldn't be confirmed.
    """
    try:
        repos = list_registered_repos()
    except SpackBackendError as exc:
        return RecipeAvailability(
            available=False,
            repo=None,
            repos_searched=[],
            message=(
                "could not determine recipe availability: repo discovery failed "
                f"({exc.code}: {exc.message})"
            ),
        )
    for repo in repos:
        if base_name in _repo_packages(repo):
            return RecipeAvailability(
                available=True,
                repo=repo.name,
                repos_searched=sorted(repo.name for repo in repos),
                message=f"recipe available in repo {repo.name!r} via spack_install",
            )
    repo_names = sorted(repo.name for repo in repos)
    return RecipeAvailability(
        available=False,
        repo=None,
        repos_searched=repo_names,
        message=f"no recipe in any registered repo (repos: {', '.join(repo_names)})",
    )


def enrich_not_installed(error: SpackBackendError, spec: str) -> SpackBackendError:
    """Attach recipe-availability context to a locate ``not_installed`` error."""
    if error.code != "not_installed":
        return error
    availability = classify_recipe_availability(base_package_name(spec))
    return SpackBackendError(
        error.code,
        error.message,
        operation=error.operation,
        returncode=error.returncode,
        detail=availability.message,
    )


def describe_package(package: str) -> SpackInfoResult:
    """Describe one recipe's versions/variants/description.

    Probes ``spack info`` first; on any failure of that subcommand (this
    deployment's spack clone has other broken subcommands, so this probe is
    defensive rather than assumed to work), falls back to statically parsing
    the recipe's ``package.py`` and says so in ``degraded``/``degraded_reason``
    -- never silently.
    """
    name = backend._validated_spec(package)
    base_name = base_package_name(name)
    probed = _probe_spack_info(base_name)
    if probed is not None:
        return probed
    return _describe_from_package_py(base_name)


def _probe_spack_info(name: str) -> SpackInfoResult | None:
    try:
        result = backend._run_spack(["info", name], operation="info", timeout_seconds=60)
    except SpackBackendError:
        return None
    parsed = _parse_spack_info_output(result.stdout)
    if parsed is None:
        return None
    description, versions, variants = parsed
    return SpackInfoResult(
        package=name,
        description=description,
        versions=versions,
        variants=variants,
        source="spack_info",
        degraded=False,
    )


def _parse_spack_info_output(stdout: str) -> tuple[str | None, list[str], list[str]] | None:
    sections: dict[str, list[str]] = defaultdict(list)
    current: str | None = None
    for raw_line in stdout.splitlines():
        stripped = raw_line.strip()
        lowered = stripped.rstrip(":").lower()
        if lowered in _INFO_SECTION_HEADERS:
            current = lowered
            continue
        if not stripped or current is None:
            continue
        sections[current].append(stripped)
    description = " ".join(sections.get("description", [])) or None
    versions = _extract_versions(sections)
    variants = _extract_variants(sections.get("variants", []))
    if description is None and not versions and not variants:
        return None
    return description, versions, variants


def _extract_versions(sections: dict[str, list[str]]) -> list[str]:
    tokens: list[str] = []
    for key in ("preferred version", "safe versions", "deprecated versions"):
        for line in sections.get(key, []):
            match = _VERSION_TOKEN.match(line)
            if match and match.group(0) not in tokens:
                tokens.append(match.group(0))
    return tokens


def _extract_variants(lines: list[str]) -> list[str]:
    variants: list[str] = []
    for line in lines:
        if line.lower().startswith("name ") or set(line) <= {"=", " ", "-"}:
            continue
        match = _VARIANT_NAME.match(line)
        if match and match.group(1) not in variants:
            variants.append(match.group(1))
    return variants


def _describe_from_package_py(name: str) -> SpackInfoResult:
    repos = list_registered_repos()
    for repo in repos:
        package_py = _repo_packages(repo).get(name)
        if package_py is None:
            continue
        description, versions, variants = _parse_package_py(package_py)
        return SpackInfoResult(
            package=name,
            repo=repo.name,
            description=description,
            versions=versions,
            variants=variants,
            source="package_py",
            degraded=True,
            degraded_reason=(
                "spack info was unavailable or failed on this deployment; parsed "
                f"{package_py} directly (best-effort description/version/variant "
                "extraction, not spack's own concretized view)"
            ),
        )
    raise SpackBackendError(
        "recipe_not_found",
        f"no recipe named {name!r} found in any registered repo",
        operation="info",
        detail=f"repos searched: {', '.join(sorted(repo.name for repo in repos))}",
    )


def _parse_package_py(path: Path) -> tuple[str | None, list[str], list[str]]:
    """Statically parse a recipe's description/versions/variants via AST.

    Never imports or executes ``package.py`` -- only ``ast.parse`` over its
    source text, so an untrusted or malformed recipe cannot run code here.
    """
    try:
        source = path.read_text(encoding="utf-8", errors="replace")
        tree = ast.parse(source, filename=str(path))
    except (OSError, SyntaxError) as exc:
        raise SpackBackendError(
            "package_py_unreadable",
            f"could not parse {path}",
            operation="info",
            detail=str(exc),
        ) from exc
    description = ast.get_docstring(tree)
    if description is not None:
        description = " ".join(description.split())
    versions: list[str] = []
    variants: list[str] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call) or not node.args:
            continue
        func_name = _call_name(node.func)
        value = _literal_str(node.args[0])
        if value is None:
            continue
        if func_name == "version" and value not in versions:
            versions.append(value)
        elif func_name == "variant" and value not in variants:
            variants.append(value)
    return description, versions, variants


def _call_name(func: ast.expr) -> str | None:
    if isinstance(func, ast.Name):
        return func.id
    if isinstance(func, ast.Attribute):
        return func.attr
    return None


def _literal_str(node: ast.expr) -> str | None:
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    return None
