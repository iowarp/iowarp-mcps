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
registered repos, then walks each repo's package directory directly: a
recipe is a subdirectory containing a ``package.py``. ``package.py`` files
are only ever statically parsed with :mod:`ast` -- never imported or
executed -- so an untrusted or malformed recipe cannot run code in this
process.

Every repo walk is honest about failure (clio-kit#370 fix round, review
finding R1/R2): a repo directory that cannot be resolved or enumerated
(missing path, permission denied, any other OSError) is reported as
*unreadable*, never silently folded into "this repo declares zero
recipes" -- that distinction is what keeps :func:`classify_recipe_availability`
from wrongly vetoing a ``spack_install`` spack itself might have served.
"""

from __future__ import annotations

import ast
import difflib
import re
from collections import defaultdict
from dataclasses import dataclass, field
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
_INFO_VERSION_HEADERS: Final = {"preferred version", "safe versions", "deprecated versions"}
_INFO_HEADER_LINE: Final = re.compile(r"^[A-Za-z][A-Za-z0-9 /]*:\s*(.*)$")
_VERSION_TOKEN: Final = re.compile(r"^[0-9][A-Za-z0-9_.\-]*")
_VARIANT_NAME: Final = re.compile(r"^([A-Za-z0-9_+.-]+)\s*\[")
_REPO_LIST_COLUMN_SPLIT: Final = re.compile(r"\s{2,}")
_REPO_YAML_SUBDIRECTORY: Final = re.compile(r"^\s*subdirectory\s*:\s*(.+?)\s*$", re.MULTILINE)


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
    repos_unreadable: list[str] = Field(
        default_factory=list,
        description=(
            "Registered repos whose package directory could not be scanned "
            "(missing path, permission denied, ...); recipes may exist there "
            "that this search could not see. Never treat an empty result as "
            "a confirmed absence when this list is non-empty."
        ),
    )
    matches: list[SpackPackageMatch]
    count: int
    total_matches: int = Field(
        description=(
            "Total ranked matches before the response cap; compare with "
            "count/truncated to tell '25 of 25' from '25 of 60'."
        )
    )
    truncated: bool = Field(
        default=False,
        description=f"True when total_matches exceeds the {_MAX_SEARCH_MATCHES}-result cap.",
    )
    installed_state_degraded: bool = Field(
        default=False,
        description=(
            "True when `spack find` failed while resolving install state; recipe "
            "availability above is still authoritative, but every match's "
            "installed/installed_packages defaults to not-installed rather than "
            "a confirmed answer."
        ),
    )
    installed_state_degraded_reason: str | None = None


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
    repos_unreadable: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class RepoScan:
    """Result of walking one registered repo's package directory.

    ``readable=False`` means this repo's catalog could not be confirmed --
    a missing path, a permission error, or any other ``OSError`` while
    enumerating it. Callers must never read ``packages == {}`` on its own as
    "this repo declares no recipes"; check ``readable`` first.
    """

    packages: dict[str, Path]
    readable: bool
    reason: str | None = None


@dataclass(frozen=True)
class _Catalog:
    """Recipe catalog across every registered repo, with unreadable repos named."""

    by_name: dict[str, list[SpackRepoRef]]
    unreadable: list[tuple[SpackRepoRef, str]]


@dataclass(frozen=True)
class _FuzzyMatchResult:
    """Ranked recipe-name matches, plus the true count before the response cap."""

    names: list[str]
    total: int


def base_package_name(spec: str) -> str:
    """Return the leading package-name token of a Spack spec string.

    ``"hdf5@1.14.3 +mpi"`` -> ``"hdf5"``. Best-effort: used only to look a
    recipe up in the catalog, never to concretize or execute anything.
    """
    match = _SPEC_NAME_BOUNDARY.search(spec)
    return spec[: match.start()] if match else spec


def _normalize_recipe_name(name: str) -> str:
    """Fold a recipe/spec name for matching: lowercase and '-' -> '_'.

    Spack's modern repo layout stores recipes under Python-module-safe
    directory names, where every ``-`` in a spec name becomes ``_``
    (``py-numpy`` -> ``packages/py_numpy``). Matching on this normalized form
    is what keeps :func:`search_packages` and
    :func:`classify_recipe_availability` from disagreeing about whether a
    hyphenated recipe name is available (clio-kit#370 fix round, R3).
    """
    return name.strip().lower().replace("-", "_")


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
    which are portable across Spack versions (or present at all: real
    ``spack repo list`` prints no banner/header when piped to a non-tty), so
    they are recognized heuristically rather than assumed to be absent or
    present. Columns are split on 2+ whitespace (spack's tabular alignment),
    falling back to a single-whitespace split for a plain two-token line;
    either way the *last* token is the path and the *first* is the name, so
    an unexpected middle column (a version/API marker) cannot be mistaken
    for the path (clio-kit#370 fix round, R2).
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
        parts = [part for part in _REPO_LIST_COLUMN_SPLIT.split(stripped) if part]
        if len(parts) < 2:
            parts = stripped.split(None, 1)
        if len(parts) < 2:
            continue
        name, path = parts[0], parts[-1]
        repos.append(SpackRepoRef(name=name, path=Path(path)))
    return repos


def _packages_subdirectory_name(repo: SpackRepoRef) -> str:
    """Return this repo's declared recipe subdirectory, defaulting to ``packages``.

    A real Spack repo may relocate its recipe directory away from the
    default ``packages/`` via ``repo.yaml``'s ``subdirectory:`` key
    (clio-kit#370 fix round, R3). Read as plain text for one scalar key --
    no YAML parser dependency, and ``repo.yaml`` is never executed or even
    fully parsed.
    """
    try:
        text = (repo.path / "repo.yaml").read_text(encoding="utf-8")
    except OSError:
        return "packages"
    match = _REPO_YAML_SUBDIRECTORY.search(text)
    if match is None:
        return "packages"
    candidate = match.group(1).strip().strip("'\"")
    return candidate or "packages"


def _scan_repo(repo: SpackRepoRef) -> RepoScan:
    """Walk one repo's recipe directory, distinguishing "empty" from "unreadable".

    Never raises for an unresolvable or unreadable repo (clio-kit#370 fix
    round, R1/R2): any ``OSError`` while resolving or walking the directory
    -- a registered path that no longer exists, a permission error, a
    transient filesystem failure -- is captured as ``readable=False`` with
    the cause in ``reason``, so exactly one repo among many can degrade
    without an untyped exception reaching the MCP layer and without the
    caller's catalog wrongly reporting "this repo declares nothing."
    :data:`SpackBackendError` (raised deliberately for the entry-count cap)
    is not caught here and propagates to the typed MCP error path as before.
    """
    packages_dir = repo.path / _packages_subdirectory_name(repo)
    try:
        if not packages_dir.is_dir():
            return RepoScan(
                packages={},
                readable=False,
                reason=f"recipe directory not found: {packages_dir}",
            )
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
        return RepoScan(packages=entries, readable=True)
    except OSError as exc:
        return RepoScan(packages={}, readable=False, reason=str(exc))


def _repo_packages(repo: SpackRepoRef) -> dict[str, Path]:
    """Return ``{package_name: package.py path}`` for one repo's recipes.

    Convenience wrapper over :func:`_scan_repo` for callers that only need
    the catalog. Callers that must distinguish "empty" from "unreadable"
    (search, classify, describe) use :func:`_scan_repo` directly.
    """
    return _scan_repo(repo).packages


def _catalog(repos: list[SpackRepoRef]) -> _Catalog:
    """Return ``{package_name: [repos declaring it]}`` across every repo.

    A repo that could not be scanned is reported in ``unreadable`` rather
    than silently contributing zero recipes (clio-kit#370 fix round, R2).
    """
    by_name: dict[str, list[SpackRepoRef]] = defaultdict(list)
    unreadable: list[tuple[SpackRepoRef, str]] = []
    for repo in repos:
        scan = _scan_repo(repo)
        if not scan.readable:
            unreadable.append((repo, scan.reason or "unknown reason"))
            continue
        for name in scan.packages:
            by_name[name].append(repo)
    return _Catalog(by_name=by_name, unreadable=unreadable)


def _fuzzy_match(query: str, candidates: list[str]) -> _FuzzyMatchResult:
    """Rank candidate recipe names by exact, prefix, substring, then typo distance.

    The exact tier also matches on the dash/underscore-normalized form
    (clio-kit#370 fix round, R3), so a query like ``py-numpy`` ranks a
    ``py_numpy`` repo directory as an exact hit rather than only surfacing
    it through the looser typo-distance fallback.
    """
    lowered_query = query.lower()
    normalized_query = _normalize_recipe_name(query)
    exact: list[str] = []
    prefix: list[str] = []
    substring: list[str] = []
    for name in candidates:
        lowered = name.lower()
        if lowered == lowered_query or _normalize_recipe_name(name) == normalized_query:
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
    return _FuzzyMatchResult(names=ranked[:_MAX_SEARCH_MATCHES], total=len(ranked))


def search_packages(query: str) -> SpackSearchResult:
    """Search recipe availability across every registered repo.

    Composes with the existing locate/find mechanism: one call answers
    "does a recipe exist", "in which repo", and "is it already installed".
    An unreadable repo degrades that one repo's contribution to the catalog
    (named in ``repos_unreadable``) rather than failing the whole search,
    and a failing ``spack find`` degrades only the installed-state half of
    the answer (``installed_state_degraded``) rather than the whole call
    (clio-kit#370 fix round, R2/S5).
    """
    normalized_query = query.strip()
    if not normalized_query:
        raise SpackBackendError("invalid_query", "query must not be empty", operation="search")
    repos = list_registered_repos()
    catalog = _catalog(repos)
    fuzzy = _fuzzy_match(normalized_query, list(catalog.by_name))
    try:
        found = find_installed()
        installed_degraded_reason: str | None = None
    except SpackBackendError as exc:
        found = backend.SpackFindResult(query=None, packages=[], count=0)
        installed_degraded_reason = f"{exc.code}: {exc.message}"
    installed_by_name: dict[str, list[SpackPackage]] = defaultdict(list)
    for package in found.packages:
        installed_by_name[package.name].append(package)
    matches = [
        SpackPackageMatch(
            name=name,
            repos=sorted(repo.name for repo in catalog.by_name[name]),
            installed=name in installed_by_name,
            installed_packages=installed_by_name.get(name, []),
        )
        for name in fuzzy.names
    ]
    unreadable_names = {repo.name for repo, _ in catalog.unreadable}
    return SpackSearchResult(
        query=normalized_query,
        repos_searched=sorted(repo.name for repo in repos if repo.name not in unreadable_names),
        repos_unreadable=sorted(f"{repo.name}: {reason}" for repo, reason in catalog.unreadable),
        matches=matches,
        count=len(matches),
        total_matches=fuzzy.total,
        truncated=fuzzy.total > len(matches),
        installed_state_degraded=installed_degraded_reason is not None,
        installed_state_degraded_reason=installed_degraded_reason,
    )


def classify_recipe_availability(base_name: str) -> RecipeAvailability:
    """Answer "does a recipe exist for this package, and where" for error text.

    Never raises: repo-discovery failure is reported as an honest
    ``message`` (no silent fallback) rather than masking the caller's
    original error or hiding the reason a recipe couldn't be confirmed.
    An unreadable repo is never folded into "no recipe in any registered
    repo" -- that claim requires every repo to have actually been read
    (clio-kit#370 fix round, R2); matching is normalized so a hyphenated
    query agrees with an underscored repo directory (R3).
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
    normalized_target = _normalize_recipe_name(base_name)
    unreadable: list[str] = []
    for repo in repos:
        scan = _scan_repo(repo)
        if not scan.readable:
            unreadable.append(f"{repo.name} ({scan.reason})")
            continue
        for candidate in scan.packages:
            if _normalize_recipe_name(candidate) == normalized_target:
                return RecipeAvailability(
                    available=True,
                    repo=repo.name,
                    repos_searched=sorted(r.name for r in repos),
                    message=f"recipe available in repo {repo.name!r} via spack_install",
                )
    repo_names = sorted(r.name for r in repos)
    if unreadable:
        return RecipeAvailability(
            available=False,
            repo=None,
            repos_searched=repo_names,
            repos_unreadable=sorted(unreadable),
            message=(
                "could not confirm recipe availability: repo(s) "
                f"{', '.join(sorted(unreadable))} could not be read; the "
                "remaining registered repos do not declare this recipe, but "
                "availability could not be fully determined"
            ),
        )
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
    -- never silently, and the reason names the actual probe failure when
    there was one (clio-kit#370 fix round, S2).
    """
    name = backend._validated_spec(package)
    base_name = base_package_name(name)
    probe_failure: SpackBackendError | None = None
    try:
        probed = _probe_spack_info(base_name)
    except SpackBackendError as exc:
        probed = None
        probe_failure = exc
    if probed is not None:
        return probed
    return _describe_from_package_py(base_name, probe_failure=probe_failure)


def _probe_spack_info(name: str) -> SpackInfoResult | None:
    """Run and parse ``spack info``; ``None`` means "ran but unparseable".

    A failure of the subcommand itself propagates as :class:`SpackBackendError`
    so the caller can carry the real cause into the package.py fallback's
    ``degraded_reason`` instead of a generic message (S2).
    """
    result = backend._run_spack(["info", name], operation="info", timeout_seconds=60)
    parsed = _parse_spack_info_output(result.stdout)
    if parsed is None:
        return None
    return SpackInfoResult(
        package=name,
        description=parsed.description,
        versions=parsed.versions,
        variants=parsed.variants,
        source="spack_info",
        degraded=not parsed.complete,
        degraded_reason=(
            None
            if parsed.complete
            else (
                "spack info output was missing one or more expected sections "
                "(description/versions/variants); the returned versions/variants "
                "may be incomplete, not a confirmed empty set"
            )
        ),
    )


@dataclass(frozen=True)
class _ParsedSpackInfo:
    """Parsed ``spack info`` fields, plus whether every expected section was seen."""

    description: str | None
    versions: list[str]
    variants: list[str]
    complete: bool


def _parse_spack_info_output(stdout: str) -> _ParsedSpackInfo | None:
    """Parse ``spack info`` output into description/versions/variants.

    Any header-shaped line (``Word...:``) ends the current section, whether
    or not it is one of the six tracked headers, and a blank line always
    ends it too -- previously only the six known headers reset the cursor,
    so an inline ``Homepage: <url>`` line (or any other single-line field)
    was silently absorbed into whatever tracked section preceded it, and an
    unrecognized block header (``Build Dependencies:``) let its body leak
    into that same section (clio-kit#370 fix round, S3).
    """
    sections: dict[str, list[str]] = defaultdict(list)
    current: str | None = None
    seen_headers: set[str] = set()
    for raw_line in stdout.splitlines():
        stripped = raw_line.strip()
        if not stripped:
            current = None
            continue
        header_match = _INFO_HEADER_LINE.match(stripped)
        if header_match is not None:
            label = stripped[: stripped.index(":")].strip().lower()
            inline_value = header_match.group(1).strip()
            if label in _INFO_SECTION_HEADERS and not inline_value:
                current = label
                seen_headers.add(label)
            else:
                current = None
            continue
        if current is None:
            continue
        sections[current].append(stripped)
    description = " ".join(sections.get("description", [])) or None
    versions = _extract_versions(sections)
    variants = _extract_variants(sections.get("variants", []))
    if description is None and not versions and not variants:
        return None
    complete = (
        "description" in seen_headers
        and bool(seen_headers & _INFO_VERSION_HEADERS)
        and "variants" in seen_headers
    )
    return _ParsedSpackInfo(
        description=description, versions=versions, variants=variants, complete=complete
    )


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


def _describe_from_package_py(
    name: str, *, probe_failure: SpackBackendError | None = None
) -> SpackInfoResult:
    repos = list_registered_repos()
    normalized_target = _normalize_recipe_name(name)
    unreadable: list[str] = []
    for repo in repos:
        scan = _scan_repo(repo)
        if not scan.readable:
            unreadable.append(f"{repo.name} ({scan.reason})")
            continue
        package_py = next(
            (
                path
                for candidate, path in scan.packages.items()
                if _normalize_recipe_name(candidate) == normalized_target
            ),
            None,
        )
        if package_py is None:
            continue
        description, versions, variants = _parse_package_py(package_py)
        cause = (
            f"{probe_failure.code}: {probe_failure.message}"
            if probe_failure is not None
            else "spack info output could not be parsed into a recognized format"
        )
        return SpackInfoResult(
            package=name,
            repo=repo.name,
            description=description,
            versions=versions,
            variants=variants,
            source="package_py",
            degraded=True,
            degraded_reason=(
                f"spack info was unavailable or failed on this deployment ({cause}); parsed "
                f"{package_py} directly (best-effort description/version/variant "
                "extraction, not spack's own concretized view)"
            ),
        )
    detail = f"repos searched: {', '.join(sorted(r.name for r in repos))}"
    if unreadable:
        detail += f"; repos unreadable: {', '.join(sorted(unreadable))}"
    raise SpackBackendError(
        "recipe_not_found",
        f"no recipe named {name!r} found in any registered repo",
        operation="info",
        detail=detail,
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
