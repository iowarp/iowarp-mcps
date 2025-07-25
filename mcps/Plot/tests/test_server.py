"""
Unit tests for Plot MCP server.
Tests the FastMCP server integration.
"""
import pytest
import sys
import os
import tempfile
import pandas as pd
import asyncio
from pathlib import Path

# Add src to path using relative path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from src.implementation.plot_capabilities import (
    create_line_plot,
    create_bar_plot,
    create_scatter_plot,
    create_histogram,
    create_heatmap,
    get_data_info
)


@pytest.fixture
def sample_data():
    """Create sample data for testing."""
    data = {
        'date': pd.date_range('2024-01-01', periods=30, freq='D'),
        'sales': [100 + i * 5 for i in range(30)],
        'profit': [20 + i * 2 for i in range(30)],
        'region': ['North', 'South', 'East', 'West'] * 7 + ['North', 'South']
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



def test_get_data_info_success(sample_csv_file):
    """Test get_data_info with valid file."""
    print("\n=== Testing Data Info Tool Success ===")
    result = get_data_info(sample_csv_file)
    print("Tool result:", result)
    
    assert result["status"] == "success"
    assert result["shape"] == (30, 4)
    assert "date" in result["columns"]
    assert "sales" in result["columns"]
    assert "profit" in result["columns"]
    assert "region" in result["columns"]



def test_get_data_info_error():
    """Test get_data_info with invalid file."""
    print("\n=== Testing Data Info Tool Error ===")
    result = get_data_info("nonexistent_file.csv")
    print("Error result:", result)
    
    assert result["status"] == "error"
    assert "error" in result



def test_create_line_plot_success(sample_csv_file, output_dir):
    """Test create_line_plot with valid parameters."""
    print("\n=== Testing Create Line Plot Tool Success ===")
    output_path = os.path.join(output_dir, "tool_line_plot.png")
    
    result = create_line_plot(
        sample_csv_file, "date", "sales", "Sales Over Time", output_path
    )
    print("Tool result:", result)
    
    assert result["status"] == "success"
    assert result["x_column"] == "date"
    assert result["y_column"] == "sales"
    assert result["title"] == "Sales Over Time"
    assert result["data_points"] == 30
    assert os.path.exists(output_path)



def test_create_line_plot_default_params(sample_csv_file):
    """Test create_line_plot with default parameters."""
    print("\n=== Testing Create Line Plot Tool Default Params ===")
    
    result = create_line_plot(sample_csv_file, "date", "sales")
    print("Tool result:", result)
    
    assert result["status"] == "success"
    assert result["x_column"] == "date"
    assert result["y_column"] == "sales"
    assert result["title"] == "Line Plot"
    assert result["output_path"] == "line_plot.png"
    assert result["data_points"] == 30
    
    # Cleanup
    if os.path.exists("line_plot.png"):
        os.unlink("line_plot.png")



def test_create_bar_plot_success(sample_csv_file, output_dir):
    """Test create_bar_plot with valid parameters."""
    print("\n=== Testing Create Bar Plot Tool Success ===")
    output_path = os.path.join(output_dir, "tool_bar_plot.png")
    
    result = create_bar_plot(
        sample_csv_file, "region", "sales", "Sales by Region", output_path
    )
    print("Tool result:", result)
    
    assert result["status"] == "success"
    assert result["x_column"] == "region"
    assert result["y_column"] == "sales"
    assert result["title"] == "Sales by Region"
    assert result["data_points"] == 30
    assert os.path.exists(output_path)



def test_create_scatter_plot_success(sample_csv_file, output_dir):
    """Test create_scatter_plot with valid parameters."""
    print("\n=== Testing Create Scatter Plot Tool Success ===")
    output_path = os.path.join(output_dir, "tool_scatter_plot.png")
    
    result = create_scatter_plot(
        sample_csv_file, "sales", "profit", "Sales vs Profit", output_path
    )
    print("Tool result:", result)
    
    assert result["status"] == "success"
    assert result["x_column"] == "sales"
    assert result["y_column"] == "profit"
    assert result["title"] == "Sales vs Profit"
    assert result["data_points"] == 30
    assert os.path.exists(output_path)



def test_create_histogram_success(sample_csv_file, output_dir):
    """Test create_histogram with valid parameters."""
    print("\n=== Testing Create Histogram Tool Success ===")
    output_path = os.path.join(output_dir, "tool_histogram.png")
    
    result = create_histogram(
        sample_csv_file, "sales", 20, "Sales Distribution", output_path
    )
    print("Tool result:", result)
    
    assert result["status"] == "success"
    assert result["column"] == "sales"
    assert result["bins"] == 20
    assert result["title"] == "Sales Distribution"
    assert result["data_points"] == 30
    assert os.path.exists(output_path)



def test_create_histogram_default_bins(sample_csv_file, output_dir):
    """Test create_histogram with default bins parameter."""
    print("\n=== Testing Create Histogram Tool Default Bins ===")
    output_path = os.path.join(output_dir, "tool_histogram_default.png")
    
    result = create_histogram(
        sample_csv_file, "sales", title="Sales Distribution", output_path=output_path
    )
    print("Tool result:", result)
    
    assert result["status"] == "success"
    assert result["column"] == "sales"
    assert result["bins"] == 30  # Default value
    assert result["title"] == "Sales Distribution"
    assert result["data_points"] == 30
    assert os.path.exists(output_path)



def test_create_heatmap_success(sample_csv_file, output_dir):
    """Test create_heatmap with valid parameters."""
    print("\n=== Testing Create Heatmap Tool Success ===")
    output_path = os.path.join(output_dir, "tool_heatmap.png")
    
    result = create_heatmap(
        sample_csv_file, "Sales Data Correlation", output_path
    )
    print("Tool result:", result)
    
    assert result["status"] == "success"
    assert result["title"] == "Sales Data Correlation"
    assert result["data_points"] == 30
    assert "numeric_columns" in result
    assert os.path.exists(output_path)



def test_create_heatmap_default_params(sample_csv_file):
    """Test create_heatmap with default parameters."""
    print("\n=== Testing Create Heatmap Tool Default Params ===")
    
    result = create_heatmap(sample_csv_file)
    print("Tool result:", result)
    
    assert result["status"] == "success"
    assert result["title"] == "Heatmap"
    assert result["output_path"] == "heatmap.png"
    assert result["data_points"] == 30
    
    # Cleanup
    if os.path.exists("heatmap.png"):
        os.unlink("heatmap.png")



def test_handler_error_handling():
    """Test error handling in tools."""
    print("\n=== Testing Tool Error Handling ===")
    
    # Test with non-existent file
    result = create_line_plot("nonexistent_file.csv", "x", "y")
    assert result["status"] == "error"
    assert "error" in result
    
    # Test with invalid column
    with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False) as f:
        data = {'a': [1, 2, 3], 'b': [4, 5, 6]}
        df = pd.DataFrame(data)
        df.to_csv(f.name, index=False)
        csv_file = f.name
    
    try:
        result = create_line_plot(csv_file, "invalid_column", "b")
        assert result["status"] == "error"
        assert "error" in result
    finally:
        os.unlink(csv_file)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
