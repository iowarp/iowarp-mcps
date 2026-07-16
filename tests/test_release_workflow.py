"""Production invariants for the clio-kit release workflow."""

from __future__ import annotations

import argparse
import re
import runpy
import tomllib
from pathlib import Path

import pytest


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = (REPOSITORY_ROOT / ".github" / "workflows" / "publish.yml").read_text(
    encoding="utf-8"
)
QUALITY_WORKFLOW = (
    REPOSITORY_ROOT / ".github" / "workflows" / "quality_control.yml"
).read_text(encoding="utf-8")
EXPECTED_JARVIS_RELEASE_URL = (
    "https://github.com/grc-iit/jarvis-cd/releases/download/v1.3.2/"
    "jarvis_cd-1.3.2-py3-none-any.whl"
)
EXPECTED_JARVIS_RELEASE_SHA256 = (
    "2e5c994b1b21caf44eecb62c1d631c5ce3886d9282549589520c1d9b49961277"
)


def test_external_actions_are_immutable_commit_pins() -> None:
    """Release and quality jobs must not execute mutable action tags."""
    for workflow in (WORKFLOW, QUALITY_WORKFLOW):
        uses = re.findall(r"^\s*uses:\s*([^\s#]+)", workflow, flags=re.MULTILINE)
        assert uses
        for action in uses:
            if action.startswith("./"):
                continue
            assert re.fullmatch(r"[^@]+@[0-9a-f]{40}", action), action


def test_release_workflow_triggers_on_every_shipped_lock() -> None:
    """Root and embedded search lock drift must run release validation."""
    pull_request_paths = WORKFLOW[
        WORKFLOW.index("  pull_request:") : WORKFLOW.index("  push:")
    ]
    push_paths = WORKFLOW[WORKFLOW.index("  push:") : WORKFLOW.index("permissions:")]
    for paths in (pull_request_paths, push_paths):
        assert "- 'uv.lock'" in paths
        assert "- 'clio-agentic-search/uv.lock'" in paths
        assert "- 'mcp-server-versions.toml'" in paths

    quality_block = WORKFLOW[WORKFLOW.index("  quality:") : WORKFLOW.index("  build:")]
    assert "uv lock --check\n" in quality_block
    assert "uv lock --check --directory clio-agentic-search" in quality_block


def test_release_security_audits_unmatrixed_shipped_environments() -> None:
    """Release validation audits shipped environments outside the MCP matrix."""
    quality_block = WORKFLOW[WORKFLOW.index("  quality:") : WORKFLOW.index("  build:")]
    assert "uv run --with 'pip-audit==2.10.1' pip-audit" in quality_block
    assert (
        "uv run --directory clio-agentic-search \\\n"
        "          --with 'pip-audit==2.10.1' pip-audit" in quality_block
    )
    assert (
        "uv run --directory clio-kit-mcp-servers/chronolog \\\n"
        "          --with 'pip-audit==2.10.1' pip-audit" in quality_block
    )
    assert (
        'uv run --directory "clio-kit-mcp-servers/$server" \\\n'
        "            --with 'pip-audit==2.10.1' pip-audit" in quality_block
    )


def test_testpypi_advisory_publish_path_is_removed() -> None:
    """Only exact-verified production tags may publish package bytes."""
    assert "publish-to-testpypi:" not in WORKFLOW
    assert "TestPyPI" not in WORKFLOW
    assert "test.pypi.org" not in WORKFLOW
    assert "continue-on-error" not in WORKFLOW
    assert "  publish-to-pypi:" in WORKFLOW
    assert "Verify exact published PyPI bytes" in WORKFLOW


def test_release_pytest_reports_reject_skipped_tests() -> None:
    """Every release JUnit report is followed by the zero-skip assertion."""
    assert WORKFLOW.count("--junitxml=") == 4
    assert WORKFLOW.count("scripts/assert_no_skipped_tests.py") == 4


