"""Tests for lmod MCP server."""

import pytest
from unittest.mock import patch, AsyncMock

from fastmcp.exceptions import ToolError

from lmod_mcp import server


@pytest.mark.asyncio
async def test_module_list_tool():
    """Test module_list tool."""
    mock_result = {
        "success": True,
        "modules": ["gcc/11.2.0", "python/3.9.0"],
        "count": 2,
    }

    with patch(
        "lmod_mcp.server.lmod_handler.list_loaded_modules", new_callable=AsyncMock
    ) as mock_handler:
        mock_handler.return_value = mock_result

        result = await server.module_list_tool()

        assert result == mock_result
        mock_handler.assert_called_once()


@pytest.mark.asyncio
async def test_module_list_tool_error():
    """Test module_list tool raises ToolError on failure."""
    mock_result = {
        "success": False,
        "error": "Module command not found",
        "modules": [],
    }

    with patch(
        "lmod_mcp.server.lmod_handler.list_loaded_modules", new_callable=AsyncMock
    ) as mock_handler:
        mock_handler.return_value = mock_result

        with pytest.raises(ToolError, match="Module command not found"):
            await server.module_list_tool()


@pytest.mark.asyncio
async def test_module_avail_tool():
    """Test module_avail tool."""
    mock_result = {
        "success": True,
        "modules": ["python/3.8.0", "python/3.9.0"],
        "count": 2,
        "pattern": "python",
    }

    with patch(
        "lmod_mcp.server.lmod_handler.search_available_modules", new_callable=AsyncMock
    ) as mock_handler:
        mock_handler.return_value = mock_result

        result = await server.module_avail_tool(pattern="python")

        assert result == mock_result
        mock_handler.assert_called_once_with("python")


@pytest.mark.asyncio
async def test_module_avail_tool_error():
    """Test module_avail tool raises ToolError on failure."""
    mock_result = {"success": False, "error": "Failed to search modules", "modules": []}

    with patch(
        "lmod_mcp.server.lmod_handler.search_available_modules", new_callable=AsyncMock
    ) as mock_handler:
        mock_handler.return_value = mock_result

        with pytest.raises(ToolError, match="Failed to search modules"):
            await server.module_avail_tool(pattern="nonexistent")


@pytest.mark.asyncio
async def test_module_show_tool():
    """Test module_show tool."""
    mock_result = {
        "success": True,
        "module": "python/3.9.0",
        "path": "/apps/modules/python/3.9.0.lua",
        "help": ["Python 3.9.0 programming language"],
        "whatis": ["Name: Python", "Version: 3.9.0"],
        "prerequisites": [],
        "conflicts": ["python"],
        "environment": ['prepend_path("PATH", "/apps/python/3.9.0/bin")'],
    }

    with patch(
        "lmod_mcp.server.lmod_handler.show_module_details", new_callable=AsyncMock
    ) as mock_handler:
        mock_handler.return_value = mock_result

        result = await server.module_show_tool("python/3.9.0")

        assert result == mock_result
        mock_handler.assert_called_once_with("python/3.9.0")


@pytest.mark.asyncio
async def test_module_show_tool_error():
    """Test module_show tool raises ToolError on failure."""
    mock_result = {
        "success": False,
        "error": "Module foo not found",
        "module": "foo",
    }

    with patch(
        "lmod_mcp.server.lmod_handler.show_module_details", new_callable=AsyncMock
    ) as mock_handler:
        mock_handler.return_value = mock_result

        with pytest.raises(ToolError, match="Module foo not found"):
            await server.module_show_tool("foo")


@pytest.mark.asyncio
async def test_module_load_tool():
    """Test module_load tool."""
    mock_result = {
        "success": True,
        "results": [
            {
                "module": "gcc/11.2.0",
                "success": True,
                "message": "Successfully loaded gcc/11.2.0",
            },
            {
                "module": "python/3.9.0",
                "success": True,
                "message": "Successfully loaded python/3.9.0",
            },
        ],
    }

    with patch(
        "lmod_mcp.server.lmod_handler.load_modules", new_callable=AsyncMock
    ) as mock_handler:
        mock_handler.return_value = mock_result

        result = await server.module_load_tool(["gcc/11.2.0", "python/3.9.0"])

        assert result == mock_result
        mock_handler.assert_called_once_with(["gcc/11.2.0", "python/3.9.0"])


