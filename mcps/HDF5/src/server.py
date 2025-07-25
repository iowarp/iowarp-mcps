import os
import sys
import json
from fastmcp import FastMCP
from dotenv import load_dotenv

# Add the parent directory to Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Load environment variables from .env file
load_dotenv()

# Import HDF5 capabilities
import mcp_handlers

# Initialize FastMCP server instance
mcp = FastMCP("HDF5Server")

# ─── HDF5 TOOLS ─────────────────────────────────────────────────────────────

@mcp.tool(
    name="list_hdf5",
    description="List HDF5 files in a directory."
)
async def list_hdf5_tool(directory: str = "data/") -> dict:
    """
    List all HDF5 files in a specified directory with comprehensive file discovery and metadata extraction for scientific data management.

    Args:
        directory (str, optional): Path to directory containing HDF5 files (default: "data/")

    Returns:
        list: List of HDF5 files (.h5 and .hdf5 extensions) with file paths and basic metadata information.
    """
    try:
        return await mcp_handlers.list_hdf5_files(directory)
    except Exception as e:
        return {
            "content": [{"text": json.dumps({"error": str(e)})}],
            "_meta": {"tool": "list_hdf5", "error": type(e).__name__},
            "isError": True
        }
    
@mcp.tool(
    name="inspect_hdf5",
    description="Inspect HDF5 file structure: lists groups, datasets, and attributes."
)
async def inspect_hdf5_tool(filename: str) -> dict:
    """
    Inspect HDF5 file structure including detailed analysis of groups, datasets, and attributes for comprehensive data understanding.

    Args:
        filename (str): Absolute path to HDF5 file

    Returns:
        dict: Detailed structure information including group hierarchy, dataset properties, attribute metadata, and data organization.
    """
    try:
        return await mcp_handlers.inspect_hdf5_handler(filename)
    except Exception as e:
        return {
            "content": [{"text": json.dumps({"error": str(e)})}],
            "_meta": {"tool": "inspect_hdf5", "error": type(e).__name__},
            "isError": True
        }

@mcp.tool(
    name="preview_hdf5",
    description="Preview first N elements of each dataset in an HDF5 file."
)
async def preview_hdf5_tool(
    filename: str,
    count: int = 10
) -> dict:
    """
    Preview first N elements of each dataset in an HDF5 file with configurable data sampling for efficient data exploration.

    Args:
        filename (str): Absolute path to HDF5 file
        count (int, optional): Number of elements to preview from each dataset (default: 10)

    Returns:
        dict: Preview data from all datasets with specified element count, including data types and sample values.
    """
    try:
        return await mcp_handlers.preview_hdf5_handler(filename, count)
    except Exception as e:
        return {
            "content": [{"text": json.dumps({"error": str(e)})}],
            "_meta": {"tool": "preview_hdf5", "error": type(e).__name__},
            "isError": True
        }

@mcp.tool(
    name="read_all_hdf5",
    description="Read every element of every dataset in an HDF5 file."
)
async def read_all_hdf5_tool(filename: str) -> dict:
    """
    Read every element of every dataset in an HDF5 file with complete data extraction and memory-efficient processing.

    Args:
        filename (str): Absolute path to HDF5 file

    Returns:
        dict: Complete dataset contents with all elements, maintaining original data structure and types.
    """
    try:
        return await mcp_handlers.read_all_hdf5_handler(filename)
    except Exception as e:
        return {
            "content": [{"text": json.dumps({"error": str(e)})}],
            "_meta": {"tool": "read_all_hdf5", "error": type(e).__name__},
            "isError": True
        }

def main():
    """
    Main entry point to start the FastMCP server using the specified transport.
    Chooses between stdio and SSE based on MCP_TRANSPORT environment variable.
    """
    try:
        transport = os.getenv("MCP_TRANSPORT", "stdio").lower()
        if transport == "sse":
            host = os.getenv("MCP_SSE_HOST", "0.0.0.0")
            port = int(os.getenv("MCP_SSE_PORT", "8000"))
            print(json.dumps({"message": f"Starting SSE on {host}:{port}"}), file=sys.stderr)
            mcp.run(transport="sse", host=host, port=port)
        else:
            print(json.dumps({"message": "Starting stdio transport"}), file=sys.stderr)
            mcp.run(transport="stdio")
    except Exception as e:
        print(json.dumps({"error": str(e)}), file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    main()
