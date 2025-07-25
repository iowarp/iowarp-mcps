
"""
Unit tests for mcp_handlers module.

Covers:
 - list_resources() returning correct resource count
 - call_tool dispatch for filter_csv, list_hdf5, node_hardware
 - Unknown‑tool error handling
"""

import os
import sys
import json
import pytest

# Add the src directory to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

import mcp_handlers


def test_list_resources():
    print("\n=== Running test_list_resources ===")
    res = mcp_handlers.list_resources()
    print("Resources returned:", res)
    assert res['_meta']['count'] == 3


def test_call_tool_filter(tmp_path):
    print("\n=== Running test_call_tool_filter ===")
    csv = tmp_path / "t.csv"
    csv.write_text("id,value\n1,10\n2,100\n")
    params = {"tool": "filter_csv", "csv_path": str(csv), "threshold": 50}
    print(f"Calling filter_csv with params: {params}")
    result = mcp_handlers.call_tool("filter_csv", params)
    print("Raw handler result:", result)
    data = json.loads(result['content'][0]['text'])
    print("Parsed JSON data:", data)
    assert data[0]['value'] == 100


def test_call_tool_list_hdf5(tmp_path):
    print("\n=== Running test_call_tool_list_hdf5 ===")
    d = tmp_path / "d"
    d.mkdir()
    (d / "x.hdf5").write_text("")
    params = {"tool": "list_hdf5", "directory": str(d)}
    print(f"Calling list_hdf5 with params: {params}")
    res = mcp_handlers.call_tool("list_hdf5", params)
    print("Raw handler result:", res)
    files = json.loads(res['content'][0]['text'])
    print("Parsed file list:", files)
    assert len(files) == 1


def test_call_tool_node_hardware():
    print("=== Running test_call_tool_node_hardware ===")
    result = mcp_handlers.call_tool("node_hardware", {"tool":"node_hardware"})
    print("Raw result:", result)
    data = json.loads(result['content'][0]['text'])
    print("Parsed data:", data)
    import os, psutil
    logical = psutil.cpu_count(logical=True) or os.cpu_count()
    physical = psutil.cpu_count(logical=False)
    print(f"Expected logical={logical}, physical={physical}")
    assert data['logical_cores'] == logical
    assert data['physical_cores'] == physical


def test_unknown_tool():
    print("\n=== Running test_unknown_tool ===")
    with pytest.raises(Exception) as excinfo:
        mcp_handlers.call_tool("bad", {})
    print("Caught exception:", excinfo.value)