def test_admin_release_authorization_gates_pypi() -> None:
    """PyPI publication requires fresh admin-controlled authorization."""
    pypi_index = WORKFLOW.index("  publish-to-pypi:")
    assert "CLIO_KIT_RELEASE_AUTHORIZATION" in WORKFLOW
    assert "secrets.CLIO_KIT_RELEASE_AUTHORIZATION" in WORKFLOW
    assert "vars.CLIO_KIT_RELEASE_AUTHORIZATION" not in WORKFLOW
    assert "/immutable-releases" not in WORKFLOW
    publish_block = WORKFLOW[pypi_index : WORKFLOW.index("  github-release:")]
    authorization_index = publish_block.index(
        "Require fresh exact admin authorization at publication"
    )
    upload_index = publish_block.index("pypa/gh-action-pypi-publish@")
    assert "      name: pypi" in publish_block
    assert "python scripts/release_authorization.py" in publish_block
    assert '--repository "$REPOSITORY"' in publish_block
    assert '--tag "$TAG_NAME"' in publish_block
    assert '--commit "$GITHUB_SHA"' in publish_block
    assert "--max-age-seconds 3600 >/dev/null" in publish_block
    assert authorization_index < upload_index


def test_release_recovery_is_exact_byte_and_fail_closed() -> None:
    """Reruns may reuse exact files, but never overwrite or accept mismatches."""
    assert "SOURCE_DATE_EPOCH" in WORKFLOW
    assert "skip-existing: true" in WORKFLOW
    assert "scripts/verify_pypi_release.py" in WORKFLOW
    assert "cmp --silent" in WORKFLOW
    assert "load_and_verify_assets false" in WORKFLOW
    assert "--clobber" not in WORKFLOW


def test_draft_release_is_resolved_and_mutated_only_by_exact_id() -> None:
    """Draft recovery must not use the published-release tag endpoint."""
    release_block = WORKFLOW[
        WORKFLOW.index("  github-release:") : WORKFLOW.index(
            "  publish-to-mcp-registry:"
        )
    ]
    create_index = release_block.index('gh release create "$TAG_NAME"')
    publish_index = release_block.index("gh api --method PATCH", create_index)
    final_fetch_index = release_block.index("fetch_published_release", publish_index)

    assert "resolve_exact_draft_release()" in release_block
    assert '"repos/$REPOSITORY/releases?per_page=100"' in release_block
    assert "--paginate" in release_block
    assert "expected one draft release" in release_block
    assert "fetch_release_by_id()" in release_block
    assert '"repos/$REPOSITORY/releases/$release_id"' in release_block
    assert "verify_release_identity || return" in release_block
    assert (
        '"https://uploads.github.com/repos/$REPOSITORY/releases/'
        '$release_id/assets?name=$encoded_name"' in release_block
    )
    assert '"repos/$REPOSITORY/releases/generate-notes"' in release_block
    assert '"$(jq -r .author.login "$release_json")"' in release_block
    assert "'github-actions[bot]' || return" in release_block
    assert "{name: $name, body: $notes[0].body, draft: false}" in release_block
    assert '--input "$publish_payload"' in release_block
    assert "gh release upload" not in release_block
    assert "gh release edit" not in release_block
    assert release_block.count("repos/$REPOSITORY/releases/tags/$TAG_NAME") == 1
    assert release_block.count("fetch_published_release") == 3
    assert "fetch_published_release" not in release_block[create_index:publish_index]
    assert publish_index < final_fetch_index


def test_new_draft_release_waits_for_bounded_list_consistency() -> None:
    """A newly created draft may take time to appear in the list endpoint."""
    release_block = WORKFLOW[
        WORKFLOW.index("  github-release:") : WORKFLOW.index(
            "  publish-to-mcp-registry:"
        )
    ]
    create_index = release_block.index('gh release create "$TAG_NAME"')
    wait_index = release_block.index("wait_for_exact_draft_release", create_index)

    assert "wait_for_exact_draft_release()" in release_block
    assert "for attempt in {1..12}; do" in release_block
    assert "if resolve_exact_draft_release; then" in release_block
    assert 'else\n              status="$?"' in release_block
    assert 'if [ "$status" -ne 1 ]; then' in release_block
    assert "sleep 5" in release_block
    assert "did not become list-visible after 12 attempts" in release_block
    assert release_block.count('gh release create "$TAG_NAME"') == 1
    assert create_index < wait_index


