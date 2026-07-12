"""Production invariants for the clio-kit release workflow."""

from __future__ import annotations

import re
from pathlib import Path


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = (REPOSITORY_ROOT / ".github" / "workflows" / "publish.yml").read_text(
    encoding="utf-8"
)


def test_external_actions_are_immutable_commit_pins() -> None:
    """Release jobs must not execute mutable third-party action tags."""
    uses = re.findall(r"^\s*uses:\s*([^\s#]+)", WORKFLOW, flags=re.MULTILINE)
    assert uses
    for action in uses:
        if action.startswith("./"):
            continue
        assert re.fullmatch(r"[^@]+@[0-9a-f]{40}", action), action


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


def test_wheel_smoke_exercises_normal_uvx_cache_materialization() -> None:
    """The release gate must cover the normal cached uvx artifact path."""
    start = WORKFLOW.index("    - name: Smoke installed root wheel")
    end = WORKFLOW.index("    - name: Attest release distributions", start)
    smoke_block = WORKFLOW[start:end]
    assert "clio-kit mcp-server spack -- --help" in smoke_block
    assert "clio-kit mcp-server jarvis -- --help" in smoke_block
    assert "--no-cache" not in smoke_block


def test_release_regenerates_and_smokes_shipped_user_contracts() -> None:
    """Release quality and wheel smoke bind the live locked-server contracts."""
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
    assert "clio-kit mcp-contracts" in smoke_block
    assert "clio-kit mcp-contract clio-kit-spack-user-v3" in smoke_block
    assert "clio-kit-jarvis-user-v3" in smoke_block
