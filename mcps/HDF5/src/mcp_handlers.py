import json
from typing import Dict, List, Any, Optional
from capabilities import hdf5_list, inspect_hdf5, preview_hdf5, read_all_hdf5

class UnknownToolError(Exception):
    """Raised when an unsupported tool_name is requested."""
    pass

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
            "isError": True
        }

async def inspect_hdf5_handler(filename: str) -> Dict[str, Any]:
    try:
        lines = inspect_hdf5.inspect_hdf5_file(filename)
        text = "\n".join(lines)
        return text
    except Exception as e:
        return {
            "content": [{"text": json.dumps({"error": str(e)})}],
            "_meta": {"tool": "inspect_hdf5", "error": type(e).__name__},
            "isError": True
        }

async def preview_hdf5_handler(filename: str, count: int = 10) -> Dict[str, Any]:
    try:
        data = preview_hdf5.preview_hdf5_datasets(filename, count)
        return data
    except Exception as e:
        return {
            "content": [{"text": json.dumps({"error": str(e)})}],
            "_meta": {"tool": "preview_hdf5", "error": type(e).__name__},
            "isError": True
        }

async def read_all_hdf5_handler(filename: str) -> Dict[str, Any]:
    try:
        data = read_all_hdf5.read_all_hdf5_datasets(filename)
        return data
    except Exception as e:
        return {
            "content": [{"text": json.dumps({"error": str(e)})}],
            "_meta": {"tool": "read_all_hdf5", "error": type(e).__name__},
            "isError": True
        }