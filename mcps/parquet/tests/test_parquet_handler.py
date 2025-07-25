import pytest
import pyarrow as pa
import pyarrow.parquet as pq
import os
import tempfile
from src.capabilities.parquet_handler import read_column

@pytest.fixture
def sample_parquet_file():
    # create sample data
    data = {
        'id': [1, 2, 3, 4, 5],
        'name': ['John', 'Jane', 'Bob', 'Alice', 'Charlie'],
        'score': [85, 92, 78, 95, 88]
    }
    # create arrow table
    table = pa.Table.from_pydict(data)
    # create temporary parquet file
    with tempfile.NamedTemporaryFile(suffix='.parquet', delete=False) as f:
        pq.write_table(table, f.name)
    yield f.name
    os.unlink(f.name)

# test successful reading of an existing column
def test_read_existing_column(sample_parquet_file):
    result = read_column(sample_parquet_file, 'score')
    assert isinstance(result, list)
    assert len(result) == 5
    assert all(isinstance(x, int) for x in result)
    assert result == [85, 92, 78, 95, 88]

# test error when reading non-existent column
def test_read_nonexistent_column(sample_parquet_file):
    with pytest.raises(Exception) as exc_info:
        read_column(sample_parquet_file, 'nonexistent_column')

# test error when reading from non-existent file
def test_read_nonexistent_file():
    with pytest.raises(FileNotFoundError):
        read_column('nonexistent_file.parquet', 'score') 