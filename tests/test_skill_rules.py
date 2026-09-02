"""The skill rules, and the federated-marketplace referral they ship beside.

A skill's description is carried in every session whether or not it fires, so
these rules are the only place a vague one gets caught before it becomes a
permanent cost to every user. The tests below pin both halves of that: what
blocks publication, and what is merely reported so a reviewer can judge it.
"""

from __future__ import annotations

import json
import textwrap
from pathlib import Path

import pytest

from clio_kit.community import (
    marketplace_add_command,
    read_community_entries,
    read_federated_marketplaces,
    read_live_marketplaces,
    read_shipped_marketplaces,
    write_live_marketplaces,
    write_shipped_marketplaces,
)
from clio_kit.skills import (
    DESCRIPTION_BUDGET,
    EVAL_LADDER,
    SkillProblem,
    always_on_cost,
    check_skill,
    check_skill_collection,
    read_skill_frontmatter,
)

GOOD_DESCRIPTION = (
    "Use when a diffraction pattern needs indexing or a lattice parameter "
    'refined. Triggers on "index this pattern", "refine the lattice". '
    "Not for electron microscopy imaging; use an imaging skill."
)


def write_skill(
    root: Path,
    name: str,
    *,
    description: str = GOOD_DESCRIPTION,
    evals: bool = True,
    extra: str = "",
) -> Path:
    """Write one skill directory and return it."""
    skill_dir = root / name
    skill_dir.mkdir(parents=True)
    (skill_dir / "SKILL.md").write_text(
        f"---\nname: {name}\ndescription: {description}\n{extra}---\n\n# {name}\n",
        encoding="utf-8",
    )
    if evals:
        (skill_dir / "evals.md").write_text("# Evals\n\n## S1\n", encoding="utf-8")
    return skill_dir


def test_a_well_formed_skill_raises_nothing(tmp_path: Path) -> None:
    report = check_skill(write_skill(tmp_path, "reading-diffraction-patterns"))
    assert report.problems == []
    assert report.advisories == []
    assert report.ok


def test_a_skill_without_recorded_scenarios_is_blocked(tmp_path: Path) -> None:
    """Untested by definition, which is the whole reason evals are required."""
    report = check_skill(write_skill(tmp_path, "untested-skill", evals=False))
    assert not report.ok
    assert any("eval scenarios" in problem for problem in report.problems)


def test_an_evals_directory_counts_as_recorded_scenarios(tmp_path: Path) -> None:
    """One file or a directory of them; the rule is that they exist."""
    skill_dir = write_skill(tmp_path, "directory-evals", evals=False)
    evals_dir = skill_dir / "evals"
    evals_dir.mkdir()
    (evals_dir / "s1.md").write_text("# S1\n", encoding="utf-8")
    assert check_skill(skill_dir).ok


def test_a_description_that_does_not_say_when_to_fire_is_blocked(
    tmp_path: Path,
) -> None:
    """A description restating the body is context paid for and never returned."""
    report = check_skill(
        write_skill(
            tmp_path,
            "restates-the-body",
            description=(
                "This skill indexes diffraction patterns and refines lattice "
                'parameters. Triggers on "index this pattern".'
            ),
        )
    )
    assert not report.ok
    assert any("Use when" in problem for problem in report.problems)


def test_a_description_without_literal_triggers_is_blocked(tmp_path: Path) -> None:
    """The matcher runs against phrases a user types, so they must be quoted."""
    report = check_skill(
        write_skill(
            tmp_path,
            "no-triggers",
            description=(
                "Use when a diffraction pattern needs indexing. Not for imaging; "
                "use an imaging skill."
            ),
        )
    )
    assert not report.ok
    assert any("Triggers on" in problem for problem in report.problems)


def test_a_missing_boundary_is_advised_but_never_blocks(tmp_path: Path) -> None:
    """A first skill with nothing to collide against is legitimately unbounded."""
    report = check_skill(
        write_skill(
            tmp_path,
            "no-boundary",
            description=(
                "Use when a diffraction pattern needs indexing. "
                'Triggers on "index this pattern".'
            ),
        )
    )
    assert report.ok, "a missing boundary must not reject a contribution"
    assert any("boundary" in advisory for advisory in report.advisories)


