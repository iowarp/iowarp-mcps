"""Tests for lmod handler capabilities."""

import pytest
from unittest.mock import patch

from lmod_mcp.capabilities import lmod_handler


@pytest.mark.asyncio
async def test_list_loaded_modules_success():
    """Test successful listing of loaded modules."""
    mock_output = "gcc/11.2.0\npython/3.9.0\n"

    with patch("lmod_mcp.capabilities.lmod_handler._run_module_command") as mock_cmd:
        mock_cmd.return_value = (mock_output, "", 0)

        result = await lmod_handler.list_loaded_modules()

        assert result["success"] is True
        assert result["modules"] == ["gcc/11.2.0", "python/3.9.0"]
        assert result["count"] == 2
        mock_cmd.assert_called_once_with(["list", "-t"], capture_stderr=True)


@pytest.mark.asyncio
async def test_list_loaded_modules_failure():
    """Test failed listing of loaded modules."""
    with patch("lmod_mcp.capabilities.lmod_handler._run_module_command") as mock_cmd:
        mock_cmd.return_value = ("", "Error: Module command failed", 1)

        result = await lmod_handler.list_loaded_modules()

        assert result["success"] is False
        assert "error" in result
        assert result["modules"] == []


@pytest.mark.asyncio
async def test_search_available_modules():
    """Test searching for available modules."""
    mock_output = """
/apps/modules:
gcc/10.2.0
gcc/11.2.0
python/3.8.0
python/3.9.0
"""

    with patch("lmod_mcp.capabilities.lmod_handler._run_module_command") as mock_cmd:
        mock_cmd.return_value = ("", mock_output, 0)  # module avail outputs to stderr

        result = await lmod_handler.search_available_modules("python")

        assert result["success"] is True
        assert "python/3.8.0" in result["modules"]
        assert "python/3.9.0" in result["modules"]
        assert result["pattern"] == "python"
        mock_cmd.assert_called_once_with(["avail", "-t", "python"], capture_stderr=True)


@pytest.mark.asyncio
async def test_show_module_details():
    """Test showing module details."""
    mock_output = """
-------------------------------------------------------------------
/apps/modules/python/3.9.0.lua:
-------------------------------------------------------------------
help([[Python 3.9.0 programming language]])
whatis("Name: Python")
whatis("Version: 3.9.0")
prepend_path("PATH", "/apps/python/3.9.0/bin")
prepend_path("LD_LIBRARY_PATH", "/apps/python/3.9.0/lib")
conflict("python")
"""

    with patch("lmod_mcp.capabilities.lmod_handler._run_module_command") as mock_cmd:
        mock_cmd.return_value = (mock_output, "", 0)

        result = await lmod_handler.show_module_details("python/3.9.0")

        assert result["success"] is True
        assert result["module"] == "python/3.9.0"
        assert "Python 3.9.0 programming language" in result["help"]
        assert "Name: Python" in result["whatis"]
        assert any("PATH" in env for env in result["environment"])


@pytest.mark.asyncio
async def test_spider_search():
    """Test spider search functionality."""
    mock_output = """
The following is a list of the modules and their versions:

gcc: 10.2.0, 11.2.0, 12.1.0
python: 3.8.0, 3.9.0, 3.10.0, 3.11.0
openmpi: 4.1.0, 4.1.1
"""

    with patch("lmod_mcp.capabilities.lmod_handler._run_module_command") as mock_cmd:
        mock_cmd.return_value = ("", mock_output, 0)

        result = await lmod_handler.spider_search()

        assert result["success"] is True
        assert "gcc" in result["modules"]
        assert "11.2.0" in result["modules"]["gcc"]
        assert len(result["modules"]["python"]) == 4


@pytest.mark.asyncio
async def test_save_module_collection():
    """Test saving module collection."""
    with patch("lmod_mcp.capabilities.lmod_handler._run_module_command") as mock_cmd:
        mock_cmd.return_value = ("", "", 0)

        result = await lmod_handler.save_module_collection("my_environment")

        assert result["success"] is True
        assert result["collection"] == "my_environment"
        mock_cmd.assert_called_once_with(
            ["save", "my_environment"], capture_stderr=True
        )


