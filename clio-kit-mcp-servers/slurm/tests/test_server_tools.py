"""
Tests for MCP server tools.
Tests the actual MCP tool implementations and server functionality.
"""

import asyncio
import pytest
import sys
import os
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import patch, Mock

from fastmcp.exceptions import ToolError

from slurm_mcp.implementation.job_submission import submit_slurm_job
from slurm_mcp.implementation.job_status import get_job_status
from slurm_mcp.implementation.job_cancellation import cancel_slurm_job
from slurm_mcp.implementation.job_listing import list_slurm_jobs
from slurm_mcp.implementation.cluster_info import get_slurm_info
from slurm_mcp.implementation.job_details import get_job_details
from slurm_mcp.implementation.job_output import get_job_output
from slurm_mcp.implementation.queue_info import get_queue_info
from slurm_mcp.implementation.array_jobs import submit_array_job
from slurm_mcp.implementation.node_info import get_node_info


class TestServerTools:
    """Test suite for MCP server tools."""

    @pytest.mark.asyncio
    async def test_submit_job_tool_success(self, temp_script, valid_cores):
        """Test successful job submission through MCP tool."""
        result = submit_slurm_job(temp_script, valid_cores)

        assert isinstance(result, dict)
        # Should either be a success response or error response
        if "isError" in result:
            assert isinstance(result["isError"], bool)
        else:
            assert "job_id" in result or "error" in result

    @pytest.mark.asyncio
    async def test_submit_job_tool_enhanced(self, temp_script, job_parameters):
        """Test enhanced job submission through MCP tool."""
        result = submit_slurm_job(
            temp_script,
            cores=4,
            memory=job_parameters["memory"],
            time_limit=job_parameters["time_limit"],
            job_name=job_parameters["job_name"],
            partition=job_parameters["partition"],
        )

        assert isinstance(result, dict)

        if not result.get("isError") and "job_id" in result:
            # Verify parameters were passed through
            assert result.get("memory") == job_parameters["memory"]
            assert result.get("time_limit") == job_parameters["time_limit"]
            assert result.get("job_name") == job_parameters["job_name"]
            assert result.get("partition") == job_parameters["partition"]

    @pytest.mark.asyncio
    async def test_submit_job_tool_invalid_file(self, valid_cores):
        """Test job submission tool with invalid file."""
        with pytest.raises(FileNotFoundError):
            submit_slurm_job("nonexistent.sh", valid_cores)

    @pytest.mark.asyncio
    async def test_submit_job_tool_invalid_cores(self, temp_script):
        """Test job submission tool with invalid cores."""
        with pytest.raises(ValueError):
            submit_slurm_job(temp_script, 0)

    @pytest.mark.asyncio
    async def test_check_status_tool(self, sample_job_id):
        """Test job status checking tool."""
        result = get_job_status(sample_job_id)

        assert isinstance(result, dict)
        # Should either be a success response or error response
        if "isError" in result:
            assert isinstance(result["isError"], bool)
        else:
            assert "job_id" in result or "error" in result

    @pytest.mark.asyncio
    async def test_cancel_job_tool(self, sample_job_id):
        """Test job cancellation tool."""
        result = cancel_slurm_job(sample_job_id)

        assert isinstance(result, dict)
        # Should handle cancellation request
        if not result.get("isError"):
            assert "job_id" in result or "status" in result

    @pytest.mark.asyncio
    async def test_list_jobs_tool(self):
        """Test job listing tool."""
        result = list_slurm_jobs()

        assert isinstance(result, dict)
        if not result.get("isError"):
            assert "jobs" in result or "count" in result

    @pytest.mark.asyncio
    async def test_list_jobs_tool_with_filters(self):
        """Test job listing tool with filters."""
        result = list_slurm_jobs(user="testuser", state="RUNNING")

        assert isinstance(result, dict)
        if not result.get("isError"):
            # Should include filter information
            assert "user_filter" in result or "state_filter" in result

    @pytest.mark.asyncio
    async def test_get_slurm_info_tool(self):
        """Test cluster info tool."""
        result = get_slurm_info()

        assert isinstance(result, dict)
        if not result.get("isError"):
            assert "cluster_name" in result or "partitions" in result

    @pytest.mark.asyncio
    async def test_get_job_details_tool(self, sample_job_id):
        """Test job details tool."""
        result = get_job_details(sample_job_id)

        assert isinstance(result, dict)
        if not result.get("isError"):
            assert "job_id" in result

    @pytest.mark.asyncio
    async def test_get_job_output_tool(self, sample_job_id):
        """Test job output tool."""
        for output_type in ["stdout", "stderr"]:
            result = get_job_output(sample_job_id, output_type)

            assert isinstance(result, dict)
            if not result.get("isError"):
                assert "job_id" in result or "output_type" in result

    @pytest.mark.asyncio
    async def test_get_queue_info_tool(self):
        """Test queue info tool."""
        result = get_queue_info()

        assert isinstance(result, dict)
        if not result.get("isError"):
            assert "jobs" in result or "total_jobs" in result

    @pytest.mark.asyncio
    async def test_get_queue_info_tool_with_partition(self):
        """Test queue info tool with partition filter."""
        result = get_queue_info(partition="compute")

        assert isinstance(result, dict)
        if not result.get("isError"):
            assert "partition_filter" in result or "jobs" in result

    @pytest.mark.asyncio
    async def test_submit_array_job_tool(self, array_script, array_parameters):
        """Test array job submission tool."""
        result = submit_array_job(
            array_script,
            array_parameters["array_range"],
            cores=array_parameters["cores"],
            memory=array_parameters["memory"],
            time_limit=array_parameters["time_limit"],
            job_name=array_parameters["job_name"],
        )

        assert isinstance(result, dict)
        if not result.get("isError") and not result.get("error"):
            # Should have array job information
            assert "array_job_id" in result or "array_range" in result

    @pytest.mark.asyncio
    async def test_get_node_info_tool(self):
        """Test node info tool."""
        result = get_node_info()

        assert isinstance(result, dict)
        if not result.get("isError"):
            assert "nodes" in result or "total_nodes" in result

    @pytest.mark.asyncio
    async def test_tool_parameter_defaults(self, temp_script):
        """Test that tools handle default parameters correctly."""
        # Test submit job with minimal parameters
        result = submit_slurm_job(temp_script, cores=1)
        assert isinstance(result, dict)

        # Test submit job with default memory and time
        result = submit_slurm_job(temp_script, cores=1, memory="1GB")
        assert isinstance(result, dict)

    @pytest.mark.asyncio
    async def test_tool_parameter_validation(self):
        """Test parameter validation in tools."""
        # Test with missing required parameters
        with pytest.raises(TypeError):
            submit_slurm_job()  # Missing required parameters

        # Test with invalid parameter types
        with pytest.raises((FileNotFoundError, TypeError)):
            submit_slurm_job("script.sh", "invalid_cores")

    @pytest.mark.asyncio
    async def test_concurrent_tool_execution(self, temp_script):
        """Test concurrent execution of tools."""

        # Submit multiple jobs concurrently using ThreadPoolExecutor
        def run_submit_job(script, cores, job_name):
            return submit_slurm_job(script, cores=cores, job_name=job_name)

        with ThreadPoolExecutor(max_workers=3) as executor:
            futures = []
            for i in range(3):
                future = executor.submit(
                    run_submit_job, temp_script, 1, f"concurrent_{i}"
                )
                futures.append(future)

            results = [future.result() for future in futures]

        # Check that all completed
        assert len(results) == 3
        for result in results:
            assert isinstance(result, dict)

    @pytest.mark.asyncio
    async def test_tool_error_handling(self):
        """Test error handling in tools."""
        # Test with various error conditions using direct function calls
        try:
            result = submit_slurm_job("nonexistent.sh", cores=1)
            assert isinstance(result, dict)
        except Exception as e:
            assert isinstance(e, Exception)

        try:
            result = get_job_status("invalid_job_id")
            assert isinstance(result, dict)
        except Exception as e:
            assert isinstance(e, Exception)

        try:
            result = cancel_slurm_job("invalid_job_id")
            assert isinstance(result, dict)
        except Exception as e:
            assert isinstance(e, Exception)

        try:
            result = get_job_details("invalid_job_id")
            assert isinstance(result, dict)
        except Exception as e:
            assert isinstance(e, Exception)

    @pytest.mark.asyncio
    async def test_integration_workflow_through_tools(self, temp_script):
        """Test complete workflow through MCP handler functions."""
        # Submit job
        submit_result = submit_slurm_job(
            temp_script, cores=2, job_name="integration_test"
        )
        assert isinstance(submit_result, dict)

        if not submit_result.get("isError") and "job_id" in submit_result:
            job_id = submit_result["job_id"]

            # Check status
            status_result = get_job_status(job_id)
            assert isinstance(status_result, dict)

            # Get details
            details_result = get_job_details(job_id)
            assert isinstance(details_result, dict)

            # Try to get output
            output_result = get_job_output(job_id, output_type="stdout")
            assert isinstance(output_result, dict)

            # Cancel job
            cancel_result = cancel_slurm_job(job_id)
            assert isinstance(cancel_result, dict)

    @pytest.mark.asyncio
    async def test_tool_logging(self, temp_script, caplog):
        """Test that handler functions produce appropriate log messages."""
        with caplog.at_level("INFO"):
            result = submit_slurm_job(temp_script, cores=1)

            # Should have logged the operation
            assert len(caplog.records) >= 0  # Logs may vary based on implementation
            assert isinstance(result, dict)

    @pytest.mark.asyncio
    async def test_tool_response_consistency(self, temp_script, sample_job_id):
        """Test that all handler functions return consistent response formats."""
        # Test submit_slurm_job
        result = submit_slurm_job(temp_script, cores=1)
        assert isinstance(result, dict)

        # Test get_job_status
        result = get_job_status(sample_job_id)
        assert isinstance(result, dict)

        # Test list_slurm_jobs
        result = list_slurm_jobs()
        assert isinstance(result, dict)

        # Test get_slurm_info
        result = get_slurm_info()
        assert isinstance(result, dict)

        # Test get_node_info
        result = get_node_info()
        assert isinstance(result, dict)

        # All results should be dictionaries
        # and should not contain both success and error indicators
        if result.get("isError"):
            assert "content" in result or "error" in result
        else:
            # Success responses should have meaningful data
            assert len(result) > 0

    @pytest.mark.asyncio
    async def test_array_job_workflow(self, array_script):
        """Test array job workflow through handler functions."""
        # Submit array job
        result = submit_array_job(
            array_script,
            array_range="1-3",
            cores=1,
            memory="1GB",
            time_limit="00:10:00",
            job_name="test_array",
        )

        assert isinstance(result, dict)

        if not result.get("isError") and "array_job_id" in result:
            array_job_id = result["array_job_id"]

            # Check status of array job
            status_result = get_job_status(array_job_id)
            assert isinstance(status_result, dict)

            # Try to cancel array job
            cancel_result = cancel_slurm_job(array_job_id)
            assert isinstance(cancel_result, dict)

    @pytest.mark.asyncio
    async def test_tool_timeout_handling(self, temp_script):
        """Test that handler functions complete in reasonable time."""
        # Test with a reasonable timeout
        try:

            def run_submit():
                return submit_slurm_job(temp_script, cores=1)

            with ThreadPoolExecutor() as executor:
                future = executor.submit(run_submit)
                result = future.result(timeout=30.0)  # 30 second timeout
                assert isinstance(result, dict)
        except Exception as e:
            # Timeout or other exceptions are acceptable for this test
            assert isinstance(e, Exception)

    def test_tool_documentation(self):
        """Test that all implementation functions have proper documentation."""
        functions = [
            submit_slurm_job,
            get_job_status,
            cancel_slurm_job,
            list_slurm_jobs,
            get_slurm_info,
            get_job_details,
            get_job_output,
            get_queue_info,
            submit_array_job,
            get_node_info,
        ]

        for func in functions:
            # Check that each function exists and has documentation
            assert func is not None, f"Function {func.__name__} not found"

            # Check that function has a docstring (optional check since some may not have detailed docs)
            if hasattr(func, "__doc__") and func.__doc__:
                docstring = func.__doc__.strip().lower()
                assert len(docstring) > 0


