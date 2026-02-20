import pytest
import os
from unittest.mock import AsyncMock, patch, MagicMock
from fastmcp.exceptions import ToolError


class TestServerToolFunctions:
    @pytest.mark.asyncio
    async def test_list_bp5_tool_success(self):
        from adios_mcp.server import list_bp5_tool

        mock_files = [
            {"name": "file1.bp", "size": 1024},
            {"name": "file2.bp5", "size": 2048},
        ]

        with patch(
            "adios_mcp.server.mcp_handlers.list_bp5_files", new_callable=AsyncMock
        ) as mock_handler:
            mock_handler.return_value = {"files": mock_files}

            result = await list_bp5_tool("/test/directory")

            mock_handler.assert_called_once_with("/test/directory")
            assert result == {"files": mock_files}

    @pytest.mark.asyncio
    async def test_list_bp5_tool_exception(self):
        from adios_mcp.server import list_bp5_tool

        with patch(
            "adios_mcp.server.mcp_handlers.list_bp5_files", new_callable=AsyncMock
        ) as mock_handler:
            mock_handler.side_effect = ToolError("Directory not found")

            with pytest.raises(ToolError, match="Directory not found"):
                await list_bp5_tool("/nonexistent")

    @pytest.mark.asyncio
    async def test_list_bp5_tool_default_directory(self):
        from adios_mcp.server import list_bp5_tool

        with patch(
            "adios_mcp.server.mcp_handlers.list_bp5_files", new_callable=AsyncMock
        ) as mock_handler:
            mock_handler.return_value = {"files": []}

            result = await list_bp5_tool()

            mock_handler.assert_called_once_with("data/")
            assert result == {"files": []}

    @pytest.mark.asyncio
    async def test_inspect_variables_tool_success(self):
        from adios_mcp.server import inspect_variables_tool

        mock_result = {"variables": {"temp": {"type": "float64", "shape": [100, 50]}}}

        with patch(
            "adios_mcp.server.mcp_handlers.inspect_variables_handler",
            new_callable=AsyncMock,
        ) as mock_handler:
            mock_handler.return_value = mock_result

            result = await inspect_variables_tool("/test/file.bp")

            mock_handler.assert_called_once_with("/test/file.bp", None)
            assert result == mock_result

    @pytest.mark.asyncio
    async def test_inspect_variables_tool_with_variable_name(self):
        from adios_mcp.server import inspect_variables_tool

        mock_result = {"variable_data": {"name": "pressure", "values": [1, 2, 3]}}

        with patch(
            "adios_mcp.server.mcp_handlers.inspect_variables_handler",
            new_callable=AsyncMock,
        ) as mock_handler:
            mock_handler.return_value = mock_result

            result = await inspect_variables_tool("/test/file.bp", "pressure")

            mock_handler.assert_called_once_with("/test/file.bp", "pressure")
            assert result == mock_result

    @pytest.mark.asyncio
    async def test_inspect_variables_tool_exception(self):
        from adios_mcp.server import inspect_variables_tool

        with patch(
            "adios_mcp.server.mcp_handlers.inspect_variables_handler",
            new_callable=AsyncMock,
        ) as mock_handler:
            mock_handler.side_effect = ToolError("ADIOS error")

            with pytest.raises(ToolError, match="ADIOS error"):
                await inspect_variables_tool("/test/file.bp")

    @pytest.mark.asyncio
    async def test_inspect_variables_at_step_tool_success(self):
        from adios_mcp.server import inspect_variables_at_step_tool

        mock_result = {"variable": "temp", "step": 5, "shape": [100], "type": "float64"}

        with patch(
            "adios_mcp.server.mcp_handlers.inspect_variables_at_step_handler",
            new_callable=AsyncMock,
        ) as mock_handler:
            mock_handler.return_value = mock_result

            result = await inspect_variables_at_step_tool("/test/file.bp", "temp", 5)

            mock_handler.assert_called_once_with("/test/file.bp", "temp", 5)
            assert result == mock_result

    @pytest.mark.asyncio
    async def test_inspect_variables_at_step_tool_exception(self):
        from adios_mcp.server import inspect_variables_at_step_tool

        with patch(
            "adios_mcp.server.mcp_handlers.inspect_variables_at_step_handler",
            new_callable=AsyncMock,
        ) as mock_handler:
            mock_handler.side_effect = ToolError("Invalid step")

            with pytest.raises(ToolError, match="Invalid step"):
                await inspect_variables_at_step_tool("/test/file.bp", "temp", 10)

    @pytest.mark.asyncio
    async def test_inspect_attributes_tool_success(self):
        from adios_mcp.server import inspect_attributes_tool

        mock_result = {
            "attributes": {"global": {"title": "simulation"}, "variables": {}}
        }

        with patch(
            "adios_mcp.server.mcp_handlers.inspect_attributes_handler",
            new_callable=AsyncMock,
        ) as mock_handler:
            mock_handler.return_value = mock_result

            result = await inspect_attributes_tool("/test/file.bp")

            mock_handler.assert_called_once_with("/test/file.bp", None)
            assert result == mock_result

    @pytest.mark.asyncio
    async def test_inspect_attributes_tool_with_variable(self):
        from adios_mcp.server import inspect_attributes_tool

        mock_result = {"attributes": {"variable_attrs": {"units": "celsius"}}}

        with patch(
            "adios_mcp.server.mcp_handlers.inspect_attributes_handler",
            new_callable=AsyncMock,
        ) as mock_handler:
            mock_handler.return_value = mock_result

            result = await inspect_attributes_tool("/test/file.bp", "temperature")

            mock_handler.assert_called_once_with("/test/file.bp", "temperature")
            assert result == mock_result

    @pytest.mark.asyncio
    async def test_inspect_attributes_tool_exception(self):
        from adios_mcp.server import inspect_attributes_tool

        with patch(
            "adios_mcp.server.mcp_handlers.inspect_attributes_handler",
            new_callable=AsyncMock,
        ) as mock_handler:
            mock_handler.side_effect = ToolError("Attribute access failed")

            with pytest.raises(ToolError, match="Attribute access failed"):
                await inspect_attributes_tool("/test/file.bp")

    @pytest.mark.asyncio
    async def test_read_variable_at_step_tool_success(self):
        from adios_mcp.server import read_variable_at_step_tool

        mock_result = {"value": [1.0, 2.0, 3.0]}

        with patch(
            "adios_mcp.server.mcp_handlers.read_variable_at_step_handler",
            new_callable=AsyncMock,
        ) as mock_handler:
            mock_handler.return_value = mock_result

            result = await read_variable_at_step_tool("/test/file.bp", "pressure", 3)

            mock_handler.assert_called_once_with("/test/file.bp", "pressure", 3)
            assert result == mock_result

    @pytest.mark.asyncio
    async def test_read_variable_at_step_tool_scalar_value(self):
        from adios_mcp.server import read_variable_at_step_tool

        mock_result = {"value": 42.5}

        with patch(
            "adios_mcp.server.mcp_handlers.read_variable_at_step_handler",
            new_callable=AsyncMock,
        ) as mock_handler:
            mock_handler.return_value = mock_result

            result = await read_variable_at_step_tool("/test/file.bp", "scalar_var", 0)

            mock_handler.assert_called_once_with("/test/file.bp", "scalar_var", 0)
            assert result == mock_result


