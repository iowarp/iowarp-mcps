"""
Test configuration and fixtures for Slurm MCP tests.
"""

import pytest
import tempfile
import os
from unittest.mock import Mock, patch, mock_open


@pytest.fixture(autouse=True)
def mock_slurm_environment():
    """Mock the entire Slurm environment for testing."""
    with (
        patch(
            "slurm_mcp.implementation.utils.check_slurm_available", return_value=True
        ),
        patch("subprocess.run") as mock_run,
        patch("subprocess.check_output") as mock_check_output,
        patch("subprocess.Popen") as mock_popen,
        patch("shutil.which") as mock_which,
        patch("time.sleep") as mock_sleep,
    ):  # Prevent actual sleeping that could cause freezing
        # Mock which to return paths for Slurm commands
        def mock_which_func(cmd):
            slurm_commands = [
                "sbatch",
                "squeue",
                "scancel",
                "sinfo",
                "scontrol",
                "sacct",
            ]
            if cmd in slurm_commands:
                return f"/usr/bin/{cmd}"
            return None

        mock_which.side_effect = mock_which_func

        # Configure mock subprocess responses based on command with timeout protection
        def mock_run_func(*args, **kwargs):
            # Add timeout to prevent hanging
            if "timeout" not in kwargs:
                kwargs["timeout"] = 5.0

            cmd = args[0] if args else kwargs.get("args", [])
            if isinstance(cmd, list):
                cmd_name = cmd[0] if cmd else ""
            else:
                cmd_name = str(cmd).split()[0] if cmd else ""

            if "sbatch" in cmd_name:
                return Mock(
                    returncode=0, stdout="Submitted batch job 12345\n", stderr=""
                )
            elif "squeue" in cmd_name:
                return Mock(
                    returncode=0,
                    stdout="JOBID PARTITION     NAME     USER ST       TIME  NODES NODELIST(REASON)\n12345   compute test_job   user  R       0:30      1 node001\n",
                    stderr="",
                )
            elif "scancel" in cmd_name:
                return Mock(returncode=0, stdout="", stderr="")
            elif "sinfo" in cmd_name:
                return Mock(
                    returncode=0,
                    stdout="PARTITION AVAIL  TIMELIMIT  NODES  STATE NODELIST\ncompute*     up   infinite      4   idle node[001-004]\n",
                    stderr="",
                )
            elif "scontrol" in cmd_name:
                return Mock(
                    returncode=0,
                    stdout="JobId=12345 JobName=test_job UserId=user(1000) GroupId=user(1000) MCS_label=N/A Priority=4294901757 Nice=0 Account=(null) QOS=(null) JobState=RUNNING Reason=None Dependency=(null)\n",
                    stderr="",
                )
            elif "sacct" in cmd_name:
                return Mock(
                    returncode=0,
                    stdout="JobID|JobName|State|ExitCode\n12345|test_job|COMPLETED|0:0\n",
                    stderr="",
                )
            else:
                return Mock(returncode=0, stdout="", stderr="")

        mock_run.side_effect = mock_run_func

        # Configure mock_check_output with timeout protection
        def mock_check_output_func(*args, **kwargs):
            # Add timeout to prevent hanging
            if "timeout" not in kwargs:
                kwargs["timeout"] = 5.0

            cmd = args[0] if args else kwargs.get("args", [])
            if isinstance(cmd, list):
                cmd_name = cmd[0] if cmd else ""
            else:
                cmd_name = str(cmd).split()[0] if cmd else ""

            if "sbatch" in cmd_name:
                return b"Submitted batch job 12345\n"
            elif "squeue" in cmd_name:
                return b"JOBID PARTITION     NAME     USER ST       TIME  NODES NODELIST(REASON)\n12345   compute test_job   user  R       0:30      1 node001\n"
            else:
                return b"12345\n"

        mock_check_output.side_effect = mock_check_output_func

        # Mock Popen for interactive commands with timeout protection
        mock_process = Mock()
        mock_process.communicate.return_value = (b"12345\n", b"")
        mock_process.returncode = 0
        mock_process.poll.return_value = 0  # Process finished
        mock_popen.return_value = mock_process

        # Mock sleep to prevent actual delays
        mock_sleep.return_value = None

        yield {
            "mock_run": mock_run,
            "mock_check_output": mock_check_output,
            "mock_popen": mock_popen,
            "mock_which": mock_which,
            "mock_sleep": mock_sleep,
        }