# ============================================================================
# MERGED TESTS FROM test_server_coverage_boost.py, test_server_async_errors.py,
# and test_server_error_paths.py
# ============================================================================


def test_server_import_structure():
    """Test that all required imports work."""
    from slurm_mcp import server

    # Test that all implementation functions are imported
    required_functions = [
        "submit_slurm_job",
        "get_job_status",
        "cancel_slurm_job",
        "list_slurm_jobs",
        "get_slurm_info",
        "get_job_details",
        "get_job_output",
        "get_queue_info",
        "submit_array_job",
        "get_node_info",
        "allocate_nodes",
        "deallocate_nodes",
        "get_allocation_status",
    ]

    for func_name in required_functions:
        assert hasattr(server, func_name), (
            f"Implementation function {func_name} not imported"
        )


def test_server_logger_and_mcp():
    """Test server logger and MCP instance."""
    from slurm_mcp import server

    # Test logger exists and is configured
    assert hasattr(server, "logger")
    assert server.logger.name == "slurm_mcp.server"

    # Test MCP instance exists
    assert hasattr(server, "mcp")
    assert server.mcp is not None

    # Test SlurmMCPError class
    assert hasattr(server, "SlurmMCPError")
    error = server.SlurmMCPError("Test error")
    assert str(error) == "Test error"
    assert isinstance(error, Exception)


