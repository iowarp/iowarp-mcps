import pytest
import os
import tempfile
from unittest.mock import patch, MagicMock


@pytest.fixture
def sample_file():
    """Create a temporary file with test content."""
    with tempfile.NamedTemporaryFile(mode="w", delete=False) as f:
        f.write("test content for server execution testing\n" * 50)
    yield f.name
    if os.path.exists(f.name):
        os.unlink(f.name)
    if os.path.exists(f.name + ".gz"):
        os.unlink(f.name + ".gz")


def test_compress_file_tool_definition_in_source():
    """Test that compress_file_tool is properly defined in source code."""
    import ast

    server_path = os.path.join(
        os.path.dirname(__file__), "..", "src", "compression_mcp", "server.py"
    )
    with open(server_path, "r") as f:
        source = f.read()

    tree = ast.parse(source)

    compress_function_found = False
    for node in ast.walk(tree):
        if isinstance(node, ast.AsyncFunctionDef) and node.name == "compress_file_tool":
            compress_function_found = True
            break

    assert compress_function_found, (
        "compress_file_tool async function not found in source"
    )


def test_main_function_execution_stdio():
    """Test main function execution with stdio transport."""
    from compression_mcp import server

    mock_mcp_instance = MagicMock()

    with patch.object(server, "mcp", mock_mcp_instance):
        with patch.dict(os.environ, {"MCP_TRANSPORT": "stdio"}):
            with patch("argparse.ArgumentParser.parse_args") as mock_parse:
                mock_parse.return_value = MagicMock(
                    transport=None, host="0.0.0.0", port=8000
                )
                server.main()

                mock_mcp_instance.run.assert_called_with(
                    transport="stdio"
                )


def test_main_function_execution_http():
    """Test main function execution with http transport."""
    from compression_mcp import server

    mock_mcp_instance = MagicMock()

    with patch.object(server, "mcp", mock_mcp_instance):
        with patch("argparse.ArgumentParser.parse_args") as mock_parse:
            mock_parse.return_value = MagicMock(
                transport="http", host="localhost", port=9000
            )
            server.main()

            mock_mcp_instance.run.assert_called_with(
                transport="http", host="localhost", port=9000
            )


def test_module_imports_and_setup():
    """Test module-level imports and setup code execution."""
    from compression_mcp import server

    assert hasattr(server, "mcp")
    assert hasattr(server, "logger")
    assert hasattr(server, "mcp_handlers")
    assert hasattr(server, "main")
    assert hasattr(server, "compress_file_tool")
    assert hasattr(server, "decompress_file_tool")


def test_environment_variable_handling():
    """Test various environment variable combinations."""
    from compression_mcp import server

    mock_mcp_instance = MagicMock()

    with patch.object(server, "mcp", mock_mcp_instance):
        with patch.dict(os.environ, {}, clear=True):
            with patch("argparse.ArgumentParser.parse_args") as mock_parse:
                mock_parse.return_value = MagicMock(
                    transport=None, host="0.0.0.0", port=8000
                )
                server.main()

                mock_mcp_instance.run.assert_called_with(
                    transport="stdio"
                )


def test_fastmcp_initialization():
    """Test FastMCP server initialization."""
    from compression_mcp import server

    assert server.mcp.name == "compression"


def test_tool_decorator_presence():
    """Test that the compress_file_tool function has the expected decorator pattern."""
    import ast

    server_path = os.path.join(
        os.path.dirname(__file__), "..", "src", "compression_mcp", "server.py"
    )
    with open(server_path, "r") as f:
        source = f.read()

    tree = ast.parse(source)

    for node in ast.walk(tree):
        if isinstance(node, ast.AsyncFunctionDef) and node.name == "compress_file_tool":
            assert len(node.decorator_list) > 0
            decorator = node.decorator_list[0]
            assert isinstance(decorator, ast.Call)
            break
    else:
        assert False, "compress_file_tool function not found"
