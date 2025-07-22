"""
Base utilities for compression capabilities.
"""
import gzip
import os
import shutil
from typing import Dict, Any
import logging

logger = logging.getLogger(__name__)


async def compress_file(file_path: str) -> Dict[str, Any]:
    """
    Compress a file using gzip compression.
    
    Args:
        file_path: Path to the file to compress
        
    Returns:
        Dictionary containing compression results
    """
    try:
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"File not found: {file_path}")
        
        output_path = file_path + '.gz'
        
        # Get original file size
        original_size = os.path.getsize(file_path)
        
        # Compress the file
        with open(file_path, 'rb') as f_in:
            with gzip.open(output_path, 'wb') as f_out:
                shutil.copyfileobj(f_in, f_out)
        
        # Get compressed file size
        compressed_size = os.path.getsize(output_path)
        
        # Calculate compression ratio
        if original_size == 0:
            compression_ratio = 0.0
        else:
            compression_ratio = (1 - (compressed_size / original_size)) * 100
        
        logger.info(f"Successfully compressed {file_path} with {compression_ratio:.2f}% reduction")
        
        return {
            "content": [{
                "text": f"File compressed successfully!\n\nOriginal file: {file_path}\nCompressed file: {output_path}\nOriginal size: {original_size:,} bytes\nCompressed size: {compressed_size:,} bytes\nCompression ratio: {compression_ratio:.2f}%"
            }],
            "_meta": {
                "tool": "compress_file",
                "original_file": file_path,
                "compressed_file": output_path,
                "original_size": original_size,
                "compressed_size": compressed_size,
                "compression_ratio": compression_ratio
            },
            "isError": False
        }
        
    except FileNotFoundError as e:
        logger.error(f"File not found: {str(e)}")
        raise Exception(f"File not found: {str(e)}")
    except PermissionError as e:
        logger.error(f"Permission denied: {str(e)}")
        raise Exception(f"Permission denied: {str(e)}")
    except Exception as e:
        logger.error(f"Compression failed: {str(e)}")
        raise Exception(f"Compression failed: {str(e)}")