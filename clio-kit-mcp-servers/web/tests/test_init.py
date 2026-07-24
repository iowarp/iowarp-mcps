"""Tests for package initialization and metadata."""

import web_mcp


class TestPackageMetadata:
    """Test package-level metadata and initialization."""

    def test_version_exists(self):
        """Test that package version is defined."""
        assert hasattr(web_mcp, "__version__")

    def test_version_format(self):
        """Test that version follows semantic versioning format."""
        version = web_mcp.__version__
        assert isinstance(version, str)
        assert len(version.split(".")) == 3

    def test_version_value(self):
        """Test that version has expected value."""
        assert web_mcp.__version__ == "1.0.0"

    def test_docstring_exists(self):
        """Test that package has a docstring."""
        assert web_mcp.__doc__ is not None
        assert len(web_mcp.__doc__) > 0
