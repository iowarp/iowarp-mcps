import pytest
import os
import tempfile
from src.capabilities.compression_handler import compress_file

@pytest.fixture
def sample_file():
    # create a temporary file with some content
    with tempfile.NamedTemporaryFile(mode='w', delete=False) as f:
        f.write("test content\n" * 100)
    yield f.name
    os.unlink(f.name)

# test successful compression of a file
def test_compress_success(sample_file):
    result = compress_file(sample_file)
    assert isinstance(result, dict)
    assert result["status"] == "success"
    assert os.path.exists(result["compressed_file"])
    os.unlink(result["compressed_file"])

# test compression of non-existent file
def test_compress_nonexistent_file():
    result = compress_file("nonexistent_file.txt")
    assert isinstance(result, dict)
    assert result["status"] == "error"
    assert "compression failed" in result["message"].lower()

# test compression of empty file
def test_compress_empty_file():
    with tempfile.NamedTemporaryFile(mode='w', delete=False) as f:
        f.write("")
    try:
        result = compress_file(f.name)
        assert isinstance(result, dict)
        assert result["status"] == "error"
        assert "compression failed" in result["message"].lower()
    finally:
        os.unlink(f.name) 