"""Tests for main entry point and server initialization."""

from unittest.mock import patch

from web_mcp import server
from web_mcp.server import main


class TestMainFunction:
    """Test the main() entry point function."""

    def test_main_default_stdio_mode(self) -> None:
        """Test main function runs in stdio mode by default."""
        with patch("web_mcp.server.create_mcp") as create:
            mock_run = create.return_value.run
            with patch("sys.argv", ["web-mcp"]):
                main()
            mock_run.assert_called_once_with(transport="stdio")

    def test_main_stdio_mode_explicit(self) -> None:
        """Test main function runs in stdio mode with --transport stdio."""
        with patch("web_mcp.server.create_mcp") as create:
            mock_run = create.return_value.run
            with patch("sys.argv", ["web-mcp", "--transport", "stdio"]):
                main()
            mock_run.assert_called_once_with(transport="stdio")

    def test_main_http_mode(self) -> None:
        """Test main function runs in http mode with --transport http."""
        with patch("web_mcp.server.create_mcp") as create:
            mock_run = create.return_value.run
            with patch("sys.argv", ["web-mcp", "--transport", "http"]):
                main()
            mock_run.assert_called_once_with(transport="http", host="0.0.0.0", port=8000)

    def test_main_custom_host_and_port(self) -> None:
        """Test main function with custom host and port."""
        with patch("web_mcp.server.create_mcp") as create:
            mock_run = create.return_value.run
            with patch(
                "sys.argv",
                ["web-mcp", "--transport", "http", "--host", "localhost", "--port", "9000"],
            ):
                main()
            mock_run.assert_called_once_with(transport="http", host="localhost", port=9000)

    def test_main_env_transport(self) -> None:
        """Test main function uses MCP_TRANSPORT env var when no --transport flag."""
        with patch("web_mcp.server.create_mcp") as create:
            mock_run = create.return_value.run
            with patch("sys.argv", ["web-mcp"]):
                with patch.dict("os.environ", {"MCP_TRANSPORT": "http"}):
                    main()
            mock_run.assert_called_once_with(transport="http", host="0.0.0.0", port=8000)

    def test_remote_url_selects_unified_searxng_provider(self) -> None:
        """One remote URL configures search as well as fetch and tasks."""

        with patch("web_mcp.server.create_mcp") as create:
            with patch("sys.argv", ["web-mcp", "--remote_url", "http://homelab:8089"]):
                main()
        configured = create.call_args.args[0]
        assert configured.search_provider == "searxng"
        assert configured.remote_url == "http://homelab:8089"


class TestServerInitialization:
    """Test server initialization and module-level setup."""

    def test_fastmcp_instance_created(self) -> None:
        """Test that FastMCP instance is properly created."""
        assert server.mcp is not None
        assert server.mcp.name == "web"

    def test_tools_registered(self) -> None:
        """Test that MCP tools are registered on the module."""
        assert hasattr(server, "fetch")
        assert hasattr(server, "_search_common")
        assert hasattr(server, "_search_searxng_tool")

    def test_settings_available(self) -> None:
        """Test that the Settings model and instance are available."""
        assert server.settings is not None
        assert hasattr(server.Settings, "model_validate")

    def test_reason_constants(self) -> None:
        """Test that the typed extension-point reason strings are exported."""
        assert server.REASON_JS_RENDER_REQUIRED == "js_render_required_browser_unavailable"
        assert server.REASON_BINARY_NOT_INLINED == "binary_content_not_inlined"
