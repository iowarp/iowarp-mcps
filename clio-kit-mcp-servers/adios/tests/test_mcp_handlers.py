import pytest
from unittest.mock import patch
from fastmcp.exceptions import ToolError
from adios_mcp.mcp_handlers import (
    UnknownToolError,
    list_bp5_files,
    inspect_variables_handler,
    inspect_variables_at_step_handler,
    inspect_attributes_handler,
    read_variable_at_step_handler,
)


class TestUnknownToolError:
    def test_unknown_tool_error_creation(self):
        """Test that UnknownToolError can be raised properly"""
        with pytest.raises(UnknownToolError):
            raise UnknownToolError("Tool 'invalid_tool' not found")

    def test_unknown_tool_error_inheritance(self):
        """Test that UnknownToolError inherits from Exception"""
        assert issubclass(UnknownToolError, Exception)


class TestListBp5Files:
    @pytest.mark.asyncio
    async def test_list_bp5_files_success(self):
        mock_files = [
            {"name": "file1.bp", "size": 1024},
            {"name": "file2.bp5", "size": 2048},
        ]

        with patch("adios_mcp.mcp_handlers.bp5_list.list_bp5") as mock_list_bp5:
            mock_list_bp5.return_value = mock_files

            result = await list_bp5_files("/test/directory")

            mock_list_bp5.assert_called_once_with("/test/directory")
            assert result == {"files": mock_files}

    @pytest.mark.asyncio
    async def test_list_bp5_files_default_directory(self):
        mock_files = []

        with patch("adios_mcp.mcp_handlers.bp5_list.list_bp5") as mock_list_bp5:
            mock_list_bp5.return_value = mock_files

            result = await list_bp5_files()

            mock_list_bp5.assert_called_once_with("data")
            assert result == {"files": mock_files}

    @pytest.mark.asyncio
    async def test_list_bp5_files_exception(self):
        with patch("adios_mcp.mcp_handlers.bp5_list.list_bp5") as mock_list_bp5:
            mock_list_bp5.side_effect = FileNotFoundError("Directory not found")

            with pytest.raises(ToolError, match="Directory not found"):
                await list_bp5_files("/nonexistent")

    @pytest.mark.asyncio
    async def test_list_bp5_files_empty_result(self):
        with patch("adios_mcp.mcp_handlers.bp5_list.list_bp5") as mock_list_bp5:
            mock_list_bp5.return_value = []

            result = await list_bp5_files("/empty/dir")

            assert result == {"files": []}

    @pytest.mark.asyncio
    async def test_list_bp5_files_various_exceptions(self):
        exception_types = [
            (PermissionError, "Permission denied"),
            (OSError, "OS error occurred"),
            (ValueError, "Invalid value"),
            (RuntimeError, "Runtime error"),
        ]

        for exception_type, message in exception_types:
            with patch("adios_mcp.mcp_handlers.bp5_list.list_bp5") as mock_list_bp5:
                mock_list_bp5.side_effect = exception_type(message)

                with pytest.raises(ToolError, match=message):
                    await list_bp5_files("/test")