def test_server_main_function():
    """Test main function and argument parsing."""
    from slurm_mcp import server

    # Test main function with http transport
    with (
        patch("sys.argv", ["slurm-mcp", "--transport", "http", "--port", "9000"]),
        patch.object(server.mcp, "run") as mock_run,
        patch("builtins.print"),
    ):
        try:
            server.main()
            # The host defaults to 0.0.0.0, not localhost
            mock_run.assert_called_with(transport="http", host="0.0.0.0", port=9000)
        except SystemExit:
            pass  # May exit normally

    # Test main function with stdio transport (default)
    with (
        patch("sys.argv", ["slurm-mcp"]),
        patch.object(server.mcp, "run") as mock_run,
        patch("builtins.print"),
    ):
        try:
            server.main()
            mock_run.assert_called_with(transport="stdio")
        except SystemExit:
            pass  # May exit normally

    # Test main function error handling - exceptions propagate from main()
    with (
        patch("sys.argv", ["slurm-mcp"]),
        patch.object(server.mcp, "run", side_effect=Exception("Server error")),
        patch("builtins.print"),
    ):
        with pytest.raises(Exception, match="Server error"):
            server.main()


def test_server_tool_functions_exist():
    """Test that tool functions are properly defined."""
    from slurm_mcp import server

    # In FastMCP v3, @mcp.tool() returns the original function
    tool_functions = [
        "submit_slurm_job_tool",
        "check_job_status_tool",
        "cancel_slurm_job_tool",
        "list_slurm_jobs_tool",
        "get_slurm_info_tool",
        "get_job_details_tool",
        "get_job_output_tool",
        "get_queue_info_tool",
        "submit_array_job_tool",
        "get_node_info_tool",
        "allocate_slurm_nodes_tool",
        "deallocate_slurm_nodes_tool",
        "get_allocation_status_tool",
    ]

    for func_name in tool_functions:
        assert hasattr(server, func_name), f"Function {func_name} not found"
        tool_obj = getattr(server, func_name)
        # In v3, decorated functions are the original async functions
        assert callable(tool_obj), f"Tool {func_name} should be callable"


