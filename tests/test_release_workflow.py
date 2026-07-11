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


def test_immutable_release_preflight_precedes_pypi() -> None:
    """PyPI publication depends on the repository immutability capability check."""
    preflight_index = WORKFLOW.index("  release-preflight:")
    pypi_index = WORKFLOW.index("  publish-to-pypi:")
    assert preflight_index < pypi_index
    assert 'gh api "repos/$REPOSITORY/immutable-releases" --jq .enabled' in WORKFLOW
    publish_block = WORKFLOW[pypi_index : WORKFLOW.index("  github-release:")]
    assert "    - release-preflight" in publish_block


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
