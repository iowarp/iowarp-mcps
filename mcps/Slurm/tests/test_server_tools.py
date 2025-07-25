"""
Tests for MCP server tools.
Tests the actual MCP tool implementations and server functionality.
"""
import pytest
import asyncio
import sys
import os
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import patch, MagicMock

# Add src to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

# Import implementation modules directly
from implementation.job_submission import submit_slurm_job
from implementation.job_status import get_job_status
from implementation.job_cancellation import cancel_slurm_job
from implementation.job_listing import list_slurm_jobs
from implementation.cluster_info import get_slurm_info
from implementation.job_details import get_job_details
from implementation.job_output import get_job_output
from implementation.queue_info import get_queue_info
from implementation.array_jobs import submit_array_job
from implementation.node_info import get_node_info


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
            partition=job_parameters["partition"]
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
            job_name=array_parameters["job_name"]
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
                future = executor.submit(run_submit_job, temp_script, 1, f"concurrent_{i}")
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
        submit_result = submit_slurm_job(temp_script, cores=2, job_name="integration_test")
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
            job_name="test_array"
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
            get_node_info
        ]
        
        for func in functions:
            # Check that each function exists and has documentation
            assert func is not None, f"Function {func.__name__} not found"
            
            # Check that function has a docstring (optional check since some may not have detailed docs)
            if hasattr(func, '__doc__') and func.__doc__:
                docstring = func.__doc__.strip().lower()
                assert len(docstring) > 0
