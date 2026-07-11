# mcp_handlers.py
import importlib
from typing import Any, Dict, Optional

from fastmcp.exceptions import ToolError


class _LazyImplementation:
    """Load an ADIOS2-backed implementation only when a tool is invoked."""

    def __init__(self, module_name: str, export_name: str) -> None:
        self._module_name = module_name
        self._export_name = export_name
        setattr(self, export_name, self._invoke)

    def _invoke(self, *args: Any, **kwargs: Any) -> Any:
        module = importlib.import_module(self._module_name)
        function = getattr(module, self._export_name)
        return function(*args, **kwargs)


bp5_list = _LazyImplementation("adios_mcp.implementation.bp5_list", "list_bp5")
bp5_inspect_variables = _LazyImplementation(
    "adios_mcp.implementation.bp5_inspect_variables", "inspect_variables"
)
bp5_attributes = _LazyImplementation(
    "adios_mcp.implementation.bp5_attributes", "inspect_attributes"
)
bp5_read_variable_at_step = _LazyImplementation(
    "adios_mcp.implementation.bp5_read_variable_at_step", "read_variable_at_step"
)
bp5_inspect_variables_at_step = _LazyImplementation(
    "adios_mcp.implementation.bp5_inspect_variables_at_step",
    "inspect_variables_at_step",
)


class UnknownToolError(Exception):
    """Raised when an unsupported tool_name is requested."""

    pass


async def list_bp5_files(directory: str = "data") -> Dict[str, Any]:
    """List all BP5 files in a specified directory.

    Args:
        directory: Path to the directory containing BP5 files

    Returns:
        Dict containing list of files and metadata
    """
    try:
        files = bp5_list.list_bp5(directory)
        return {"files": files}
    except Exception as e:
        raise ToolError(str(e)) from e


async def inspect_variables_handler(
    filename: str, variable_name: Optional[str] = None
) -> Dict[str, Any]:
    """Async handler for 'inspect_variables' tool.

    Args:
        filename: Path to the BP5 file
        variable_name: Optional name of specific variable to inspect

    Returns:
        Dict containing either metadata for all variables or data for a specific variable
    """
    try:
        if variable_name:
            return bp5_inspect_variables.inspect_variables(filename, variable_name)
        else:
            return bp5_inspect_variables.inspect_variables(filename)
    except Exception as e:
        raise ToolError(str(e)) from e


async def inspect_variables_at_step_handler(
    filename: str, variable_name: str, step: int
) -> Dict[str, Any]:
    """Async handler for 'inspect_variables_at_step' tool.

    Args:
        filename: Path to the BP5 file
        variable_name: Name of the variable to inspect
        step: Step number to inspect

    Returns:
        Dict containing variable metadata or error information
    """
    try:
        result = bp5_inspect_variables_at_step.inspect_variables_at_step(
            filename, variable_name, step
        )
        return result
    except Exception as e:
        raise ToolError(str(e)) from e


async def inspect_attributes_handler(
    filename: str, variable_name: Optional[str] = None
) -> Dict[str, Any]:
    """Async handler for 'inspect_attributes' tool."""
    try:
        return bp5_attributes.inspect_attributes(filename, variable_name)
    except Exception as e:
        raise ToolError(str(e)) from e


async def read_variable_at_step_handler(
    filename: str, variable_name: str, target_step: int
) -> Dict[str, Any]:
    """Async handler for 'read_variable_at_step' tool."""
    try:
        value = bp5_read_variable_at_step.read_variable_at_step(
            filename, variable_name, target_step
        )
        return {"value": value}
    except Exception as e:
        raise ToolError(str(e)) from e
