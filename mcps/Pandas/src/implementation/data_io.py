"""
Data I/O capabilities for loading and saving data in various formats.
"""
import pandas as pd
import numpy as np
import os
from typing import Optional, List, Any, Dict
import traceback


def load_data_file(file_path: str, file_format: Optional[str] = None,
                   sheet_name: Optional[str] = None, encoding: Optional[str] = None,
                   columns: Optional[List[str]] = None, nrows: Optional[int] = None) -> dict:
    """
    Load data from various file formats.
    
    Args:
        file_path: Path to the data file
        file_format: File format (csv, excel, json, parquet, hdf5)
        sheet_name: Sheet name for Excel files
        encoding: File encoding
        columns: Specific columns to load
        nrows: Number of rows to load
    
    Returns:
        Dictionary with loaded data and metadata
    """
    try:
        if not os.path.exists(file_path):
            return {
                "success": False,
                "error": f"File not found: {file_path}",
                "error_type": "FileNotFoundError"
            }
        
        # Auto-detect file format if not provided
        if file_format is None:
            file_extension = os.path.splitext(file_path)[1].lower()
            format_map = {
                '.csv': 'csv',
                '.xlsx': 'excel',
                '.xls': 'excel',
                '.json': 'json',
                '.parquet': 'parquet',
                '.h5': 'hdf5',
                '.hdf5': 'hdf5'
            }
            file_format = format_map.get(file_extension, 'csv')
        
        # Load data based on format
        if file_format == 'csv':
            df = pd.read_csv(file_path, encoding=encoding, usecols=columns, nrows=nrows)
        elif file_format == 'excel':
            df = pd.read_excel(file_path, sheet_name=sheet_name, usecols=columns, nrows=nrows)
            # Handle case where multiple sheets are read (returns dict)
            if isinstance(df, dict):
                # If no sheet_name specified, use the first sheet
                if sheet_name is None:
                    df = list(df.values())[0]
                else:
                    df = df[sheet_name]
        elif file_format == 'json':
            df = pd.read_json(file_path, encoding=encoding, nrows=nrows)
            if columns:
                df = df[columns]
        elif file_format == 'parquet':
            df = pd.read_parquet(file_path, columns=columns)
            if nrows:
                df = df.head(nrows)
        elif file_format == 'hdf5':
            df = pd.read_hdf(file_path, key='data', columns=columns)
            if nrows:
                df = df.head(nrows)
        else:
            return {
                "success": False,
                "error": f"Unsupported file format: {file_format}",
                "error_type": "ValueError"
            }
        
        # Convert data to JSON-serializable format
        data_dict = df.to_dict('records')
        
        # Convert numpy types to Python native types for JSON serialization
        for record in data_dict:
            for key, value in record.items():
                if pd.isna(value):
                    record[key] = None
                elif hasattr(value, 'dtype'):
                    if 'int' in str(value.dtype):
                        record[key] = int(value)
                    elif 'float' in str(value.dtype):
                        record[key] = float(value)
                    elif 'bool' in str(value.dtype):
                        record[key] = bool(value)
                    else:
                        record[key] = str(value)
        
        # Get basic info
        info = {
            "shape": df.shape,
            "columns": df.columns.tolist(),
            "dtypes": df.dtypes.astype(str).to_dict(),
            "memory_usage": int(df.memory_usage(deep=True).sum()),
            "missing_values": {k: int(v) for k, v in df.isnull().sum().to_dict().items()}
        }
        
        return {
            "success": True,
            "file_path": file_path,
            "file_format": file_format,
            "data": data_dict[:100] if len(data_dict) > 100 else data_dict,  # Limit to first 100 rows
            "total_rows": len(data_dict),
            "info": info,
            "message": f"Successfully loaded {len(data_dict)} rows from {file_path}"
        }
        
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "error_type": type(e).__name__,
            "traceback": traceback.format_exc()
        }


