"""Production invariants for the clio-kit release workflow."""

from __future__ import annotations

import re
from pathlib import Path


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = (REPOSITORY_ROOT / ".github" / "workflows" / "publish.yml").read_text(
    encoding="utf-8"
)
QUALITY_WORKFLOW = (
    REPOSITORY_ROOT / ".github" / "workflows" / "quality_control.yml"
).read_text(encoding="utf-8")


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


def test_release_regenerates_and_smokes_shipped_user_contracts() -> None:
    """Release quality and wheel smoke bind the live locked-server contracts."""
    quality_block = WORKFLOW[WORKFLOW.index("  quality:") : WORKFLOW.index("  build:")]
    assert "for server in jarvis slurm spack; do" in quality_block

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
    assert "mcp-contract clio-kit-slurm-user-v3" in smoke_block
    assert "mcp-contract clio-kit-spack-user-v2" in smoke_block
    assert "clio-kit-jarvis-user-v3" in smoke_block


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
