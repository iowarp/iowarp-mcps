import pytest
import os
import tempfile

from fastmcp.exceptions import ToolError
from compression_mcp.mcp_handlers import compress_file_handler


@pytest.fixture
def sample_file():
    # create a temporary file with some content
    with tempfile.NamedTemporaryFile(mode="w", delete=False) as f:
        f.write("test content\n" * 100)
    yield f.name
    os.unlink(f.name)


@pytest.mark.asyncio
async def test_compress_file_handler_success(sample_file):
    """Test successful compression through MCP handler."""
    result = await compress_file_handler(sample_file)
    assert isinstance(result, dict)
    assert result["original_file"] == sample_file
    assert result["compressed_size"] > 0
    assert os.path.exists(result["compressed_file"])
    os.unlink(result["compressed_file"])


@pytest.mark.asyncio
async def test_compress_file_handler_error():
    """Test error handling in MCP handler raises ToolError."""
    with pytest.raises(ToolError, match="File not found"):
        await compress_file_handler("nonexistent_file.txt")
