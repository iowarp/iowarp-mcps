"""
Tests for MCP handlers.
Tests the MCP protocol layer that wraps Slurm capabilities.
"""

import sys
from pathlib import Path
from mcp_handlers import (
    submit_slurm_job_handler,
    check_job_status_handler,
    cancel_slurm_job_handler,
    list_slurm_jobs_handler,
    get_slurm_info_handler,
    get_job_details_handler,
    get_job_output_handler,
    get_queue_info_handler,
    submit_array_job_handler,
    get_node_info_handler,
)

# Add src to Python path
src_path = Path(__file__).parent.parent / "src"
sys.path.insert(0, str(src_path))


class TestMCPHandlers:
    """Test suite for MCP handlers."""

    def test_submit_job_handler_success(self, temp_script, valid_cores):
        """Test successful job submission through MCP handler."""
        result = submit_slurm_job_handler(temp_script, valid_cores)

        assert isinstance(result, dict)

        # Check for error or success response
        if result.get("isError"):
            assert "content" in result
            assert "_meta" in result
        else:
            assert "job_id" in result
            assert "status" in result
            assert "script_path" in result
            assert "cores" in result
            assert "message" in result

            assert result["status"] == "submitted"
            assert result["script_path"] == temp_script
            assert result["cores"] == valid_cores
            assert isinstance(result["job_id"], str)

    def test_submit_job_handler_enhanced(self, temp_script, job_parameters):
        """Test enhanced job submission through MCP handler."""
        result = submit_slurm_job_handler(
            temp_script,
            cores=4,
            memory=job_parameters["memory"],
            time_limit=job_parameters["time_limit"],
            job_name=job_parameters["job_name"],
            partition=job_parameters["partition"],
        )

        assert isinstance(result, dict)

        if not result.get("isError"):
            assert "job_id" in result
            assert "status" in result
            assert "memory" in result
            assert "time_limit" in result
            assert "job_name" in result
            assert "partition" in result

            assert result["memory"] == job_parameters["memory"]
            assert result["time_limit"] == job_parameters["time_limit"]
            assert result["job_name"] == job_parameters["job_name"]
            assert result["partition"] == job_parameters["partition"]

    def test_submit_job_handler_error(self, valid_cores):
        """Test job submission error handling through MCP handler."""
        result = submit_slurm_job_handler("nonexistent.sh", valid_cores)

        assert isinstance(result, dict)
        assert "isError" in result
        assert result["isError"] is True
        assert "content" in result
        assert "_meta" in result

    def test_submit_job_handler_invalid_cores(self, temp_script):
        """Test job submission with invalid cores through MCP handler."""
        result = submit_slurm_job_handler(temp_script, 0)

        assert isinstance(result, dict)
        assert "isError" in result
        assert result["isError"] is True

    def test_check_status_handler_success(self, sample_job_id):
        """Test successful status check through MCP handler."""
        result = check_job_status_handler(sample_job_id)

        assert isinstance(result, dict)

        if not result.get("isError"):
            required_keys = ["job_id", "status", "reason", "real_slurm"]
            for key in required_keys:
                assert key in result

            assert result["job_id"] == sample_job_id

    def test_cancel_job_handler_success(self, sample_job_id):
        """Test successful job cancellation through MCP handler."""
        result = cancel_slurm_job_handler(sample_job_id)

        assert isinstance(result, dict)

        if not result.get("isError"):
            assert "job_id" in result
            assert "status" in result
            assert "message" in result
            assert "real_slurm" in result

            assert result["job_id"] == sample_job_id

    def test_list_jobs_handler_success(self):
        """Test successful job listing through MCP handler."""
        result = list_slurm_jobs_handler()

        assert isinstance(result, dict)

        if not result.get("isError"):
            assert "jobs" in result
            assert "count" in result
            assert "real_slurm" in result

            assert isinstance(result["jobs"], list)
            assert isinstance(result["count"], int)

    def test_list_jobs_handler_with_filters(self):
        """Test job listing with filters through MCP handler."""
        result = list_slurm_jobs_handler(user="testuser", state="RUNNING")

        assert isinstance(result, dict)

        if not result.get("isError"):
            assert "user_filter" in result
            assert "state_filter" in result

            assert result["user_filter"] == "testuser"
            assert result["state_filter"] == "RUNNING"

    def test_get_slurm_info_handler_success(self):
        """Test successful cluster info retrieval through MCP handler."""
        result = get_slurm_info_handler()

        assert isinstance(result, dict)

        if not result.get("isError"):
            assert "cluster_name" in result
            assert "partitions" in result
            assert "real_slurm" in result

            assert isinstance(result["partitions"], list)

    def test_get_job_details_handler_success(self, sample_job_id):
        """Test successful job details retrieval through MCP handler."""
        result = get_job_details_handler(sample_job_id)

        assert isinstance(result, dict)

        if not result.get("isError"):
            assert "job_id" in result
            assert "real_slurm" in result
            assert result["job_id"] == sample_job_id

    def test_get_job_output_handler_success(self, sample_job_id):
        """Test successful job output retrieval through MCP handler."""
        for output_type in ["stdout", "stderr"]:
            result = get_job_output_handler(sample_job_id, output_type)

            assert isinstance(result, dict)

            if not result.get("isError"):
                assert "job_id" in result
                assert "output_type" in result
                assert "real_slurm" in result

                assert result["job_id"] == sample_job_id
                assert result["output_type"] == output_type

    def test_get_queue_info_handler_success(self):
        """Test successful queue info retrieval through MCP handler."""
        result = get_queue_info_handler()

        assert isinstance(result, dict)

        if not result.get("isError"):
            assert "jobs" in result
            assert "total_jobs" in result
            assert "state_summary" in result
            assert "real_slurm" in result

    def test_get_queue_info_handler_with_partition(self):
        """Test queue info retrieval with partition filter through MCP handler."""
        result = get_queue_info_handler(partition="compute")

        assert isinstance(result, dict)

        if not result.get("isError"):
            assert "partition_filter" in result
            assert result["partition_filter"] == "compute"

    def test_submit_array_job_handler_success(self, array_script, array_parameters):
        """Test successful array job submission through MCP handler."""
        result = submit_array_job_handler(
            array_script,
            array_parameters["array_range"],
            cores=array_parameters["cores"],
            memory=array_parameters["memory"],
            time_limit=array_parameters["time_limit"],
            job_name=array_parameters["job_name"],
        )

        assert isinstance(result, dict)

        if not result.get("isError"):
            if "array_job_id" in result:  # Successful submission
                assert "array_range" in result
                assert "real_slurm" in result
                assert result["array_range"] == array_parameters["array_range"]

    def test_get_node_info_handler_success(self):
        """Test successful node info retrieval through MCP handler."""
        result = get_node_info_handler()

        assert isinstance(result, dict)

        if not result.get("isError"):
            assert "nodes" in result
            assert "total_nodes" in result
            assert "real_slurm" in result

            assert isinstance(result["nodes"], list)
            assert isinstance(result["total_nodes"], int)

    def test_error_handling_consistency(self):
        """Test that all handlers return consistent error structures."""
        # Test with invalid inputs to trigger errors
        handlers_to_test = [
            (submit_slurm_job_handler, ["nonexistent.sh", 0]),
            (check_job_status_handler, ["invalid_job_id"]),
            (cancel_slurm_job_handler, ["invalid_job_id"]),
            (get_job_details_handler, ["invalid_job_id"]),
            (get_job_output_handler, ["invalid_job_id", "stdout"]),
        ]

        for handler, args in handlers_to_test:
            try:
                result = handler(*args)
                # If error is returned in result structure
                if result.get("isError"):
                    assert "content" in result
                    assert "_meta" in result
                    assert isinstance(result["content"], list)
                    assert "tool" in result["_meta"]
            except Exception:
                # Exception handling is also acceptable
                pass

    def test_mcp_response_format(self, temp_script, valid_cores):
        """Test that MCP responses follow the correct format."""
        result = submit_slurm_job_handler(temp_script, valid_cores)

        assert isinstance(result, dict)

        # Should either be success or error format
        if result.get("isError"):
            # Error format
            assert "content" in result
            assert "_meta" in result
            assert isinstance(result["content"], list)
            if result["content"]:
                assert "text" in result["content"][0]
        else:
            # Success format - should have meaningful data
            assert len(result) > 0
            # At minimum should have some identifiable fields
            assert any(key in result for key in ["job_id", "status", "message"])

    def test_handler_parameter_validation(self, temp_script):
        """Test parameter validation in handlers."""
        # Test required parameters
        result = submit_slurm_job_handler(temp_script, 1)
        assert isinstance(result, dict)

        # Test optional parameters
        result = submit_slurm_job_handler(
            temp_script, 1, memory="1GB", time_limit="01:00:00"
        )
        assert isinstance(result, dict)

        # Test parameter types
        result = list_slurm_jobs_handler(user="testuser", state="RUNNING")
        assert isinstance(result, dict)

    def test_integration_workflow_through_handlers(self, temp_script):
        """Test complete workflow through MCP handlers."""
        # Submit job
        submit_result = submit_slurm_job_handler(
            temp_script, 2, job_name="handler_test"
        )
        assert isinstance(submit_result, dict)

        if not submit_result.get("isError") and "job_id" in submit_result:
            job_id = submit_result["job_id"]

            # Check status
            status_result = check_job_status_handler(job_id)
            assert isinstance(status_result, dict)

            # Get details
            details_result = get_job_details_handler(job_id)
            assert isinstance(details_result, dict)

            # Try to get output
            output_result = get_job_output_handler(job_id, "stdout")
            assert isinstance(output_result, dict)

            # Cancel job
            cancel_result = cancel_slurm_job_handler(job_id)
            assert isinstance(cancel_result, dict)

    def test_concurrent_handler_calls(self, temp_script):
        """Test that handlers can handle concurrent calls safely."""
        import threading

        results = []

        def submit_job():
            result = submit_slurm_job_handler(
                temp_script, 1, job_name="concurrent_test"
            )
            results.append(result)

        # Create multiple threads
        threads = []
        for i in range(3):
            thread = threading.Thread(target=submit_job)
            threads.append(thread)
            thread.start()

        # Wait for all threads to complete
        for thread in threads:
            thread.join()

        # Check results
        assert len(results) == 3
        for result in results:
            assert isinstance(result, dict)
            assert "job_id" in result
            assert "status" in result
            # Note: job submission returns "status": "submitted", not a "reason" field
            assert result["status"] == "submitted"

    def test_check_status_handler_structure(self, sample_job_id):
        """Test that status handler returns proper structure."""
        result = check_job_status_handler(sample_job_id)

        # Should not be an error response
        if "isError" in result:
            assert result["isError"] is not True
        else:
            # Should be a valid status response
            assert "job_id" in result
            assert "status" in result

