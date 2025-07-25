"""
Unit tests for hdf5_list.list_hdf5 function.

Covers:
 - Successful listing of .hdf5 files in a directory
 - Directory‑not‑found error
"""
import os
import sys
import pytest

# Add the src directory to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from capabilities import hdf5_list


def test_list_hdf5_basic(tmp_path):
    print("\n=== Running test_list_hdf5_basic ===")
    d = tmp_path / "dir"
    d.mkdir()
    (d / "a.hdf5").write_text("")
    (d / "b.hdf5").write_text("")
    print(f"Mock directory created at: {d}")

    files = hdf5_list.list_hdf5(str(d))
    print("Files found:", files)
    assert len(files) == 2


def test_list_hdf5_no_dir():
    print("\n=== Running test_list_hdf5_no_dir ===")
    with pytest.raises(FileNotFoundError) as excinfo:
        hdf5_list.list_hdf5("no_such_dir")
    print("Caught exception:", excinfo.value)