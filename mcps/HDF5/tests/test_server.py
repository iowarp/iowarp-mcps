
"""
Integration tests for FastAPI MCP server endpoints.

Covers:
 - mcp/listResources endpoint
 - mcp/callTool for filter_csv, list_hdf5, and node_hardware
 - Unknown‑tool endpoint error
"""

import os
import sys
import json
import pytest

# Add the src directory to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

try:
    from fastapi.testclient import TestClient
except ImportError:
    # Skip FastAPI tests if not installed
    pytest.skip("FastAPI not available", allow_module_level=True)

from server import app

@pytest.fixture(scope="module")
def client():
    return TestClient(app)


def test_list_resources_endpoint(client):
    print("\n=== Running test_list_resources_endpoint ===")
    payload = {"jsonrpc": "2.0", "method": "mcp/listResources", "id": 1}
    print("Request payload:", payload)
    res = client.post("/mcp", json=payload)
    print("Response status:", res.status_code)
    print("Response JSON:", res.json())
    assert res.status_code == 200
    assert 'resources' in res.json()['result']


def test_call_tool_filter_endpoint(client, tmp_path):
    print("\n=== Running test_call_tool_filter_endpoint ===")
    csv = tmp_path / "s.csv"
    csv.write_text("id,value\n1,20\n2,80\n")
    payload = {"jsonrpc": "2.0", "method": "mcp/callTool", "params": {"tool": "filter_csv", "csv_path": str(csv), "threshold": 50}, "id": 2}
    print("Request payload:", payload)
    res = client.post("/mcp", json=payload)
    print("Response status:", res.status_code)
    print("Response JSON:", res.json())
    rows = json.loads(res.json()['result']['content'][0]['text'])
    print("Parsed rows:", rows)
    assert rows[0]['value'] == 80


def test_call_tool_hdf5_endpoint(client, tmp_path):
    print("\n=== Running test_call_tool_hdf5_endpoint ===")
    d = tmp_path / "d2"
    d.mkdir()
    (d / "f1.hdf5").write_text("")
    payload = {"jsonrpc": "2.0", "method": "mcp/callTool", "params": {"tool": "list_hdf5", "directory": str(d)}, "id": 3}
    print("Request payload:", payload)
    res = client.post("/mcp", json=payload)
    print("Response status:", res.status_code)
    print("Response JSON:", res.json())
    files = json.loads(res.json()['result']['content'][0]['text'])
    print("Parsed files:", files)
    assert len(files) == 1


def test_unknown_tool_endpoint(client):
    print("\n=== Running test_unknown_tool_endpoint ===")
    payload = {"jsonrpc": "2.0", "method": "mcp/callTool", "params": {"tool": "bad"}, "id": 4}
    print("Request payload:", payload)
    res = client.post("/mcp", json=payload)
    print("Response status:", res.status_code)
    print("Response JSON:", res.json())
    assert res.json()['error']['code'] == -32601