def test_pypi_verification_uses_pre_publish_immutable_copies() -> None:
    """Publisher-generated sidecars must not contaminate exact-byte discovery."""
    publish_block = WORKFLOW[
        WORKFLOW.index("  publish-to-pypi:") : WORKFLOW.index("  github-release:")
    ]
    stage_index = publish_block.index(
        "Stage immutable copies for post-publish verification"
    )
    upload_index = publish_block.index("pypa/gh-action-pypi-publish@")
    verify_index = publish_block.index("Verify exact published PyPI bytes")

    assert stage_index < upload_index < verify_index
    assert "mkdir verification-dist" in publish_block
    assert "cmp --silent" in publish_block
    assert "--dist-dir verification-dist" in publish_block


def test_final_release_requires_attestation_and_immutability() -> None:
    """Publishing remains gated by provenance, immutable state, and release verification."""
    assert "gh attestation verify" in WORKFLOW
    assert "--deny-self-hosted-runners" in WORKFLOW
    assert 'test "$(jq -r .immutable "$release_json")" = true' in WORKFLOW
    assert 'gh release verify "$TAG_NAME"' in WORKFLOW
    registry_block = WORKFLOW[WORKFLOW.index("  publish-to-mcp-registry:") :]
    assert "    - github-release" in registry_block


def test_registry_duplicate_versions_require_exact_live_verification() -> None:
    """A duplicate response succeeds only for the exact active registry record."""
    registry_block = WORKFLOW[WORKFLOW.index("  publish-to-mcp-registry:") :]
    assert "scripts/verify_mcp_registry_release.py" in registry_block
    assert '--manifest "$server_dir/server.json"' in registry_block
    assert "--timeout 60" in registry_block
    assert "publish_result=duplicate" in registry_block
    duplicate_index = registry_block.index("publish_result=duplicate")
    verify_index = registry_block.index("scripts/verify_mcp_registry_release.py")
    skipped_index = registry_block.index("SKIPPED=$((SKIPPED + 1))")
    assert duplicate_index < verify_index < skipped_index
    assert "Registry state does not exactly match" in registry_block


def test_registry_publishes_only_contracts_versioned_for_this_release() -> None:
    """Unchanged immutable Registry versions must not be republished."""
    registry_block = WORKFLOW[WORKFLOW.index("  publish-to-mcp-registry:") :]
    assert 'Path("mcp-server-versions.toml")' in registry_block
    assert 'data["mcp-registry-release"]["publish"]' in registry_block
    assert 'for server_name in "${release_servers[@]}"' in registry_block
    assert "clio-kit-mcp-servers/*/" not in registry_block


def test_wheel_smoke_exercises_persistent_uv_tool_installation() -> None:
    """The release gate must cover the supported persistent tool path."""
    start = WORKFLOW.index("    - name: Smoke installed root wheel")
    end = WORKFLOW.index("    - name: Attest release distributions", start)
    smoke_block = WORKFLOW[start:end]
    assert '"$clio_kit" mcp-server spack -- --help' in smoke_block
    assert '"$clio_kit" mcp-server jarvis -- --help' in smoke_block
    assert '"$clio_kit" mcp-server slurm -- --help' in smoke_block
    assert 'uv tool install --no-cache "$wheel"' in smoke_block
    assert "UV_TOOL_DIR" in smoke_block
    assert "UV_TOOL_BIN_DIR" in smoke_block
    assert 'export CLIO_KIT_CACHE_DIR="$child_cache"' in smoke_block
    assert smoke_block.count('"$clio_kit"') >= 2
    assert "locked_server_project_identity" in smoke_block
    assert "locked_server_environment" in smoke_block
    assert 'test "$reused_spack_environment" = "$spack_environment"' in smoke_block
    assert 'test "$second_child_identity" = "$first_child_identity"' in smoke_block
    assert "uvx" not in smoke_block