@pytest.fixture
def mock_slurm_responses():
    """Provide mock responses for different Slurm scenarios."""
    return {
        "job_submission_success": {
            "returncode": 0,
            "stdout": "Submitted batch job 12345\n",
            "stderr": "",
        },
        "job_submission_failure": {
            "returncode": 1,
            "stdout": "",
            "stderr": "sbatch: error: job submission failed\n",
        },
        "job_status_running": {
            "returncode": 0,
            "stdout": "JOBID PARTITION     NAME     USER ST       TIME  NODES NODELIST(REASON)\n12345   compute test_job   user  R       0:30      1 node001\n",
            "stderr": "",
        },
        "job_status_completed": {
            "returncode": 0,
            "stdout": "JOBID PARTITION     NAME     USER ST       TIME  NODES NODELIST(REASON)\n12345   compute test_job   user CD      1:00      1 node001\n",
            "stderr": "",
        },
        "cluster_info": {
            "returncode": 0,
            "stdout": "PARTITION AVAIL  TIMELIMIT  NODES  STATE NODELIST\ncompute*     up   infinite      4   idle node[001-004]\ndebug        up       30:00      2   idle node[005-006]\n",
            "stderr": "",
        },
        "node_info": {
            "returncode": 0,
            "stdout": "NodeName=node001 CPUs=24 RealMemory=64000 State=IDLE\nNodeName=node002 CPUs=24 RealMemory=64000 State=IDLE\n",
            "stderr": "",
        },
    }


@pytest.fixture
def mock_slurm_unavailable():
    """Mock Slurm as unavailable for testing graceful degradation."""
    with (
        patch(
            "slurm_mcp.implementation.utils.check_slurm_available", return_value=False
        ),
        patch("shutil.which", return_value=None),
        patch("subprocess.run") as mock_run,
        patch("subprocess.check_output") as mock_check_output,
    ):
        # When Slurm is unavailable, operations should return appropriate messages
        def mock_run_unavailable(*args, **kwargs):
            return Mock(
                returncode=127,  # Command not found
                stdout="",
                stderr="sbatch: command not found",
            )

        def mock_check_output_unavailable(*args, **kwargs):
            from subprocess import CalledProcessError

            raise CalledProcessError(
                127, args[0] if args else "command", "command not found"
            )

        mock_run.side_effect = mock_run_unavailable
        mock_check_output.side_effect = mock_check_output_unavailable

        yield {"mock_run": mock_run, "mock_check_output": mock_check_output}


@pytest.fixture
def temp_script():
    """Create a temporary test script."""
    script_content = """#!/bin/bash
echo "Test job started on $(hostname)"
echo "Current directory: $(pwd)"
echo "Date: $(date)"
sleep 2
echo "Test job completed successfully"
"""
    fd, script_path = tempfile.mkstemp(suffix=".sh", prefix="test_slurm_")
    with os.fdopen(fd, "w") as f:
        f.write(script_content)
    os.chmod(script_path, 0o755)

    yield script_path

    # Cleanup
    if os.path.exists(script_path):
        os.unlink(script_path)


@pytest.fixture
def array_script():
    """Create a temporary array job script."""
    script_content = """#!/bin/bash
echo "Array job task ${SLURM_ARRAY_TASK_ID} started"
echo "Array job ID: ${SLURM_ARRAY_JOB_ID}"
echo "Task ID: ${SLURM_ARRAY_TASK_ID}"
sleep $((SLURM_ARRAY_TASK_ID + 1))
echo "Array task ${SLURM_ARRAY_TASK_ID} completed"
"""
    fd, script_path = tempfile.mkstemp(suffix=".sh", prefix="test_array_")
    with os.fdopen(fd, "w") as f:
        f.write(script_content)
    os.chmod(script_path, 0o755)

    yield script_path

    # Cleanup
    if os.path.exists(script_path):
        os.unlink(script_path)


@pytest.fixture
def invalid_script():
    """Create a temporary invalid script."""
    script_content = """#!/bin/bash
echo "This script will fail"
exit 1
"""
    fd, script_path = tempfile.mkstemp(suffix=".sh", prefix="test_invalid_")
    with os.fdopen(fd, "w") as f:
        f.write(script_content)
    os.chmod(script_path, 0o755)

    yield script_path

    # Cleanup
    if os.path.exists(script_path):
        os.unlink(script_path)


@pytest.fixture
def valid_cores():
    """Return a valid number of cores for testing."""
    return 2


@pytest.fixture
def invalid_cores():
    """Return an invalid number of cores for testing."""
    return 0


