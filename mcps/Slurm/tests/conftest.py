"""
Test configuration and fixtures for Slurm MCP tests.
"""
import pytest
import tempfile
import os
import sys
from pathlib import Path

# Add src to Python path
src_path = Path(__file__).parent.parent / "src"
sys.path.insert(0, str(src_path))


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
    fd, script_path = tempfile.mkstemp(suffix='.sh', prefix='test_slurm_')
    with os.fdopen(fd, 'w') as f:
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
    fd, script_path = tempfile.mkstemp(suffix='.sh', prefix='test_array_')
    with os.fdopen(fd, 'w') as f:
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
    fd, script_path = tempfile.mkstemp(suffix='.sh', prefix='test_invalid_')
    with os.fdopen(fd, 'w') as f:
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
        "partition": "compute"
    }


@pytest.fixture
def array_parameters():
    """Return sample array job parameters."""
    return {
        "array_range": "1-5",
        "cores": 2,
        "memory": "2GB",
        "time_limit": "00:30:00",
        "job_name": "test_array_job"
    }


@pytest.fixture
def mock_job_output():
    """Return mock job output content."""
    return {
        "stdout": "Test job started\nProcessing data...\nTest job completed\n",
        "stderr": "Warning: test mode\n"
    }


@pytest.fixture
def temp_output_file():
    """Create a temporary output file for testing."""
    fd, output_path = tempfile.mkstemp(suffix='.out', prefix='slurm_test_')
    with os.fdopen(fd, 'w') as f:
        f.write("Test job output\nProcessing completed\nResults saved\n")
    
    yield output_path
    
    # Cleanup
    if os.path.exists(output_path):
        os.unlink(output_path)


@pytest.fixture
def temp_error_file():
    """Create a temporary error file for testing."""
    fd, error_path = tempfile.mkstemp(suffix='.err', prefix='slurm_test_')
    with os.fdopen(fd, 'w') as f:
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
    
    temp_dir = tempfile.mkdtemp(prefix='slurm_test_data_')
    
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
        "SLURM_ARRAY_TASK_ID": "1"
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