def test_ares_probe_exercises_persistent_uv_tool_installation() -> None:
    """Live Ares acceptance must use the same supported persistent tool path."""
    probe = (
        REPOSITORY_ROOT
        / "clio-kit-mcp-servers"
        / "jarvis"
        / "scripts"
        / "live_ares_semantic_mcp_probe.py"
    ).read_text(encoding="utf-8")
    probe_module = runpy.run_path(
        str(
            REPOSITORY_ROOT
            / "clio-kit-mcp-servers"
            / "jarvis"
            / "scripts"
            / "live_ares_semantic_mcp_probe.py"
        )
    )
    assert '[uv, "tool", "install", "--force", "--no-cache", wheel]' in probe
    assert '"UV_TOOL_DIR"' in probe
    assert '"UV_TOOL_BIN_DIR"' in probe
    assert '"UV_CACHE_DIR"' in probe
    assert '"CLIO_KIT_CACHE_DIR"' in probe
    assert "env.pop(inherited_name, None)" in probe
    assert '"PYTHONPATH"' in probe
    assert '"VIRTUAL_ENV"' in probe
    assert 'base_cmd = [str(clio_kit), "mcp-server", "jarvis"]' in probe
    assert 'server_args = ["--spack-command", str(spack_command)]' in probe
    assert '"--spack-command",' in probe
    assert '"spack_command": str(spack_command)' in probe
    assert 'env["JARVIS_ROOT"] = str(jarvis_root)' in probe
    assert '"jarvis_root": str(jarvis_root)' in probe
    assert '"locked_jarvis": locked_jarvis' in probe
    assert 'assert "%" not in log_path.name' in probe
    assert "assert log_path.is_file()" in probe
    assert probe_module["EXPECTED_JARVIS_VERSION"] == "1.3.2"
    assert probe_module["EXPECTED_JARVIS_URL"] == EXPECTED_JARVIS_RELEASE_URL
    assert probe_module["EXPECTED_JARVIS_SHA256"] == EXPECTED_JARVIS_RELEASE_SHA256
    assert "uvx" not in probe


def test_ares_probe_validates_explicit_spack_command(tmp_path: Path) -> None:
    """Live validation must bind its Spack semantics to an executable path."""
    probe_module = runpy.run_path(
        str(
            REPOSITORY_ROOT
            / "clio-kit-mcp-servers"
            / "jarvis"
            / "scripts"
            / "live_ares_semantic_mcp_probe.py"
        )
    )
    validate = probe_module["_spack_command_path"]
    command = tmp_path / "spack"
    command.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
    command.chmod(0o700)

    assert validate(str(command)) == command.resolve()
    with pytest.raises(argparse.ArgumentTypeError, match="does not exist"):
        validate(str(tmp_path / "missing-spack"))


def test_wheel_smoke_binds_jarvis_artifacts_to_exact_release_wheel() -> None:
    """The installed JARVIS child must expose artifacts from the locked release."""
    jarvis_project = tomllib.loads(
        (
            REPOSITORY_ROOT / "clio-kit-mcp-servers" / "jarvis" / "pyproject.toml"
        ).read_text(encoding="utf-8")
    )
    dependency = next(
        value
        for value in jarvis_project["project"]["dependencies"]
        if value.startswith("jarvis-cd @ ")
    )
    match = re.fullmatch(
        r"jarvis-cd @ "
        r"(https://github\.com/grc-iit/jarvis-cd/releases/download/v1\.3\.2/"
        r"jarvis_cd-1\.3\.2-py3-none-any\.whl)"
        r"#sha256=([0-9a-f]{64})",
        dependency,
    )
    assert match is not None
    expected_url, expected_digest = match.groups()
    jarvis_lock = tomllib.loads(
        (REPOSITORY_ROOT / "clio-kit-mcp-servers" / "jarvis" / "uv.lock").read_text(
            encoding="utf-8"
        )
    )
    jarvis_package = next(
        package for package in jarvis_lock["package"] if package["name"] == "jarvis-cd"
    )
    assert jarvis_package["version"] == "1.3.2"
    assert jarvis_package["source"] == {"url": expected_url}
    assert jarvis_package["wheels"] == [
        {"url": expected_url, "hash": f"sha256:{expected_digest}"}
    ]

    start = WORKFLOW.index("    - name: Smoke installed root wheel")
    end = WORKFLOW.index("    - name: Attest release distributions", start)
    smoke_block = WORKFLOW[start:end]
    assert "mcp-contract clio-kit-jarvis-user-v3.1" in smoke_block
    assert '"jarvis_get_execution"' in smoke_block
    assert '"jarvis_get_execution_progress"' not in smoke_block
    assert '"jarvis_get_execution_artifacts"' not in smoke_block
    assert 'get_servers_path() / "jarvis"' in smoke_block
    assert 'distribution("jarvis-cd")' in smoke_block
    assert 'installed.version == "1.3.2"' in smoke_block
    assert expected_url in smoke_block
    assert expected_digest in smoke_block
    assert "expected_requirement in project" in smoke_block
    assert 'package["name"] == "jarvis-cd"' in smoke_block
    assert 'jarvis_package["version"] == "1.3.2"' in smoke_block
    assert 'jarvis_package["source"] == {"url": expected_url}' in smoke_block
    assert '"hash": f"sha256:{expected_digest}"' in smoke_block
    assert 'installed.read_text("direct_url.json")' in smoke_block
    assert 'direct_url["url"] == expected_url' in smoke_block
    assert 'getattr(Pipeline, "get_execution_artifacts", None)' in smoke_block
    assert "pipeline_source.is_relative_to(Path(sys.prefix).resolve())" in smoke_block


