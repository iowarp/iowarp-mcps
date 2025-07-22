import pytest
import os
import tempfile
from mcp_handlers import compress_file_handler


@pytest.fixture
def sample_file():
    # create a temporary file with some content
    with tempfile.NamedTemporaryFile(mode='w', delete=False) as f:
        f.write("test content\n" * 100)
    yield f.name
    os.unlink(f.name)


@pytest.mark.asyncio
async def test_compress_file_handler_success(sample_file):
    """Test successful compression through MCP handler"""
    result = await compress_file_handler(sample_file)
    assert isinstance(result, dict)
    assert result["isError"] == False
    assert result["_meta"]["tool"] == "compress_file"
    assert "compressed successfully" in result["content"][0]["text"]
    assert os.path.exists(result["_meta"]["compressed_file"])
    os.unlink(result["_meta"]["compressed_file"])


@pytest.mark.asyncio
async def test_compress_file_handler_error():
    """Test error handling in MCP handler"""
    result = await compress_file_handler("nonexistent_file.txt")
    assert isinstance(result, dict)
    assert result["isError"] == True
    assert result["_meta"]["tool"] == "compress_file"
    assert "error" in result["_meta"]
    assert "File not found" in result["content"][0]["text"]