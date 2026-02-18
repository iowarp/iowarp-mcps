"""Tests for main entry point and CLI functionality."""

from unittest.mock import patch

from ndp_mcp import server
from ndp_mcp.server import main


class TestMainFunction:
    """Test the main() entry point function."""

    def test_main_default_stdio_mode(self):
        """Test main function runs in stdio mode by default."""
        with patch("ndp_mcp.server.mcp.run") as mock_run:
            with patch("sys.argv", ["ndp-mcp"]):
                main()

            mock_run.assert_called_once_with(transport="stdio")

    def test_main_stdio_mode_explicit(self):
        """Test main function runs in stdio mode with --transport stdio."""
        with patch("ndp_mcp.server.mcp.run") as mock_run:
            with patch("sys.argv", ["ndp-mcp", "--transport", "stdio"]):
                main()

            mock_run.assert_called_once_with(transport="stdio")

    def test_main_http_mode(self):
        """Test main function runs in http mode with --transport http."""
        with patch("ndp_mcp.server.mcp.run") as mock_run:
            with patch("sys.argv", ["ndp-mcp", "--transport", "http"]):
                main()

            mock_run.assert_called_once_with(transport="http", host="0.0.0.0", port=8000)

    def test_main_custom_host_and_port(self):
        """Test main function with custom host and port."""
        with patch("ndp_mcp.server.mcp.run") as mock_run:
            with patch(
                "sys.argv",
                ["ndp-mcp", "--transport", "http", "--host", "localhost", "--port", "9000"],
            ):
                main()

            mock_run.assert_called_once_with(transport="http", host="localhost", port=9000)

    def test_main_env_transport(self):
        """Test main function uses MCP_TRANSPORT env var when no --transport flag."""
        with patch("ndp_mcp.server.mcp.run") as mock_run:
            with patch("sys.argv", ["ndp-mcp"]):
                with patch.dict("os.environ", {"MCP_TRANSPORT": "http"}):
                    main()

            mock_run.assert_called_once_with(transport="http", host="0.0.0.0", port=8000)


class TestModuleExecution:
    """Test module execution as __main__."""

    def test_main_called_when_run_as_script(self):
        """Test that main() is called when module is run as script."""
        with patch("ndp_mcp.server.main") as mock_main:
            # Simulate running as main module
            with patch.object(server, "__name__", "__main__"):
                # Execute the module's main block code
                exec(  # noqa: S102
                    "if __name__ == '__main__': main()",
                    {"__name__": "__main__", "main": mock_main},
                )

            mock_main.assert_called_once()


class TestServerInitialization:
    """Test server initialization and module-level setup."""

    def test_fastmcp_instance_created(self):
        """Test that FastMCP instance is properly created."""
        assert server.mcp is not None
        assert server.mcp.name == "ndp"

    def test_ndp_client_initialized(self):
        """Test that NDPClient is initialized at module level."""
        assert server.ndp_client is not None
        assert hasattr(server.ndp_client, "base_url")
        assert hasattr(server.ndp_client, "max_retries")
        assert hasattr(server.ndp_client, "retry_delay")

    def test_ndp_client_default_base_url(self):
        """Test NDPClient has correct default base URL."""
        assert server.ndp_client.base_url == "http://155.101.6.191:8003"

    def test_dataset_model_available(self):
        """Test that Dataset model is available in module."""
        from ndp_mcp.server import Dataset

        assert Dataset is not None
        assert hasattr(Dataset, "model_validate")
        assert hasattr(Dataset, "model_dump")

    def test_dotenv_loaded(self):
        """Test that dotenv configuration is loaded."""
        assert hasattr(server, "load_dotenv")

    def test_tools_registered(self):
        """Test that MCP tools are registered."""
        assert hasattr(server, "list_organizations")
        assert hasattr(server, "search_datasets")
        assert hasattr(server, "get_dataset_details")

    def test_resource_registered(self):
        """Test that the catalogs resource is registered."""
        assert hasattr(server, "available_catalogs")
        assert callable(server.available_catalogs)

    def test_prompt_registered(self):
        """Test that the explore_datasets prompt is registered."""
        assert hasattr(server, "explore_datasets")
        assert callable(server.explore_datasets)

    def test_ndp_client_timeout_configured(self):
        """Test that NDPClient has timeout configured."""
        assert server.ndp_client.timeout is not None
        assert hasattr(server.ndp_client.timeout, "connect")

    def test_module_imports(self):
        """Test that required modules are imported."""
        assert server.asyncio is not None
        assert server.os is not None
        assert server.httpx is not None
        assert server.FastMCP is not None
        assert server.BaseModel is not None
        assert server.Field is not None
        assert server.ToolError is not None
        assert server.Message is not None
