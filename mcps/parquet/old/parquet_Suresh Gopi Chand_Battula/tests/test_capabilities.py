# test_capabilities file
import pytest
from src.capabilities.hdf5_handler import HDF5Handler
from src.capabilities.parquet_handler import ParquetHandler
from src.capabilities.pandas_handler import PandasHandler
from src.capabilities.parallel_sort import ParallelSortHandler
from src.capabilities.compression import CompressionHandler
from src.capabilities.visualization import VisualizationHandler

@pytest.mark.asyncio
async def test_hdf5_handler_find_files():
    """Test HDF5 handler find_files operation."""
    handler = HDF5Handler()
    result = await handler.find_files({"directory": "/test/data", "pattern": "*.hdf5"})
    
    assert "files" in result
    assert isinstance(result["files"], list)
    assert len(result["files"]) > 0
    assert "count" in result
    assert result["count"] == len(result["files"])
    assert "directory" in result
    assert "pattern" in result

@pytest.mark.asyncio
async def test_parquet_handler_read_column():
    """Test Parquet handler read_column operation."""
    handler = ParquetHandler()
    result = await handler.read_column({"file_path": "test.parquet", "column_name": "test_column"})
    
    assert "column_name" in result
    assert "file_path" in result
    assert "data" in result
    assert isinstance(result["data"], list)
    assert "count" in result
    assert result["count"] == len(result["data"])

@pytest.mark.asyncio
async def test_pandas_handler_filter_data():
    """Test Pandas handler filter_data operation."""
    handler = PandasHandler()
    result = await handler.filter_data({
        "file_path": "test.csv", 
        "column": "value", 
        "operator": ">", 
        "value": 50
    })
    
    assert "file_path" in result
    assert "filter_condition" in result
    assert "filtered_data" in result
    assert isinstance(result["filtered_data"], list)
    assert "row_count" in result
    assert result["row_count"] == len(result["filtered_data"])

@pytest.mark.asyncio
async def test_parallel_sort_handler():
    """Test ParallelSort handler."""
    handler = ParallelSortHandler()
    result = await handler.sort_by_timestamp("test_log.txt", {
        "output_path": "test_log_sorted.txt",
        "timestamp_format": "%Y-%m-%d %H:%M:%S"
    })
    
    assert "input_file" in result
    assert "output_file" in result
    assert "status" in result
    assert result["status"] == "completed"
    assert "lines_processed" in result
    assert "execution_time_seconds" in result

@pytest.mark.asyncio
async def test_compression_handler_compress():
    """Test Compression handler compress operation."""
    handler = CompressionHandler()
    result = await handler.compress_file("test.log", {"format": "gzip"})
    
    assert "input_file" in result
    assert "output_file" in result
    assert "format" in result
    assert "original_size_bytes" in result
    assert "compressed_size_bytes" in result
    assert "compression_ratio" in result

@pytest.mark.asyncio
async def test_compression_handler_decompress():
    """Test Compression handler decompress operation."""
    handler = CompressionHandler()
    result = await handler.decompress_file("test.log.gzip", {"format": "gzip"})
    
    assert "input_file" in result
    assert "output_file" in result
    assert "format" in result
    assert "decompressed_size_bytes" in result
    assert "status" in result
    assert result["status"] == "completed"

@pytest.mark.asyncio
async def test_visualization_handler():
    """Test Visualization handler."""
    handler = VisualizationHandler()
    result = await handler.plot_data("test.csv", {
        "column_x": "A",
        "column_y": "B",
        "output_path": "test_plot.png"
    })
    
    assert "input_file" in result
    assert "output_file" in result
    assert "columns_plotted" in result
    assert len(result["columns_plotted"]) == 2
    assert "status" in result
    assert result["status"] == "completed"