class TestInspectVariablesHandler:
    @pytest.mark.asyncio
    async def test_inspect_variables_handler_no_variable_name(self):
        mock_result = {"variables": {"temp": {"type": "float64", "shape": [100, 50]}}}

        with patch(
            "adios_mcp.mcp_handlers.bp5_inspect_variables.inspect_variables"
        ) as mock_inspect:
            mock_inspect.return_value = mock_result

            result = await inspect_variables_handler("/test/file.bp")

            mock_inspect.assert_called_once_with("/test/file.bp")
            assert result == mock_result

    @pytest.mark.asyncio
    async def test_inspect_variables_handler_with_variable_name(self):
        mock_result = {"variable_data": {"name": "pressure", "values": [1, 2, 3]}}

        with patch(
            "adios_mcp.mcp_handlers.bp5_inspect_variables.inspect_variables"
        ) as mock_inspect:
            mock_inspect.return_value = mock_result

            result = await inspect_variables_handler("/test/file.bp", "pressure")

            mock_inspect.assert_called_once_with("/test/file.bp", "pressure")
            assert result == mock_result

    @pytest.mark.asyncio
    async def test_inspect_variables_handler_exception(self):
        with patch(
            "adios_mcp.mcp_handlers.bp5_inspect_variables.inspect_variables"
        ) as mock_inspect:
            mock_inspect.side_effect = Exception("ADIOS inspection failed")

            with pytest.raises(ToolError, match="ADIOS inspection failed"):
                await inspect_variables_handler("/test/file.bp")

    @pytest.mark.asyncio
    async def test_inspect_variables_handler_file_not_found(self):
        with patch(
            "adios_mcp.mcp_handlers.bp5_inspect_variables.inspect_variables"
        ) as mock_inspect:
            mock_inspect.side_effect = FileNotFoundError("BP5 file not found")

            with pytest.raises(ToolError, match="BP5 file not found"):
                await inspect_variables_handler("/nonexistent/file.bp")

    @pytest.mark.asyncio
    async def test_inspect_variables_handler_empty_variable_name(self):
        mock_result = {"variables": {}}

        with patch(
            "adios_mcp.mcp_handlers.bp5_inspect_variables.inspect_variables"
        ) as mock_inspect:
            mock_inspect.return_value = mock_result

            result = await inspect_variables_handler("/test/file.bp", "")

            # Empty string is falsy, so it calls without variable_name parameter
            mock_inspect.assert_called_once_with("/test/file.bp")
            assert result == mock_result


class TestInspectVariablesAtStepHandler:
    @pytest.mark.asyncio
    async def test_inspect_variables_at_step_handler_success(self):
        mock_result = {
            "variable": "temperature",
            "step": 5,
            "shape": [100],
            "type": "float64",
        }

        with patch(
            "adios_mcp.mcp_handlers.bp5_inspect_variables_at_step.inspect_variables_at_step"
        ) as mock_inspect:
            mock_inspect.return_value = mock_result

            result = await inspect_variables_at_step_handler(
                "/test/file.bp", "temperature", 5
            )

            mock_inspect.assert_called_once_with("/test/file.bp", "temperature", 5)
            assert result == mock_result

    @pytest.mark.asyncio
    async def test_inspect_variables_at_step_handler_exception(self):
        with patch(
            "adios_mcp.mcp_handlers.bp5_inspect_variables_at_step.inspect_variables_at_step"
        ) as mock_inspect:
            mock_inspect.side_effect = ValueError("Invalid step number")

            with pytest.raises(ToolError, match="Invalid step number"):
                await inspect_variables_at_step_handler("/test/file.bp", "temp", 10)

    @pytest.mark.asyncio
    async def test_inspect_variables_at_step_handler_negative_step(self):
        with patch(
            "adios_mcp.mcp_handlers.bp5_inspect_variables_at_step.inspect_variables_at_step"
        ) as mock_inspect:
            mock_inspect.side_effect = ValueError("Step must be non-negative")

            with pytest.raises(ToolError, match="Step must be non-negative"):
                await inspect_variables_at_step_handler("/test/file.bp", "temp", -1)

    @pytest.mark.asyncio
    async def test_inspect_variables_at_step_handler_zero_step(self):
        mock_result = {"variable": "pressure", "step": 0, "min": 1.0, "max": 10.0}

        with patch(
            "adios_mcp.mcp_handlers.bp5_inspect_variables_at_step.inspect_variables_at_step"
        ) as mock_inspect:
            mock_inspect.return_value = mock_result

            result = await inspect_variables_at_step_handler(
                "/test/file.bp", "pressure", 0
            )

            mock_inspect.assert_called_once_with("/test/file.bp", "pressure", 0)
            assert result == mock_result

    @pytest.mark.asyncio
    async def test_inspect_variables_at_step_handler_large_step(self):
        mock_result = {"variable": "velocity", "step": 1000, "data_available": True}

        with patch(
            "adios_mcp.mcp_handlers.bp5_inspect_variables_at_step.inspect_variables_at_step"
        ) as mock_inspect:
            mock_inspect.return_value = mock_result

            result = await inspect_variables_at_step_handler(
                "/test/file.bp", "velocity", 1000
            )

            assert result == mock_result


