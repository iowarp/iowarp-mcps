"""
Test cases for Plot MCP server functionality.
"""
import pytest
import os
import tempfile
from pathlib import Path
import pandas as pd
import sys

# Add src to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from src.implementation.plot_capabilities import (
    create_line_plot,
    create_bar_plot,
    create_scatter_plot,
    create_histogram,
    create_heatmap,
    get_data_info
)

@pytest.fixture
def sample_csv_file():
    """Create a temporary CSV file for testing."""
    data = {
        'x': [1, 2, 3, 4, 5],
        'y': [2, 4, 6, 8, 10],
        'category': ['A', 'B', 'A', 'B', 'A'],
        'value': [10, 20, 30, 40, 50]
    }
    df = pd.DataFrame(data)
    
    with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False) as f:
        df.to_csv(f.name, index=False)
        yield f.name
    
    # Cleanup
    os.unlink(f.name)

@pytest.fixture
def output_dir():
    """Create a temporary directory for output files."""
    with tempfile.TemporaryDirectory() as temp_dir:
        yield temp_dir

def test_get_get_data_info(sample_csv_file):
    """Test getting data information."""
    result = get_data_info(sample_csv_file)
    
    assert result["status"] == "success"
    assert result["shape"] == (5, 4)
    assert "x" in result["columns"]
    assert "y" in result["columns"]
    assert "category" in result["columns"]
    assert "value" in result["columns"]

def test_create_create_line_plot(sample_csv_file, output_dir):
    """Test creating line plot."""
    output_path = os.path.join(output_dir, "test_line_plot.png")
    
    result = create_line_plot(
        sample_csv_file, "x", "y", "Test Line Plot", output_path
    )
    
    assert result["status"] == "success"
    assert result["x_column"] == "x"
    assert result["y_column"] == "y"
    assert result["data_points"] == 5
    assert os.path.exists(output_path)

def test_create_create_bar_plot(sample_csv_file, output_dir):
    """Test creating bar plot."""
    output_path = os.path.join(output_dir, "test_bar_plot.png")
    
    result = create_bar_plot(
        sample_csv_file, "category", "value", "Test Bar Plot", output_path
    )
    
    assert result["status"] == "success"
    assert result["x_column"] == "category"
    assert result["y_column"] == "value"
    assert result["data_points"] == 5
    assert os.path.exists(output_path)

def test_create_create_scatter_plot(sample_csv_file, output_dir):
    """Test creating scatter plot."""
    output_path = os.path.join(output_dir, "test_scatter_plot.png")
    
    result = create_scatter_plot(
        sample_csv_file, "x", "y", "Test Scatter Plot", output_path
    )
    
    assert result["status"] == "success"
    assert result["x_column"] == "x"
    assert result["y_column"] == "y"
    assert result["data_points"] == 5
    assert os.path.exists(output_path)

def test_create_histogram_handler(sample_csv_file, output_dir):
    """Test creating histogram."""
    output_path = os.path.join(output_dir, "test_histogram.png")
    
    result = create_histogram(
        sample_csv_file, "value", 10, "Test Histogram", output_path
    )
    
    assert result["status"] == "success"
    assert result["column"] == "value"
    assert result["bins"] == 10
    assert result["data_points"] == 5
    assert os.path.exists(output_path)

def test_create_heatmap_handler(sample_csv_file, output_dir):
    """Test creating heatmap."""
    output_path = os.path.join(output_dir, "test_heatmap.png")
    
    result = create_heatmap(
        sample_csv_file, "Test Heatmap", output_path
    )
    
    assert result["status"] == "success"
    assert result["data_points"] == 5
    assert os.path.exists(output_path)

def test_error_handling():
    """Test error handling for invalid files."""
    result = get_data_info("nonexistent_file.csv")
    assert result["status"] == "error"
    
    result = create_line_plot("nonexistent_file.csv", "x", "y", "Test", "output.png")
    assert result["status"] == "error"

if __name__ == "__main__":
    pytest.main([__file__])
