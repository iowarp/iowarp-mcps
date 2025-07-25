import pytest
import pandas as pd
import os
import tempfile
from src.capabilities.pandas_handler import analyze_csv

@pytest.fixture
def sample_csv_file():
    # create a temporary csv file
    with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.csv') as f:
        f.write("id,score\n")
        f.write("1,85\n")
        f.write("2,92\n")
        f.write("3,78\n")
    yield f.name
    os.unlink(f.name)

# test successful analysis of csv data
@pytest.mark.asyncio
async def test_analyze_success(sample_csv_file):
    result = await analyze_csv(sample_csv_file, 'score', 80)
    assert isinstance(result, dict)
    assert result["status"] == "success"
    assert len(result["data"]) == 2

# test analysis with non-existent file
@pytest.mark.asyncio
async def test_analyze_nonexistent_file():
    result = await analyze_csv("nonexistent.csv", "score", 80)
    assert isinstance(result, dict)
    assert result["status"] == "error"
    assert "no such file or directory" in result["message"].lower()

# test analysis with non-existent column
@pytest.mark.asyncio
async def test_analyze_nonexistent_column(sample_csv_file):
    result = await analyze_csv(sample_csv_file, "invalid_column", 80)
    assert isinstance(result, dict)
    assert result["status"] == "error"
    assert "invalid_column" in result["message"].lower() 