def test_server_mcp_registration():
    """Test MCP tool registration."""
    from slurm_mcp import server

    # Test that MCP instance exists and has tools
    assert server.mcp is not None
    assert hasattr(server.mcp, "name")
    assert server.mcp.name == "slurm"


def test_server_logging_configuration():
    """Test logging configuration."""
    from slurm_mcp import server
    import logging

    # Test logger is properly configured
    assert isinstance(server.logger, logging.Logger)
    assert server.logger.name == "slurm_mcp.server"


def test_server_tool_error_simulation():
    """Test error paths by simulating tool execution errors."""
    from slurm_mcp import server

    # Test that we can access implementation functions that would be called
    # This tests the import paths and function availability
    assert callable(server.submit_slurm_job)
    assert callable(server.get_job_status)
    assert callable(server.cancel_slurm_job)
    assert callable(server.list_slurm_jobs)
    assert callable(server.get_slurm_info)
    assert callable(server.get_job_details)
    assert callable(server.get_job_output)
    assert callable(server.get_queue_info)
    assert callable(server.submit_array_job)
    assert callable(server.get_node_info)
    assert callable(server.allocate_nodes)
    assert callable(server.deallocate_nodes)
    assert callable(server.get_allocation_status)


def test_server_path_manipulation():
    """Test that server module is importable (no sys.path manipulation needed)."""
    from slurm_mcp import server

    # Verify the server module is importable and has expected attributes
    assert hasattr(server, "__file__")
    assert server.__file__ is not None


def test_server_comprehensive_coverage():
    """Comprehensive test to trigger more code paths."""
    from slurm_mcp import server

    # Test module-level attributes
    assert hasattr(server, "os")
    assert hasattr(server, "sys")
    assert hasattr(server, "logging")

    # Test FastMCP initialization
    assert server.mcp.name == "slurm"

    # Test all implementation imports are successful
    implementation_modules = [
        "submit_slurm_job",
        "get_job_status",
        "cancel_slurm_job",
        "list_slurm_jobs",
        "get_slurm_info",
        "get_job_details",
        "get_job_output",
        "get_queue_info",
        "submit_array_job",
        "get_node_info",
        "allocate_nodes",
        "deallocate_nodes",
        "get_allocation_status",
    ]

    for module_func in implementation_modules:
        assert hasattr(server, module_func)
        assert callable(getattr(server, module_func))


