"""
Tests for Slurm capabilities.
Tests real Slurm job submission and status checking.
Requires Slurm to be installed and available on the system.
"""

import pytest
import os
import tempfile
import sys
from pathlib import Path
from implementation.slurm_handler import (
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
    _check_slurm_available,
    _create_sbatch_script,
)

# Add src to Python path
src_path = Path(__file__).parent.parent / "src"
sys.path.insert(0, str(src_path))


class TestSlurmCapabilities:
    """Test suite for Slurm capabilities."""

    def test_slurm_availability_check(self):
        """Test Slurm availability detection."""
        # This will return True or False based on actual system
        result = _check_slurm_available()
        assert isinstance(result, bool)

    def test_sbatch_script_creation_basic(self, temp_script):
        """Test basic SBATCH script generation."""
        cores = 4
        sbatch_script = _create_sbatch_script(temp_script, cores)

        assert os.path.exists(sbatch_script)

        with open(sbatch_script, "r") as f:
            content = f.read()

        # Check for basic SBATCH directives
        assert "#!/bin/bash" in content
        assert f"#SBATCH --cpus-per-task={cores}" in content
        assert "#SBATCH --job-name=mcp_job" in content
        assert "#SBATCH --output=logs/slurm_output/slurm_%j.out" in content
        assert "#SBATCH --error=logs/slurm_output/slurm_%j.err" in content

        # Cleanup
        os.unlink(sbatch_script)

    def test_sbatch_script_creation_enhanced(self, temp_script, job_parameters):
        """Test enhanced SBATCH script generation with all parameters."""
        cores = 4
        sbatch_script = _create_sbatch_script(
            temp_script,
            cores,
            memory=job_parameters["memory"],
            time_limit=job_parameters["time_limit"],
            job_name=job_parameters["job_name"],
            partition=job_parameters["partition"],
        )

        assert os.path.exists(sbatch_script)

        with open(sbatch_script, "r") as f:
            content = f.read()

        # Check for enhanced SBATCH directives
        assert f"#SBATCH --mem={job_parameters['memory']}" in content
        assert f"#SBATCH --time={job_parameters['time_limit']}" in content
        assert f"#SBATCH --job-name={job_parameters['job_name']}" in content
        assert f"#SBATCH --partition={job_parameters['partition']}" in content

        # Cleanup
        os.unlink(sbatch_script)

    def test_job_submission_validation(self, temp_script):
        """Test job submission parameter validation."""
        # Test invalid cores
        with pytest.raises(ValueError):
            submit_slurm_job(temp_script, 0)

        with pytest.raises(ValueError):
            submit_slurm_job(temp_script, -1)

        # Test invalid script path
        with pytest.raises(FileNotFoundError):
            submit_slurm_job("/nonexistent/script.sh", 4)

    def test_enhanced_job_submission(self, temp_script, job_parameters):
        """Test job submission with enhanced parameters."""
        result = submit_slurm_job(
            temp_script,
            4,
            memory=job_parameters["memory"],
            time_limit=job_parameters["time_limit"],
            job_name=job_parameters["job_name"],
            partition=job_parameters["partition"],
        )

        # Should return a dictionary with job_id
        assert isinstance(result, dict)
        assert "job_id" in result
        assert len(result["job_id"]) > 0

    def test_job_status_structure(self, sample_job_id):
        """Test that job status returns proper structure."""
        status = get_job_status(sample_job_id)

        required_keys = ["job_id", "status", "reason", "real_slurm"]
        for key in required_keys:
            assert key in status

        assert isinstance(status["real_slurm"], bool)
        assert status["job_id"] == sample_job_id

    def test_cancel_job_functionality(self, sample_job_id):
        """Test job cancellation functionality."""
        result = cancel_slurm_job(sample_job_id)

        # Should return proper structure
        required_keys = ["job_id", "status", "message", "real_slurm"]
        for key in required_keys:
            assert key in result

        assert result["job_id"] == sample_job_id
        assert result["status"] in ["cancelled", "error"]

    def test_list_jobs_functionality(self):
        """Test job listing functionality."""
        # Test without filters
        result = list_slurm_jobs()

        # Should return proper structure
        required_keys = ["jobs", "count", "real_slurm"]
        for key in required_keys:
            assert key in result

        assert isinstance(result["jobs"], list)
        assert isinstance(result["count"], int)
        assert result["count"] == len(result["jobs"])

        # Test with user filter
        result_filtered = list_slurm_jobs(user="testuser")
        assert "user_filter" in result_filtered
        assert result_filtered["user_filter"] == "testuser"

        # Test with state filter
        result_state = list_slurm_jobs(state="RUNNING")
        assert "state_filter" in result_state
        assert result_state["state_filter"] == "RUNNING"

    def test_cluster_info_functionality(self):
        """Test cluster information functionality."""
        result = get_slurm_info()

        # Should return proper structure
        required_keys = ["cluster_name", "partitions", "real_slurm"]
        for key in required_keys:
            assert key in result

        assert isinstance(result["partitions"], list)
        assert isinstance(result["real_slurm"], bool)

        # Check partition structure if any partitions exist
        if result["partitions"]:
            partition = result["partitions"][0]
            partition_keys = ["partition", "avail_idle", "timelimit", "nodes", "state"]
            for key in partition_keys:
                assert key in partition

    def test_job_details_functionality(self, sample_job_id):
        """Test detailed job information retrieval."""
        result = get_job_details(sample_job_id)

        required_keys = ["job_id", "real_slurm"]
        for key in required_keys:
            assert key in result

        assert result["job_id"] == sample_job_id
        assert isinstance(result["real_slurm"], bool)

        # Should have either details or error
        assert "details" in result or "error" in result

    def test_job_output_functionality(self, sample_job_id):
        """Test job output retrieval functionality."""
        for output_type in ["stdout", "stderr"]:
            result = get_job_output(sample_job_id, output_type)

            required_keys = ["job_id", "output_type", "real_slurm"]
            for key in required_keys:
                assert key in result

            assert result["job_id"] == sample_job_id
            assert result["output_type"] == output_type

            # Should have either content or error
            assert "content" in result or "error" in result

    def test_queue_info_functionality(self):
        """Test queue information functionality."""
        # Test without partition filter
        result = get_queue_info()

        required_keys = ["jobs", "total_jobs", "state_summary", "real_slurm"]
        for key in required_keys:
            assert key in result

        assert isinstance(result["jobs"], list)
        assert isinstance(result["total_jobs"], int)
        assert isinstance(result["state_summary"], dict)

        # Test with partition filter
        result_filtered = get_queue_info(partition="compute")
        assert "partition_filter" in result_filtered
        assert result_filtered["partition_filter"] == "compute"

    def test_array_job_submission(self, array_script, array_parameters):
        """Test array job submission functionality."""
        result = submit_array_job(
            array_script,
            array_parameters["array_range"],
            cores=array_parameters["cores"],
            memory=array_parameters["memory"],
            time_limit=array_parameters["time_limit"],
            job_name=array_parameters["job_name"],
        )

        if "error" not in result:
            required_keys = ["array_job_id", "array_range", "real_slurm"]
            for key in required_keys:
                assert key in result

            assert result["array_range"] == array_parameters["array_range"]
            assert isinstance(result["real_slurm"], bool)

    def test_node_info_functionality(self):
        """Test node information functionality."""
        result = get_node_info()

        required_keys = ["nodes", "total_nodes", "real_slurm"]
        for key in required_keys:
            assert key in result

        assert isinstance(result["nodes"], list)
        assert isinstance(result["total_nodes"], int)
        assert result["total_nodes"] == len(result["nodes"])

        # Check node structure if any nodes exist
        if result["nodes"]:
            node = result["nodes"][0]
            node_keys = ["node_name", "state", "cpus", "memory"]
            for key in node_keys:
                assert key in node

    def test_job_workflow_integration(self, temp_script):
        """Test complete job workflow integration."""
        # Submit job
        submit_result = submit_slurm_job(
            temp_script, cores=2, job_name="integration_test"
        )
        assert isinstance(submit_result, dict)
        assert "job_id" in submit_result

        job_id = submit_result["job_id"]

        # Check status
        status = get_job_status(job_id)
        assert status["job_id"] == job_id

        # Get details
        details = get_job_details(job_id)
        assert details["job_id"] == job_id

        # Try to cancel (should work even if job doesn't exist)
        cancel_result = cancel_slurm_job(job_id)
        assert cancel_result["job_id"] == job_id

    def test_error_handling(self):
        """Test error handling in various scenarios."""
        # Test with invalid job ID
        status = get_job_status("invalid_job_id")
        assert "job_id" in status
        assert "real_slurm" in status

        # Test cancellation of non-existent job
        cancel_result = cancel_slurm_job("999999999")
        assert "job_id" in cancel_result
        assert "status" in cancel_result

    def test_real_slurm_detection(self):
        """Test that real Slurm detection works properly."""
        is_real = _check_slurm_available()

        # Test job submission only if Slurm is available
        if is_real:
            with tempfile.NamedTemporaryFile(mode="w", suffix=".sh", delete=False) as f:
                f.write("#!/bin/bash\necho 'test'\n")
                script_path = f.name

            os.chmod(script_path, 0o755)

            try:
                submit_result = submit_slurm_job(script_path, 2)
                job_id = submit_result["job_id"]
                status = get_job_status(job_id)

                # The real_slurm flag should be True
                assert status["real_slurm"]

                # Should return a valid job ID
                assert isinstance(job_id, str)
                assert job_id.isdigit()
                assert 1 <= len(job_id) <= 10
            finally:
                os.unlink(script_path)
        else:
            # If Slurm is not available, submission should fail
            with tempfile.NamedTemporaryFile(mode="w", suffix=".sh", delete=False) as f:
                f.write("#!/bin/bash\necho 'test'\n")
                script_path = f.name

            os.chmod(script_path, 0o755)

            try:
                with pytest.raises(RuntimeError, match="Slurm is not available"):
                    submit_slurm_job(script_path, 2)
            finally:
                os.unlink(script_path)

    def test_job_submission_with_valid_script(self, temp_script, valid_cores):
        """Test job submission with valid script and cores."""
        submit_result = submit_slurm_job(temp_script, valid_cores)

        assert isinstance(submit_result, dict)
        assert "job_id" in submit_result
        job_id = submit_result["job_id"]
        assert isinstance(job_id, str)
        assert job_id.isdigit()

    def test_job_submission_with_invalid_file(self, valid_cores):
        """Test job submission with non-existent file."""
        with pytest.raises(FileNotFoundError):
            submit_slurm_job("nonexistent_file.sh", valid_cores)

    def test_job_submission_with_invalid_cores(self, temp_script, invalid_cores):
        """Test job submission with invalid core count."""
        with pytest.raises(ValueError):
            submit_slurm_job(temp_script, invalid_cores)

    def test_job_status_check(self, sample_job_id):
        """Test job status checking."""
        status = get_job_status(sample_job_id)

        assert isinstance(status, dict)
        assert "job_id" in status
        assert "status" in status
        assert "reason" in status
        assert status["job_id"] == sample_job_id