@pytest.mark.asyncio
async def test_module_load_tool_error():
    """Test module_load tool raises ToolError on failure."""
    mock_result = {
        "success": False,
        "results": [
            {
                "module": "bad/1.0",
                "success": False,
                "error": "Module bad/1.0 not found",
            }
        ],
    }

    with patch(
        "lmod_mcp.server.lmod_handler.load_modules", new_callable=AsyncMock
    ) as mock_handler:
        mock_handler.return_value = mock_result

        with pytest.raises(ToolError, match="Failed to load modules"):
            await server.module_load_tool(["bad/1.0"])


@pytest.mark.asyncio
async def test_module_unload_tool():
    """Test module_unload tool."""
    mock_result = {
        "success": True,
        "results": [
            {
                "module": "python/3.9.0",
                "success": True,
                "message": "Successfully unloaded python/3.9.0",
            }
        ],
    }

    with patch(
        "lmod_mcp.server.lmod_handler.unload_modules", new_callable=AsyncMock
    ) as mock_handler:
        mock_handler.return_value = mock_result

        result = await server.module_unload_tool(["python/3.9.0"])

        assert result == mock_result
        mock_handler.assert_called_once_with(["python/3.9.0"])


@pytest.mark.asyncio
async def test_module_unload_tool_error():
    """Test module_unload tool raises ToolError on failure."""
    mock_result = {
        "success": False,
        "results": [
            {
                "module": "notloaded/1.0",
                "success": False,
                "error": "Module notloaded/1.0 is not loaded",
            }
        ],
    }

    with patch(
        "lmod_mcp.server.lmod_handler.unload_modules", new_callable=AsyncMock
    ) as mock_handler:
        mock_handler.return_value = mock_result

        with pytest.raises(ToolError, match="Failed to unload modules"):
            await server.module_unload_tool(["notloaded/1.0"])


@pytest.mark.asyncio
async def test_module_swap_tool():
    """Test module_swap tool."""
    mock_result = {
        "success": True,
        "message": "Successfully swapped gcc/10.2.0 with gcc/11.2.0",
        "old_module": "gcc/10.2.0",
        "new_module": "gcc/11.2.0",
    }

    with patch(
        "lmod_mcp.server.lmod_handler.swap_modules", new_callable=AsyncMock
    ) as mock_handler:
        mock_handler.return_value = mock_result

        result = await server.module_swap_tool("gcc/10.2.0", "gcc/11.2.0")

        assert result == mock_result
        mock_handler.assert_called_once_with("gcc/10.2.0", "gcc/11.2.0")


@pytest.mark.asyncio
async def test_module_swap_tool_error():
    """Test module_swap tool raises ToolError on failure."""
    mock_result = {
        "success": False,
        "error": "Failed to swap old with new",
        "old_module": "old",
        "new_module": "new",
    }

    with patch(
        "lmod_mcp.server.lmod_handler.swap_modules", new_callable=AsyncMock
    ) as mock_handler:
        mock_handler.return_value = mock_result

        with pytest.raises(ToolError, match="Failed to swap old with new"):
            await server.module_swap_tool("old", "new")


@pytest.mark.asyncio
async def test_module_spider_tool():
    """Test module_spider tool."""
    mock_result = {
        "success": True,
        "modules": {
            "gcc": ["10.2.0", "11.2.0", "12.1.0"],
            "python": ["3.8.0", "3.9.0", "3.10.0"],
        },
        "pattern": None,
    }

    with patch(
        "lmod_mcp.server.lmod_handler.spider_search", new_callable=AsyncMock
    ) as mock_handler:
        mock_handler.return_value = mock_result

        result = await server.module_spider_tool(pattern=None)

        assert result == mock_result
        mock_handler.assert_called_once_with(None)


@pytest.mark.asyncio
async def test_module_spider_tool_error():
    """Test module_spider tool raises ToolError on failure."""
    mock_result = {"success": False, "error": "Failed to run spider search", "modules": []}

    with patch(
        "lmod_mcp.server.lmod_handler.spider_search", new_callable=AsyncMock
    ) as mock_handler:
        mock_handler.return_value = mock_result

        with pytest.raises(ToolError, match="Failed to run spider search"):
            await server.module_spider_tool(pattern="bad")


