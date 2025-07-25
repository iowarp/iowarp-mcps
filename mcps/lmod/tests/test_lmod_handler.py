"""Tests for lmod handler capabilities."""
import pytest
from unittest.mock import patch, AsyncMock
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))
from capabilities import lmod_handler


@pytest.mark.asyncio
async def test_list_loaded_modules_success():
    """Test successful listing of loaded modules."""
    mock_output = "gcc/11.2.0\npython/3.9.0\n"
    
    with patch('capabilities.lmod_handler._run_module_command') as mock_cmd:
        mock_cmd.return_value = (mock_output, '', 0)
        
        result = await lmod_handler.list_loaded_modules()
        
        assert result['success'] is True
        assert result['modules'] == ['gcc/11.2.0', 'python/3.9.0']
        assert result['count'] == 2
        mock_cmd.assert_called_once_with(['list', '-t'], capture_stderr=True)


@pytest.mark.asyncio
async def test_list_loaded_modules_failure():
    """Test failed listing of loaded modules."""
    with patch('capabilities.lmod_handler._run_module_command') as mock_cmd:
        mock_cmd.return_value = ('', 'Error: Module command failed', 1)
        
        result = await lmod_handler.list_loaded_modules()
        
        assert result['success'] is False
        assert 'error' in result
        assert result['modules'] == []


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
    
    with patch('capabilities.lmod_handler._run_module_command') as mock_cmd:
        mock_cmd.return_value = ('', mock_output, 0)  # module avail outputs to stderr
        
        result = await lmod_handler.search_available_modules('python')
        
        assert result['success'] is True
        assert 'python/3.8.0' in result['modules']
        assert 'python/3.9.0' in result['modules']
        assert result['pattern'] == 'python'
        mock_cmd.assert_called_once_with(['avail', '-t', 'python'], capture_stderr=True)


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
    
    with patch('capabilities.lmod_handler._run_module_command') as mock_cmd:
        mock_cmd.return_value = (mock_output, '', 0)
        
        result = await lmod_handler.show_module_details('python/3.9.0')
        
        assert result['success'] is True
        assert result['module'] == 'python/3.9.0'
        assert 'Python 3.9.0 programming language' in result['help']
        assert 'Name: Python' in result['whatis']
        assert any('PATH' in env for env in result['environment'])


@pytest.mark.asyncio
async def test_load_modules():
    """Test loading modules."""
    with patch('capabilities.lmod_handler._run_module_command') as mock_cmd:
        mock_cmd.return_value = ('', '', 0)
        
        result = await lmod_handler.load_modules(['gcc/11.2.0', 'python/3.9.0'])
        
        assert result['success'] is True
        assert len(result['results']) == 2
        assert all(r['success'] for r in result['results'])
        assert mock_cmd.call_count == 2


@pytest.mark.asyncio
async def test_load_modules_partial_failure():
    """Test loading modules with partial failure."""
    with patch('capabilities.lmod_handler._run_module_command') as mock_cmd:
        # First module succeeds, second fails
        mock_cmd.side_effect = [
            ('', '', 0),
            ('', 'Module not found', 1)
        ]
        
        result = await lmod_handler.load_modules(['gcc/11.2.0', 'invalid/module'])
        
        assert result['success'] is False
        assert result['results'][0]['success'] is True
        assert result['results'][1]['success'] is False


@pytest.mark.asyncio
async def test_swap_modules():
    """Test swapping modules."""
    with patch('capabilities.lmod_handler._run_module_command') as mock_cmd:
        mock_cmd.return_value = ('', '', 0)
        
        result = await lmod_handler.swap_modules('gcc/10.2.0', 'gcc/11.2.0')
        
        assert result['success'] is True
        assert result['old_module'] == 'gcc/10.2.0'
        assert result['new_module'] == 'gcc/11.2.0'
        mock_cmd.assert_called_once_with(['swap', 'gcc/10.2.0', 'gcc/11.2.0'], capture_stderr=True)


@pytest.mark.asyncio
async def test_spider_search():
    """Test spider search functionality."""
    mock_output = """
The following is a list of the modules and their versions:

gcc: 10.2.0, 11.2.0, 12.1.0
python: 3.8.0, 3.9.0, 3.10.0, 3.11.0
openmpi: 4.1.0, 4.1.1
"""
    
    with patch('capabilities.lmod_handler._run_module_command') as mock_cmd:
        mock_cmd.return_value = ('', mock_output, 0)
        
        result = await lmod_handler.spider_search()
        
        assert result['success'] is True
        assert 'gcc' in result['modules']
        assert '11.2.0' in result['modules']['gcc']
        assert len(result['modules']['python']) == 4


@pytest.mark.asyncio
async def test_save_module_collection():
    """Test saving module collection."""
    with patch('capabilities.lmod_handler._run_module_command') as mock_cmd:
        mock_cmd.return_value = ('', '', 0)
        
        result = await lmod_handler.save_module_collection('my_environment')
        
        assert result['success'] is True
        assert result['collection'] == 'my_environment'
        mock_cmd.assert_called_once_with(['save', 'my_environment'], capture_stderr=True)


@pytest.mark.asyncio
async def test_restore_module_collection():
    """Test restoring module collection."""
    with patch('capabilities.lmod_handler._run_module_command') as mock_cmd:
        # First call restores, second call lists modules
        mock_cmd.side_effect = [
            ('', '', 0),  # restore
            ('gcc/11.2.0\npython/3.9.0\n', '', 0)  # list
        ]
        
        result = await lmod_handler.restore_module_collection('my_environment')
        
        assert result['success'] is True
        assert result['collection'] == 'my_environment'
        assert 'gcc/11.2.0' in result['loaded_modules']
        assert 'python/3.9.0' in result['loaded_modules']


@pytest.mark.asyncio
async def test_list_saved_collections():
    """Test listing saved collections."""
    mock_output = """
Named collection list:
  1) default   2) dev_env   3) prod_env
"""
    
    with patch('capabilities.lmod_handler._run_module_command') as mock_cmd:
        mock_cmd.return_value = (mock_output, '', 0)
        
        result = await lmod_handler.list_saved_collections()
        
        assert result['success'] is True
        assert 'default' in result['collections']
        assert 'dev_env' in result['collections']
        assert 'prod_env' in result['collections']
        assert result['count'] == 3


@pytest.mark.asyncio
async def test_module_command_not_found():
    """Test handling when module command is not found."""
    with patch('lmod_mcp.capabilities.lmod_handler.asyncio.create_subprocess_exec') as mock_exec:
        mock_exec.side_effect = FileNotFoundError()
        
        stdout, stderr, returncode = await lmod_handler._run_module_command(['list'])
        
        assert returncode == 1
        assert 'Module command not found' in stderr
        assert stdout == ''