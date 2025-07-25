# test_mcp_handlers file
import pytest
from src.mcp_handlers import handle_mcp_request, list_resources, list_tools, call_tool, get_resource

@pytest.mark.asyncio
async def test_list_resources():
    """Test listing available resources."""
    result, metadata = await list_resources({})
    
    assert "resources" in result
    assert isinstance(result["resources"], list)
    assert len(result["resources"]) > 0
    assert metadata["status"] == "success"
    
    # Check structure of a resource
    resource = result["resources"][0]
    assert "id" in resource
    assert "type" in resource
    assert "description" in resource

@pytest.mark.asyncio
async def test_list_tools():
    """Test listing available tools."""
    result, metadata = await list_tools({})
    
    assert "tools" in result
    assert isinstance(result["tools"], list)
    assert len(result["tools"]) > 0
    assert metadata["status"] == "success"
    
    # Check structure of a tool
    tool = result["tools"][0]
    assert "id" in tool
    assert "type" in tool
    assert "description" in tool

@pytest.mark.asyncio
async def test_get_resource_missing_id():
    """Test getting a resource without providing an ID."""
    result, metadata = await get_resource({})
    
    assert not result
    assert metadata["status"] == "error"
    assert "Resource ID is required" in metadata["message"]

@pytest.mark.asyncio
async def test_get_resource_nonexistent():
    """Test getting a non-existent resource."""
    result, metadata = await get_resource({"resource_id": "nonexistent_resource"})
    
    assert not result
    assert metadata["status"] == "error"
    assert "Resource not found" in metadata["message"]

@pytest.mark.asyncio
async def test_get_resource_valid():
    """Test getting a valid resource."""
    result, metadata = await get_resource({"resource_id": "hdf5_files"})
    
    assert "resource_details" in result
    assert metadata["status"] == "success"
    assert result["resource_details"]["id"] == "hdf5_files"

@pytest.mark.asyncio
async def test_call_tool_missing_id():
    """Test calling a tool without providing an ID."""
    result, metadata = await call_tool({})
    
    assert not result
    assert metadata["status"] == "error"
    assert "Tool ID is required" in metadata["message"]

@pytest.mark.asyncio
async def test_call_tool_nonexistent():
    """Test calling a non-existent tool."""
    result, metadata = await call_tool({"tool_id": "nonexistent_tool"})
    
    assert not result
    assert metadata["status"] == "error"
    assert "Tool not found" in metadata["message"]

@pytest.mark.asyncio
async def test_handle_mcp_request_unknown_method():
    """Test handling an unknown MCP method."""
    result, metadata = await handle_mcp_request("unknown/method", {})
    
    assert not result
    assert metadata["status"] == "error"
    assert "Unknown method" in metadata["message"]