@pytest.mark.asyncio
async def test_module_save_tool():
    """Test module_save tool."""
    mock_result = {
        "success": True,
        "message": "Successfully saved module collection as my_env",
        "collection": "my_env",
    }

    with patch(
        "lmod_mcp.server.lmod_handler.save_module_collection", new_callable=AsyncMock
    ) as mock_handler:
        mock_handler.return_value = mock_result

        result = await server.module_save_tool("my_env")

        assert result == mock_result
        mock_handler.assert_called_once_with("my_env")


@pytest.mark.asyncio
async def test_module_save_tool_error():
    """Test module_save tool raises ToolError on failure."""
    mock_result = {
        "success": False,
        "error": "Failed to save collection bad_name",
        "collection": "bad_name",
    }

    with patch(
        "lmod_mcp.server.lmod_handler.save_module_collection", new_callable=AsyncMock
    ) as mock_handler:
        mock_handler.return_value = mock_result

        with pytest.raises(ToolError, match="Failed to save collection bad_name"):
            await server.module_save_tool("bad_name")


@pytest.mark.asyncio
async def test_module_restore_tool():
    """Test module_restore tool."""
    mock_result = {
        "success": True,
        "message": "Successfully restored module collection my_env",
        "collection": "my_env",
        "loaded_modules": ["gcc/11.2.0", "python/3.9.0"],
    }

    with patch(
        "lmod_mcp.server.lmod_handler.restore_module_collection", new_callable=AsyncMock
    ) as mock_handler:
        mock_handler.return_value = mock_result

        result = await server.module_restore_tool("my_env")

        assert result == mock_result
        mock_handler.assert_called_once_with("my_env")


@pytest.mark.asyncio
async def test_module_restore_tool_error():
    """Test module_restore tool raises ToolError on failure."""
    mock_result = {
        "success": False,
        "error": "Failed to restore collection missing",
        "collection": "missing",
    }

    with patch(
        "lmod_mcp.server.lmod_handler.restore_module_collection", new_callable=AsyncMock
    ) as mock_handler:
        mock_handler.return_value = mock_result

        with pytest.raises(ToolError, match="Failed to restore collection missing"):
            await server.module_restore_tool("missing")


@pytest.mark.asyncio
async def test_module_savelist_tool():
    """Test module_savelist tool."""
    mock_result = {
        "success": True,
        "collections": ["default", "dev_env", "prod_env"],
        "count": 3,
    }

    with patch(
        "lmod_mcp.server.lmod_handler.list_saved_collections", new_callable=AsyncMock
    ) as mock_handler:
        mock_handler.return_value = mock_result

        result = await server.module_savelist_tool()

        assert result == mock_result
        mock_handler.assert_called_once()


@pytest.mark.asyncio
async def test_module_savelist_tool_error():
    """Test module_savelist tool raises ToolError on failure."""
    mock_result = {
        "success": False,
        "error": "Failed to list saved collections",
        "collections": [],
    }

    with patch(
        "lmod_mcp.server.lmod_handler.list_saved_collections", new_callable=AsyncMock
    ) as mock_handler:
        mock_handler.return_value = mock_result

        with pytest.raises(ToolError, match="Failed to list saved collections"):
            await server.module_savelist_tool()


def test_main_function():
    """Test the main function entry point."""
    with (
        patch("sys.argv", ["lmod-mcp"]),
        patch.object(server.mcp, "run") as mock_mcp_run,
    ):
        server.main()

        mock_mcp_run.assert_called_once_with(
            transport="stdio"
        )


def test_main_module_execution():
    """Test __main__ module execution."""
    with patch("lmod_mcp.server.main") as mock_main:
        # Simulate running the module directly
        exec(
            "if __name__ == '__main__': main()",
            {"__name__": "__main__", "main": mock_main},
        )

        mock_main.assert_called_once()


def test_module_system_status_resource():
    """Test the lmod://status resource."""
    result = server.module_system_status()
    assert result["system"] == "lmod"
    assert "list" in result["operations"]
    assert "load" in result["operations"]
    assert "spider" in result["operations"]


def test_setup_environment_prompt():
    """Test the setup_environment prompt."""
    messages = server.setup_environment("tensorflow")
    assert len(messages) == 1
    text = messages[0].content.text
    assert "tensorflow" in text
    assert "Search available modules" in text
