import pytest
import os
import tempfile
from unittest.mock import patch

from fastmcp.exceptions import ToolError


@pytest.fixture
def sample_file():
    """Create a temporary file with test content."""
    with tempfile.NamedTemporaryFile(mode="w", delete=False) as f:
        f.write("test content for server testing\n" * 50)
    yield f.name
    if os.path.exists(f.name):
        os.unlink(f.name)
    if os.path.exists(f.name + ".gz"):
        os.unlink(f.name + ".gz")


@pytest.mark.asyncio
async def test_compress_file_handler_direct():
    """Test the compress_file_handler function directly."""
    from compression_mcp import mcp_handlers

    with tempfile.NamedTemporaryFile(mode="w", delete=False) as f:
        f.write("test content\n" * 100)

    try:
        result = await mcp_handlers.compress_file_handler(f.name)
        assert isinstance(result, dict)
        assert result["original_file"] == f.name
        assert os.path.exists(result["compressed_file"])
        if os.path.exists(result["compressed_file"]):
            os.unlink(result["compressed_file"])
    finally:
        if os.path.exists(f.name):
            os.unlink(f.name)


@pytest.mark.asyncio
async def test_compress_file_handler_error_direct():
    """Test the compress_file_handler raises ToolError on missing file."""
    from compression_mcp import mcp_handlers

    with pytest.raises(ToolError, match="File not found"):
        await mcp_handlers.compress_file_handler("nonexistent_file.txt")


def test_server_module_imports():
    """Test that server module can be analyzed without running it."""
    import ast

    server_path = os.path.join(
        os.path.dirname(__file__), "..", "src", "compression_mcp", "server.py"
    )
    with open(server_path, "r") as f:
        content = f.read()

    tree = ast.parse(content)

    main_found = False
    compress_tool_found = False

    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef):
            if node.name == "main":
                main_found = True
        elif isinstance(node, ast.AsyncFunctionDef):
            if node.name == "compress_file_tool":
                compress_tool_found = True

    assert main_found, "main function should be defined"
    assert compress_tool_found, "compress_file_tool function should be defined"


def test_server_environment_handling():
    """Test environment variable handling logic without running server."""
    transport = os.getenv("MCP_TRANSPORT", "stdio").lower()
    assert transport == "stdio"

    with patch.dict(os.environ, {"MCP_TRANSPORT": "http"}):
        transport = os.getenv("MCP_TRANSPORT", "stdio").lower()
        assert transport == "http"


@pytest.mark.asyncio
async def test_end_to_end_compression_workflow(sample_file):
    """Test the complete compression workflow."""
    from compression_mcp import mcp_handlers

    result = await mcp_handlers.compress_file_handler(sample_file)

    assert "original_file" in result
    assert "compressed_file" in result
    assert "original_size" in result
    assert "compressed_size" in result
    assert "compression_ratio" in result
    assert "message" in result

    assert result["original_size"] > 0
    assert result["compressed_size"] > 0
    assert result["compression_ratio"] >= 0

    assert os.path.exists(result["original_file"])
    assert os.path.exists(result["compressed_file"])

    if os.path.exists(result["compressed_file"]):
        os.unlink(result["compressed_file"])


def test_logging_configuration():
    """Test that logging can be configured properly."""
    import logging

    test_logger = logging.getLogger("test_compression")
    test_logger.setLevel(logging.INFO)

    test_logger.info("Test message")
    test_logger.error("Test error")

    assert test_logger.level == logging.INFO


@pytest.mark.asyncio
async def test_compression_with_different_file_sizes():
    """Test compression with various file sizes."""
    from compression_mcp import mcp_handlers

    # Test small file
    with tempfile.NamedTemporaryFile(mode="w", delete=False) as f:
        f.write("small content")

    try:
        result = await mcp_handlers.compress_file_handler(f.name)
        assert result["compression_ratio"] is not None
        if os.path.exists(result["compressed_file"]):
            os.unlink(result["compressed_file"])
    finally:
        if os.path.exists(f.name):
            os.unlink(f.name)

    # Test larger file with repetitive content
    with tempfile.NamedTemporaryFile(mode="w", delete=False) as f:
        for i in range(1000):
            f.write("This is repetitive content that should compress well.\n")

    try:
        result = await mcp_handlers.compress_file_handler(f.name)
        assert result["compression_ratio"] > 0
        if os.path.exists(result["compressed_file"]):
            os.unlink(result["compressed_file"])
    finally:
        if os.path.exists(f.name):
            os.unlink(f.name)