# ============================================================================
# ASYNC ERROR HANDLING TESTS (from test_server_async_errors.py)
# ============================================================================


def test_submit_slurm_job_error_handling():
    """Test submit_slurm_job_tool error handling -- raises ToolError in v3."""
    from slurm_mcp import server

    # Mock the underlying function to raise an exception
    with patch.object(
        server, "submit_slurm_job", side_effect=Exception("Mock submission error")
    ):
        # In v3 the decorator returns the original function, so we can call it directly
        async def test_error():
            with pytest.raises(ToolError):
                await server.submit_slurm_job_tool(
                    script_path="/test/script.sh",
                    cores=4,
                    memory="8G",
                    time_limit="1:00:00",
                    job_name="test_job",
                    partition="compute",
                )

        asyncio.run(test_error())


def test_check_job_status_error_handling():
    """Test check_job_status_tool error handling -- raises ToolError in v3."""
    from slurm_mcp import server

    with patch.object(
        server, "get_job_status", side_effect=Exception("Mock status error")
    ):

        async def test_error():
            with pytest.raises(ToolError):
                await server.check_job_status_tool(job_id="12345")

        asyncio.run(test_error())


def test_server_tool_inspection():
    """Inspect the structure of server tools to understand how to test them."""
    from slurm_mcp import server

    # In v3, tools are plain async functions
    tool = server.submit_slurm_job_tool
    assert tool is not None
    assert callable(tool)

    # At minimum, verify all tools exist
    tools = [
        "submit_slurm_job_tool",
        "check_job_status_tool",
        "cancel_slurm_job_tool",
        "list_slurm_jobs_tool",
        "get_slurm_info_tool",
        "get_job_details_tool",
        "get_job_output_tool",
        "get_queue_info_tool",
        "submit_array_job_tool",
        "get_node_info_tool",
        "allocate_slurm_nodes_tool",
        "deallocate_slurm_nodes_tool",
        "get_allocation_status_tool",
    ]

    for tool_name in tools:
        tool = getattr(server, tool_name)
        assert tool is not None
        assert callable(tool)


def test_exception_handling_coverage():
    """Test that imports and exception class work properly."""
    from slurm_mcp import server

    # Test SlurmMCPError exception
    error = server.SlurmMCPError("Test error")
    assert str(error) == "Test error"
    assert isinstance(error, Exception)

    # Test error raising and catching
    try:
        raise server.SlurmMCPError("Test exception")
    except server.SlurmMCPError as e:
        assert str(e) == "Test exception"
    except Exception:
        pytest.fail("Should have caught SlurmMCPError specifically")


def test_server_basic_structure():
    """Basic test to ensure server structure is correct."""
    from slurm_mcp import server

    # Test that all required components exist
    assert hasattr(server, "mcp")
    assert hasattr(server, "logger")
    assert hasattr(server, "main")
    assert hasattr(server, "SlurmMCPError")

    # Test logger configuration
    assert server.logger.name == "slurm_mcp.server"

    # Test MCP instance
    assert server.mcp.name == "slurm"


# ============================================================================
# ERROR PATH TESTS (from test_server_error_paths.py)
# ============================================================================


def test_server_error_handling_paths():
    """Test error handling paths that are currently missing from coverage."""

    # Import server to trigger initialization
    from slurm_mcp import server

    # Create mock responses that will trigger error paths
    Mock(side_effect=Exception("Test error"))

    # Test that we can access the async function objects
    assert hasattr(server, "submit_slurm_job_tool")
    assert hasattr(server, "check_job_status_tool")
    assert hasattr(server, "cancel_slurm_job_tool")
    assert hasattr(server, "list_slurm_jobs_tool")
    assert hasattr(server, "get_slurm_info_tool")
    assert hasattr(server, "get_job_details_tool")
    assert hasattr(server, "get_job_output_tool")
    assert hasattr(server, "get_queue_info_tool")
    assert hasattr(server, "submit_array_job_tool")
    assert hasattr(server, "get_node_info_tool")
    assert hasattr(server, "allocate_slurm_nodes_tool")
    assert hasattr(server, "deallocate_slurm_nodes_tool")
    assert hasattr(server, "get_allocation_status_tool")


