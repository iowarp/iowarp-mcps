"""Tests for recipe discovery: search, info, and availability classification.

clio-kit#370 -- the curated spack surface previously could only answer "is X
installed"; these tests exercise the new "does a recipe exist at all, and
where" half of the provisioning loop. The mechanism under test never shells
out to the broken ``spack list``; it walks each registered repo's
``packages/`` directory directly, so most tests build a real fixture repo
tree under ``tmp_path`` rather than mocking a subprocess.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from spack_mcp import backend, discovery


def _write_package_py(
    repo_root: Path,
    name: str,
    *,
    docstring: str = "A demo package.",
    versions: list[str] | None = None,
    variants: list[str] | None = None,
) -> Path:
    package_dir = repo_root / "packages" / name
    package_dir.mkdir(parents=True)
    lines = [f'"""{docstring}"""', "", "class Demo:"]
    for version in versions or []:
        lines.append(f'    version("{version}")')
    for variant in variants or []:
        lines.append(f'    variant("{variant}", default=True)')
    if not versions and not variants:
        lines.append("    pass")
    package_py = package_dir / "package.py"
    package_py.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return package_py


def _repo_list_stdout(entries: list[tuple[str, str]]) -> str:
    lines = [f"==> {len(entries)} package repositories", "Namespace     Path", "-" * 40]
    lines.extend(f"{name}    {path}" for name, path in entries)
    return "\n".join(lines) + "\n"


def _result(stdout: str, *, returncode: int = 0) -> backend._CommandResult:
    return backend._CommandResult(
        argv=("spack",), returncode=returncode, stdout=stdout, stderr="", duration_seconds=0.1
    )


def _recording_run_spack(
    monkeypatch: pytest.MonkeyPatch, stdout: str, *, returncode: int = 0
) -> list[list[str]]:
    """Stub ``backend._run_spack`` while recording and policing its argv.

    R4: an argv-ignoring stub (a bare ``lambda *args, **kwargs: ...``) would
    let a reintroduced ``spack list`` call -- the exact defect this module
    exists to avoid, and the one confirmed broken on the ares deployment
    clone -- slip through green. Every discovery-layer stub built on this
    helper instead records what it was called with and fails loudly the
    moment ``list`` is invoked as the first subcommand.
    """
    invocations: list[list[str]] = []

    def fake(args: list[str], *, operation: str, timeout_seconds: int) -> backend._CommandResult:
        invocations.append(list(args))
        if args and args[0] == "list":
            raise AssertionError(f"spack list must never be invoked; got argv={args}")
        return _result(stdout, returncode=returncode)

    monkeypatch.setattr(backend, "_run_spack", fake)
    return invocations


# ── base_package_name ──


@pytest.mark.parametrize(
    ("spec", "expected"),
    [
        ("hdf5", "hdf5"),
        ("hdf5@1.14.3", "hdf5"),
        ("py-numpy@1.2 +mpi", "py-numpy"),
        ("gcc-runtime%gcc@13", "gcc-runtime"),
        ("hdf5^mpich", "hdf5"),
        ("hdf5/abc123", "hdf5"),
    ],
)
def test_base_package_name_extracts_leading_token(spec: str, expected: str) -> None:
    assert discovery.base_package_name(spec) == expected


# ── repo list parsing ──


def test_parse_repo_list_skips_banner_header_and_separator() -> None:
    output = _repo_list_stdout([("builtin", "/opt/spack/var/spack/repos/builtin")])

    repos = discovery._parse_repo_list(output)

    assert repos == [
        discovery.SpackRepoRef(name="builtin", path=Path("/opt/spack/var/spack/repos/builtin"))
    ]


def test_parse_repo_list_skips_malformed_lines() -> None:
    output = "\n".join(
        [
            "==> 2 package repositories",
            "Namespace     Path",
            "----          ----",
            "onlyonecolumn",
            "builtin    /opt/spack/var/spack/repos/builtin",
        ]
    )

    repos = discovery._parse_repo_list(output)

    assert repos == [
        discovery.SpackRepoRef(name="builtin", path=Path("/opt/spack/var/spack/repos/builtin"))
    ]


def test_list_registered_repos_returns_parsed_repos(monkeypatch: pytest.MonkeyPatch) -> None:
    output = _repo_list_stdout([("builtin", "/opt/spack/var/spack/repos/builtin")])
    invocations = _recording_run_spack(monkeypatch, output)

    repos = discovery.list_registered_repos()

    assert repos == [
        discovery.SpackRepoRef(name="builtin", path=Path("/opt/spack/var/spack/repos/builtin"))
    ]
    assert invocations == [["repo", "list"]]


def test_parse_repo_list_handles_bare_piped_output_with_no_banner_or_header() -> None:
    """S6: real `spack repo list` prints no ``==>``/``Namespace`` header when
    piped to a non-tty (the banner is tty-only); the fixture used elsewhere
    in this file adds one defensively, but the parser must not require it."""
    output = "builtin    /opt/spack/var/spack/repos/builtin\n"

    repos = discovery._parse_repo_list(output)

    assert repos == [
        discovery.SpackRepoRef(name="builtin", path=Path("/opt/spack/var/spack/repos/builtin"))
    ]


def test_parse_repo_list_takes_the_last_column_as_the_path(tmp_path: Path) -> None:
    """R2: a third column (a version/API marker some Spack releases print)
    must not be mistaken for the path -- the path is always the last token."""
    _write_package_py(tmp_path, "zlib")

    repos = discovery._parse_repo_list(f"builtin    v2.0    {tmp_path}\n")

    assert repos == [discovery.SpackRepoRef(name="builtin", path=tmp_path)]
    scan = discovery._scan_repo(repos[0])
    assert scan.readable is True
    assert set(scan.packages) == {"zlib"}


def test_list_registered_repos_raises_when_none_registered(monkeypatch: pytest.MonkeyPatch) -> None:
    invocations = _recording_run_spack(monkeypatch, "")

    with pytest.raises(backend.SpackBackendError) as error:
        discovery.list_registered_repos()

    assert error.value.code == "no_repos_registered"
    assert error.value.operation == "search"
    assert invocations == [["repo", "list"]]


def test_list_registered_repos_propagates_broken_subcommand(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """spack repo list itself failing (e.g. a broken clone) is a typed error,
    never silently treated as zero repos."""

    def fail(*_args: object, **_kwargs: object) -> backend._CommandResult:
        raise backend.SpackBackendError("command_failed", "boom", operation="search", returncode=1)

    monkeypatch.setattr(backend, "_run_spack", fail)

    with pytest.raises(backend.SpackBackendError) as error:
        discovery.list_registered_repos()

    assert error.value.code == "command_failed"


# ── package directory walking ──


def test_repo_packages_requires_package_py(tmp_path: Path) -> None:
    repo = discovery.SpackRepoRef(name="builtin", path=tmp_path)
    _write_package_py(tmp_path, "zlib")
    (tmp_path / "packages" / "not-a-recipe").mkdir(parents=True)  # no package.py

    packages = discovery._repo_packages(repo)

    assert set(packages) == {"zlib"}


def test_repo_packages_returns_empty_for_missing_packages_dir(tmp_path: Path) -> None:
    repo = discovery.SpackRepoRef(name="empty", path=tmp_path)

    assert discovery._repo_packages(repo) == {}


def test_repo_packages_ignores_stray_files_alongside_recipe_dirs(tmp_path: Path) -> None:
    repo = discovery.SpackRepoRef(name="builtin", path=tmp_path)
    _write_package_py(tmp_path, "zlib")
    (tmp_path / "packages" / "README.md").write_text("not a recipe dir", encoding="utf-8")

    packages = discovery._repo_packages(repo)

    assert set(packages) == {"zlib"}


def test_repo_packages_enforces_entry_cap(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(discovery, "_MAX_PACKAGE_ENTRIES_PER_REPO", 1)
    repo = discovery.SpackRepoRef(name="huge", path=tmp_path)
    _write_package_py(tmp_path, "one")
    _write_package_py(tmp_path, "two")

    with pytest.raises(backend.SpackBackendError) as error:
        discovery._repo_packages(repo)

    assert error.value.code == "response_too_large"


# ── search ──


def test_search_rejects_empty_query() -> None:
    with pytest.raises(backend.SpackBackendError) as error:
        discovery.search_packages("   ")

    assert error.value.code == "invalid_query"


def test_search_finds_exact_and_fuzzy_matches_and_reports_repos(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo_root = tmp_path / "builtin"
    _write_package_py(repo_root, "hdf5")
    _write_package_py(repo_root, "hdf5-vol-async")
    _write_package_py(repo_root, "zlib")
    monkeypatch.setattr(
        discovery, "list_registered_repos", lambda: [discovery.SpackRepoRef("builtin", repo_root)]
    )
    monkeypatch.setattr(
        discovery,
        "find_installed",
        lambda query=None: backend.SpackFindResult(
            query=query,
            packages=[backend.SpackPackage(name="hdf5", version="1.14.3", dag_hash="abc")],
            count=1,
        ),
    )

    result = discovery.search_packages("hdf5")

    names = {match.name for match in result.matches}
    assert names == {"hdf5", "hdf5-vol-async"}
    assert result.repos_searched == ["builtin"]
    by_name = {match.name: match for match in result.matches}
    assert by_name["hdf5"].installed is True
    assert by_name["hdf5"].installed_packages[0].dag_hash == "abc"
    assert by_name["hdf5-vol-async"].installed is False
    assert by_name["hdf5-vol-async"].repos == ["builtin"]


def test_fuzzy_match_ranks_exact_prefix_substring_then_typo_distance() -> None:
    candidates = ["py-numpy", "numpy-utils", "scipy", "numpy"]

    ranked = discovery._fuzzy_match("numpy", candidates).names

    # exact match first, then prefix, then substring; scipy is unrelated
    assert ranked[0] == "numpy"
    assert ranked[1] == "numpy-utils"
    assert ranked[2] == "py-numpy"
    assert "scipy" not in ranked


def test_fuzzy_match_tolerates_typos_via_close_match_fallback() -> None:
    candidates = ["lammps", "gromacs", "openmpi"]

    ranked = discovery._fuzzy_match("lamps", candidates).names  # missing an 'm'

    assert "lammps" in ranked


def test_fuzzy_match_normalizes_dash_underscore_into_the_exact_tier() -> None:
    """R3: Spack's Python-module-safe repo directories fold '-' to '_'
    (py-numpy -> packages/py_numpy); search must rank that as an exact
    match, not merely surface it through the looser typo-distance fallback,
    so it agrees with the install gate's exact-match classification."""
    candidates = ["py_numpy", "numpy"]

    result = discovery._fuzzy_match("py-numpy", candidates)

    assert result.names[0] == "py_numpy"


