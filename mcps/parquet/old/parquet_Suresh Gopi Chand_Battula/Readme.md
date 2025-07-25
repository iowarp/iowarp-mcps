## Suresh Gopi Chand Battula A20538580

## MCP Server

A Model Context Protocol (MCP) server for scientific computing resources, enabling AI agents and Large Language Models (LLMs) to interact with scientific data and tools through a standardized interface.

# Overview

This project implements a Scientific MCP Server that acts as a gateway between AI agents/LLMs and scientific computing resources. It follows the JSON-RPC 2.0 protocol and provides a modular, asynchronous architecture for handling scientific data operations and utilities.

## MCP capabilities Implimented : 
## Features

Implemented MCP JSON-RPC 2.0 protocol for AI agent interaction

      Data-focused capabilities:
         -HDF5 file system interaction for scientific datasets
         -Parquet columnar data format operations for efficient data storage
         -Pandas data analysis for data manipulation and filtering
      Tool/utility-focused capabilities:
         -Parallel sorting for large log files
         -File compression utilities with gzip, bz2, and zip support
         -Data visualization with Matplotlib for scientific plotting

## Requirements

Python 3.10 or higher
Dependencies listed in pyproject.toml:
    fastapi
    uvicorn
    pydantic
    python-multipart
    h5py
    pyarrow
    pandas
    matplotlib
    jinja2 (for HTML templates)

## Project Structure
    mcp_server/
    ├── pyproject.toml     # Project metadata and dependencies
    ├── README.md          # This file
    ├── src/               # Source code
    │   ├── __init__.py
    │   ├── server.py      # Main server application
    │   ├── mcp_handlers.py # MCP method handlers
    │   └── capabilities/  # Capability implementations
    │       ├── __init__.py
    │       ├── hdf5_handler.py
    │       ├── parquet_handler.py
    │       ├── pandas_handler.py
    │       ├── parallel_sort.py
    │       ├── compression.py # fully implemented not simulated
    │       └── visualization.py
    └── tests/             # Test suite
        ├── __init__.py
        ├── test_mcp_handlers.py
        └── test_capabilities.py

## Installation

Clone this repository:

    git clone https://github.com/sureshgopichand/mcp_server.git
    cd mcp_server

Create and activate a virtual environment:

    Using venv (if uv is not available)
    python3 -m venv venv
    source venv/bin/activate  # On Windows: venv\Scripts\activate
    Or using uv (if installed)
    uv venv
    source .venv/bin/activate  # On Windows: .venv\Scripts\activate

 Install dependencies:
 
    Using pip
    pip install -e .
    Or using uv
    uv pip install -e .

Install development dependencies (optional):

    Using pip
    pip install pytest pytest-asyncio httpx
    Or using uv
    uv pip install -e ".[dev]"


## Running the Server

python -m src.server

## Start the server with:

The server will be available at http://localhost:8000.

## API Endpoints

/mcp: Main MCP JSON-RPC 2.0 endpoint

/health: Health check endpoint

/docs: FastAPI auto-generated documentation (Swagger UI)

/: Web UI for interacting with the server

MCP Methods

The server implements the following MCP methods:

      mcp/listResources: List available scientific data resources
      {
        "method": "mcp/listResources",
        "params": {},
        "id": "1",
        "jsonrpc": "2.0"
      }
      mcp/getResource: Get details about a specific resource
      {
        "method": "mcp/getResource",
        "params": {
          "resource_id": "hdf5_files"
        },
        "id": "2",
        "jsonrpc": "2.0"
      }
      mcp/listTools: List available scientific tools
      {
        "method": "mcp/listTools",
        "params": {},
        "id": "3",
        "jsonrpc": "2.0"
      }
      mcp/callTool: Execute a tool with parameters
      {
        "method": "mcp/callTool",
        "params": {
          "tool_id": "hdf5",
          "tool_params": {
            "operation": "find_files",
            "directory": "/data/sim_run_123",
            "pattern": "*.hdf5"
          }
        },
        "id": "4",
        "jsonrpc": "2.0"
      }

## Example Requests

List Resources - Get Resource Details
List Tools     - Call Tool (HDF5 Find Files)
Call Tool (Compression)
Call Tool (Plot Data)

## Testing

Run the test suite with:

      pytest

This will execute all tests in the tests/ directory, verifying the functionality of MCP handlers and individual capabilities.

## Troubleshooting

ModuleNotFoundError: Make sure your virtual environment is activated and all dependencies are installed.

ImportError: Check that your file structure matches the imports in your code.

Permission denied: Ensure you have execute permissions for your Python files.

Port already in use: Change the port in server.py if port 8000 is already in use.

## Future Enhancements

Add authentication and authorization

Implement more scientific data formats

Add support for remote computation resources

Enhance visualization capabilities

Implement streaming responses for large data

## License
This project is licensed under the MIT License