class TestInspectAttributesHandler:
    @pytest.mark.asyncio
    async def test_inspect_attributes_handler_no_variable_name(self):
        mock_result = {"global_attributes": {"title": "simulation", "version": "1.0"}}

        with patch(
            "adios_mcp.mcp_handlers.bp5_attributes.inspect_attributes"
        ) as mock_inspect:
            mock_inspect.return_value = mock_result

            result = await inspect_attributes_handler("/test/file.bp")

            mock_inspect.assert_called_once_with("/test/file.bp", None)
            assert result == mock_result

    @pytest.mark.asyncio
    async def test_inspect_attributes_handler_with_variable_name(self):
        mock_result = {
            "variable_attributes": {"units": "celsius", "description": "temperature"}
        }

        with patch(
            "adios_mcp.mcp_handlers.bp5_attributes.inspect_attributes"
        ) as mock_inspect:
            mock_inspect.return_value = mock_result

            result = await inspect_attributes_handler("/test/file.bp", "temperature")

            mock_inspect.assert_called_once_with("/test/file.bp", "temperature")
            assert result == mock_result

    @pytest.mark.asyncio
    async def test_inspect_attributes_handler_exception(self):
        with patch(
            "adios_mcp.mcp_handlers.bp5_attributes.inspect_attributes"
        ) as mock_inspect:
            mock_inspect.side_effect = RuntimeError("Attribute access failed")

            with pytest.raises(ToolError, match="Attribute access failed"):
                await inspect_attributes_handler("/test/file.bp")

    @pytest.mark.asyncio
    async def test_inspect_attributes_handler_empty_attributes(self):
        mock_result = {"attributes": {}}

        with patch(
            "adios_mcp.mcp_handlers.bp5_attributes.inspect_attributes"
        ) as mock_inspect:
            mock_inspect.return_value = mock_result

            result = await inspect_attributes_handler(
                "/test/file.bp", "nonexistent_var"
            )

            assert result == mock_result

    @pytest.mark.asyncio
    async def test_inspect_attributes_handler_complex_attributes(self):
        mock_result = {
            "global_attributes": {
                "simulation_params": {"timestep": 0.01, "total_time": 100.0},
                "mesh_info": {"nodes": 1000, "elements": 500},
            },
            "variable_attributes": {"units": "m/s", "range": [0.0, 50.0]},
        }

        with patch(
            "adios_mcp.mcp_handlers.bp5_attributes.inspect_attributes"
        ) as mock_inspect:
            mock_inspect.return_value = mock_result

            result = await inspect_attributes_handler("/test/file.bp", "velocity")

            assert result == mock_result