@pytest.fixture
def sample_job_id():
    """Return a sample job ID for testing."""
    return "1234567"


@pytest.fixture
def sample_array_job_id():
    """Return a sample array job ID for testing."""
    return "2345678"


@pytest.fixture
def job_parameters():
    """Return sample job parameters."""
    return {
        "memory": "4GB",
        "time_limit": "01:00:00",
        "job_name": "test_job",
        "partition": "compute",
    }


@pytest.fixture
def array_parameters():
    """Return sample array job parameters."""
    return {
        "array_range": "1-5",
        "cores": 2,
        "memory": "2GB",
        "time_limit": "00:30:00",
        "job_name": "test_array_job",
    }


@pytest.fixture
def mock_job_output():
    """Return mock job output content."""
    return {
        "stdout": "Test job started\nProcessing data...\nTest job completed\n",
        "stderr": "Warning: test mode\n",
    }


@pytest.fixture
def temp_output_file():
    """Create a temporary output file for testing."""
    fd, output_path = tempfile.mkstemp(suffix=".out", prefix="slurm_test_")
    with os.fdopen(fd, "w") as f:
        f.write("Test job output\nProcessing completed\nResults saved\n")

    yield output_path

    # Cleanup
    if os.path.exists(output_path):
        os.unlink(output_path)


@pytest.fixture
def temp_error_file():
    """Create a temporary error file for testing."""
    fd, error_path = tempfile.mkstemp(suffix=".err", prefix="slurm_test_")
    with os.fdopen(fd, "w") as f:
        f.write("Warning: test mode\nDebug: initialization complete\n")

    yield error_path

    # Cleanup
    if os.path.exists(error_path):
        os.unlink(error_path)


@pytest.fixture(scope="session")
def test_data_dir():
    """Create a temporary directory for test data."""
    import tempfile
    import shutil

    temp_dir = tempfile.mkdtemp(prefix="slurm_test_data_")

    # Create some test files
    os.makedirs(os.path.join(temp_dir, "scripts"), exist_ok=True)
    os.makedirs(os.path.join(temp_dir, "output"), exist_ok=True)

    yield temp_dir

    # Cleanup
    shutil.rmtree(temp_dir, ignore_errors=True)


@pytest.fixture
def slurm_env_vars():
    """Set up Slurm environment variables for testing."""
    env_vars = {
        "SLURM_JOB_ID": "1234567",
        "SLURM_JOB_NAME": "test_job",
        "SLURM_CPUS_PER_TASK": "4",
        "SLURM_MEM_PER_NODE": "8192",
        "SLURM_JOB_PARTITION": "compute",
        "SLURM_ARRAY_JOB_ID": "2345678",
        "SLURM_ARRAY_TASK_ID": "1",
    }

    # Set environment variables
    original_vars = {}
    for key, value in env_vars.items():
        original_vars[key] = os.environ.get(key)
        os.environ[key] = value

    yield env_vars

    # Restore original environment
    for key, original_value in original_vars.items():
        if original_value is None:
            os.environ.pop(key, None)
        else:
            os.environ[key] = original_value


@pytest.fixture
def mock_filesystem():
    """Mock filesystem operations for testing."""
    with (
        patch("os.path.exists") as mock_exists,
        patch("os.makedirs") as mock_makedirs,
        patch("builtins.open", mock_open()) as mock_file,
        patch("tempfile.mkdtemp") as mock_mkdtemp,
    ):
        # Mock path existence checks
        mock_exists.return_value = True

        # Mock temporary directory creation
        mock_mkdtemp.return_value = "/tmp/slurm_test"

        yield {
            "mock_exists": mock_exists,
            "mock_makedirs": mock_makedirs,
            "mock_file": mock_file,
            "mock_mkdtemp": mock_mkdtemp,
        }


@pytest.fixture
def mock_validation():
    """Mock validation functions for testing."""
    with (
        patch(
            "slurm_mcp.implementation.utils.validate_job_script"
        ) as mock_validate_script,
        patch(
            "slurm_mcp.implementation.utils.validate_partition"
        ) as mock_validate_partition,
        patch("slurm_mcp.implementation.utils.validate_job_id") as mock_validate_id,
    ):
        mock_validate_script.return_value = True
        mock_validate_partition.return_value = True
        mock_validate_id.return_value = True

        yield {
            "mock_validate_script": mock_validate_script,
            "mock_validate_partition": mock_validate_partition,
            "mock_validate_id": mock_validate_id,
        }
