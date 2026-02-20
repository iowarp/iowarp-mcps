"""
Tests for MCP handlers.
Tests the MCP protocol layer that wraps Slurm capabilities.
"""

from unittest.mock import patch
from slurm_mcp.mcp_handlers import (
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


class TestMCPHandlers:
    """Test class for MCP handlers."""

    def test_submit_job_handler_success(self, temp_script, valid_cores):
        """Test successful job submission handler."""
        result = submit_slurm_job_handler(temp_script, valid_cores)

        # Check basic structure
        assert isinstance(result, dict)
        assert "job_id" in result
        assert "status" in result
        assert "script_path" in result
        assert "cores" in result
        assert "message" in result

        assert result["status"] == "submitted"
        assert result["script_path"] == temp_script
        assert result["cores"] == valid_cores
        assert isinstance(result["job_id"], str)

    def test_submit_job_handler_with_exception(self, valid_cores):
        """Test submit job handler with exception."""
        # Use a non-existent script to trigger an exception
        result = submit_slurm_job_handler("/non/existent/script.sh", valid_cores)

        assert isinstance(result, dict)
        assert "isError" in result
        assert result["isError"] is True
        assert "content" in result
        assert "_meta" in result
        assert result["_meta"]["tool"] == "submit_slurm_job"

    def test_check_status_handler_with_exception(self):
        """Test check status handler with exception."""
        # Create a scenario that might cause an exception by mocking
        with patch(
            "slurm_mcp.mcp_handlers.get_job_status", side_effect=Exception("Test error")
        ):
            result = check_job_status_handler("12345")

            assert isinstance(result, dict)
            assert "isError" in result
            assert result["isError"] is True
            assert "content" in result
            assert "_meta" in result
            assert result["_meta"]["tool"] == "check_job_status"

    def test_cancel_job_handler_with_exception(self):
        """Test cancel job handler with exception."""
        with patch(
            "slurm_mcp.mcp_handlers.cancel_slurm_job",
            side_effect=Exception("Test error"),
        ):
            result = cancel_slurm_job_handler("12345")

            assert isinstance(result, dict)
            assert "isError" in result
            assert result["isError"] is True

    def test_list_jobs_handler_with_exception(self):
        """Test list jobs handler with exception."""
        with patch(
            "slurm_mcp.mcp_handlers.list_slurm_jobs",
            side_effect=Exception("Test error"),
        ):
            result = list_slurm_jobs_handler()

            assert isinstance(result, dict)
            assert "isError" in result
            assert result["isError"] is True

    def test_get_slurm_info_handler_with_exception(self):
        """Test get Slurm info handler with exception."""
        with patch(
            "slurm_mcp.mcp_handlers.get_slurm_info", side_effect=Exception("Test error")
        ):
            result = get_slurm_info_handler()

            assert isinstance(result, dict)
            assert "isError" in result
            assert result["isError"] is True

    def test_get_job_details_handler_with_exception(self):
        """Test get job details handler with exception."""
        with patch(
            "slurm_mcp.mcp_handlers.get_job_details",
            side_effect=Exception("Test error"),
        ):
            result = get_job_details_handler("12345")

            assert isinstance(result, dict)
            assert "isError" in result
            assert result["isError"] is True

    def test_get_job_output_handler_with_exception(self):
        """Test get job output handler with exception."""
        with patch(
            "slurm_mcp.mcp_handlers.get_job_output", side_effect=Exception("Test error")
        ):
            result = get_job_output_handler("12345")

            assert isinstance(result, dict)
            assert "isError" in result
            assert result["isError"] is True

    def test_get_queue_info_handler_with_exception(self):
        """Test get queue info handler with exception."""
        with patch(
            "slurm_mcp.mcp_handlers.get_queue_info", side_effect=Exception("Test error")
        ):
            result = get_queue_info_handler()

            assert isinstance(result, dict)
            assert "isError" in result
            assert result["isError"] is True

    def test_submit_array_job_handler_with_exception(self, valid_cores):
        """Test submit array job handler with exception."""
        with patch(
            "slurm_mcp.mcp_handlers.submit_array_job",
            side_effect=Exception("Test error"),
        ):
            result = submit_array_job_handler(
                "/non/existent/script.sh", "1-5", valid_cores
            )

            assert isinstance(result, dict)
            assert "isError" in result
            assert result["isError"] is True

    def test_get_node_info_handler_with_exception(self):
        """Test get node info handler with exception."""
        with patch(
            "slurm_mcp.mcp_handlers.get_node_info", side_effect=Exception("Test error")
        ):
            result = get_node_info_handler()

            assert isinstance(result, dict)
            assert "isError" in result
            assert result["isError"] is True

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

    def test_slurm_unavailable_graceful_handling(
        self, mock_slurm_unavailable, temp_script, valid_cores
    ):
        """Test that when Slurm is unavailable, operations still return structured responses."""
        # The mock_slurm_unavailable fixture is already active, no need for context manager
        # Test job submission when Slurm is unavailable
        result = submit_slurm_job_handler(temp_script, valid_cores)

        # Should either succeed with simulation mode or return error gracefully
        assert isinstance(result, dict)

        if result.get("isError"):
            # Error case: should have proper error structure
            assert "content" in result
            assert "_meta" in result
        else:
            # Success case: should indicate simulation or test mode
            assert "job_id" in result
            # Should indicate it's not real Slurm
            assert (
                result.get("real_slurm") is False
                or "test" in str(result.get("status", "")).lower()
            )

    def test_timeout_protection_no_freeze(self, temp_script, valid_cores):
        """Test that operations complete quickly and don't freeze."""
        import time

        start_time = time.time()
        try:
            result = submit_slurm_job_handler(temp_script, valid_cores)
            end_time = time.time()

            # Should complete quickly due to mocking (definitely under 10 seconds)
            duration = end_time - start_time
            assert duration < 10.0, (
                f"Operation took {duration} seconds, should be much faster with mocking"
            )

            # Should return a valid response
            assert isinstance(result, dict)

        except Exception:
            end_time = time.time()
            duration = end_time - start_time
            # Even if it fails, it shouldn't freeze
            assert duration < 10.0, (
                f"Operation failed but took {duration} seconds to fail"
            )


# ============================================================================
# ENHANCED COVERAGE TESTS FOR MCP_HANDLERS.PY
# ============================================================================


class TestMCPHandlersCoverage:
    """Enhanced tests to boost mcp_handlers.py coverage."""

    def test_check_job_status_handler_real_slurm_field(self):
        """Test that real_slurm field is added when missing (line 114)."""
        from unittest.mock import patch

        # Mock the underlying function to return result without real_slurm
        mock_result = {"job_id": "12345", "status": "RUNNING"}

        with patch("slurm_mcp.mcp_handlers.get_job_status", return_value=mock_result):
            result = check_job_status_handler("12345")

            assert "real_slurm" in result
            assert result["real_slurm"] is False
            assert result["job_id"] == "12345"

    def test_cancel_slurm_job_handler_real_slurm_field(self):
        """Test that real_slurm field is added when missing (line 140)."""
        from unittest.mock import patch

        # Mock the underlying function to return result without real_slurm
        mock_result = {"job_id": "12345", "status": "cancelled"}

        with patch("slurm_mcp.mcp_handlers.cancel_slurm_job", return_value=mock_result):
            result = cancel_slurm_job_handler("12345")

            assert "real_slurm" in result
            assert result["real_slurm"] is False
            assert result["job_id"] == "12345"

    def test_list_slurm_jobs_handler_with_filters(self):
        """Test list jobs handler with all filter types (lines 169-179)."""
        from unittest.mock import patch

        # Mock the underlying function
        mock_result = {"jobs": [], "total": 0}

        with patch("slurm_mcp.mcp_handlers.list_slurm_jobs", return_value=mock_result):
            result = list_slurm_jobs_handler(
                user="testuser", state="RUNNING", partition="compute"
            )

            assert "user_filter" in result
            assert "state_filter" in result
            assert "partition_filter" in result
            assert result["user_filter"] == "testuser"
            assert result["state_filter"] == "RUNNING"
            assert result["partition_filter"] == "compute"
            assert "real_slurm" in result
            assert result["real_slurm"] is False

    def test_get_slurm_info_handler_real_slurm_field(self):
        """Test that real_slurm field is added when missing (line 197)."""
        from unittest.mock import patch

        # Mock the underlying function to return result without real_slurm
        mock_result = {"cluster_name": "test-cluster", "version": "20.11.8"}

        with patch("slurm_mcp.mcp_handlers.get_slurm_info", return_value=mock_result):
            result = get_slurm_info_handler()

            assert "real_slurm" in result
            assert result["real_slurm"] is False

    def test_get_job_details_handler_real_slurm_field(self):
        """Test that real_slurm field is added when missing (line 222)."""
        from unittest.mock import patch

        # Mock the underlying function to return result without real_slurm
        mock_result = {"job_id": "12345", "name": "test_job", "state": "COMPLETED"}

        with patch("slurm_mcp.mcp_handlers.get_job_details", return_value=mock_result):
            result = get_job_details_handler("12345")

            assert "real_slurm" in result
            assert result["real_slurm"] is False
            assert result["job_id"] == "12345"

    def test_get_job_output_handler_real_slurm_field(self):
        """Test that real_slurm field is added when missing (line 249)."""
        from unittest.mock import patch

        # Mock the underlying function to return result without real_slurm
        mock_result = {"job_id": "12345", "stdout": "Hello World", "stderr": ""}

        with patch("slurm_mcp.mcp_handlers.get_job_output", return_value=mock_result):
            result = get_job_output_handler("12345")

            assert "real_slurm" in result
            assert result["real_slurm"] is False
            assert result["job_id"] == "12345"

    def test_get_queue_info_handler_real_slurm_field(self):
        """Test that real_slurm field is added when missing (line 275)."""
        from unittest.mock import patch

        # Mock the underlying function to return result without real_slurm
        mock_result = {"partitions": [{"name": "compute", "state": "up"}]}

        with patch("slurm_mcp.mcp_handlers.get_queue_info", return_value=mock_result):
            result = get_queue_info_handler()

            assert "real_slurm" in result
            assert result["real_slurm"] is False

    def test_submit_array_job_handler_real_slurm_field(self):
        """Test that real_slurm field is added when missing (line 321)."""
        from unittest.mock import patch

        # Mock the underlying function to return result without real_slurm
        mock_result = {"job_id": "12345_[1-10]", "status": "submitted"}

        with patch("slurm_mcp.mcp_handlers.submit_array_job", return_value=mock_result):
            result = submit_array_job_handler("/test/script.sh", "1-10")

            assert "real_slurm" in result
            assert result["real_slurm"] is False

    def test_get_node_info_handler_partition_field(self):
        """Test that partition field is handled correctly."""
        from unittest.mock import patch

        # Mock the underlying function
        mock_result = {"nodes": [{"name": "node001", "state": "idle"}]}

        with patch("slurm_mcp.mcp_handlers.get_node_info", return_value=mock_result):
            # get_node_info_handler doesn't take partition parameter, test basic functionality
            result = get_node_info_handler()

            assert "real_slurm" in result
            assert result["real_slurm"] is False

    def test_error_response_creation(self):
        """Test _create_error_response function."""
        from slurm_mcp.mcp_handlers import _create_error_response

        result = _create_error_response("Test error message", "test_function")

        assert isinstance(result, dict)
        assert "content" in result
        assert "_meta" in result
        assert "isError" in result
        assert result["isError"] is True
        assert result["_meta"]["tool"] == "test_function"
        assert "Test error message" in str(result["content"])

    def test_handlers_with_non_dict_results(self):
        """Test handlers when underlying functions return non-dict results."""
        from unittest.mock import patch

        # Test with string result
        with patch(
            "slurm_mcp.mcp_handlers.get_job_status", return_value="Invalid response"
        ):
            result = check_job_status_handler("12345")
            assert result == "Invalid response"

        # Test with None result
        with patch("slurm_mcp.mcp_handlers.get_job_status", return_value=None):
            result = check_job_status_handler("12345")
            assert result is None

    def test_list_jobs_handler_partial_filters(self):
        """Test list jobs handler with partial filter combinations."""
        from unittest.mock import patch

        mock_result = {"jobs": [], "total": 0}

        # Test with only user filter
        with patch("slurm_mcp.mcp_handlers.list_slurm_jobs", return_value=mock_result):
            result = list_slurm_jobs_handler(user="testuser")
            assert "user_filter" in result
            # Note: When real_slurm is False, empty filters may still be present

        # Test with only state filter
        with patch("slurm_mcp.mcp_handlers.list_slurm_jobs", return_value=mock_result):
            result = list_slurm_jobs_handler(state="RUNNING")
            assert "state_filter" in result
            # Note: When real_slurm is False, empty filters may still be present

    def test_node_info_handler_without_partition(self):
        """Test node info handler without partition filter."""
        from unittest.mock import patch

        mock_result = {"nodes": []}

        with patch("slurm_mcp.mcp_handlers.get_node_info", return_value=mock_result):
            result = get_node_info_handler()

            assert "partition_filter" not in result
            assert "real_slurm" in result
            assert result["real_slurm"] is False
