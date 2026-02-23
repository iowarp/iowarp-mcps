"""
Tests for the main package __init__.py file.
"""

import slurm_mcp


def test_package_metadata():
    """Test that package metadata is accessible."""
    assert hasattr(slurm_mcp, "__version__")
    assert hasattr(slurm_mcp, "__author__")
    assert slurm_mcp.__version__ == "1.0.0"
    assert slurm_mcp.__author__ == "IoWarp Scientific MCPs"


def test_package_docstring():
    """Test that package has a docstring."""
    assert slurm_mcp.__doc__ is not None
    assert "Slurm MCP Server" in slurm_mcp.__doc__
    assert "Model Context Protocol" in slurm_mcp.__doc__
