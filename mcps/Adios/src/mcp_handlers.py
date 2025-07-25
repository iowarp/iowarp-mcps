# mcp_handlers.py
import json
from typing import Any, Dict, Optional
from implementation import (
    bp5_list,
    bp5_inspect_variables,
    bp5_attributes,
    bp5_read_variable_at_step,
    bp5_inspect_variables_at_step,
)


class UnknownToolError(Exception):
    """Raised when an unsupported tool_name is requested."""

    pass


async def list_bp5_files(directory: str = "data") -> Dict[str, Any]:
    """
    List all BP5 files in a specified directory with comprehensive file information including metadata and structure details.

    Args:
        directory: Path to the directory containing BP5 files

    Returns:
        Dict containing list of files and metadata
    """
    try:
        files = bp5_list.list_bp5(directory)
        return {"files": files}
    except Exception as e:
        return {
            "content": [{"text": json.dumps({"error": str(e)})}],
            "_meta": {"tool": "list_bp5", "error": type(e).__name__},
            "isError": True,
        }


async def inspect_variables_handler(
    filename: str, variable_name: Optional[str] = None
) -> Dict[str, Any]:
    """
    Async handler for 'inspect_variables' tool.

    Args:
        filename: Path to the BP5 file
        variable_name: Optional name of specific variable to inspect

    Returns:
        Dict containing either metadata for all variables or data for a specific variable
    """
    try:
        if variable_name:
            # If variable name is provided, use read_variable_at_step to get its data
            # We'll get data from step 0 as a default
            return bp5_inspect_variables.inspect_variables(filename, variable_name)
        else:
            # If no variable name, return metadata for all variables
            return bp5_inspect_variables.inspect_variables(filename)
    except Exception as e:
        return {
            "content": [{"text": json.dumps({"error": str(e)})}],
            "_meta": {"tool": "inspect_variables", "error": type(e).__name__},
            "isError": True,
        }


async def inspect_variables_at_step_handler(
    filename: str, variable_name: str, step: int
) -> Dict[str, Any]:
    """
    Async handler for 'inspect_variables_at_step' tool.

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
        return {
            "content": [{"text": json.dumps({"error": str(e)})}],
            "_meta": {"tool": "inspect_variables_at_step", "error": type(e).__name__},
            "isError": True,
        }


async def inspect_attributes_handler(
    filename: str, variable_name: Optional[str] = None
) -> Dict[str, Any]:
    """
    Async handler for 'inspect_attributes' tool.
    """
    try:
        return bp5_attributes.inspect_attributes(filename, variable_name)
    except Exception as e:
        return {
            "content": [{"text": json.dumps({"error": str(e)})}],
            "_meta": {"tool": "inspect_attributes", "error": type(e).__name__},
            "isError": True,
        }


async def read_variable_at_step_handler(
    filename: str, variable_name: str, target_step: int
) -> Dict[str, Any]:
    try:
        value = bp5_read_variable_at_step.read_variable_at_step(
            filename, variable_name, target_step
        )
        return {"value": value}
    except Exception as e:
        return {
            "content": [{"text": json.dumps({"error": str(e)})}],
            "_meta": {"tool": "read_variable_at_step", "error": type(e).__name__},
            "isError": True,
        }
