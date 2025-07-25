import json
from fastapi.responses import JSONResponse
from src.capabilities.hdf5_handler import list_hdf5_files
from src.capabilities.slurm_handler import submit_slurm_job
from src.capabilities.parquet_handler import read_parquet_column
from src.capabilities.compression_handler import file_compression

async def handle_mcp_request(request: dict):
    jsonrpc = request.get("jsonrpc")
    method = request.get("method")
    params = request.get("params")
    request_id = request.get("id")

    if method == "mcp/listResources":
        return await list_resources()
    elif method == "mcp/callTool":
        return await call_tool(params)
    else:
        return JSONResponse(content={"error": "Method not supported"}, status_code=400)
    

async def list_resources():
    resources = [
        {"name": "HDF5", "type": "data", "details": "Mocked HDF5 resource"},
        {"name": "Slurm", "type": "tool", "details": "Mocked Slurm job submission"},
        {"name": "Parquet", "type": "data", "details": "Columnar storage file format"},
        {"name": "Compression", "type": "tool", "details": "Data compression"}
    ]
    return JSONResponse(content={"jsonrpc": "2.0", "result": resources, "id": 1})

async def call_tool(params):
    tool_name = params.get("tool_name")
    if tool_name == "Slurm":
        return await slurm_tool_action(params)
    elif tool_name == "HDF5":
        return await hdf5_tool_action(params)
    elif tool_name == "Parquet":
        return await parquet_tool_action(params)
    elif tool_name == "Compression":
        return await compression_tool_action(params)
    else:
        return JSONResponse(content={"error": "Tool not recognized"}, status_code=400)

async def slurm_tool_action(params):
    # Assuming you are simulating job submission
    script_path = params.get("script_path")
    core_count = params.get("core_count", 1)
    job_id = submit_slurm_job(script_path, core_count)
    return JSONResponse(content={"jsonrpc": "2.0", "result": job_id, "id": 1})

async def hdf5_tool_action(params):
    path_pattern = params.get("path_pattern", "./")
    files = list_hdf5_files(path_pattern)
    return JSONResponse(content={"jsonrpc": "2.0", "result": files, "id": 1})

async def parquet_tool_action(params):
    action = params.get("action")
    file_path = params.get("file_path")
    column_name = params.get("column_name")
    data = read_parquet_column(action, file_path, column_name)
    return {"jsonrpc": "2.0", "result": data, "id": 1}

async def compression_tool_action(params):
    file_path = params.get("file_path")
    data = file_compression(file_path)
    return {"jsonrpc": "2.0", "result": data, "id": 1}