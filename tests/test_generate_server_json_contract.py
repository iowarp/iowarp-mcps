"""Registry contract tests for deterministic server.json generation."""

from __future__ import annotations

import importlib.util
import json
import re
import sys
import tomllib
from pathlib import Path
from types import ModuleType
from typing import IO, Any

import pytest


def _load_generator() -> ModuleType:
    script = Path(__file__).resolve().parents[1] / "scripts" / "generate_server_json.py"
    spec = importlib.util.spec_from_file_location("clio_kit_manifest_generator", script)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"could not load manifest generator: {script}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


GENERATOR = _load_generator()

# Community entries live in the launcher package so the same reader backs both
# manifest generation and contributor-facing validation.
from clio_kit.community import read_community_entries  # noqa: E402
from clio_kit.plugins import PluginProblem, read_skill_frontmatter  # noqa: E402


def test_json_writer_requests_platform_independent_newlines(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Generated release metadata must remain byte-identical on Windows."""
    real_open = open
    observed: dict[str, Any] = {}

    def checked_open(*args: Any, **kwargs: Any) -> IO[str]:
        observed["newline"] = kwargs.get("newline")
        return real_open(*args, **kwargs)

    monkeypatch.setattr(GENERATOR, "open", checked_open, raising=False)
    output = tmp_path / "manifest.json"
    GENERATOR._write_json(output, {"name": "demo"})

    assert observed["newline"] == "\n"
    assert output.read_bytes() == b'{\n  "name": "demo"\n}\n'


def test_pypi_manifest_uses_standard_fixed_package_arguments() -> None:
    """Registry clients can launch one selected server from the shared wheel."""
    manifest = GENERATOR.build_server_json(
        "spack",
        {"description": "Spack MCP"},
        {"tools": []},
        server_version="2.0.0",
        pypi_version="2.3.0",
        scope="scientific",
    )

    assert manifest["version"] == "2.0.0"
    assert manifest["packages"] == [
        {
            "registryType": "pypi",
            "identifier": "clio-kit",
            "version": "2.3.0",
            "transport": {"type": "stdio"},
            "packageArguments": [
                {"type": "positional", "value": "mcp-server"},
                {"type": "positional", "value": "spack"},
            ],
        }
    ]


def test_every_committed_server_has_an_agent_runnable_package_coordinate() -> None:
    """Every registry record selects its exact server from the shared wheel."""
    repository_root = Path(__file__).resolve().parents[1]
    servers_root = repository_root / "clio-kit-mcp-servers"
    projects = sorted(path.parent for path in servers_root.glob("*/pyproject.toml"))
    manifests = sorted(servers_root.glob("*/server.json"))
    expected_version = GENERATOR.read_root_version(repository_root)
    expected_server_versions = GENERATOR.read_server_versions(repository_root)
    publish_servers = GENERATOR.read_registry_publish_servers(repository_root)
    marketplace = json.loads(
        (repository_root / ".claude-plugin" / "marketplace.json").read_text(
            encoding="utf-8"
        )
    )
    # The marketplace publishes two kinds of entry against different sources:
    # per-server plugins under clio-kit-mcp-servers/, and workflow bundles
    # under plugins/ whose whole content is a dependency list. They are keyed
    # differently -- a server entry drops the clio- prefix to match its
    # directory name, a bundle's name IS its identity -- so splitting them on
    # source keeps each set checkable against its own inventory.
    marketplace_plugins = {
        plugin["name"].removeprefix("clio-"): plugin
        for plugin in marketplace["plugins"]
        if plugin["source"].startswith("./clio-kit-mcp-servers/")
    }
    bundle_plugins = {
        plugin["name"]: plugin
        for plugin in marketplace["plugins"]
        if plugin["source"].startswith("./plugins/")
    }
    skill_plugins = {
        plugin["name"]: plugin
        for plugin in marketplace["plugins"]
        if plugin["source"].startswith("./skills/")
    }
    expected_bundles = GENERATOR.read_bundles(repository_root)
    expected_skill_plugins = {
        f"{bundle_name}-skills"
        for bundle_name in expected_bundles
        if (repository_root / "skills" / f"{bundle_name}-skills").is_dir()
    }
    gemini_extension = json.loads(
        (repository_root / "gemini-extension.json").read_text(encoding="utf-8")
    )
    readme = (repository_root / "README.md").read_text(encoding="utf-8")

    assert projects
    assert manifests == [project / "server.json" for project in projects]
    assert list(expected_server_versions) == sorted(expected_server_versions)
    assert set(expected_server_versions) == {project.name for project in projects}
    assert publish_servers == ("geo", "lmod", "seismology", "spack", "web")
    assert marketplace["metadata"]["version"] == expected_version
    assert set(marketplace_plugins) == set(expected_server_versions)
    assert set(bundle_plugins) == set(expected_bundles)
    assert set(skill_plugins) == expected_skill_plugins
    # Every published entry is one of the three kinds. A fourth source shape
    # would be an entry nothing in this repository accounts for.
    assert len(marketplace_plugins) + len(bundle_plugins) + len(skill_plugins) == len(
        marketplace["plugins"]
    )
    assert gemini_extension["version"] == expected_version
    for path in manifests:
        server_name = path.parent.name
        manifest = json.loads(path.read_text(encoding="utf-8"))
        plugin = json.loads(
            (path.parent / ".claude-plugin" / "plugin.json").read_text(encoding="utf-8")
        )
        assert manifest["version"] == expected_server_versions[server_name]
        assert plugin["version"] == expected_server_versions[server_name]
        assert (
            marketplace_plugins[server_name]["version"]
            == expected_server_versions[server_name]
        )
        assert (
            f"| **`{server_name}`** | {expected_server_versions[server_name]} |"
            in readme
        )
        assert f"<!-- mcp-name: {manifest['name']} -->" in readme
        assert manifest["packages"] == [
            {
                "registryType": "pypi",
                "identifier": "clio-kit",
                "version": expected_version,
                "transport": {"type": "stdio"},
                "packageArguments": [
                    {"type": "positional", "value": "mcp-server"},
                    {"type": "positional", "value": path.parent.name},
                ],
            }
        ]


def test_jarvis_current_contract_matches_registry_package_and_capability() -> None:
    """JARVIS contract revisions advance every independently versioned surface."""
    repository_root = Path(__file__).resolve().parents[1]
    jarvis_root = repository_root / "clio-kit-mcp-servers" / "jarvis"
    contract_index = json.loads(
        (
            repository_root / "src" / "clio_kit" / "_mcp_contracts" / "index.json"
        ).read_text(encoding="utf-8")
    )
    current_contract = next(
        contract
        for contract in contract_index["contracts"]
        if contract["server_name"] == "jarvis"
    )
    contract_match = re.fullmatch(
        r"clio-kit-jarvis-user-v(?P<major>\d+)\.(?P<minor>\d+)",
        current_contract["contract_id"],
    )
    assert current_contract["contract_id"] == "clio-kit-jarvis-user-v3.7"
    assert contract_match is not None
    contract_major_minor = (
        int(contract_match.group("major")),
        int(contract_match.group("minor")),
    )

    inventory_version = GENERATOR.read_server_versions(repository_root)["jarvis"]
    package_version = tomllib.loads(
        (jarvis_root / "pyproject.toml").read_text(encoding="utf-8")
    )["project"]["version"]
    lock_document = tomllib.loads((jarvis_root / "uv.lock").read_text(encoding="utf-8"))
    lock_version = next(
        package["version"]
        for package in lock_document["package"]
        if package["name"] == "jarvis-mcp"
    )
    registry_version = json.loads(
        (jarvis_root / "server.json").read_text(encoding="utf-8")
    )["version"]
    capability_source = (
        jarvis_root / "src" / "jarvis_mcp" / "capabilities" / "__init__.py"
    ).read_text(encoding="utf-8")
    capability_match = re.search(
        r'^__version__\s*=\s*"(?P<version>\d+\.\d+\.\d+)"$',
        capability_source,
        flags=re.MULTILINE,
    )
    assert capability_match is not None
    capability_version = capability_match.group("version")

    exact_versions = {
        inventory_version,
        package_version,
        lock_version,
        registry_version,
        capability_version,
    }
    assert exact_versions == {inventory_version}
    inventory_parts = inventory_version.split(".")
    assert len(inventory_parts) == 3
    assert tuple(map(int, inventory_parts[:2])) == contract_major_minor


def test_persistent_configs_use_the_installed_tool() -> None:
    """Long-lived MCP client configurations must not depend on uvx caches."""
    assert GENERATOR.build_claude_desktop_config(["jarvis"]) == {
        "mcpServers": {
            "clio-jarvis": {
                "command": "clio-kit",
                "args": ["mcp-server", "jarvis"],
            }
        }
    }
    extension = GENERATOR.build_gemini_extension(
        ["jarvis"],
        pypi_version="2.3.0",
    )
    assert extension["version"] == "2.3.0"
    assert extension["mcpServers"] == {
        "clio-jarvis": {
            "command": "clio-kit",
            "args": ["mcp-server", "jarvis"],
        }
    }


def test_plugin_versions_distinguish_contracts_from_the_root_wheel(
    tmp_path: Path,
) -> None:
    """Per-server plugins use contract versions while bundles use the wheel version."""
    GENERATOR.write_claude_plugin_files(
        tmp_path,
        "spack",
        {"description": "Spack MCP", "version": "9.9.9"},
        server_version="2.0.0",
    )
    plugin = json.loads(
        (tmp_path / ".claude-plugin" / "plugin.json").read_text(encoding="utf-8")
    )
    marketplace = GENERATOR.build_marketplace_json(
        [{"name": "clio-spack", "version": "2.0.0"}],
        pypi_version="2.3.0",
    )

    assert plugin["version"] == "2.0.0"
    assert marketplace["metadata"]["version"] == "2.3.0"
    assert marketplace["plugins"][0]["version"] == "2.0.0"


def test_bundle_membership_must_partition_the_shipped_servers() -> None:
    """A bundle catalogue that is not a partition is a catalogue with holes."""
    shipped = {"spack", "slurm", "hdf5"}

    # Exactly one bundle per server: the only accepted shape.
    GENERATOR.assert_bundles_partition_servers(
        {
            "clio-hpc": {"servers": ["slurm", "spack"]},
            "clio-scientific-io": {"servers": ["hdf5"]},
        },
        shipped,
    )

    # A server named by no bundle would publish outside the catalogue,
    # reachable only by someone who already knew it existed.
    with pytest.raises(ValueError, match=r"unplaced=\['hdf5'\]"):
        GENERATOR.assert_bundles_partition_servers(
            {"clio-hpc": {"servers": ["slurm", "spack"]}}, shipped
        )

    # A membership list naming a server that no longer ships is stale, and
    # would generate a bundle whose install resolves nothing.
    with pytest.raises(ValueError, match=r"unknown=\['geojson'\]"):
        GENERATOR.assert_bundles_partition_servers(
            {
                "clio-hpc": {"servers": ["slurm", "spack"]},
                "clio-geoscience": {"servers": ["geojson", "hdf5"]},
            },
            shipped,
        )

    # One server in two bundles makes "which workflow owns this" unanswerable.
    with pytest.raises(ValueError, match=r"duplicated=\['spack in clio-hpc"):
        GENERATOR.assert_bundles_partition_servers(
            {
                "clio-hpc": {"servers": ["slurm", "spack"]},
                "clio-scientific-io": {"servers": ["hdf5", "spack"]},
            },
            shipped,
        )


def test_bundles_depend_on_members_without_copying_them(tmp_path: Path) -> None:
    """A bundle carries a dependency list and nothing else executable."""
    entry = GENERATOR.write_bundle_plugin(
        tmp_path,
        "clio-hpc",
        {
            "version": "1.0.0",
            "description": "Run work on a cluster.",
            "servers": ["slurm", "spack"],
        },
    )
    manifest = json.loads(
        (
            tmp_path / "plugins" / "clio-hpc" / ".claude-plugin" / "plugin.json"
        ).read_text(encoding="utf-8")
    )

    assert manifest["dependencies"] == ["clio-slurm", "clio-spack"]
    # Bare names, not {"name": ..., "version": ...}: a constrained dependency
    # resolves against a `{plugin-name}--v{version}` git tag, which would mean
    # tagging every server plugin on every release for a pin nothing needs.
    assert all(isinstance(dep, str) for dep in manifest["dependencies"])
    # No components of its own -- the bundle must not restate what it bundles.
    assert not {"mcpServers", "skills", "commands", "agents", "hooks"} & set(manifest)
    assert entry["source"] == "./plugins/clio-hpc"


def test_shipped_bundle_catalogue_partitions_the_shipped_servers() -> None:
    """The committed bundle tables must cover this repository, not a fixture."""
    repo_root = Path(__file__).resolve().parents[1]
    bundles = GENERATOR.read_bundles(repo_root)
    shipped = {
        server_dir.name
        for server_dir in (repo_root / "clio-kit-mcp-servers").iterdir()
        if (server_dir / "pyproject.toml").exists()
    }

    GENERATOR.assert_bundles_partition_servers(bundles, shipped)


def test_skill_name_must_match_its_directory(tmp_path: Path) -> None:
    """A skill is namespaced by its directory but referred to by its name."""
    skill_dir = tmp_path / "running-a-simulation-on-a-cluster"
    skill_dir.mkdir()
    frontmatter = (
        "---\nname: {name}\ndescription: Does a thing. Use when asked.\n---\n\nBody.\n"
    )

    (skill_dir / "SKILL.md").write_text(
        frontmatter.format(name="running-a-simulation-on-a-cluster"), encoding="utf-8"
    )
    assert (
        read_skill_frontmatter(skill_dir)["name"] == "running-a-simulation-on-a-cluster"
    )

    # Disagreeing is a reference that resolves nowhere, so it must not ship.
    (skill_dir / "SKILL.md").write_text(
        frontmatter.format(name="running-on-a-cluster"), encoding="utf-8"
    )
    with pytest.raises(PluginProblem, match="but lives in"):
        read_skill_frontmatter(skill_dir)["name"]

    # A description is what decides whether the skill fires at all; without
    # one the skill costs tokens in every session and never triggers.
    (skill_dir / "SKILL.md").write_text(
        "---\nname: running-a-simulation-on-a-cluster\n---\n\nBody.\n", encoding="utf-8"
    )
    with pytest.raises(PluginProblem, match="needs a description"):
        read_skill_frontmatter(skill_dir)


def test_bundle_depends_on_its_skills_only_once_they_exist(tmp_path: Path) -> None:
    """Skills join a bundle by dependency, and only when actually written."""
    spec = {
        "version": "1.0.0",
        "description": "Run work on a cluster.",
        "servers": ["slurm", "spack"],
    }

    # No skills authored yet: the bundle still ships, servers only.
    assert GENERATOR.write_skills_plugin(tmp_path, "clio-hpc", spec) is None
    manifest_path = tmp_path / "plugins" / "clio-hpc" / ".claude-plugin" / "plugin.json"
    GENERATOR.write_bundle_plugin(tmp_path, "clio-hpc", spec)
    before = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert before["dependencies"] == ["clio-slurm", "clio-spack"]

    skill_dir = tmp_path / "skills" / "clio-hpc-skills" / "skills" / "sizing-a-request"
    skill_dir.mkdir(parents=True)
    (skill_dir / "SKILL.md").write_text(
        "---\nname: sizing-a-request\ndescription: Sizes a request. Use when asked.\n---\n\nBody.\n",
        encoding="utf-8",
    )

    # A skill with no recorded scenarios is untested by definition, so it must
    # not ship: it would cost tokens in every session with nothing showing it
    # earns them.
    with pytest.raises(ValueError, match="ships no evals.md"):
        GENERATOR.write_skills_plugin(tmp_path, "clio-hpc", spec)
    (skill_dir / "evals.md").write_text("# Evals\n\n## S1\n", encoding="utf-8")

    entry = GENERATOR.write_skills_plugin(tmp_path, "clio-hpc", spec)
    GENERATOR.write_bundle_plugin(tmp_path, "clio-hpc", spec)
    after = json.loads(manifest_path.read_text(encoding="utf-8"))

    assert entry is not None
    assert entry["source"] == "./skills/clio-hpc-skills"
    assert after["dependencies"] == ["clio-slurm", "clio-spack", "clio-hpc-skills"]
    # The skills are a dependency, never a path: a plugin's component paths
    # cannot leave its own directory, so a bundle pointing at a shared skills
    # folder would resolve to nothing once installed.
    assert "skills" not in after


def test_shipped_skills_load_and_are_reachable_from_a_bundle() -> None:
    """Every committed skill parses, and its plugin is depended on."""
    repo_root = Path(__file__).resolve().parents[1]
    skills_root = repo_root / "skills"
    if not skills_root.is_dir():
        pytest.skip("no skills shipped yet")

    for plugin_dir in sorted(skills_root.iterdir()):
        if not plugin_dir.is_dir():
            continue
        bundle_name = plugin_dir.name.removesuffix("-skills")
        bundle_manifest = json.loads(
            (
                repo_root / "plugins" / bundle_name / ".claude-plugin" / "plugin.json"
            ).read_text(encoding="utf-8")
        )
        assert plugin_dir.name in bundle_manifest["dependencies"]
        shipped = sorted(
            path for path in (plugin_dir / "skills").iterdir() if path.is_dir()
        )
        assert shipped, f"{plugin_dir} ships no skills"
        for skill_dir in shipped:
            assert read_skill_frontmatter(skill_dir)["name"] == skill_dir.name
            assert (skill_dir / "evals.md").is_file(), (
                f"{skill_dir} ships without recorded scenarios"
            )


def _write_community_entry(repo_root: Path, name: str, body: str) -> Path:
    entries = repo_root / "community" / "entries"
    entries.mkdir(parents=True, exist_ok=True)
    path = entries / f"{name}.toml"
    path.write_text(body, encoding="utf-8")
    return path


def test_community_entries_index_outside_repositories(tmp_path: Path) -> None:
    """An outside contribution is a pointer, not a copy of anything."""
    _write_community_entry(
        tmp_path,
        "materials-lab",
        'name = "materials-lab"\n'
        'description = "Crystal structure skills."\n'
        'category = "materials-science"\n'
        'maintainer = "some-lab"\n'
        'keywords = ["materials"]\n'
        "\n[source]\n"
        'type = "github"\n'
        'repo = "some-lab/materials-agent-skills"\n'
        'ref = "v1.2.0"\n',
    )
    # npm is what lets a TypeScript or Go plugin be listed without living here.
    _write_community_entry(
        tmp_path,
        "crystal-mcp",
        'name = "crystal-mcp"\n'
        'description = "A TypeScript MCP server."\n'
        "\n[source]\n"
        'type = "npm"\n'
        'package = "@acme/crystal-mcp"\n'
        'version = "^2.0.0"\n',
    )

    entries = read_community_entries(tmp_path)
    by_name = {entry["name"]: entry for entry in entries}

    assert by_name["materials-lab"]["source"] == {
        "source": "github",
        "repo": "some-lab/materials-agent-skills",
        "ref": "v1.2.0",
    }
    assert by_name["crystal-mcp"]["source"] == {
        "source": "npm",
        "package": "@acme/crystal-mcp",
        "version": "^2.0.0",
    }
    # A user should be able to see which entries are maintained here and which
    # are only pointed at.
    assert by_name["materials-lab"]["metadata"] == {
        "maintainer": "some-lab",
        "indexed": True,
    }


def test_community_entries_reject_shapes_that_would_publish_broken(
    tmp_path: Path,
) -> None:
    """The content is not ours, so the shape is checked hard."""
    entries_dir = tmp_path / "community" / "entries"

    # A name that disagrees with its filename makes the entry unfindable by
    # the file someone would edit to fix it.
    _write_community_entry(
        tmp_path,
        "materials-lab",
        'name = "materials"\ndescription = "x"\n\n[source]\ntype = "github"\nrepo = "a/b"\n',
    )
    with pytest.raises(ValueError, match="rename the file to match"):
        read_community_entries(tmp_path)

    # clio- is generated from this repository's own servers, bundles and
    # skills; an outside entry claiming it would shadow one of ours.
    _write_community_entry(
        tmp_path,
        "clio-materials",
        'name = "clio-materials"\ndescription = "x"\n\n[source]\ntype = "github"\nrepo = "a/b"\n',
    )
    (entries_dir / "materials-lab.toml").unlink()
    with pytest.raises(ValueError, match="may not claim the clio- prefix"):
        read_community_entries(tmp_path)
    (entries_dir / "clio-materials.toml").unlink()

    # A github source without a repo resolves to nothing at install time.
    _write_community_entry(
        tmp_path,
        "incomplete",
        'name = "incomplete"\ndescription = "x"\n\n[source]\ntype = "github"\n',
    )
    with pytest.raises(ValueError, match=r"needs \['repo'\]"):
        read_community_entries(tmp_path)

    # A field the source type does not use is a silent typo, not a no-op.
    _write_community_entry(
        tmp_path,
        "incomplete",
        'name = "incomplete"\ndescription = "x"\n\n[source]\ntype = "npm"\n'
        'package = "@a/b"\nrepo = "a/b"\n',
    )
    with pytest.raises(ValueError, match=r"unexpected fields: \['repo'\]"):
        read_community_entries(tmp_path)

    # A description is what a user reads before installing something we did
    # not write.
    _write_community_entry(
        tmp_path,
        "incomplete",
        'name = "incomplete"\n\n[source]\ntype = "github"\nrepo = "a/b"\n',
    )
    with pytest.raises(ValueError, match="needs a description"):
        read_community_entries(tmp_path)


def test_no_community_entries_is_a_valid_state(tmp_path: Path) -> None:
    """An empty index generates a marketplace of just our own plugins."""
    assert read_community_entries(tmp_path) == []
    (tmp_path / "community" / "entries").mkdir(parents=True)
    assert read_community_entries(tmp_path) == []


def test_every_shipped_server_resolves_to_exactly_one_published_scope() -> None:
    """Scope is total over the server inventory and defaults to scientific."""
    repo_root = Path(__file__).resolve().parents[1]
    versions = GENERATOR.read_server_versions(repo_root)
    scopes = GENERATOR.read_server_classification(repo_root, versions)

    assert set(scopes) == set(versions)
    assert set(scopes.values()) <= {"scientific", "general"}
    assert scopes["web"] == "general"
    assert scopes["hdf5"] == "scientific"


def test_classifying_an_unknown_server_fails_generation(tmp_path: Path) -> None:
    """A renamed or removed server cannot be left silently misclassified."""
    versions_file = tmp_path / GENERATOR.SERVER_VERSIONS_FILE
    versions_file.write_text(
        'schema-version = 1\n\n[classification]\ngeneral = ["ghost"]\n',
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="unknown servers: ghost"):
        GENERATOR.read_server_classification(tmp_path, {"web": "1.0.0"})


def test_general_classification_inventory_must_be_sorted(tmp_path: Path) -> None:
    """Deterministic manifests need a deterministic classification order."""
    versions_file = tmp_path / GENERATOR.SERVER_VERSIONS_FILE
    versions_file.write_text(
        'schema-version = 1\n\n[classification]\ngeneral = ["web", "compression"]\n',
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="must be sorted"):
        GENERATOR.read_server_classification(
            tmp_path, {"compression": "1.0.0", "web": "1.0.0"}
        )


def test_published_marketplace_categories_carry_real_scope() -> None:
    """The marketplace category distinguishes servers instead of a fixed literal."""
    repo_root = Path(__file__).resolve().parents[1]
    marketplace = json.loads(
        (repo_root / ".claude-plugin" / "marketplace.json").read_text(encoding="utf-8")
    )
    # The catalogue now also publishes workflow bundles and skill plugins, and
    # a scope classifies a SERVER. Split on source so this still checks what it
    # was written to check: that a server's category is its real scope rather
    # than one fixed literal for everything.
    server_entries = [
        plugin
        for plugin in marketplace["plugins"]
        if plugin["source"].startswith("./clio-kit-mcp-servers/")
    ]
    categories = {plugin["category"] for plugin in server_entries}

    assert categories == {"scientific", "general"}
    assert all(plugin["keywords"] for plugin in server_entries)


def test_readme_bundle_table_matches_the_generated_manifests() -> None:
    """Documented bundle membership must be the membership that ships.

    This table has drifted twice already, both times because it was written
    from the design rather than from the manifests, and once because a server
    merge changed membership underneath it. A reader has no way to tell a stale
    row from a current one, so it is checked rather than trusted.
    """
    repo_root = Path(__file__).resolve().parents[1]
    readme = (repo_root / "README.md").read_text(encoding="utf-8").splitlines()

    for bundle_dir in sorted((repo_root / "plugins").iterdir()):
        manifest = json.loads(
            (bundle_dir / ".claude-plugin" / "plugin.json").read_text(encoding="utf-8")
        )
        name = manifest["name"]
        shipped = sorted(
            dependency.removeprefix("clio-")
            for dependency in manifest["dependencies"]
            if not dependency.endswith("-skills")
        )
        rows = [line for line in readme if line.startswith(f"| `{name}`")]
        assert rows, f"README has no row for {name}"
        documented = sorted(cell.strip() for cell in rows[0].split("|")[2].split(","))
        assert documented == shipped, (
            f"{name}: README says {documented}, ships {shipped}"
        )


def test_readme_server_count_matches_the_shipped_inventory() -> None:
    """A count in prose is the first thing to go stale after a server merge."""
    repo_root = Path(__file__).resolve().parents[1]
    readme = (repo_root / "README.md").read_text(encoding="utf-8")
    shipped = len(list((repo_root / "clio-kit-mcp-servers").glob("*/pyproject.toml")))

    for claim in re.findall(r"(\d+) (?:available )?MCP servers", readme):
        assert int(claim) == shipped, f"README claims {claim} servers, {shipped} ship"
