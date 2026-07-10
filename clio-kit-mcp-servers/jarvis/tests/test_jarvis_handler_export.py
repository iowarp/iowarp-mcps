"""Tests for JARVIS pipeline export helpers."""

from __future__ import annotations

import pytest

from jarvis_mcp.capabilities.jarvis_handler import export_pipeline


@pytest.mark.asyncio
async def test_export_pipeline_returns_structured_snapshot(mock_pipeline):
    """Export returns pipeline metadata, environment, and package configs."""
    result = await export_pipeline("test_pipeline", include_yaml=False)

    assert result["pipeline_id"] == "test_pipeline"
    assert result["config_path"].endswith("test_pipeline.yaml")
    assert result["env"] == {"PATH": "/usr/bin"}
    assert result["config"] == {"sub_pkgs": [["builtin.lammps", "lammps"]]}
    assert result["packages"] == [
        {
            "pkg_id": "lammps",
            "pkg_type": "builtin.lammps",
            "global_id": "test_pipeline.lammps",
            "config_path": "/tmp/jarvis-config/test_pipeline/lammps/lammps.yaml",
            "config": {"test_config": "test_value"},
        }
    ]
    mock_pipeline.load.assert_called_once_with("test_pipeline")


@pytest.mark.asyncio
async def test_export_pipeline_includes_source_yaml_when_recorded(
    tmp_path, mock_pipeline
):
    """Export includes YAML text when the loaded pipeline records a source YAML path."""
    pipeline_yaml = tmp_path / "pipeline.yaml"
    pipeline_yaml.write_text("name: test_pipeline\npkgs: []\n", encoding="utf-8")
    mock_pipeline.config["JARVIS_YAML_PATH"] = str(pipeline_yaml)

    result = await export_pipeline("test_pipeline")

    assert result["yaml_path"] == str(pipeline_yaml)
    assert result["pipeline_yaml"] == "name: test_pipeline\npkgs: []\n"