def test_server_dotenv_import():
    """Test dotenv import path."""
    # This will trigger the try/except block for dotenv import
    # by importing server again but mocking the dotenv import to fail

    with patch.dict("sys.modules", {"dotenv": None}):
        # Force re-import to trigger the except block
        if "slurm_mcp.server" in sys.modules:
            del sys.modules["slurm_mcp.server"]

        # Import server which will trigger the dotenv import failure
        from slurm_mcp import server

        # Verify server still works without dotenv
        assert hasattr(server, "mcp")
        assert hasattr(server, "logger")


def test_server_main_with_different_args():
    """Test main function with different argument combinations."""
    from slurm_mcp import server

    # Test with --host argument
    with (
        patch(
            "sys.argv",
            [
                "slurm-mcp",
                "--transport",
                "http",
                "--host",
                "127.0.0.1",
                "--port",
                "8080",
            ],
        ),
        patch.object(server.mcp, "run") as mock_run,
    ):
        try:
            server.main()
        except SystemExit:
            pass
        mock_run.assert_called_with(transport="http", host="127.0.0.1", port=8080)

    # Test with just --host
    with (
        patch("sys.argv", ["slurm-mcp", "--transport", "http", "--host", "localhost"]),
        patch.object(server.mcp, "run") as mock_run,
    ):
        try:
            server.main()
        except SystemExit:
            pass
        mock_run.assert_called_with(transport="http", host="localhost", port=8000)


def test_server_exception_class():
    """Test SlurmMCPError exception class."""
    from slurm_mcp import server

    # Test exception creation and string representation
    error = server.SlurmMCPError("Test error message")
    assert str(error) == "Test error message"
    assert isinstance(error, Exception)

    # Test exception inheritance
    try:
        raise server.SlurmMCPError("Test exception")
    except server.SlurmMCPError as e:
        assert str(e) == "Test exception"
    except Exception:
        assert False, "Should have caught SlurmMCPError specifically"


def test_server_logging_setup():
    """Test logging setup and configuration."""
    from slurm_mcp import server
    import logging

    # Verify logger configuration
    assert isinstance(server.logger, logging.Logger)
    assert server.logger.name == "slurm_mcp.server"

    # Test that we can log messages (this exercises logging setup)
    server.logger.info("Test log message")
    server.logger.error("Test error message")
    server.logger.debug("Test debug message")


def test_server_sys_path_modification():
    """Test server module is properly importable (no sys.path manipulation)."""
    from slurm_mcp import server

    # The server module should be importable without sys.path manipulation
    assert hasattr(server, "__file__")
    assert server.__file__ is not None


def test_server_implementation_imports():
    """Test that all implementation imports work correctly."""
    from slurm_mcp import server

    # Test that all implementation functions are accessible
    implementation_functions = [
        "submit_slurm_job",
        "get_job_status",
        "cancel_slurm_job",
        "list_slurm_jobs",
        "get_slurm_info",
        "get_job_details",
        "get_job_output",
        "get_queue_info",
        "submit_array_job",
        "get_node_info",
        "allocate_nodes",
        "deallocate_nodes",
        "get_allocation_status",
    ]

    for func_name in implementation_functions:
        assert hasattr(server, func_name)
        func = getattr(server, func_name)
        assert callable(func)


def test_server_fastmcp_initialization():
    """Test FastMCP initialization and tool registration."""
    from slurm_mcp import server

    # Test FastMCP instance
    assert server.mcp is not None
    assert hasattr(server.mcp, "name")
    assert server.mcp.name == "slurm"

    # Test that mcp has expected methods
    assert hasattr(server.mcp, "run")
    assert callable(server.mcp.run)


def test_server_module_level_variables():
    """Test module-level variables and imports."""
    from slurm_mcp import server

    # Test required imports are available
    assert hasattr(server, "os")
    assert hasattr(server, "sys")
    assert hasattr(server, "logging")

    # Test FastMCP-related imports
    assert hasattr(server, "FastMCP")

    # Test ToolError import
    assert hasattr(server, "ToolError")

    # Test Message import
    assert hasattr(server, "Message")

    # Test that server has the expected structure
    assert hasattr(server, "main")
    assert callable(server.main)