def test_release_regenerates_and_smokes_shipped_user_contracts() -> None:
    """Release quality and wheel smoke bind the live locked-server contracts."""
    quality_block = WORKFLOW[WORKFLOW.index("  quality:") : WORKFLOW.index("  build:")]
    assert "for server in jarvis scientific-catalog slurm spack; do" in quality_block

    generation_start = WORKFLOW.index(
        "    - name: Regenerate and verify deterministic publishing manifests"
    )
    generation_end = WORKFLOW.index(
        "    - name: Build every root-wheel server package",
        generation_start,
    )
    generation_block = WORKFLOW[generation_start:generation_end]
    assert "scripts/generate_server_json.py" in generation_block
    assert "src/clio_kit/_mcp_contracts" in generation_block

    smoke_start = WORKFLOW.index("    - name: Smoke installed root wheel")
    smoke_end = WORKFLOW.index(
        "    - name: Attest release distributions",
        smoke_start,
    )
    smoke_block = WORKFLOW[smoke_start:smoke_end]
    assert '"$clio_kit" mcp-contracts' in smoke_block
    assert "mcp-contract clio-kit-jarvis-user-v3.1" in smoke_block
    assert "mcp-contract clio-kit-jarvis-user-v3" in smoke_block
    assert "mcp-contract clio-kit-scientific-catalog-user-v1" in smoke_block
    assert "mcp-contract clio-kit-slurm-user-v3" in smoke_block
    assert "mcp-contract clio-kit-spack-user-v2" in smoke_block
    assert "clio-kit-jarvis-user-v3.1" in smoke_block


def test_quality_matrix_is_required_and_lock_sensitive() -> None:
    """Types and all declared supported test lanes are blocking checks."""
    assert "continue-on-error" not in QUALITY_WORKFLOW
    infrastructure_check = QUALITY_WORKFLOW[
        QUALITY_WORKFLOW.index('if [ "$RUN_ALL" = "false" ]') : QUALITY_WORKFLOW.index(
            'echo "Run all: $RUN_ALL"'
        )
    ]
    assert "uv\\.lock$" in infrastructure_check
    assert "mcp-server-versions\\.toml$" in infrastructure_check
    assert "clio-agentic-search/uv\\.lock$" in infrastructure_check
    assert 'python-version: ["3.10", "3.11", "3.12"]' in QUALITY_WORKFLOW
    assert 'python-version: ["3.11", "3.12"]' in QUALITY_WORKFLOW
    assert "uv lock --check" in QUALITY_WORKFLOW
    assert QUALITY_WORKFLOW.count("uv sync --locked --dev") == 3


def test_quality_junit_reports_reject_skipped_tests() -> None:
    """Upgraded MCPs, Windows containment, and search reject test skips."""
    assert QUALITY_WORKFLOW.count("--junitxml=") == 3
    assert QUALITY_WORKFLOW.count("scripts/assert_no_skipped_tests.py") == 3
    assert 'case "${{ matrix.mcp }}" in' in QUALITY_WORKFLOW
    assert "jarvis|slurm|spack)" in QUALITY_WORKFLOW