def test_an_overlong_description_is_advised_with_its_real_size(
    tmp_path: Path,
) -> None:
    padding = "x" * DESCRIPTION_BUDGET
    report = check_skill(
        write_skill(tmp_path, "verbose", description=f"{GOOD_DESCRIPTION} {padding}")
    )
    assert report.ok
    assert any(str(DESCRIPTION_BUDGET) in advisory for advisory in report.advisories)


def test_a_name_disagreeing_with_its_folder_is_unreadable(tmp_path: Path) -> None:
    skill_dir = tmp_path / "folder-name"
    skill_dir.mkdir()
    (skill_dir / "SKILL.md").write_text(
        f"---\nname: different-name\ndescription: {GOOD_DESCRIPTION}\n---\n",
        encoding="utf-8",
    )
    with pytest.raises(SkillProblem, match="different-name"):
        check_skill(skill_dir)


def test_a_collection_reports_every_skill_rather_than_the_first(
    tmp_path: Path,
) -> None:
    """A contributor should see the whole list in one run, not one per run."""
    write_skill(tmp_path, "good-one")
    write_skill(tmp_path, "bad-one", evals=False)
    reports = check_skill_collection(tmp_path)
    assert [report.name for report in reports] == ["bad-one", "good-one"]
    assert always_on_cost(reports) == 2 * len(GOOD_DESCRIPTION)


def test_our_own_skills_all_satisfy_the_rules_we_publish() -> None:
    """The bar we ask outside contributors to clear is the bar we clear."""
    skills_root = Path(__file__).resolve().parent.parent / "skills"
    reports = [
        report
        for collection in sorted(skills_root.iterdir())
        if collection.is_dir()
        for report in check_skill_collection(collection / "skills")
    ]
    assert reports, "expected to find shipped skills"
    failing = {report.name: report.problems for report in reports if report.problems}
    assert not failing, f"shipped skills violate our own rules: {failing}"


# --- federated marketplaces ------------------------------------------------


def write_entry(repo_root: Path, name: str, body: str) -> None:
    entries = repo_root / "community" / "entries"
    entries.mkdir(parents=True, exist_ok=True)
    (entries / f"{name}.toml").write_text(textwrap.dedent(body), encoding="utf-8")


def test_a_marketplace_entry_stays_out_of_the_installable_catalogue(
    tmp_path: Path,
) -> None:
    """Claude Code has no nested marketplace, so publishing one would break."""
    write_entry(
        tmp_path,
        "materials-lab",
        """
        name        = "materials-lab"
        kind        = "marketplace"
        description = "Crystal structure and diffraction skills."
        maintainer  = "some-lab"

        [source]
        type = "github"
        repo = "some-lab/materials-agent-skills"
        """,
    )
    assert read_community_entries(tmp_path) == []
    federated = read_federated_marketplaces(tmp_path)
    assert [entry["name"] for entry in federated] == ["materials-lab"]
    assert (
        federated[0]["add_command"]
        == "claude plugin marketplace add some-lab/materials-agent-skills"
    )


def test_an_entry_defaults_to_an_installable_plugin(tmp_path: Path) -> None:
    """Omitting kind keeps the behaviour every existing entry relies on."""
    write_entry(
        tmp_path,
        "materials-lab",
        """
        name        = "materials-lab"
        description = "Crystal structure and diffraction skills."

        [source]
        type = "github"
        repo = "some-lab/materials-agent-skills"
        """,
    )
    assert [entry["name"] for entry in read_community_entries(tmp_path)] == [
        "materials-lab"
    ]
    assert read_federated_marketplaces(tmp_path) == []


def test_a_marketplace_cannot_be_published_as_an_npm_package(tmp_path: Path) -> None:
    """`marketplace add` takes a repository; npm names a package."""
    write_entry(
        tmp_path,
        "materials-lab",
        """
        name        = "materials-lab"
        kind        = "marketplace"
        description = "Crystal structure and diffraction skills."

        [source]
        type    = "npm"
        package = "@some-lab/materials"
        """,
    )
    with pytest.raises(ValueError, match="marketplace add"):
        read_federated_marketplaces(tmp_path)


