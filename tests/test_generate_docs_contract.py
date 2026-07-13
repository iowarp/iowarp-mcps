"""Regression tests for generated MCP site contract metadata."""

import importlib.util
import json
import re
from pathlib import Path
from types import ModuleType

import pytest


def _load_generator() -> ModuleType:
    path = Path(__file__).resolve().parents[1] / "scripts" / "generate_docs.py"
    spec = importlib.util.spec_from_file_location("clio_kit_generate_docs", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"could not load documentation generator: {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


GENERATOR = _load_generator()
DocusaurusGenerator = GENERATOR.DocusaurusGenerator


def test_generated_page_replaces_stale_description(tmp_path: Path) -> None:
    """A contract upgrade must not preserve an old generated description."""
    server = tmp_path / "server"
    server.mkdir()
    (server / "README.md").write_text("# Slurm\n", encoding="utf-8")
    output = tmp_path / "site"
    page = output / "docs" / "mcps" / "slurm.md"
    page.parent.mkdir(parents=True)
    page.write_text(
        '<MCPDetail description="stale v1 description" />\n', encoding="utf-8"
    )

    DocusaurusGenerator(output)._generate_mcp_markdown(
        {
            "name": "Slurm",
            "slug": "slurm",
            "category": "System Management",
            "description": "Fresh v3 agent contract",
            "icon": "scheduler",
            "version": "3.0.0",
            "actions": ["slurm_submit"],
            "platforms": ["claude"],
            "keywords": ["slurm"],
            "license": "BSD-3-Clause",
            "tools": [{"name": "slurm_submit", "description": "Submit one job."}],
            "path": str(server),
        }
    )

    rendered = page.read_text(encoding="utf-8")
    assert 'description="Fresh v3 agent contract"' in rendered
    assert "stale v1 description" not in rendered
    assert 'actions={["slurm_submit"]}' in rendered


def test_showcase_generation_is_deterministic_and_keeps_non_mcp_tile(
    tmp_path: Path,
) -> None:
    """Clean and incremental generation produce identical complete showcase data."""
    server = tmp_path / "server"
    server.mkdir()
    source_data = {
        "spack": {
            "name": "Spack",
            "slug": "spack",
            "category": "System Management",
            "description": "Authoritative Spack description",
            "icon": "packages",
            "version": "2.0.1",
            "updated": "2026-07-13",
            "actions": ["spack_install"],
            "platforms": ["claude"],
            "keywords": ["spack"],
            "license": "BSD-3-Clause",
            "tools": [{"name": "spack_install", "description": "Install."}],
            "path": str(server),
        }
    }
    incremental = tmp_path / "incremental"
    stale_data = incremental / "src" / "data"
    stale_data.mkdir(parents=True)
    (stale_data / "mcpData.js").write_text(
        'export const mcpData = {"spack":{"description":"stale"}};\n',
        encoding="utf-8",
    )
    clean = tmp_path / "clean"

    DocusaurusGenerator(incremental).generate_all_docs(source_data)
    DocusaurusGenerator(clean).generate_all_docs(source_data)

    incremental_output = (incremental / "src" / "data" / "mcpData.js").read_text(
        encoding="utf-8"
    )
    clean_output = (clean / "src" / "data" / "mcpData.js").read_text(encoding="utf-8")
    assert incremental_output == clean_output
    match = re.search(r"export const mcpData = ({.*?});", clean_output, re.DOTALL)
    assert match is not None
    showcase = json.loads(match.group(1))
    assert showcase["agentic_search"]["docPath"] == "/docs/agentic-search"
    assert showcase["spack"]["description"] == "Authoritative Spack description"
    assert showcase["spack"]["stats"]["updated"] == "2026-07-13"


@pytest.mark.parametrize("value", [None, "2026-7-13", "not-a-date"])
def test_documentation_date_must_be_explicit_and_canonical(value: object) -> None:
    """Wall-clock fallback cannot make generated docs drift between runs."""
    inventory = {"documentation": {"updated": value}}

    with pytest.raises(ValueError, match="documentation.updated"):
        GENERATOR.read_documentation_updated(inventory)