class TestReadVariableAtStepHandler:
    @pytest.mark.asyncio
    async def test_read_variable_at_step_handler_success(self):
        mock_value = [1.0, 2.0, 3.0, 4.0, 5.0]

        with patch(
            "adios_mcp.mcp_handlers.bp5_read_variable_at_step.read_variable_at_step"
        ) as mock_read:
            mock_read.return_value = mock_value

            result = await read_variable_at_step_handler("/test/file.bp", "pressure", 3)

            mock_read.assert_called_once_with("/test/file.bp", "pressure", 3)
            assert result == {"value": mock_value}

    @pytest.mark.asyncio
    async def test_read_variable_at_step_handler_scalar_value(self):
        mock_value = 42.5

        with patch(
            "adios_mcp.mcp_handlers.bp5_read_variable_at_step.read_variable_at_step"
        ) as mock_read:
            mock_read.return_value = mock_value

            result = await read_variable_at_step_handler(
                "/test/file.bp", "scalar_var", 0
            )

            assert result == {"value": mock_value}

    @pytest.mark.asyncio
    async def test_read_variable_at_step_handler_exception(self):
        with patch(
            "adios_mcp.mcp_handlers.bp5_read_variable_at_step.read_variable_at_step"
        ) as mock_read:
            mock_read.side_effect = Exception("Failed to read variable")

            with pytest.raises(ToolError, match="Failed to read variable"):
                await read_variable_at_step_handler("/test/file.bp", "temp", 5)

    @pytest.mark.asyncio
    async def test_read_variable_at_step_handler_file_not_found(self):
        with patch(
            "adios_mcp.mcp_handlers.bp5_read_variable_at_step.read_variable_at_step"
        ) as mock_read:
            mock_read.side_effect = FileNotFoundError("BP5 file not found")

            with pytest.raises(ToolError, match="BP5 file not found"):
                await read_variable_at_step_handler("/nonexistent/file.bp", "var", 0)

    @pytest.mark.asyncio
    async def test_read_variable_at_step_handler_variable_not_found(self):
        with patch(
            "adios_mcp.mcp_handlers.bp5_read_variable_at_step.read_variable_at_step"
        ) as mock_read:
            mock_read.side_effect = KeyError("Variable 'nonexistent_var' not found")

            with pytest.raises(ToolError):
                await read_variable_at_step_handler(
                    "/test/file.bp", "nonexistent_var", 0
                )

    @pytest.mark.asyncio
    async def test_read_variable_at_step_handler_step_out_of_range(self):
        with patch(
            "adios_mcp.mcp_handlers.bp5_read_variable_at_step.read_variable_at_step"
        ) as mock_read:
            mock_read.side_effect = IndexError("Step 100 out of range")

            with pytest.raises(ToolError, match="Step 100 out of range"):
                await read_variable_at_step_handler("/test/file.bp", "temp", 100)

    @pytest.mark.asyncio
    async def test_read_variable_at_step_handler_large_array(self):
        # Test with a large array to ensure proper handling
        mock_value = list(range(10000))

        with patch(
            "adios_mcp.mcp_handlers.bp5_read_variable_at_step.read_variable_at_step"
        ) as mock_read:
            mock_read.return_value = mock_value

            result = await read_variable_at_step_handler(
                "/test/file.bp", "large_array", 0
            )

            assert result == {"value": mock_value}
            assert len(result["value"]) == 10000

    @pytest.mark.asyncio
    async def test_read_variable_at_step_handler_empty_array(self):
        mock_value = []

        with patch(
            "adios_mcp.mcp_handlers.bp5_read_variable_at_step.read_variable_at_step"
        ) as mock_read:
            mock_read.return_value = mock_value

            result = await read_variable_at_step_handler(
                "/test/file.bp", "empty_var", 0
            )

            assert result == {"value": []}

    @pytest.mark.asyncio
    async def test_read_variable_at_step_handler_none_value(self):
        mock_value = None

        with patch(
            "adios_mcp.mcp_handlers.bp5_read_variable_at_step.read_variable_at_step"
        ) as mock_read:
            mock_read.return_value = mock_value

            result = await read_variable_at_step_handler("/test/file.bp", "null_var", 0)

            assert result == {"value": None}


class TestHandlersIntegration:
    @pytest.mark.asyncio
    async def test_all_handlers_import_correctly(self):
        """Test that all handlers can be imported and called"""
        handlers = [
            list_bp5_files,
            inspect_variables_handler,
            inspect_variables_at_step_handler,
            inspect_attributes_handler,
            read_variable_at_step_handler,
        ]

        for handler in handlers:
            assert callable(handler)
            assert hasattr(handler, "__name__")

    @pytest.mark.asyncio
    async def test_error_response_raises_tool_error(self):
        """Test that all handlers raise ToolError on failure"""
        handlers_and_args = [
            (list_bp5_files, ("/test",)),
            (inspect_variables_handler, ("/test", None)),
            (inspect_variables_at_step_handler, ("/test", "var", 0)),
            (inspect_attributes_handler, ("/test", None)),
            (read_variable_at_step_handler, ("/test", "var", 0)),
        ]

        for handler, args in handlers_and_args:
            # Mock each handler's underlying implementation to raise an exception
            if "list_bp5_files" in handler.__name__:
                patch_target = "adios_mcp.mcp_handlers.bp5_list.list_bp5"
            elif "inspect_variables_at_step" in handler.__name__:
                patch_target = "adios_mcp.mcp_handlers.bp5_inspect_variables_at_step.inspect_variables_at_step"
            elif "inspect_variables" in handler.__name__:
                patch_target = (
                    "adios_mcp.mcp_handlers.bp5_inspect_variables.inspect_variables"
                )
            elif "inspect_attributes" in handler.__name__:
                patch_target = (
                    "adios_mcp.mcp_handlers.bp5_attributes.inspect_attributes"
                )
            elif "read_variable_at_step" in handler.__name__:
                patch_target = "adios_mcp.mcp_handlers.bp5_read_variable_at_step.read_variable_at_step"

            with patch(patch_target) as mock_impl:
                mock_impl.side_effect = Exception("Test error")

                with pytest.raises(ToolError, match="Test error"):
                    await handler(*args)