@pytest.mark.asyncio
async def test_restore_module_collection():
    """Test restoring module collection."""
    with patch("lmod_mcp.capabilities.lmod_handler._run_module_command") as mock_cmd:
        # First call restores, second call lists modules
        mock_cmd.side_effect = [
            ("", "", 0),  # restore
            ("gcc/11.2.0\npython/3.9.0\n", "", 0),  # list
        ]

        result = await lmod_handler.restore_module_collection("my_environment")

        assert result["success"] is True
        assert result["collection"] == "my_environment"
        assert "gcc/11.2.0" in result["loaded_modules"]
        assert "python/3.9.0" in result["loaded_modules"]


@pytest.mark.asyncio
async def test_list_saved_collections():
    """Test listing saved collections."""
    mock_output = """
Named collection list:
  1) default   2) dev_env   3) prod_env
"""

    with patch("lmod_mcp.capabilities.lmod_handler._run_module_command") as mock_cmd:
        mock_cmd.return_value = (mock_output, "", 0)

        result = await lmod_handler.list_saved_collections()

        assert result["success"] is True
        assert "default" in result["collections"]
        assert "dev_env" in result["collections"]
        assert "prod_env" in result["collections"]
        assert result["count"] == 3


@pytest.mark.asyncio
async def test_module_command_not_found():
    """Test handling when module command is not found."""
    with patch(
        "lmod_mcp.capabilities.lmod_handler.asyncio.create_subprocess_exec"
    ) as mock_exec:
        mock_exec.side_effect = FileNotFoundError()

        stdout, stderr, returncode = await lmod_handler._run_module_command(["list"])

        assert returncode == 1
        assert "Module command not found" in stderr
        assert stdout == ""


@pytest.mark.asyncio
async def test_module_command_generic_exception():
    """Test handling when module command raises generic exception."""
    with patch(
        "lmod_mcp.capabilities.lmod_handler.asyncio.create_subprocess_exec"
    ) as mock_exec:
        mock_exec.side_effect = Exception("Generic error")

        stdout, stderr, returncode = await lmod_handler._run_module_command(["list"])

        assert returncode == 1
        assert "Error running module command: Generic error" in stderr
        assert stdout == ""


@pytest.mark.asyncio
async def test_search_available_modules_failure():
    """Test search_available_modules when command fails without output."""
    with patch("lmod_mcp.capabilities.lmod_handler._run_module_command") as mock_cmd:
        mock_cmd.return_value = ("", "", 1)  # Failure with no output

        result = await lmod_handler.search_available_modules("python")

        assert result["success"] is False
        assert result["error"] == "Failed to search modules"
        assert result["modules"] == []


@pytest.mark.asyncio
async def test_show_module_details_failure():
    """Test show_module_details when command fails."""
    with patch("lmod_mcp.capabilities.lmod_handler._run_module_command") as mock_cmd:
        mock_cmd.return_value = ("", "Module not found", 1)

        result = await lmod_handler.show_module_details("nonexistent/1.0")

        assert result["success"] is False
        assert "Module not found" in result["error"]


@pytest.mark.asyncio
async def test_spider_search_failure():
    """Test spider_search when command fails without output."""
    with patch("lmod_mcp.capabilities.lmod_handler._run_module_command") as mock_cmd:
        mock_cmd.return_value = ("", "", 1)  # Failure with no output

        result = await lmod_handler.spider_search("python")

        assert result["success"] is False
        assert result["error"] == "Failed to run spider search"
        assert result["modules"] == []


@pytest.mark.asyncio
async def test_save_module_collection_failure():
    """Test save_module_collection when command fails."""
    with patch("lmod_mcp.capabilities.lmod_handler._run_module_command") as mock_cmd:
        mock_cmd.return_value = ("", "Permission denied", 1)

        result = await lmod_handler.save_module_collection("test_env")

        assert result["success"] is False
        assert "Permission denied" in result["error"]
        assert result["collection"] == "test_env"


