"""Tests for package initialization and metadata."""

import ndp_mcp


class TestPackageMetadata:
    """Test package-level metadata and initialization."""

    def test_version_exists(self):
        """Test that package version is defined."""
        assert hasattr(ndp_mcp, "__version__")

    def test_version_format(self):
        """Test that version follows semantic versioning format."""
        version = ndp_mcp.__version__
        assert isinstance(version, str)
        assert len(version.split(".")) == 3

    def test_version_value(self):
        """Test that version has expected value."""
        assert ndp_mcp.__version__ == "1.0.0"

    def test_docstring_exists(self):
        """Test that package has a docstring."""
        assert ndp_mcp.__doc__ is not None
        assert len(ndp_mcp.__doc__) > 0

    def test_docstring_content(self):
        """Test that docstring mentions NDP."""
        assert "National Data Platform" in ndp_mcp.__doc__ or "NDP" in ndp_mcp.__doc__
        assert "MCP" in ndp_mcp.__doc__
