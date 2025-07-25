import pytest
import json
import os
import tempfile
from server import mcp


@pytest.fixture
def sample_file():
    # create a temporary file with some content
    with tempfile.NamedTemporaryFile(mode='w', delete=False) as f:
        f.write("test content for integration testing\n" * 50)
    yield f.name
    if os.path.exists(f.name):
        os.unlink(f.name)
    if os.path.exists(f.name + '.gz'):
        os.unlink(f.name + '.gz')


@pytest.mark.asyncio
async def test_compress_file_tool(sample_file):
    """Test the MCP tool integration through the handler"""
    from mcp_handlers import compress_file_handler
    
    # Call the handler directly (which is what the MCP tool would call)
    result = await compress_file_handler(sample_file)
    
    assert isinstance(result, dict)
    assert result["isError"] == False
    assert result["_meta"]["tool"] == "compress_file"
    assert os.path.exists(result["_meta"]["compressed_file"])


def test_mcp_server_initialization():
    """Test that the MCP server initializes correctly"""
    assert mcp.name == "CompressionMCP"
    # Test that the server object exists and has the correct name
    # We can't easily access internal FastMCP structure, so just verify basic properties