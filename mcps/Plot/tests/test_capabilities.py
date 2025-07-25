"""
Unit tests for Plot capabilities.
Tests the individual capability modules.
"""
import pytest
import sys
import os
import tempfile
import pandas as pd
from pathlib import Path

# Add src to path using relative path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from src.implementation.plot_capabilities import (
    load_data,
    get_data_info,
    create_line_plot,
    create_bar_plot,
    create_scatter_plot,
    create_histogram,
    create_heatmap
)


@pytest.fixture
def sample_data():
    """Create sample data for testing."""
    data = {
        'x': [1, 2, 3, 4, 5, 6, 7, 8, 9, 10],
        'y': [2, 4, 6, 8, 10, 12, 14, 16, 18, 20],
        'category': ['A', 'B', 'A', 'B', 'A', 'B', 'A', 'B', 'A', 'B'],
        'value': [10, 20, 30, 40, 50, 60, 70, 80, 90, 100],
        'random': [15, 25, 35, 23, 45, 33, 55, 67, 78, 89]
    }
    return pd.DataFrame(data)


@pytest.fixture
def sample_csv_file(sample_data):
    """Create a temporary CSV file for testing."""
    with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False) as f:
        sample_data.to_csv(f.name, index=False)
        yield f.name
    
    # Cleanup
    os.unlink(f.name)


@pytest.fixture
def output_dir():
    """Create a temporary directory for output files."""
    with tempfile.TemporaryDirectory() as temp_dir:
        yield temp_dir


def test_load_data_csv(sample_csv_file):
    """Test loading data from CSV file."""
    print("\n=== Testing Load Data CSV ===")
    df = load_data(sample_csv_file)
    print("Data shape:", df.shape)
    print("Columns:", df.columns.tolist())
    
    assert df.shape == (10, 5)
    assert 'x' in df.columns
    assert 'y' in df.columns
    assert 'category' in df.columns
    assert 'value' in df.columns
    assert 'random' in df.columns


def test_load_data_invalid_file():
    """Test loading data from invalid file."""
    print("\n=== Testing Load Data Invalid File ===")
    with pytest.raises(FileNotFoundError):
        load_data("nonexistent_file.csv")


def test_get_data_info_success(sample_csv_file):
    """Test getting data information successfully."""
    print("\n=== Testing Get Data Info Success ===")
    result = get_data_info(sample_csv_file)
    print("Data info result:", result)
    
    assert result["status"] == "success"
    assert result["shape"] == (10, 5)
    assert "x" in result["columns"]
    assert "y" in result["columns"]
    assert "category" in result["columns"]
    assert "value" in result["columns"]
    assert "random" in result["columns"]
    assert "dtypes" in result
    assert "null_counts" in result


def test_get_data_info_error():
    """Test getting data information with error."""
    print("\n=== Testing Get Data Info Error ===")
    result = get_data_info("nonexistent_file.csv")
    print("Error result:", result)
    
    assert result["status"] == "error"
    assert "error" in result


def test_create_line_plot_success(sample_csv_file, output_dir):
    """Test creating line plot successfully."""
    print("\n=== Testing Create Line Plot Success ===")
    output_path = os.path.join(output_dir, "test_line_plot.png")
    
    result = create_line_plot(sample_csv_file, "x", "y", "Test Line Plot", output_path)
    print("Line plot result:", result)
    
    assert result["status"] == "success"
    assert result["plot_type"] == "line"
    assert result["x_column"] == "x"
    assert result["y_column"] == "y"
    assert result["title"] == "Test Line Plot"
    assert result["data_points"] == 10
    assert os.path.exists(output_path)


def test_create_line_plot_invalid_column(sample_csv_file, output_dir):
    """Test creating line plot with invalid column."""
    print("\n=== Testing Create Line Plot Invalid Column ===")
    output_path = os.path.join(output_dir, "test_line_plot_error.png")
    
    result = create_line_plot(sample_csv_file, "invalid_column", "y", "Test Line Plot", output_path)
    print("Error result:", result)
    
    assert result["status"] == "error"
    assert "error" in result


def test_create_bar_plot_success(sample_csv_file, output_dir):
    """Test creating bar plot successfully."""
    print("\n=== Testing Create Bar Plot Success ===")
    output_path = os.path.join(output_dir, "test_bar_plot.png")
    
    result = create_bar_plot(sample_csv_file, "category", "value", "Test Bar Plot", output_path)
    print("Bar plot result:", result)
    
    assert result["status"] == "success"
    assert result["plot_type"] == "bar"
    assert result["x_column"] == "category"
    assert result["y_column"] == "value"
    assert result["title"] == "Test Bar Plot"
    assert result["data_points"] == 10
    assert os.path.exists(output_path)


def test_create_scatter_plot_success(sample_csv_file, output_dir):
    """Test creating scatter plot successfully."""
    print("\n=== Testing Create Scatter Plot Success ===")
    output_path = os.path.join(output_dir, "test_scatter_plot.png")
    
    result = create_scatter_plot(sample_csv_file, "x", "random", "Test Scatter Plot", output_path)
    print("Scatter plot result:", result)
    
    assert result["status"] == "success"
    assert result["plot_type"] == "scatter"
    assert result["x_column"] == "x"
    assert result["y_column"] == "random"
    assert result["title"] == "Test Scatter Plot"
    assert result["data_points"] == 10
    assert os.path.exists(output_path)


def test_create_histogram_success(sample_csv_file, output_dir):
    """Test creating histogram successfully."""
    print("\n=== Testing Create Histogram Success ===")
    output_path = os.path.join(output_dir, "test_histogram.png")
    
    result = create_histogram(sample_csv_file, "value", 10, "Test Histogram", output_path)
    print("Histogram result:", result)
    
    assert result["status"] == "success"
    assert result["plot_type"] == "histogram"
    assert result["column"] == "value"
    assert result["bins"] == 10
    assert result["title"] == "Test Histogram"
    assert result["data_points"] == 10
    assert os.path.exists(output_path)


def test_create_heatmap_success(sample_csv_file, output_dir):
    """Test creating heatmap successfully."""
    print("\n=== Testing Create Heatmap Success ===")
    output_path = os.path.join(output_dir, "test_heatmap.png")
    
    result = create_heatmap(sample_csv_file, "Test Heatmap", output_path)
    print("Heatmap result:", result)
    
    assert result["status"] == "success"
    assert result["plot_type"] == "heatmap"
    assert result["title"] == "Test Heatmap"
    assert result["data_points"] == 10
    assert "numeric_columns" in result
    assert os.path.exists(output_path)


def test_create_heatmap_no_numeric_columns():
    """Test creating heatmap with no numeric columns."""
    print("\n=== Testing Create Heatmap No Numeric Columns ===")
    
    # Create data with only categorical columns
    data = {'category1': ['A', 'B', 'C'], 'category2': ['X', 'Y', 'Z']}
    df = pd.DataFrame(data)
    
    with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False) as f:
        df.to_csv(f.name, index=False)
        csv_file = f.name
    
    try:
        result = create_heatmap(csv_file, "Test Heatmap", "test_heatmap.png")
        print("Error result:", result)
        
        assert result["status"] == "error"
        assert "error" in result
    finally:
        os.unlink(csv_file)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
