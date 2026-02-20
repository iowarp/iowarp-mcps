import pytest
import os
import tempfile

from compression_mcp.server import mcp


@pytest.fixture
def sample_file():
    # create a temporary file with some content
    with tempfile.NamedTemporaryFile(mode="w", delete=False) as f:
        f.write("test content for integration testing\n" * 50)
    yield f.name
    if os.path.exists(f.name):
        os.unlink(f.name)
    if os.path.exists(f.name + ".gz"):
        os.unlink(f.name + ".gz")


@pytest.mark.asyncio
async def test_compress_file_tool(sample_file):
    """Test the MCP tool integration through the handler."""
    from compression_mcp.mcp_handlers import compress_file_handler

    result = await compress_file_handler(sample_file)

    assert isinstance(result, dict)
    assert result["original_file"] == sample_file
    assert os.path.exists(result["compressed_file"])


def test_mcp_server_initialization():
    """Test that the MCP server initializes correctly."""
    assert mcp.name == "compression"
