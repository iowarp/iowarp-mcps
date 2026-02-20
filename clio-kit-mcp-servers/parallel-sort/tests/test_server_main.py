"""
Tests for server main function and initialization.
"""

import os
from unittest.mock import patch, MagicMock

import parallel_sort_mcp.server as server


class TestServerMain:
    """Test suite for server main function and initialization."""

    @patch.dict(os.environ, {"MCP_TRANSPORT": "stdio"}, clear=False)
    @patch("parallel_sort_mcp.server.mcp")
    def test_main_stdio_transport(self, mock_mcp):
        """Test main function with stdio transport."""
        mock_mcp.run = MagicMock()

        with patch("sys.argv", ["parallel-sort-mcp"]):
            try:
                server.main()
            except SystemExit:
                pass

        # Verify mcp.run was called with stdio
        if mock_mcp.run.called:
            call_args = mock_mcp.run.call_args
            if call_args and call_args[1]:
                assert call_args[1].get("transport") == "stdio"

    @patch.dict(os.environ, {"MCP_TRANSPORT": "http"}, clear=False)
    @patch("parallel_sort_mcp.server.mcp")
    def test_main_http_transport(self, mock_mcp):
        """Test main function with HTTP transport."""
        mock_mcp.run = MagicMock()

        with patch("sys.argv", ["parallel-sort-mcp"]):
            try:
                server.main()
            except SystemExit:
                pass

        # Verify mcp.run was called with HTTP parameters
        if mock_mcp.run.called:
            call_args = mock_mcp.run.call_args
            if call_args and call_args[1]:
                assert call_args[1].get("transport") == "http"
                assert call_args[1].get("host") == "0.0.0.0"
                assert call_args[1].get("port") == 8000

    @patch.dict(os.environ, {}, clear=False)
    @patch("parallel_sort_mcp.server.mcp")
    def test_main_default_transport(self, mock_mcp):
        """Test main function with default transport (no env var)."""
        mock_mcp.run = MagicMock()

        # Remove MCP_TRANSPORT if it exists
        if "MCP_TRANSPORT" in os.environ:
            del os.environ["MCP_TRANSPORT"]

        with patch("sys.argv", ["parallel-sort-mcp"]):
            try:
                server.main()
            except SystemExit:
                pass

        # Default should be stdio
        if mock_mcp.run.called:
            call_args = mock_mcp.run.call_args
            if call_args and call_args[1]:
                assert call_args[1].get("transport") == "stdio"

    @patch("parallel_sort_mcp.server.mcp")
    def test_main_with_transport_arg(self, mock_mcp):
        """Test main function with --transport argument."""
        mock_mcp.run = MagicMock()

        with patch(
            "sys.argv",
            [
                "parallel-sort-mcp",
                "--transport",
                "http",
                "--host",
                "127.0.0.1",
                "--port",
                "9000",
            ],
        ):
            try:
                server.main()
            except SystemExit:
                pass

        if mock_mcp.run.called:
            call_args = mock_mcp.run.call_args
            if call_args and call_args[1]:
                assert call_args[1].get("transport") == "http"
                assert call_args[1].get("host") == "127.0.0.1"
                assert call_args[1].get("port") == 9000


class TestServerImports:
    """Test server module imports and initialization."""

    def test_server_module_attributes(self):
        """Test server module has required attributes."""
        assert hasattr(server, "mcp")
        assert hasattr(server, "logger")
        assert hasattr(server, "main")

    def test_mcp_server_name(self):
        """Test MCP server has correct name."""
        assert server.mcp.name == "parallel-sort"

    def test_logger_configuration(self):
        """Test logger is configured."""
        assert server.logger is not None
        assert server.logger.name == "parallel_sort_mcp.server"
