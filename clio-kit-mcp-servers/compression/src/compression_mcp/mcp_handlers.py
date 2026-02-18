"""MCP handlers for compression capabilities."""

from fastmcp.exceptions import ToolError
from .capabilities.compression_base import compress_file, decompress_file


async def compress_file_handler(file_path: str) -> dict:
    """Handler wrapping the file compression capability for MCP.

    Args:
        file_path: Path to the file to compress

    Returns:
        Compression results dictionary

    Raises:
        ToolError: On any compression failure
    """
    try:
        return await compress_file(file_path)
    except Exception as e:
        raise ToolError(str(e)) from e


async def decompress_file_handler(file_path: str) -> dict:
    """Handler wrapping the file decompression capability for MCP.

    Args:
        file_path: Path to the .gz file to decompress

    Returns:
        Decompression results dictionary

    Raises:
        ToolError: On any decompression failure
    """
    try:
        return await decompress_file(file_path)
    except Exception as e:
        raise ToolError(str(e)) from e
