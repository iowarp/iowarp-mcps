"""Base utilities for compression capabilities."""

import gzip
import os
import shutil
import logging

logger = logging.getLogger(__name__)


async def compress_file(file_path: str) -> dict:
    """Compress a file using gzip compression.

    Args:
        file_path: Path to the file to compress

    Returns:
        Dictionary containing compression results

    Raises:
        FileNotFoundError: If the file does not exist
        PermissionError: If access is denied
    """
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"File not found: {file_path}")

    output_path = file_path + ".gz"
    original_size = os.path.getsize(file_path)

    with open(file_path, "rb") as f_in:
        with gzip.open(output_path, "wb") as f_out:
            shutil.copyfileobj(f_in, f_out)

    compressed_size = os.path.getsize(output_path)

    if original_size == 0:
        compression_ratio = 0.0
    else:
        compression_ratio = (1 - (compressed_size / original_size)) * 100

    logger.info(
        f"Successfully compressed {file_path} with {compression_ratio:.2f}% reduction"
    )

    return {
        "original_file": file_path,
        "compressed_file": output_path,
        "original_size": original_size,
        "compressed_size": compressed_size,
        "compression_ratio": round(compression_ratio, 2),
        "message": (
            f"Compressed {os.path.basename(file_path)}: "
            f"{original_size:,} → {compressed_size:,} bytes "
            f"({compression_ratio:.1f}% reduction)"
        ),
    }


async def decompress_file(file_path: str) -> dict:
    """Decompress a gzip-compressed file.

    Args:
        file_path: Path to the .gz file to decompress

    Returns:
        Dictionary containing decompression results

    Raises:
        FileNotFoundError: If the file does not exist
        ValueError: If the file is not a .gz file
        PermissionError: If access is denied
    """
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"File not found: {file_path}")

    if not file_path.endswith(".gz"):
        raise ValueError(f"Not a gzip file (expected .gz extension): {file_path}")

    output_path = file_path[:-3]  # Remove .gz extension
    compressed_size = os.path.getsize(file_path)

    with gzip.open(file_path, "rb") as f_in:
        with open(output_path, "wb") as f_out:
            shutil.copyfileobj(f_in, f_out)

    decompressed_size = os.path.getsize(output_path)

    logger.info(f"Successfully decompressed {file_path}")

    return {
        "compressed_file": file_path,
        "decompressed_file": output_path,
        "compressed_size": compressed_size,
        "decompressed_size": decompressed_size,
        "message": (
            f"Decompressed {os.path.basename(file_path)}: "
            f"{compressed_size:,} → {decompressed_size:,} bytes"
        ),
    }