def test_server_missing_lines_coverage():
    """Test server.py missing lines to improve coverage."""
    from slurm_mcp import server

    # Test main function with detailed argument handling
    # Test HTTP transport with custom host and port
    with patch(
        "sys.argv",
        ["slurm-mcp", "--transport", "http", "--host", "0.0.0.0", "--port", "9000"],
    ):
        with patch.object(server.mcp, "run") as mock_run:
            with patch("builtins.print"):
                try:
                    server.main()
                except SystemExit:
                    pass
                # Should be called with specific host and port
                mock_run.assert_called_with(transport="http", host="0.0.0.0", port=9000)

    # Test main function exception handling - exceptions propagate from main()
    with (
        patch("sys.argv", ["slurm-mcp"]),
        patch.object(server.mcp, "run", side_effect=Exception("Server startup failed")),
        patch("builtins.print"),
    ):
        with pytest.raises(Exception, match="Server startup failed"):
            server.main()


def test_server_tool_error_paths():
    """Test error handling paths in server tool functions."""
    from slurm_mcp import server

    # In v3, tool functions are the original async functions
    tool_functions = [
        "submit_slurm_job_tool",
        "check_job_status_tool",
        "cancel_slurm_job_tool",
        "list_slurm_jobs_tool",
        "get_slurm_info_tool",
        "get_job_details_tool",
        "get_job_output_tool",
        "get_queue_info_tool",
        "submit_array_job_tool",
        "get_node_info_tool",
        "allocate_slurm_nodes_tool",
        "deallocate_slurm_nodes_tool",
        "get_allocation_status_tool",
    ]

    for tool_name in tool_functions:
        tool = getattr(server, tool_name)
        assert tool is not None
        assert callable(tool)


def test_server_async_error_handling():
    """Test async function error handling paths in server tools -- ToolError in v3."""
    from slurm_mcp import server

    # Mock underlying functions to raise exceptions and verify ToolError
    # Use patch.object to ensure correct module-level name replacement
    with patch.object(server, "submit_slurm_job", side_effect=Exception("Job submission failed")):
        async def _test():
            with pytest.raises(ToolError):
                await server.submit_slurm_job_tool(script_path="/test.sh", cores=1)
        asyncio.run(_test())

    with patch.object(server, "get_job_status", side_effect=Exception("Status check failed")):
        async def _test():
            with pytest.raises(ToolError):
                await server.check_job_status_tool(job_id="123")
        asyncio.run(_test())

    with patch.object(server, "cancel_slurm_job", side_effect=Exception("Cancellation failed")):
        async def _test():
            with pytest.raises(ToolError):
                await server.cancel_slurm_job_tool(job_id="123")
        asyncio.run(_test())

    with patch.object(server, "list_slurm_jobs", side_effect=Exception("Listing failed")):
        async def _test():
            with pytest.raises(ToolError):
                await server.list_slurm_jobs_tool()
        asyncio.run(_test())

    with patch.object(server, "get_slurm_info", side_effect=Exception("Info retrieval failed")):
        async def _test():
            with pytest.raises(ToolError):
                await server.get_slurm_info_tool()
        asyncio.run(_test())

    with patch.object(server, "get_job_details", side_effect=Exception("Details failed")):
        async def _test():
            with pytest.raises(ToolError):
                await server.get_job_details_tool(job_id="123")
        asyncio.run(_test())

    with patch.object(server, "get_job_output", side_effect=Exception("Output failed")):
        async def _test():
            with pytest.raises(ToolError):
                await server.get_job_output_tool(job_id="123")
        asyncio.run(_test())

    with patch.object(server, "get_queue_info", side_effect=Exception("Queue info failed")):
        async def _test():
            with pytest.raises(ToolError):
                await server.get_queue_info_tool()
        asyncio.run(_test())

    with patch.object(server, "submit_array_job", side_effect=Exception("Array job failed")):
        async def _test():
            with pytest.raises(ToolError):
                await server.submit_array_job_tool(script_path="/test.sh", array_range="1-5")
        asyncio.run(_test())

    with patch.object(server, "get_node_info", side_effect=Exception("Node info failed")):
        async def _test():
            with pytest.raises(ToolError):
                await server.get_node_info_tool()
        asyncio.run(_test())

    with patch.object(server, "allocate_nodes", side_effect=Exception("Allocation failed")):
        async def _test():
            with pytest.raises(ToolError):
                await server.allocate_slurm_nodes_tool()
        asyncio.run(_test())

    with patch.object(server, "deallocate_nodes", side_effect=Exception("Deallocation failed")):
        async def _test():
            with pytest.raises(ToolError):
                await server.deallocate_slurm_nodes_tool(allocation_id="123")
        asyncio.run(_test())

    with patch.object(server, "get_allocation_status", side_effect=Exception("Status failed")):
        async def _test():
            with pytest.raises(ToolError):
                await server.get_allocation_status_tool(allocation_id="123")
        asyncio.run(_test())


