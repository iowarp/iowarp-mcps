import pytest
import os
import tempfile
from src.capabilities.sort_handler import sort_log_by_timestamp

# fixture to create a temporary log file with test data
@pytest.fixture
def sample_log_file():
    # create a temporary file
    with tempfile.NamedTemporaryFile(mode='w', delete=False) as f:
        # write sample log entries
        f.write("2024-03-15 10:30:45 INFO test message 1\n")
        f.write("2024-03-15 09:15:30 ERROR error message\n")
        f.write("2024-03-15 11:45:20 DEBUG debug message\n")
        f.write("2024-03-15 10:00:00 INFO test message 2\n")
    
    yield f.name
    os.unlink(f.name)

# test successful sorting of log file
def test_sort_log_success(sample_log_file):
    result = sort_log_by_timestamp(sample_log_file)
    
    assert isinstance(result, list)
    assert len(result) == 4
    
    timestamps = [line.split()[1] for line in result]
    assert timestamps == sorted(timestamps)

# test empty file handling
def test_sort_empty_file():
    with tempfile.NamedTemporaryFile(mode='w', delete=False) as f:
        pass
    
    try:
        result = sort_log_by_timestamp(f.name)
        assert isinstance(result, list)
        assert len(result) == 0
    finally:
        os.unlink(f.name)

# test non-existent file
def test_sort_nonexistent_file():
    result = sort_log_by_timestamp("nonexistent_file.log")
    assert isinstance(result, dict)
    assert "error" in result
    assert "error processing file" in result["error"].lower()