@pytest.mark.asyncio
async def test_restore_module_collection_failure():
    """Test restore_module_collection when command fails."""
    with patch("lmod_mcp.capabilities.lmod_handler._run_module_command") as mock_cmd:
        mock_cmd.return_value = ("", "Collection not found", 1)

        result = await lmod_handler.restore_module_collection("nonexistent")

        assert result["success"] is False
        assert "Collection not found" in result["error"]
        assert result["collection"] == "nonexistent"


@pytest.mark.asyncio
async def test_list_saved_collections_failure():
    """Test list_saved_collections when command fails."""
    with patch("lmod_mcp.capabilities.lmod_handler._run_module_command") as mock_cmd:
        mock_cmd.return_value = ("", "Command failed", 1)

        result = await lmod_handler.list_saved_collections()

        assert result["success"] is False
        assert "Command failed" in result["error"]
        assert result["collections"] == []


@pytest.mark.asyncio
async def test_list_saved_collections_no_named_collections():
    """Test list_saved_collections with no named collections output."""
    mock_output = "No named collections"

    with patch("lmod_mcp.capabilities.lmod_handler._run_module_command") as mock_cmd:
        mock_cmd.return_value = (mock_output, "", 0)

        result = await lmod_handler.list_saved_collections()

        assert result["success"] is True
        assert result["collections"] == []
        assert result["count"] == 0


@pytest.mark.asyncio
async def test_list_saved_collections_simple_names():
    """Test list_saved_collections with simple collection names (no numbers)."""
    mock_output = """
Named collection list:
default
dev_env  
prod_env
"""

    with patch("lmod_mcp.capabilities.lmod_handler._run_module_command") as mock_cmd:
        mock_cmd.return_value = (mock_output, "", 0)

        result = await lmod_handler.list_saved_collections()

        assert result["success"] is True
        assert "default" in result["collections"]
        assert "dev_env" in result["collections"]
        assert "prod_env" in result["collections"]
        assert result["count"] == 3


@pytest.mark.asyncio
async def test_show_module_details_with_path_and_prereqs():
    """Test show_module_details with module path and prerequisites."""
    mock_output = """
help([[This is python/3.9.0 help text]])
whatis("Name: Python")
whatis("Version: 3.9.0")
prereq("gcc/9.0")
conflict("python/2.7")
/apps/modulefiles/python/3.9.0.lua
prepend_path("PATH", "/apps/python/3.9.0/bin")
setenv("PYTHON_ROOT", "/apps/python/3.9.0")
"""

    with patch("lmod_mcp.capabilities.lmod_handler._run_module_command") as mock_cmd:
        mock_cmd.return_value = (mock_output, "", 0)

        result = await lmod_handler.show_module_details("python/3.9.0")

        assert result["success"] is True
        assert result["module"] == "python/3.9.0"
        assert "/apps/modulefiles/python/3.9.0.lua" in result["path"]
        assert "gcc/9.0" in result["prerequisites"]
        assert "python/2.7" in result["conflicts"]
        assert "This is python/3.9.0 help text" in result["help"][0]


@pytest.mark.asyncio
async def test_show_module_details_with_tcl_module():
    """Test show_module_details with .tcl module file."""
    mock_output = """
whatis("Name: GCC")
whatis("Version: 11.2.0")
/apps/modulefiles/gcc/11.2.0.tcl
setenv("CC", "gcc")
"""

    with patch("lmod_mcp.capabilities.lmod_handler._run_module_command") as mock_cmd:
        mock_cmd.return_value = (mock_output, "", 0)

        result = await lmod_handler.show_module_details("gcc/11.2.0")

        assert result["success"] is True
        assert "/apps/modulefiles/gcc/11.2.0.tcl" in result["path"]
