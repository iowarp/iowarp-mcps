"""Regression tests for generated MCP site contract metadata."""

import importlib.util
from pathlib import Path
from types import ModuleType


def _load_generator() -> ModuleType:
    path = Path(__file__).resolve().parents[1] / "scripts" / "generate_docs.py"
    spec = importlib.util.spec_from_file_location("clio_kit_generate_docs", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"could not load documentation generator: {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


DocusaurusGenerator = _load_generator().DocusaurusGenerator


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