def test_search_returns_empty_result_on_no_match(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo_root = tmp_path / "builtin"
    _write_package_py(repo_root, "zlib")
    monkeypatch.setattr(
        discovery, "list_registered_repos", lambda: [discovery.SpackRepoRef("builtin", repo_root)]
    )
    monkeypatch.setattr(
        discovery,
        "find_installed",
        lambda query=None: backend.SpackFindResult(query=query, packages=[], count=0),
    )

    result = discovery.search_packages("totally-unrelated-xyz")

    assert result.count == 0
    assert result.matches == []
    assert result.total_matches == 0
    assert result.truncated is False


def test_search_caps_match_count_and_reports_truncation(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """S4: a capped result must say so -- otherwise an agent cannot tell
    '25 of 25' from '25 of 60'."""
    repo_root = tmp_path / "builtin"
    for index in range(40):
        _write_package_py(repo_root, f"demo-{index:02d}")
    monkeypatch.setattr(
        discovery, "list_registered_repos", lambda: [discovery.SpackRepoRef("builtin", repo_root)]
    )
    monkeypatch.setattr(
        discovery,
        "find_installed",
        lambda query=None: backend.SpackFindResult(query=query, packages=[], count=0),
    )

    result = discovery.search_packages("demo")

    assert result.count == discovery._MAX_SEARCH_MATCHES
    assert result.total_matches == 40
    assert result.truncated is True


def test_search_reports_unreadable_repos_without_dropping_readable_results(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """R2: one unreadable repo must not empty out or fail the whole search;
    the readable repo's results still come back, and the unreadable one is
    named rather than silently absent."""
    readable_repo = tmp_path / "builtin"
    _write_package_py(readable_repo, "zlib")
    missing_repo = discovery.SpackRepoRef(name="iowarp", path=tmp_path / "does-not-exist")
    monkeypatch.setattr(
        discovery,
        "list_registered_repos",
        lambda: [discovery.SpackRepoRef("builtin", readable_repo), missing_repo],
    )
    monkeypatch.setattr(
        discovery,
        "find_installed",
        lambda query=None: backend.SpackFindResult(query=query, packages=[], count=0),
    )

    result = discovery.search_packages("zlib")

    assert {match.name for match in result.matches} == {"zlib"}
    assert result.repos_searched == ["builtin"]
    assert any(entry.startswith("iowarp") for entry in result.repos_unreadable)


def test_search_degrades_installed_state_when_spack_find_fails(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """S5: a broken `spack find` must not discard the already-computed
    recipe-availability half of the answer -- only the installed-state half
    degrades, with a typed reason."""
    repo_root = tmp_path / "builtin"
    _write_package_py(repo_root, "zlib")
    monkeypatch.setattr(
        discovery, "list_registered_repos", lambda: [discovery.SpackRepoRef("builtin", repo_root)]
    )

    def fail(query: str | None = None) -> backend.SpackFindResult:
        raise backend.SpackBackendError(
            "command_failed", "Spack find failed", operation="find", returncode=1
        )

    monkeypatch.setattr(discovery, "find_installed", fail)

    result = discovery.search_packages("zlib")

    assert {match.name for match in result.matches} == {"zlib"}
    assert result.installed_state_degraded is True
    assert result.installed_state_degraded_reason is not None
    assert "command_failed" in result.installed_state_degraded_reason
    assert result.matches[0].installed is False


def test_search_packages_end_to_end_never_invokes_spack_list(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """R4 regression, at the level a reintroduced call would actually trip:
    the real backend._run_bounded_command seam (not an argv-ignoring stub).
    ``spack list`` is broken on at least one deployment clone this module
    targets (module docstring); this is the one explicit end-to-end guard
    for the constraint the whole module exists to satisfy."""
    repo_root = tmp_path / "builtin"
    _write_package_py(repo_root, "zlib")
    monkeypatch.setattr(backend, "_spack_executable", lambda: "/opt/spack/bin/spack")
    invocations: list[list[str]] = []

    def fake_run_bounded(
        argv: list[str], *, env: dict[str, str], timeout_seconds: int, **kwargs: object
    ) -> backend._CommandResult:
        invocations.append(list(argv))
        subcommand = argv[1:2]
        if subcommand == ["repo"]:
            return backend._CommandResult(
                argv=tuple(argv),
                returncode=0,
                stdout=f"builtin    {repo_root}\n",
                stderr="",
                duration_seconds=0.01,
            )
        if subcommand == ["find"]:
            return backend._CommandResult(
                argv=tuple(argv), returncode=0, stdout="[]", stderr="", duration_seconds=0.01
            )
        raise AssertionError(f"unexpected spack subcommand invoked: {argv}")

    monkeypatch.setattr(backend, "_run_bounded_command", fake_run_bounded)

    result = discovery.search_packages("zlib")

    assert {match.name for match in result.matches} == {"zlib"}
    subcommands = [argv[1] for argv in invocations]
    assert "list" not in subcommands
    assert subcommands == ["repo", "find"]


# ── recipe availability classification ──


def test_classify_recipe_availability_found(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo_root = tmp_path / "builtin"
    _write_package_py(repo_root, "lammps")
    monkeypatch.setattr(
        discovery, "list_registered_repos", lambda: [discovery.SpackRepoRef("builtin", repo_root)]
    )

    availability = discovery.classify_recipe_availability("lammps")

    assert availability.available is True
    assert availability.repo == "builtin"
    assert "spack_install" in availability.message


def test_classify_recipe_availability_not_found_lists_repos(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo_root = tmp_path / "builtin"
    _write_package_py(repo_root, "zlib")
    monkeypatch.setattr(
        discovery, "list_registered_repos", lambda: [discovery.SpackRepoRef("builtin", repo_root)]
    )

    availability = discovery.classify_recipe_availability("nonexistent-package")

    assert availability.available is False
    assert availability.repo is None
    assert "builtin" in availability.message
    assert "no recipe in any registered repo" in availability.message


def test_classify_recipe_availability_degrades_honestly_on_discovery_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Repo discovery failing must not be silently swallowed as unavailable."""

    def fail() -> list[discovery.SpackRepoRef]:
        raise backend.SpackBackendError(
            "command_failed", "spack repo list broke", operation="search"
        )

    monkeypatch.setattr(discovery, "list_registered_repos", fail)

    availability = discovery.classify_recipe_availability("lammps")

    assert availability.available is False
    assert "repo discovery failed" in availability.message
    assert "command_failed" in availability.message


def test_classify_recipe_availability_reports_unreadable_repo_instead_of_false_negative(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """R2: a registered repo whose recipe directory cannot be scanned must
    never be silently folded into "no recipe in any registered repo" --
    that claim is indistinguishable from a confirmed absence and would
    wrongly veto a spack_install spack itself might have served (see
    test_provisioning.py's availability_unknown coverage)."""
    readable_repo = tmp_path / "builtin"
    _write_package_py(readable_repo, "zlib")
    missing_repo = discovery.SpackRepoRef(name="iowarp", path=tmp_path / "does-not-exist")
    monkeypatch.setattr(
        discovery,
        "list_registered_repos",
        lambda: [discovery.SpackRepoRef("builtin", readable_repo), missing_repo],
    )

    availability = discovery.classify_recipe_availability("lammps")

    assert availability.available is False
    assert availability.repos_unreadable != []
    assert any("iowarp" in entry for entry in availability.repos_unreadable)
    assert "no recipe in any registered repo" not in availability.message
    assert "could not" in availability.message.lower()


def test_classify_and_search_agree_on_dash_underscore_recipe_naming(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """R3: search and the install gate must never disagree about a
    hyphen-vs-underscore recipe name (py-numpy query, py_numpy directory --
    Spack's modern Python-module-safe repo layout), tested both ways."""
    repo_root = tmp_path / "builtin"
    _write_package_py(repo_root, "py_numpy")
    monkeypatch.setattr(
        discovery, "list_registered_repos", lambda: [discovery.SpackRepoRef("builtin", repo_root)]
    )
    monkeypatch.setattr(
        discovery,
        "find_installed",
        lambda query=None: backend.SpackFindResult(query=query, packages=[], count=0),
    )

    availability_dash = discovery.classify_recipe_availability("py-numpy")
    availability_underscore = discovery.classify_recipe_availability("py_numpy")
    search_dash = discovery.search_packages("py-numpy")

    assert availability_dash.available is True
    assert availability_dash.repo == "builtin"
    assert availability_underscore.available is True
    assert "py_numpy" in {match.name for match in search_dash.matches}


def test_classify_recipe_availability_honors_repo_yaml_subdirectory(tmp_path: Path) -> None:
    """R3: repo.yaml's `subdirectory:` key can relocate a repo's recipes
    away from the default packages/ directory."""
    repo_root = tmp_path / "custom"
    (repo_root / "recipes" / "lammps").mkdir(parents=True)
    (repo_root / "recipes" / "lammps" / "package.py").write_text(
        '"""Demo lammps."""\n\nclass Demo:\n    pass\n', encoding="utf-8"
    )
    (repo_root / "repo.yaml").write_text("subdirectory: recipes\n", encoding="utf-8")
    repo = discovery.SpackRepoRef(name="custom", path=repo_root)

    scan = discovery._scan_repo(repo)

    assert scan.readable is True
    assert set(scan.packages) == {"lammps"}


# ── locate error enrichment ──


def test_enrich_not_installed_adds_availability_detail(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo_root = tmp_path / "builtin"
    _write_package_py(repo_root, "lammps")
    monkeypatch.setattr(
        discovery, "list_registered_repos", lambda: [discovery.SpackRepoRef("builtin", repo_root)]
    )
    error = backend.SpackBackendError("not_installed", "missing: lammps", operation="locate")

    enriched = discovery.enrich_not_installed(error, "lammps@1.0")

    assert enriched.code == "not_installed"
    assert enriched.message == error.message
    assert enriched.detail is not None
    assert "builtin" in enriched.detail


def test_enrich_not_installed_passes_through_other_codes() -> None:
    error = backend.SpackBackendError("ambiguous_spec", "many matches", operation="locate")

    assert discovery.enrich_not_installed(error, "lammps") is error


# ── info: spack info parsing ──


_SPACK_INFO_OUTPUT = """\
AutotoolsPackage:   zlib

Description:
    A free, general-purpose, legally unencumbered lossless
    data-compression library.

Homepage: https://zlib.net

Preferred version:
    1.3.1    https://zlib.net/fossils/zlib-1.3.1.tar.gz

Safe versions:
    1.3.1    https://zlib.net/fossils/zlib-1.3.1.tar.gz
    1.3      https://zlib.net/fossils/zlib-1.3.tar.gz

Deprecated versions:
    None

Variants:
    Name [Default]                 When    Allowed values    Description
    ===========================    ====    ===============   ==============================
    optimize [on]                  --      on, off            Enable -O2/-O3
    pic [on]                       --      on, off             Position-independent code
"""


def test_parse_spack_info_output_extracts_description_versions_variants() -> None:
    parsed = discovery._parse_spack_info_output(_SPACK_INFO_OUTPUT)

    assert parsed is not None
    # S6: exact comparison, not a loose substring check -- a loose check is
    # what let the S3 Homepage-pollution bug ship green in the first place.
    assert parsed.description == (
        "A free, general-purpose, legally unencumbered lossless data-compression library."
    )
    assert parsed.versions == ["1.3.1", "1.3"]
    assert parsed.variants == ["optimize", "pic"]
    assert parsed.complete is True


def test_parse_spack_info_output_returns_none_for_unrecognized_format() -> None:
    assert discovery._parse_spack_info_output("total garbage\nnot spack info at all\n") is None


_SPACK_INFO_OUTPUT_WITH_UNTRACKED_SECTIONS = """\
AutotoolsPackage:   zlib

Description:
    A free, general-purpose, legally unencumbered lossless
    data-compression library.

Homepage: https://zlib.net

Preferred version:
    1.3.1    https://zlib.net/fossils/zlib-1.3.1.tar.gz

Safe versions:
    1.3.1    https://zlib.net/fossils/zlib-1.3.1.tar.gz

Variants:
    Name [Default]     When    Allowed values    Description
    ===============    ====    ==============    ===========
    optimize [on]      --      on, off           Enable -O2

Build Dependencies:
    gmake [on]  cmake

Licenses:
    Zlib
"""


def test_parse_spack_info_output_does_not_leak_untracked_sections_into_tracked_ones() -> None:
    """S3: only a blank line or another header line used to reset the
    section cursor for the six tracked headers -- any other single-line
    field (`Homepage: <url>`) was silently absorbed into whichever tracked
    section preceded it, and an untracked block header (`Build
    Dependencies:`) let its body leak into that same section."""
    parsed = discovery._parse_spack_info_output(_SPACK_INFO_OUTPUT_WITH_UNTRACKED_SECTIONS)

    assert parsed is not None
    assert parsed.description is not None
    assert "Homepage" not in parsed.description
    assert "gmake" not in parsed.variants
    assert parsed.variants == ["optimize"]


def test_parse_spack_info_output_marks_incomplete_when_a_section_is_missing() -> None:
    """S1: `_parse_spack_info_output` must distinguish "every expected
    section was recognized" from "some sections were never seen" -- the
    latter is a partial parse, not a confirmed empty versions/variants set."""
    partial = "Description:\n    Only a description survives a format change.\n"

    parsed = discovery._parse_spack_info_output(partial)

    assert parsed is not None
    assert parsed.description == "Only a description survives a format change."
    assert parsed.versions == []
    assert parsed.variants == []
    assert parsed.complete is False


def test_describe_package_uses_spack_info_when_it_works(monkeypatch: pytest.MonkeyPatch) -> None:
    invocations = _recording_run_spack(monkeypatch, _SPACK_INFO_OUTPUT)

    result = discovery.describe_package("zlib")

    assert result.source == "spack_info"
    assert result.degraded is False
    assert result.degraded_reason is None
    assert result.versions == ["1.3.1", "1.3"]
    assert invocations == [["info", "zlib"]]


def test_describe_package_marks_degraded_when_spack_info_output_is_partial(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """S1: a partial (but exit-0, parseable) spack info output must not be
    presented as a complete, confirmed-empty answer."""
    partial = "Description:\n    Only a description survives a format change.\n"
    _recording_run_spack(monkeypatch, partial)

    result = discovery.describe_package("zlib")

    assert result.source == "spack_info"
    assert result.degraded is True
    assert result.degraded_reason is not None
    assert result.versions == []
    assert result.variants == []


def test_describe_package_falls_back_when_spack_info_exits_zero_but_unparseable(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """spack info can succeed (exit 0) yet emit a format this parser cannot
    read (a future Spack version, a locale change, ...); that must still
    degrade to the package.py fallback, never crash or return an empty
    unlabeled result."""
    repo_root = tmp_path / "builtin"
    _write_package_py(repo_root, "zlib", docstring="Fallback description.")
    _recording_run_spack(monkeypatch, "nothing recognizable here\n")
    monkeypatch.setattr(
        discovery, "list_registered_repos", lambda: [discovery.SpackRepoRef("builtin", repo_root)]
    )

    result = discovery.describe_package("zlib")

    assert result.source == "package_py"
    assert result.degraded is True
    assert result.description == "Fallback description."


def test_describe_package_falls_back_to_package_py_and_says_so(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo_root = tmp_path / "builtin"
    _write_package_py(
        repo_root,
        "zlib",
        docstring="A compression library.",
        versions=["1.3.1", "1.3"],
        variants=["shared"],
    )

    def fail(*_args: object, **_kwargs: object) -> backend._CommandResult:
        raise backend.SpackBackendError("command_failed", "info subcommand broke", operation="info")

    monkeypatch.setattr(backend, "_run_spack", fail)
    monkeypatch.setattr(
        discovery, "list_registered_repos", lambda: [discovery.SpackRepoRef("builtin", repo_root)]
    )

    result = discovery.describe_package("zlib")

    assert result.source == "package_py"
    assert result.degraded is True
    assert result.degraded_reason is not None
    assert "spack info" in result.degraded_reason
    # S2: degraded_reason must carry the actual typed cause, not a generic
    # sentence -- "info subcommand broke" reached spack via a command_failed
    # SpackBackendError, and that code must survive into the reason text.
    assert "command_failed" in result.degraded_reason
    assert "info subcommand broke" in result.degraded_reason
    assert result.repo == "builtin"
    assert result.versions == ["1.3.1", "1.3"]
    assert result.variants == ["shared"]
    assert result.description == "A compression library."


def test_describe_package_raises_recipe_not_found_when_absent_everywhere(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo_root = tmp_path / "builtin"
    _write_package_py(repo_root, "zlib")

    def fail(*_args: object, **_kwargs: object) -> backend._CommandResult:
        raise backend.SpackBackendError("command_failed", "info subcommand broke", operation="info")

    monkeypatch.setattr(backend, "_run_spack", fail)
    monkeypatch.setattr(
        discovery, "list_registered_repos", lambda: [discovery.SpackRepoRef("builtin", repo_root)]
    )

    with pytest.raises(backend.SpackBackendError) as error:
        discovery.describe_package("does-not-exist")

    assert error.value.code == "recipe_not_found"
    assert error.value.operation == "info"
    assert "builtin" in (error.value.detail or "")


def test_parse_package_py_rejects_unreadable_source(tmp_path: Path) -> None:
    broken = tmp_path / "package.py"
    broken.write_text("def broken(:\n", encoding="utf-8")  # SyntaxError

    with pytest.raises(backend.SpackBackendError) as error:
        discovery._parse_package_py(broken)

    assert error.value.code == "package_py_unreadable"


def test_parse_package_py_ignores_non_string_version_args(tmp_path: Path) -> None:
    package_py = tmp_path / "package.py"
    package_py.write_text(
        '"""Demo."""\nclass Demo:\n    version(1)\n    version("1.0")\n    other_call()\n',
        encoding="utf-8",
    )

    description, versions, variants = discovery._parse_package_py(package_py)

    assert description == "Demo."
    assert versions == ["1.0"]
    assert variants == []


def test_parse_package_py_recognizes_attribute_style_calls(tmp_path: Path) -> None:
    """spack recipes sometimes call version()/variant() through an attribute
    (e.g. inherited helpers); the recognizer must not require a bare name."""
    package_py = tmp_path / "package.py"
    package_py.write_text(
        '"""Demo."""\n'
        "class Demo:\n"
        "    self.version('1.0')\n"
        "    self.variant('shared', default=True)\n",
        encoding="utf-8",
    )

    _, versions, variants = discovery._parse_package_py(package_py)

    assert versions == ["1.0"]
    assert variants == ["shared"]