def test_an_unknown_kind_is_refused(tmp_path: Path) -> None:
    write_entry(
        tmp_path,
        "materials-lab",
        """
        name        = "materials-lab"
        kind        = "extension"
        description = "Crystal structure and diffraction skills."

        [source]
        type = "github"
        repo = "some-lab/materials-agent-skills"
        """,
    )
    with pytest.raises(ValueError, match="kind"):
        read_community_entries(tmp_path)


def test_a_url_marketplace_refers_to_its_url(tmp_path: Path) -> None:
    assert (
        marketplace_add_command(
            {"source": "url", "url": "https://gitlab.example.com/team/index.git"}
        )
        == "claude plugin marketplace add https://gitlab.example.com/team/index.git"
    )


def test_the_shipped_catalogue_round_trips(tmp_path: Path) -> None:
    """The wheel carries this data; `community/` is not shipped."""
    package_dir = tmp_path / "clio_kit"
    package_dir.mkdir()
    write_shipped_marketplaces(package_dir, [{"name": "materials-lab"}])
    assert (package_dir / "_federated_marketplaces.json").is_file()


def test_reading_a_shipped_catalogue_that_is_absent_is_not_an_error() -> None:
    """An installation with no federated entries must still answer."""
    assert isinstance(read_shipped_marketplaces(), list)


# --- live vs baked federated catalogue --------------------------------------
#
# A referral baked into the wheel only reaches users on a clio-kit release,
# which defeats the point of indexing: a contributor's catalogue should arrive
# on the next `marketplace update`. So the live copy inside the marketplace
# wins, and the baked snapshot is only a fallback.


def write_known_marketplaces(config_dir: Path, install_location: Path) -> None:
    plugins = config_dir / "plugins"
    plugins.mkdir(parents=True, exist_ok=True)
    (plugins / "known_marketplaces.json").write_text(
        json.dumps(
            {"clio-kit": {"installLocation": str(install_location)}},
            indent=2,
        ),
        encoding="utf-8",
    )


def test_a_referral_reaches_users_without_a_clio_kit_release(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The copy inside the marketplace is what an updated client reads."""
    marketplace = tmp_path / "marketplace"
    write_live_marketplaces(marketplace, [{"name": "materials-lab"}])
    config = tmp_path / "config"
    write_known_marketplaces(config, marketplace)
    monkeypatch.setenv("CLAUDE_CONFIG_DIR", str(config))

    assert [entry["name"] for entry in read_live_marketplaces()] == ["materials-lab"]


def test_an_unreadable_client_record_falls_back_rather_than_failing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """known_marketplaces.json is client-internal, so every read is best-effort."""
    config = tmp_path / "config"
    (config / "plugins").mkdir(parents=True)
    (config / "plugins" / "known_marketplaces.json").write_text(
        "not json", encoding="utf-8"
    )
    monkeypatch.setenv("CLAUDE_CONFIG_DIR", str(config))

    assert read_live_marketplaces() == []


def test_a_missing_client_directory_is_not_an_error(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("CLAUDE_CONFIG_DIR", str(tmp_path / "absent"))
    assert read_live_marketplaces() == []


def test_a_marketplace_without_a_referral_file_is_skipped(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """An added marketplace that publishes no catalogue must not shadow one."""
    config = tmp_path / "config"
    write_known_marketplaces(config, tmp_path / "empty-marketplace")
    monkeypatch.setenv("CLAUDE_CONFIG_DIR", str(config))
    assert read_live_marketplaces() == []


def test_an_eval_status_off_the_ladder_is_refused(tmp_path: Path) -> None:
    skill = write_skill(tmp_path, "demo", extra="clio-kit:\n  eval-status: vibes\n")
    report = check_skill(skill)
    assert not report.ok
    assert any("not on the ladder" in p for p in report.problems)


def test_every_rung_of_the_ladder_is_accepted(tmp_path: Path) -> None:
    for rung in EVAL_LADDER:
        skill = write_skill(
            tmp_path / rung, "demo", extra=f"clio-kit:\n  eval-status: {rung}\n"
        )
        assert check_skill(skill).ok, rung


def test_our_own_skills_all_declare_a_rung_we_recognise() -> None:
    for skill_md in Path("skills").glob("*/skills/*/SKILL.md"):
        fields = read_skill_frontmatter(skill_md.parent)
        assert fields.get("eval-status") in EVAL_LADDER, skill_md
