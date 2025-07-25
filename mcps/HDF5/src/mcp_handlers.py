import json
import csv
import os
import psutil
from typing import Dict, Any
from capabilities import hdf5_list, inspect_hdf5, preview_hdf5, read_all_hdf5


class UnknownToolError(Exception):
    """Raised when an unsupported tool_name is requested."""

    pass


def list_resources() -> Dict[str, Any]:
    """
    List available resources/tools.

    Returns:
        Dict containing count of available resources
    """
    return {
        "_meta": {"count": 3},
        "content": [{"text": json.dumps(["list_hdf5", "filter_csv", "node_hardware"])}],
    }


def call_tool(tool_name: str, params: Dict[str, Any]) -> Dict[str, Any]:
    """
    Call a specific tool based on the tool name.

    Args:
        tool_name: Name of the tool to call
        params: Parameters for the tool

    Returns:
        Dict containing the tool result

    Raises:
        UnknownToolError: If the tool is not supported
    """
    if tool_name == "list_hdf5":
        directory = params.get("directory", "data")
        return list_hdf5_files_sync(directory)
    elif tool_name == "filter_csv":
        csv_path = params.get("csv_path")
        threshold = params.get("threshold")
        if csv_path is None or threshold is None:
            return {
                "content": [
                    {
                        "text": json.dumps(
                            {
                                "error": "Missing required parameters: csv_path and threshold"
                            }
                        )
                    }
                ],
                "_meta": {"tool": "filter_csv", "error": "ValueError"},
                "isError": True,
            }
        return filter_csv_sync(str(csv_path), float(threshold))
    elif tool_name == "node_hardware":
        return node_hardware_sync()
    else:
        raise UnknownToolError(f"Unknown tool: {tool_name}")


def list_hdf5_files_sync(directory: str = "data") -> Dict[str, Any]:
    """
    Synchronous version of list_hdf5_files.

    Args:
        directory: Path to the directory containing HDF5 files

    Returns:
        Dict containing list of files and metadata
    """
    try:
        files = hdf5_list.list_hdf5(directory)
        return {
            "content": [{"text": json.dumps(files)}],
            "_meta": {"tool": "list_hdf5"},
        }
    except Exception as e:
        return {
            "content": [{"text": json.dumps({"error": str(e)})}],
            "_meta": {"tool": "list_hdf5", "error": type(e).__name__},
            "isError": True,
        }


def filter_csv_sync(csv_path: str, threshold: float) -> Dict[str, Any]:
    """
    Filter CSV data based on a threshold value.

    Args:
        csv_path: Path to the CSV file
        threshold: Threshold value for filtering

    Returns:
        Dict containing filtered data
    """
    try:
        if not os.path.exists(csv_path):
            return {
                "content": [
                    {"text": json.dumps({"error": f"File not found: {csv_path}"})}
                ],
                "_meta": {"tool": "filter_csv", "error": "FileNotFoundError"},
                "isError": True,
            }

        filtered_data = []
        with open(csv_path, "r") as file:
            reader = csv.DictReader(file)
            for row in reader:
                # Try to convert value to float for comparison
                try:
                    value = float(row.get("value", 0))
                    if value > threshold:
                        # Convert the value back to the original type for the result
                        filtered_row = row.copy()
                        filtered_row["value"] = value  # Keep as float
                        filtered_data.append(filtered_row)
                except (ValueError, TypeError):
                    # If conversion fails, skip the row
                    continue

        return {
            "content": [{"text": json.dumps(filtered_data)}],
            "_meta": {"tool": "filter_csv"},
        }
    except Exception as e:
        return {
            "content": [{"text": json.dumps({"error": str(e)})}],
            "_meta": {"tool": "filter_csv", "error": type(e).__name__},
            "isError": True,
        }


def node_hardware_sync() -> Dict[str, Any]:
    """
    Get node hardware information.

    Returns:
        Dict containing hardware information
    """
    try:
        logical_cores = psutil.cpu_count(logical=True) or os.cpu_count()
        physical_cores = psutil.cpu_count(logical=False)

        hardware_info = {
            "logical_cores": logical_cores,
            "physical_cores": physical_cores,
            "cpu_model": "Unknown",  # Could be enhanced with more detailed CPU info
            "memory_total": psutil.virtual_memory().total,
            "memory_available": psutil.virtual_memory().available,
        }

        return {
            "content": [{"text": json.dumps(hardware_info)}],
            "_meta": {"tool": "node_hardware"},
        }
    except Exception as e:
        return {
            "content": [{"text": json.dumps({"error": str(e)})}],
            "_meta": {"tool": "node_hardware", "error": type(e).__name__},
            "isError": True,
        }


async def list_hdf5_files(directory: str = "data") -> Dict[str, Any]:
    """
    List HDF5 files in a directory.

    Args:
        directory: Path to the directory containing HDF5 files

    Returns:
        Dict containing list of files and metadata
    """
    try:
        files = hdf5_list.list_hdf5(directory)
        return files
    except Exception as e:
        return {
            "content": [{"text": json.dumps({"error": str(e)})}],
            "_meta": {"tool": "list_hdf5", "error": type(e).__name__},
            "isError": True,
        }


async def inspect_hdf5_handler(filename: str) -> Dict[str, Any]:
    try:
        lines = inspect_hdf5.inspect_hdf5_file(filename)
        text = "\n".join(lines)
        return {"result": text}
    except Exception as e:
        return {
            "content": [{"text": json.dumps({"error": str(e)})}],
            "_meta": {"tool": "inspect_hdf5", "error": type(e).__name__},
            "isError": True,
        }


async def preview_hdf5_handler(filename: str, count: int = 10) -> Dict[str, Any]:
    try:
        data = preview_hdf5.preview_hdf5_datasets(filename, count)
        return data
    except Exception as e:
        return {
            "content": [{"text": json.dumps({"error": str(e)})}],
            "_meta": {"tool": "preview_hdf5", "error": type(e).__name__},
            "isError": True,
        }


async def read_all_hdf5_handler(filename: str) -> Dict[str, Any]:
    try:
        data = read_all_hdf5.read_all_hdf5_datasets(filename)
        return data
    except Exception as e:
        return {
            "content": [{"text": json.dumps({"error": str(e)})}],
            "_meta": {"tool": "read_all_hdf5", "error": type(e).__name__},
            "isError": True,
        }
