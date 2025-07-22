"""
MCP handlers for compression capabilities.
These handlers wrap the compression capabilities for MCP protocol compliance.
"""
import json
from typing import Dict, Any
from capabilities.compression_base import compress_file


async def compress_file_handler(file_path: str) -> Dict[str, Any]:
    """
    Handler wrapping the file compression capability for MCP.
    Returns compression results or an error payload on failure.
    
    Args:
        file_path: Path to the file to compress
        
    Returns:
        MCP-compliant response dictionary
    """
    try:
        result = await compress_file(file_path)
        return result
    except Exception as e:
        return {
            "content": [{"text": json.dumps({"error": str(e)})}],
            "_meta": {"tool": "compress_file", "error": type(e).__name__},
            "isError": True
        }