import tempfile
import pathlib
from fastapi.testclient import TestClient
from src.server import app
import os
import pyarrow as pa
import pyarrow.parquet as pq

client = TestClient(app)

#################################################################
#Test case1: Check MCP returns only .hdf5 files
    # Creating a temporary directory
    # Creating 2 hdf5 files & one txt file
    # Sedning post request to callTool with tool_name as HDF5
#################################################################
def test_call_hdf5_tool_with_mock_files():
    print("\nTest case1: Check MCP returns only .hdf5 files")
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = pathlib.Path(temp_dir)

        # Create mock HDF5 and non-HDF5 files
        (temp_path / "mock1.hdf5").touch()
        (temp_path / "mock2.hdf5").touch()
        (temp_path / "ignore.txt").touch()

        # Construct the request with the temp path pattern
        request = {
            "jsonrpc": "2.0",
            "method": "mcp/callTool",
            "params": {
                "tool_name": "HDF5",
                "path_pattern": f"{temp_dir}/"
            },
            "id": 1
        }

        response = client.post("/mcp", json=request)
        assert response.status_code == 200
        result = response.json()["result"]
        #print(result)
        assert len(result) == 2
        assert any("mock1.hdf5" in file for file in result)
        assert any("mock2.hdf5" in file for file in result)
        assert all("ignore.txt" not in file for file in result)


#################################################################
#Test case2: Wrong File path
#################################################################
def test_call_hdf5_tool_with_incorrect_path():
    print("Test case2: Wrong File path")
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = pathlib.Path(temp_dir)
    # Construct the request with the temp path pattern
    request = {
        "jsonrpc": "2.0",
        "method": "mcp/callTool",
        "params": {
            "tool_name": "HDF5",
            "path_pattern": f"{temp_dir}/wrong_path/"
        },
        "id": 1
    }

    response = client.post("/mcp", json=request)
    assert response.status_code == 400
    #print(response.json()["detail"])
    

#################################################################
#Test case3: Check Slurm capability
    # Creating a temporary .sh file
    # Sedning post request to callTool with tool_name as Slurm
    # Checking  mock Job ID return or not.
#################################################################
def test_call_slurm_tool_with_mock_script():
    print("Test case3: Check Slurm capability")
    # Create a temporary dummy script file to simulate the Slurm script
    with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".sh") as tmp_script:
        tmp_script.write("#!/bin/bash\necho Hello Slurm\n")
        tmp_script_path = tmp_script.name

    try:
        request = {
            "jsonrpc": "2.0",
            "method": "mcp/callTool",
            "params": {
                "tool_name": "Slurm",
                "script_path": tmp_script_path,
                "core_count": 4
            },
            "id": 1
        }

        response = client.post("/mcp", json=request)
        assert response.status_code == 200
        result = response.json()["result"]
        #print(result)
        assert "Job submitted" in result
        assert "Mock Job ID" in result

    finally:
        # Clean up the temporary script file
        os.unlink(tmp_script_path)


#################################################################
#Test case4: Check Slurm capability - Passing empty script
#################################################################
def test_slurm_submit_with_missing_script_path():
    print("Test case4: Check Slurm capability - Passing empty script")
    request = {
        "jsonrpc": "2.0",
        "method": "mcp/callTool",
        "params": {
            "tool_name": "SLURM",
            "action": "submit",
            "script_path": ""  # Missing or empty script path
        },
        "id": 1
    }

    response = client.post("/mcp", json=request)

    assert response.status_code == 400
    assert "error" in response.json()
    #print(response.json()["error"])


#################################################################
#Test case5: 
    #created a parquet table with two columns name & age
    #Reading a column age.
#################################################################
def test_parquet_read_column(tmp_path):
    print("Test case5: parquet read column")
    data = pa.table({'name': ['Alice', 'Bob'], 'age': [25, 30]})
    parquet_path = tmp_path / "sample.parquet"
    pq.write_table(data, parquet_path)

    request = {
        "jsonrpc": "2.0",
        "method": "mcp/callTool",
        "params": {
            "tool_name": "Parquet",
            "action": "read_column",
            "file_path": str(parquet_path),
            "column_name": "age",
        },
        "id": 1
    }

    response = client.post("/mcp", json=request)
    assert response.status_code == 200
   # print(response.json())
    assert response.json()["result"] == {"age":[25, 30]}

#################################################################
#Test case6: 
    #created a parquet table with two columns name & age
    #Reading a non-exist column.
#################################################################
def test_parquet_read_incorrect_column(tmp_path):
    print("Test case6: parquet read incorrect column")
    data = pa.table({'name': ['Alice', 'Bob'], 'age': [25, 30]})
    parquet_path = tmp_path / "sample.parquet"
    pq.write_table(data, parquet_path)

    request = {
        "jsonrpc": "2.0",
        "method": "mcp/callTool",
        "params": {
            "tool_name": "Parquet",
            "action": "read_column",
            "file_path": str(parquet_path),
            "column_name": "unknown",
        },
        "id": 1
    }

    response = client.post("/mcp", json=request)
    #print(response.json())
    assert response.json()["result"]["status_code"] == 400

#################################################################
#Test case7: compressing a file - output.log
#################################################################
def test_compression_gzip(tmp_path):
    print("Test case7: compressing a file")
    file_path = tmp_path / "output.log"
    file_path.write_text("This is some log data.")

    request = {
        "jsonrpc": "2.0",
        "method": "mcp/callTool",
        "params": {
            "tool_name": "Compression",
            "file_path": str(file_path)
        },
        "id": 1
    }

    response = client.post("/mcp", json=request)
    result = response.json()["result"]
    #print(result)
    assert result["status_code"] == 200
    assert "output.log.gz" in result["body"]


#################################################################
#Test case8: compressing a file - Sendin non-exist file
#################################################################
def test_compression_gzip_incorrect_file():
    print("Test case8: compressing a file - Sending non-exist file")
    request = {
        "jsonrpc": "2.0",
        "method": "mcp/callTool",
        "params": {
            "tool_name": "Compression",
            "file_path": "unknown.log"
        },
        "id": 1
    }

    response = client.post("/mcp", json=request)
    result = response.json()["result"]
    #print(result)
    assert result["status_code"] == 400