class TestMainFunction:
    def test_main_default_stdio_transport(self):
        from adios_mcp.server import main

        mock_mcp = MagicMock()

        with (
            patch("adios_mcp.server.mcp", mock_mcp),
            patch("sys.argv", ["adios-mcp"]),
            patch.dict(os.environ, {}, clear=True),
        ):
            main()

            mock_mcp.run.assert_called_once_with(transport="stdio")

    def test_main_http_transport_via_args(self):
        from adios_mcp.server import main

        mock_mcp = MagicMock()

        with (
            patch("adios_mcp.server.mcp", mock_mcp),
            patch("sys.argv", ["adios-mcp", "--transport", "http"]),
        ):
            main()

            mock_mcp.run.assert_called_once_with(
                transport="http", host="0.0.0.0", port=8000
            )

    def test_main_custom_host_port_via_args(self):
        from adios_mcp.server import main

        mock_mcp = MagicMock()

        with (
            patch("adios_mcp.server.mcp", mock_mcp),
            patch(
                "sys.argv",
                [
                    "adios-mcp",
                    "--transport",
                    "http",
                    "--host",
                    "localhost",
                    "--port",
                    "9000",
                ],
            ),
        ):
            main()

            mock_mcp.run.assert_called_once_with(
                transport="http", host="localhost", port=9000
            )

    def test_main_stdio_transport_explicit(self):
        from adios_mcp.server import main

        mock_mcp = MagicMock()

        with (
            patch("adios_mcp.server.mcp", mock_mcp),
            patch("sys.argv", ["adios-mcp", "--transport", "stdio"]),
        ):
            main()

            mock_mcp.run.assert_called_once_with(transport="stdio")

    def test_main_transport_from_env(self):
        from adios_mcp.server import main

        mock_mcp = MagicMock()

        with (
            patch("adios_mcp.server.mcp", mock_mcp),
            patch("sys.argv", ["adios-mcp"]),
            patch.dict(os.environ, {"MCP_TRANSPORT": "http"}, clear=True),
        ):
            main()

            mock_mcp.run.assert_called_once_with(
                transport="http", host="0.0.0.0", port=8000
            )

    def test_main_args_override_env(self):
        from adios_mcp.server import main

        mock_mcp = MagicMock()

        with (
            patch("adios_mcp.server.mcp", mock_mcp),
            patch("sys.argv", ["adios-mcp", "--transport", "stdio"]),
            patch.dict(os.environ, {"MCP_TRANSPORT": "http"}, clear=True),
        ):
            main()

            mock_mcp.run.assert_called_once_with(transport="stdio")


class TestServerIntegration:
    def test_server_imports(self):
        """Test that all required modules are properly imported"""
        import adios_mcp.server as server

        assert hasattr(server, "FastMCP")
        assert hasattr(server, "mcp_handlers")
        assert hasattr(server, "mcp")

    def test_server_has_tool_error_import(self):
        """Test that ToolError is properly imported"""
        import adios_mcp.server as server

        assert hasattr(server, "ToolError")

    def test_server_has_message_import(self):
        """Test that Message is properly imported"""
        import adios_mcp.server as server

        assert hasattr(server, "Message")

    def test_server_has_resource(self):
        """Test that the adios_capabilities resource is defined"""
        from adios_mcp.server import adios_capabilities

        result = adios_capabilities()
        assert "supported_formats" in result
        assert "BP4" in result["supported_formats"]
        assert "BP5" in result["supported_formats"]

    def test_server_has_prompt(self):
        """Test that the explore_bp_file prompt is defined"""
        from adios_mcp.server import explore_bp_file

        messages = explore_bp_file("/test/file.bp")
        assert len(messages) == 1
        assert "/test/file.bp" in messages[0].content.text