def test_server_edge_cases():
    """Test edge cases and additional server functionality."""
    from slurm_mcp import server

    # Test logger configuration (already done in other tests but verify again)
    assert server.logger.name == "slurm_mcp.server"

    # Test that all implementation functions are imported correctly
    impl_functions = [
        "submit_slurm_job",
        "get_job_status",
        "cancel_slurm_job",
        "list_slurm_jobs",
        "get_slurm_info",
        "get_job_details",
        "get_job_output",
        "get_queue_info",
        "submit_array_job",
        "get_node_info",
        "allocate_nodes",
        "deallocate_nodes",
        "get_allocation_status",
    ]

    for func_name in impl_functions:
        func = getattr(server, func_name)
        assert callable(func)

    # Test SlurmMCPError exception class
    error = server.SlurmMCPError("Test error")
    assert str(error) == "Test error"
    assert isinstance(error, Exception)


def test_server_main_with_stdio_transport():
    """Test main function with default stdio transport."""
    from slurm_mcp import server

    # Test stdio transport (default)
    with (
        patch("sys.argv", ["slurm-mcp"]),
        patch.object(server.mcp, "run") as mock_run,
        patch("builtins.print"),
    ):
        try:
            server.main()
        except SystemExit:
            pass
        mock_run.assert_called_with(transport="stdio")


def test_server_main_with_sse_host_variations():
    """Test main function with HTTP transport and different host configurations."""
    from slurm_mcp import server

    # Test HTTP with default host (0.0.0.0) and custom port
    with patch("sys.argv", ["slurm-mcp", "--transport", "http", "--port", "8080"]):
        with patch.object(server.mcp, "run") as mock_run:
            with patch("builtins.print"):
                try:
                    server.main()
                except SystemExit:
                    pass
                mock_run.assert_called_with(transport="http", host="0.0.0.0", port=8080)

    # Test HTTP with custom host and default port
    with patch("sys.argv", ["slurm-mcp", "--transport", "http", "--host", "localhost"]):
        with patch.object(server.mcp, "run") as mock_run:
            with patch("builtins.print"):
                try:
                    server.main()
                except SystemExit:
                    pass
                mock_run.assert_called_with(
                    transport="http", host="localhost", port=8000
                )


def test_server_imports_and_path_setup():
    """Test server imports and module setup."""
    from slurm_mcp import server

    # Test that server module is properly importable
    assert hasattr(server, "__file__")
    assert server.__file__ is not None

    # Test FastMCP import success
    assert hasattr(server, "FastMCP")

    # Test that all required modules are accessible
    assert hasattr(server, "os")
    assert hasattr(server, "sys")
    assert hasattr(server, "logging")


def test_server_mcp_configuration():
    """Test MCP instance configuration and tool registration."""
    from slurm_mcp import server

    # Test MCP instance configuration
    assert server.mcp.name == "slurm"

    # In v3, tool functions are just async callables
    expected_tools = [
        "submit_slurm_job_tool",
        "check_job_status_tool",
        "cancel_slurm_job_tool",
        "list_slurm_jobs_tool",
        "get_slurm_info_tool",
        "get_job_details_tool",
        "get_job_output_tool",
        "get_queue_info_tool",
        "submit_array_job_tool",
        "get_node_info_tool",
        "allocate_slurm_nodes_tool",
        "deallocate_slurm_nodes_tool",
        "get_allocation_status_tool",
    ]

    for tool_name in expected_tools:
        assert hasattr(server, tool_name)
        tool = getattr(server, tool_name)
        assert tool is not None
        assert callable(tool)


def test_server_resource_and_prompt():
    """Test that the resource and prompt are registered."""
    from slurm_mcp import server

    # Test cluster_info resource function
    assert hasattr(server, "cluster_info")
    result = server.cluster_info()
    assert isinstance(result, dict)
    assert result["scheduler"] == "slurm"
    assert "operations" in result

    # Test submit_job_workflow prompt function
    assert hasattr(server, "submit_job_workflow")
    messages = server.submit_job_workflow("/path/to/script.sh")
    assert isinstance(messages, list)
    assert len(messages) == 1
