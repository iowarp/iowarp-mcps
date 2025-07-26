"""
Integration tests for the complete Slurm MCP workflow.
Tests end-to-end functionality from MCP tools through to Slurm capabilities.
"""

import pytest
import tempfile
import os
import sys
import time

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

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

from implementation.slurm_handler import _check_slurm_available


class TestIntegration:
    """Integration tests for complete Slurm MCP workflow."""

    def test_complete_job_workflow(self, temp_script):
        """Test complete job submission and monitoring workflow."""
        # Submit job
        submit_result = submit_slurm_job(
            temp_script,
            cores=2,
            memory="1GB",
            time_limit="00:05:00",
            job_name="integration_test",
        )

        assert isinstance(submit_result, dict)

        # If submission was successful, test the complete workflow
        if not submit_result.get("isError") and "job_id" in submit_result:
            job_id = submit_result["job_id"]

            # Check initial status
            status_result = get_job_status(job_id)
            assert isinstance(status_result, dict)
            assert "job_id" in status_result or not status_result.get("isError")

            # Get detailed job information
            details_result = get_job_details(job_id)
            assert isinstance(details_result, dict)

            # Try to get job output (may not exist yet)
            stdout_result = get_job_output(job_id, "stdout")
            assert isinstance(stdout_result, dict)

            stderr_result = get_job_output(job_id, "stderr")
            assert isinstance(stderr_result, dict)

            # Cancel the job to clean up
            cancel_result = cancel_slurm_job(job_id)
            assert isinstance(cancel_result, dict)

    def test_array_job_workflow(self, array_script):
        """Test complete array job workflow."""
        # Submit array job
        submit_result = submit_array_job(
            array_script,
            array_range="1-3",
            cores=1,
            memory="1GB",
            time_limit="00:05:00",
            job_name="integration_array_test",
        )

        assert isinstance(submit_result, dict)

        if not submit_result.get("isError") and "array_job_id" in submit_result:
            array_job_id = submit_result["array_job_id"]

            # Check array job status
            status_result = get_job_status(array_job_id)
            assert isinstance(status_result, dict)

            # Get array job details
            details_result = get_job_details(array_job_id)
            assert isinstance(details_result, dict)

            # Cancel array job
            cancel_result = cancel_slurm_job(array_job_id)
            assert isinstance(cancel_result, dict)

    def test_job_monitoring_workflow(self, temp_script):
        """Test job monitoring and information gathering workflow."""
        # Get initial cluster state
        cluster_info = get_slurm_info()
        assert isinstance(cluster_info, dict)

        node_info = get_node_info()
        assert isinstance(node_info, dict)

        queue_info = get_queue_info()
        assert isinstance(queue_info, dict)

        # List current jobs
        job_list = list_slurm_jobs()
        assert isinstance(job_list, dict)

        # Submit a job for monitoring
        submit_result = submit_slurm_job(
            temp_script, cores=1, job_name="monitoring_test"
        )

        if not submit_result.get("isError") and "job_id" in submit_result:
            job_id = submit_result["job_id"]

            # Monitor job through multiple status checks
            for i in range(3):
                status = get_job_status(job_id)
                assert isinstance(status, dict)

                # Small delay between checks
                time.sleep(0.5)

            # Get updated queue info
            updated_queue = get_queue_info()
            assert isinstance(updated_queue, dict)

            # Clean up
            cancel_slurm_job(job_id)

    def test_error_propagation(self):
        """Test that errors propagate correctly through the system."""
        # Test with invalid script
        with pytest.raises(FileNotFoundError):
            submit_slurm_job("nonexistent_script.sh", 1)

        # Test with invalid job ID
        result = get_job_status("invalid_job_id_12345")
        assert isinstance(result, dict)
        # Should handle gracefully - either error flag or meaningful response

        # Test with invalid parameters
        with pytest.raises((FileNotFoundError, ValueError)):
            submit_slurm_job(
                "test.sh", 0
            )  # Invalid cores (file not found first, then invalid cores)

    def test_concurrent_operations(self, temp_script):
        """Test multiple job operations."""
        # Submit multiple jobs sequentially (since handlers are synchronous)
        submit_results = []
        for i in range(3):
            result = submit_slurm_job(
                temp_script, cores=1, job_name=f"concurrent_test_{i}"
            )
            submit_results.append(result)

        # Check results
        job_ids = []
        for result in submit_results:
            assert isinstance(result, dict)
            if not result.get("isError") and "job_id" in result:
                job_ids.append(result["job_id"])

        # If we got job IDs, test status checks
        if job_ids:
            status_results = [get_job_status(job_id) for job_id in job_ids]

            for result in status_results:
                assert isinstance(result, dict)

            # Clean up jobs
            cancel_results = [cancel_slurm_job(job_id) for job_id in job_ids]
            for result in cancel_results:
                assert isinstance(result, dict)

    def test_queue_and_cluster_info_consistency(self):
        """Test that queue and cluster information is consistent."""
        # Get cluster information
        cluster_info = get_slurm_info()
        queue_info = get_queue_info()
        node_info = get_node_info()
        job_list = list_slurm_jobs()

        # All should return dictionary responses
        assert isinstance(cluster_info, dict)
        assert isinstance(queue_info, dict)
        assert isinstance(node_info, dict)
        assert isinstance(job_list, dict)

        # Check consistency between different info sources
        if not cluster_info.get("isError") and not queue_info.get("isError"):
            # Both should indicate same real_slurm status
            if "real_slurm" in cluster_info and "real_slurm" in queue_info:
                assert cluster_info["real_slurm"] == queue_info["real_slurm"]

    def test_job_lifecycle_with_output(self, temp_script):
        """Test complete job lifecycle including output retrieval."""
        # Create a script that generates output
        script_content = """#!/bin/bash
echo "Job started at $(date)"
echo "Environment variables:"
echo "SLURM_JOB_ID: $SLURM_JOB_ID"
echo "SLURM_JOB_NAME: $SLURM_JOB_NAME"
echo "Working directory: $(pwd)"
echo "Hostname: $(hostname)"
sleep 2
echo "Job processing complete"
echo "Job finished at $(date)"
"""

        # Create temporary script with output
        fd, output_script = tempfile.mkstemp(suffix=".sh", prefix="lifecycle_test_")
        try:
            with os.fdopen(fd, "w") as f:
                f.write(script_content)
            os.chmod(output_script, 0o755)

            # Submit job
            submit_result = submit_slurm_job(
                output_script,
                cores=1,
                memory="1GB",
                time_limit="00:05:00",
                job_name="lifecycle_test",
            )

            if not submit_result.get("isError") and "job_id" in submit_result:
                job_id = submit_result["job_id"]

                # Wait a bit for job to potentially start
                time.sleep(2)

                # Check job status multiple times
                for check in range(3):
                    status = get_job_status(job_id)
                    assert isinstance(status, dict)
                    time.sleep(1)

                # Try to get job output
                stdout_result = get_job_output(job_id, "stdout")
                stderr_result = get_job_output(job_id, "stderr")

                assert isinstance(stdout_result, dict)
                assert isinstance(stderr_result, dict)

                # Clean up
                cancel_slurm_job(job_id)

        finally:
            if os.path.exists(output_script):
                os.unlink(output_script)

    def test_filtered_operations(self):
        """Test operations with various filters and parameters."""
        # Test job listing with different filters
        all_jobs = list_slurm_jobs()
        assert isinstance(all_jobs, dict)

        user_jobs = list_slurm_jobs(user="testuser")
        assert isinstance(user_jobs, dict)

        running_jobs = list_slurm_jobs(state="RUNNING")
        assert isinstance(running_jobs, dict)

        # Test queue info with partition filter
        all_queue = get_queue_info()
        assert isinstance(all_queue, dict)

        partition_queue = get_queue_info(partition="compute")
        assert isinstance(partition_queue, dict)

    def test_parameter_combinations(self, temp_script):
        """Test various parameter combinations for job submission."""
        # Test different parameter combinations
        parameter_sets = [
            {"cores": 1},
            {"cores": 2, "memory": "2GB"},
            {"cores": 1, "time_limit": "00:30:00"},
            {"cores": 2, "memory": "4GB", "time_limit": "01:00:00"},
            {"cores": 1, "job_name": "param_test"},
            {
                "cores": 2,
                "memory": "2GB",
                "job_name": "param_test_2",
                "partition": "compute",
            },
        ]

        for params in parameter_sets:
            result = submit_slurm_job(temp_script, **params)
            assert isinstance(result, dict)

            # If successful, clean up
            if not result.get("isError") and "job_id" in result:
                job_id = result["job_id"]
                cancel_slurm_job(job_id)

    def test_system_resource_awareness(self):
        """Test that the system is aware of its environment."""
        is_real_slurm = _check_slurm_available()

        # Get system information
        cluster_info = get_slurm_info()
        node_info = get_node_info()

        if not cluster_info.get("isError"):
            # real_slurm flag should match system detection
            if "real_slurm" in cluster_info:
                assert cluster_info["real_slurm"] == is_real_slurm

        if not node_info.get("isError"):
            if "real_slurm" in node_info:
                assert node_info["real_slurm"] == is_real_slurm

    def test_robustness_under_load(self, temp_script):
        """Test system robustness under higher load."""
        # Submit multiple jobs and perform various operations
        results = []

        # Job submissions
        for i in range(5):
            result = submit_slurm_job(temp_script, cores=1, job_name=f"load_test_{i}")
            results.append(result)

        # Information gathering
        results.append(get_slurm_info())
        results.append(get_node_info())
        results.append(get_queue_info())
        results.append(list_slurm_jobs())

        # Check that all operations completed
        job_ids = []
        for result in results:
            assert isinstance(result, dict)
            if "job_id" in result:
                job_ids.append(result["job_id"])

        # Clean up any submitted jobs
        if job_ids:
            cancel_results = [cancel_slurm_job(job_id) for job_id in job_ids]
            for result in cancel_results:
                assert isinstance(result, dict)

    def test_data_consistency_across_calls(self, temp_script):
        """Test data consistency across multiple API calls."""
        # Submit a job
        submit_result = submit_slurm_job(
            temp_script, cores=1, job_name="consistency_test"
        )

        if not submit_result.get("isError") and "job_id" in submit_result:
            job_id = submit_result["job_id"]

            # Get job information through different methods
            status1 = get_job_status(job_id)
            details1 = get_job_details(job_id)

            # Small delay
            time.sleep(0.5)

            # Get information again
            status2 = get_job_status(job_id)
            details2 = get_job_details(job_id)

            # Job ID should be consistent
            if not status1.get("isError") and "job_id" in status1:
                assert status1["job_id"] == job_id
            if not status2.get("isError") and "job_id" in status2:
                assert status2["job_id"] == job_id
            if not details1.get("isError") and "job_id" in details1:
                assert details1["job_id"] == job_id
            if not details2.get("isError") and "job_id" in details2:
                assert details2["job_id"] == job_id

            # Clean up
            cancel_slurm_job(job_id)

    def test_environment_detection(self):
        """Test that the system correctly detects its environment."""
        is_real_slurm = _check_slurm_available()
        assert isinstance(is_real_slurm, bool)

        if is_real_slurm:
            # If real Slurm is available, certain commands should be accessible
            import shutil

            assert shutil.which("sbatch") is not None
            assert shutil.which("squeue") is not None
        else:
            # In mock mode, system should still function
            # This is tested by all other tests working
            pass
