from src.mcp_handlers import handle_mcp_request
from fastapi.testclient import TestClient
from src.server import app

client = TestClient(app)

#################################################################
#Test case1: Check MCP returning the resource list.
#################################################################
def test_list_resources():
    print("\nTest case1: Check MCP returning the resource list")
    request = {
        "jsonrpc": "2.0",
        "method": "mcp/listResources",
        "params": {},
        "id": 1
    }
    response = client.post("/mcp", json=request)
    assert response.status_code == 200
    result = response.json()["result"]
    #print(result)
    resource_names = [res["name"] for res in result]
    assert "HDF5" in resource_names
    assert "Slurm" in resource_names
    assert "Parquet" in resource_names
    assert "Compression" in resource_names

#################################################################
#Test case2: Check MCP returning error for wrong endpoint.
#################################################################
def test_unsupported_method():
    print("Test case2: Check MCP returning error for wrong endpoint.")
    request = {
        "jsonrpc": "2.0",
        "method": "mcp/unknownMethod",
        "params": {},
        "id": 1
    }
    response = client.post("/mcp", json=request)
    assert response.status_code == 400
    #print(response.json()["error"])
    assert response.json()["error"] == "Method not supported"

#################################################################
#Test case3: Check handling of wrong tool calling
#################################################################
def test_call_tool():
    print("Test case3: Check handling of wrong tool calling")
    request = {
        "jsonrpc": "2.0",
        "method": "mcp/callTool",
        "params": {"tool_name": "unknownTool"},
        "id": 1
    }
    response = client.post("/mcp", json=request)
    assert response.status_code == 400
   # print(response.json()["error"])
    assert response.json()["error"] == "Tool not recognized"