def save_data_file(data: dict, file_path: str, file_format: Optional[str] = None,
                   index: bool = True) -> dict:
    """
    Save data to various file formats.
    
    Args:
        data: Data dictionary to save
        file_path: Path to save the file
        file_format: File format (csv, excel, json, parquet, hdf5)
        index: Whether to include index in saved file
    
    Returns:
        Dictionary with save results
    """
    try:
        # Convert data to DataFrame
        if isinstance(data, dict):
            if 'data' in data:
                df = pd.DataFrame(data['data'])
            else:
                df = pd.DataFrame(data)
        else:
            df = pd.DataFrame(data)
        
        # Auto-detect file format if not provided
        if file_format is None:
            file_extension = os.path.splitext(file_path)[1].lower()
            format_map = {
                '.csv': 'csv',
                '.xlsx': 'excel',
                '.xls': 'excel',
                '.json': 'json',
                '.parquet': 'parquet',
                '.h5': 'hdf5',
                '.hdf5': 'hdf5'
            }
            file_format = format_map.get(file_extension, 'csv')
        
        # Create directory if it doesn't exist
        os.makedirs(os.path.dirname(file_path), exist_ok=True)
        
        # Save data based on format
        if file_format == 'csv':
            df.to_csv(file_path, index=index)
        elif file_format == 'excel':
            df.to_excel(file_path, index=index)
        elif file_format == 'json':
            df.to_json(file_path, orient='records', indent=2)
        elif file_format == 'parquet':
            df.to_parquet(file_path, index=index)
        elif file_format == 'hdf5':
            df.to_hdf(file_path, key='data', mode='w', index=index)
        else:
            return {
                "success": False,
                "error": f"Unsupported file format: {file_format}",
                "error_type": "ValueError"
            }
        
        # Get file size
        file_size = os.path.getsize(file_path)
        
        return {
            "success": True,
            "file_path": file_path,
            "file_format": file_format,
            "file_size_bytes": file_size,
            "file_size_mb": round(file_size / (1024 * 1024), 2),
            "rows_saved": len(df),
            "columns_saved": len(df.columns),
            "message": f"Successfully saved {len(df)} rows to {file_path}"
        }
        
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "error_type": type(e).__name__,
            "traceback": traceback.format_exc()
        }


def get_file_info(file_path: str) -> dict:
    """
    Get information about a data file without loading it.
    
    Args:
        file_path: Path to the data file
    
    Returns:
        Dictionary with file information
    """
    try:
        if not os.path.exists(file_path):
            return {
                "success": False,
                "error": f"File not found: {file_path}",
                "error_type": "FileNotFoundError"
            }
        
        # Get file stats
        file_stats = os.stat(file_path)
        file_size = file_stats.st_size
        
        # Auto-detect file format
        file_extension = os.path.splitext(file_path)[1].lower()
        format_map = {
            '.csv': 'csv',
            '.xlsx': 'excel',
            '.xls': 'excel',
            '.json': 'json',
            '.parquet': 'parquet',
            '.h5': 'hdf5',
            '.hdf5': 'hdf5'
        }
        file_format = format_map.get(file_extension, 'unknown')
        
        # Try to get basic info without loading full file
        info = {
            "file_path": file_path,
            "file_format": file_format,
            "file_size_bytes": file_size,
            "file_size_mb": round(file_size / (1024 * 1024), 2),
            "modified_time": file_stats.st_mtime
        }
        
        # Try to get more detailed info for specific formats
        if file_format == 'csv':
            # Count lines for CSV
            with open(file_path, 'r', encoding='utf-8') as f:
                line_count = sum(1 for _ in f)
            info["estimated_rows"] = line_count - 1  # Subtract header
            
            # Get column names
            df_sample = pd.read_csv(file_path, nrows=0)
            info["columns"] = df_sample.columns.tolist()
            info["column_count"] = len(df_sample.columns)
            
        elif file_format == 'parquet':
            # Get parquet metadata
            import pyarrow.parquet as pq
            parquet_file = pq.ParquetFile(file_path)
            info["rows"] = parquet_file.metadata.num_rows
            info["columns"] = parquet_file.schema.names
            info["column_count"] = len(parquet_file.schema.names)
        
        return {
            "success": True,
            **info
        }
        
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "error_type": type(e).__name__,
            "traceback": traceback.format_exc()
        }
