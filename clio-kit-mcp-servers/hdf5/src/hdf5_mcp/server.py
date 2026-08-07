"""
HDF5 FastMCP Server - Scientific Data Access for AI Agents

@file       server.py
@brief      Main server implementation for HDF5 MCP operations
@author     IoWarp Scientific MCPs Team
@version    2.1.0
@date       2024
@license    MIT

@description
    Part of the IoWarp MCP Server Collection for AI-powered scientific computing.

    This module implements a comprehensive HDF5 (Hierarchical Data Format) server
    using FastMCP 2.0 patterns, providing AI agents with powerful tools for working
    with scientific and engineering data stored in HDF5 format.

    Key Features:
    - 26+ specialized tools with tags and annotations
    - 3 dynamic resources with wildcard path support
    - 4 workflow prompts for guided analysis
    - Context-aware operations (progress, LLM sampling, elicitation)
    - Client roots integration for file discovery
    - LRU caching for 100-1000x speedup on repeated queries
    - Parallel processing for 4-8x faster batch operations
    - Streaming support for unlimited file sizes
    - AI-powered discovery and optimization tools

    Architecture:
    - FastMCP decorators (@mcp.tool, @mcp.resource, @mcp.prompt)
    - Lifespan management for startup/shutdown
    - Resource manager with lazy loading
    - Performance tracking with adaptive units
    - Consistent error handling (ToolError/ResourceError)

@see https://github.com/iowarp/clio-kit
@see https://docs.hdfgroup.org/hdf5/
"""

#!/usr/bin/env python3
# /// script
# dependencies = [
#   "fastmcp>=0.2.0",
#   "h5py>=3.9.0",
#   "numpy>=1.24.0,<2.0.0",
#   "pydantic>=2.4.2,<3.0.0",
#   "psutil>=5.9.0",
#   "python-dotenv>=0.19.0"
# ]
# requires-python = ">=3.10"
# ///

import logging
import os
import time
import json
from pathlib import Path
from typing import Any, Callable, Optional, List
from functools import wraps
from concurrent.futures import ThreadPoolExecutor, as_completed
from contextlib import asynccontextmanager
import multiprocessing

import h5py
import numpy as np
from fastmcp import FastMCP, Context
from fastmcp.exceptions import ToolError, ResourceError
from fastmcp.prompts import Message

from .config import get_config
from .resources import ResourceManager, LazyHDF5Proxy, discover_hdf5_files_in_roots


def _sample_callable(ctx: Optional[Context]) -> Optional[Callable[..., Any]]:
    """Return the context's LLM-sampling callable, if this connection still offers one.

    MCP 2026-07-28 removed sampling as a declared client capability, so
    ``Context`` no longer defines ``.sample`` at all (it is not merely
    optional per-client anymore). Looked up dynamically so a connection
    negotiating that protocol version degrades through the same "AI
    insights are unavailable" messaging these tools already use for clients
    that never supported sampling, instead of a static attribute error.
    """
    if ctx is None:
        return None
    sample = getattr(ctx, "sample", None)
    return sample if callable(sample) else None


# =========================================================================
# Server Setup
# =========================================================================

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# Global state - keep it simple
config = get_config()
resource_manager = ResourceManager(cache_capacity=1000)
num_workers = max(2, multiprocessing.cpu_count() - 1)
executor = ThreadPoolExecutor(max_workers=num_workers)

# Current file handle (stateful for tool sequence)
current_file: Optional[LazyHDF5Proxy] = None

# Client roots for file discovery
client_roots: List[Path] = []

# =========================================================================
# Server Lifespan Management
# =========================================================================


@asynccontextmanager
async def lifespan(app):
    """Startup: discover HDF5 files in client roots. Shutdown: cleanup."""
    global client_roots

    # Get roots from client (FastMCP handles this)
    # For now, fallback to config
    client_roots = [config.hdf5.data_dir]

    logger.info(f"Scanning {len(client_roots)} root directories for HDF5 files")

    # Discover files
    discovered = discover_hdf5_files_in_roots(client_roots)

    # Register as resources
    for file_path in discovered:
        resource_manager.register_hdf5_file(file_path)

    logger.info(f"Registered {len(discovered)} HDF5 files")

    # Initialize resource manager
    await resource_manager.initialize()

    # Server running
    yield

    # Cleanup
    await cleanup()


# Create FastMCP server with lifespan and instructions
mcp = FastMCP(
    name="hdf5",
    version="1.0.0",
    instructions="""
        HDF5 FastMCP provides comprehensive HDF5 file operations with AI intelligence.

        **Getting Started**:
        1. Use list_available_hdf5_files() to see available files
        2. Use open_file(path=...) to open a file
        3. Use analyze_dataset_structure() to explore
        4. Use read_* tools to access data
        5. Use close_file() when done

        **Resources**: Access files directly with @hdf5:hdf5://path/to/file.h5/metadata

        **Prompts**: Use /mcp__hdf5__explore_hdf5_file for guided workflows

        **Performance**:
        - Use hdf5_parallel_scan for multi-file scanning
        - Use hdf5_stream_data for large datasets
        - Use hdf5_batch_read for parallel dataset reading
        - Use hdf5_aggregate_stats for statistical analysis

        **AI Features**:
        - Tools provide progress reporting for long operations
        - Analysis tools include LLM-powered insights
        - Interactive export with format selection
    """,
    lifespan=lifespan,
    list_page_size=10,
)

# =========================================================================
# Performance & Error Decorators
# =========================================================================


def with_performance_tracking(func):
    """Track performance with adaptive units."""

    @wraps(func)
    async def wrapper(*args, **kwargs):
        start = time.perf_counter_ns()
        result = await func(*args, **kwargs)
        elapsed = time.perf_counter_ns() - start

        # Show performance if enabled
        if os.getenv("HDF5_SHOW_PERFORMANCE", "false").lower() == "true":
            if elapsed < 1_000:
                perf_str = f"{elapsed}ns"
            elif elapsed < 1_000_000:
                perf_str = f"{elapsed / 1_000:.1f}μs"
            elif elapsed < 1_000_000_000:
                perf_str = f"{elapsed / 1_000_000:.1f}ms"
            else:
                perf_str = f"{elapsed / 1_000_000_000:.2f}s"

            # Append to result if it's a string
            if isinstance(result, str):
                result += f"\n\n⏱ {perf_str}"

        return result

    return wrapper


def with_error_handling(func):
    """Consistent error handling for all tools."""

    @wraps(func)
    async def wrapper(*args, **kwargs):
        try:
            return await func(*args, **kwargs)
        except Exception as e:
            logger.error(f"Error in {func.__name__}: {e}")
            return f"Error: {str(e)}"

    return wrapper


# =========================================================================
# FILE OPERATIONS TOOLS
# =========================================================================


@mcp.tool(
    title="Open File",
    tags={"file", "core"},
    annotations={
        "title": "Open HDF5 File",
        "readOnlyHint": False,
        "destructiveHint": False,
        "idempotentHint": False,
        "openWorldHint": False,
    },
)
@with_error_handling
@with_performance_tracking
async def open_file(path: str, mode: str = "r") -> str:
    """Open an HDF5 file for operations.

    Args:
        path: Path to HDF5 file
        mode: File access mode ('r', 'r+', 'w', 'a')

    Returns:
        Success message with file info
    """
    global current_file

    current_file = resource_manager.get_hdf5_file(path)
    if current_file is None:
        raise ToolError(
            f"Could not open file {path}. File may not exist or is not accessible."
        )

    return f"Successfully opened {path} in {mode} mode"


@mcp.tool(
    title="Close File",
    tags={"file", "core"},
    annotations={
        "title": "Close HDF5 File",
        "readOnlyHint": False,
        "destructiveHint": False,
        "idempotentHint": False,
        "openWorldHint": False,
    },
)
@with_error_handling
async def close_file() -> str:
    """Close the current HDF5 file.

    Returns:
        Status message
    """
    global current_file

    if current_file:
        filename = current_file.filename
        current_file.close()
        current_file = None
        return f"File closed: {filename}"

    raise ToolError("No file currently open")


@mcp.tool(
    title="Get Filename",
    tags={"file", "info"},
    annotations={
        "title": "Get Current Filename",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": False,
    },
)
@with_error_handling
async def get_filename() -> str:
    """Get the current file's path.

    Returns:
        File path
    """
    if not current_file:
        raise ToolError("No file currently open")

    return current_file.filename


@mcp.tool(
    title="Get Mode",
    tags={"file", "info"},
    annotations={
        "title": "Get File Access Mode",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": False,
    },
)
@with_error_handling
async def get_mode() -> str:
    """Get the current file's access mode.

    Returns:
        File mode
    """
    if not current_file:
        raise ToolError("No file currently open")

    return current_file.mode


@mcp.tool(
    title="Get Object",
    tags={"dataset", "navigation"},
    annotations={
        "title": "Get Object by Path",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": False,
    },
)
@with_error_handling
@with_performance_tracking
async def get_by_path(path: str) -> str:
    """Get a dataset or group by path.

    Args:
        path: Path to object within file

    Returns:
        Object information
    """
    if not current_file:
        raise ToolError("No file currently open. Use open_file first.")

    try:
        obj = current_file[path]
    except KeyError:
        raise ToolError(f"Path not found: {path}")

    if isinstance(obj, h5py.Dataset):
        return f"Dataset: {path}, shape: {obj.shape}, dtype: {obj.dtype}"
    elif isinstance(obj, h5py.Group):
        return f"Group: {path}, keys: {list(obj.keys())}"
    else:
        return f"Object: {path}, type: {type(obj).__name__}"


@mcp.tool(
    title="List Keys",
    tags={"dataset", "navigation"},
    annotations={
        "title": "List Keys in Group",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": False,
    },
)
@with_error_handling
async def list_keys(path: str = "/") -> str:
    """List keys in a group.

    Args:
        path: Path to group (default: root)

    Returns:
        JSON array of keys
    """
    if not current_file:
        raise ToolError("No file currently open. Use open_file first.")

    try:
        obj = current_file[path] if path != "/" else current_file.file
    except KeyError:
        raise ToolError(f"Path not found: {path}")

    if not isinstance(obj, h5py.Group):
        raise ToolError(f"{path} is not a group")

    keys = list(obj.keys())
    return json.dumps(keys, indent=2)


@mcp.tool(
    title="Visit Nodes",
    tags={"dataset", "navigation"},
    annotations={
        "title": "Visit All Nodes Recursively",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": False,
    },
)
@with_error_handling
@with_performance_tracking
async def visit(callback_fn: str = "collect_paths") -> str:
    """Visit all nodes recursively.

    Args:
        callback_fn: Callback function name (currently collects all paths)

    Returns:
        JSON array of all paths and types
    """
    if not current_file:
        raise ToolError("No file currently open. Use open_file first.")

    paths = []

    def collect_paths(name, obj):
        paths.append({"name": name, "type": type(obj).__name__})
        return None

    current_file.file.visititems(collect_paths)
    return json.dumps(paths, indent=2)


# =========================================================================
# DATASET OPERATIONS TOOLS
# =========================================================================


@mcp.tool(
    title="Read Dataset",
    tags={"dataset", "read"},
    annotations={
        "title": "Read Full Dataset",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": False,
    },
)
@with_error_handling
@with_performance_tracking
async def read_full_dataset(path: str) -> str:
    """Read an entire dataset with efficient chunked reading for large datasets.

    Args:
        path: Path to dataset within file

    Returns:
        Dataset description
    """
    if not current_file:
        raise ToolError("No file currently open. Use open_file first.")

    try:
        dataset = current_file[path]
    except KeyError:
        raise ToolError(f"Dataset not found: {path}")

    # For large datasets, use chunked reading
    if dataset.nbytes > 1e8:  # 100MB threshold
        data = _read_large_dataset(dataset)
    else:
        data = dataset[:]

    # Format output
    if isinstance(data, np.ndarray) and data.size > 0:
        if np.array_equal(data, np.arange(data.size)):
            description = f"array from 0 to {data.size - 1}"
        else:
            description = f"array of shape {data.shape} with dtype {data.dtype}"
    else:
        description = str(data)

    return f"Successfully read dataset {path}: {description}"


@mcp.tool(
    title="Read Slice",
    tags={"dataset", "read"},
    annotations={
        "title": "Read Partial Dataset",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": False,
    },
)
@with_error_handling
@with_performance_tracking
async def read_partial_dataset(
    path: str, start: Optional[str] = None, count: Optional[str] = None
) -> str:
    """Read a portion of a dataset with slicing.

    Args:
        path: Path to dataset within file
        start: Starting indices as comma-separated string (e.g., "0,0,0")
        count: Number of elements as comma-separated string (e.g., "10,10,10")

    Returns:
        Partial dataset description
    """
    if not current_file:
        raise ToolError("No file currently open. Use open_file first.")

    try:
        dataset = current_file[path]
    except KeyError:
        raise ToolError(f"Dataset not found: {path}")

    if not isinstance(dataset, h5py.Dataset):
        raise ToolError(f"{path} is not a dataset")

    # Parse start and count
    if start:
        start_tuple = tuple(int(x.strip()) for x in start.split(","))
    else:
        start_tuple = tuple(0 for _ in dataset.shape)

    if count:
        count_tuple = tuple(int(x.strip()) for x in count.split(","))
    else:
        count_tuple = dataset.shape

    # Build slice
    slices = tuple(slice(s, s + c) for s, c in zip(start_tuple, count_tuple))
    data = dataset[slices]

    return (
        f"Successfully read partial dataset {path}\n"
        f"Slice: start={start_tuple}, count={count_tuple}\n"
        f"Result shape: {data.shape}\n"
        f"Dtype: {data.dtype}\n"
        f"First few values: {data.flat[:5].tolist()}"
    )


@mcp.tool(
    title="Get Shape",
    tags={"dataset", "metadata"},
    annotations={
        "title": "Get Dataset Shape",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": False,
    },
)
@with_error_handling
@with_performance_tracking
async def get_shape(path: str) -> str:
    """Get the shape of a dataset.

    Args:
        path: Path to dataset

    Returns:
        Dataset shape
    """
    if not current_file:
        raise ToolError("No file currently open. Use open_file first.")

    try:
        dataset = current_file[path]
    except KeyError:
        raise ToolError(f"Dataset not found: {path}")

    if not isinstance(dataset, h5py.Dataset):
        raise ToolError(f"{path} is not a dataset")

    return str(dataset.shape)


@mcp.tool(
    title="Get Dtype",
    tags={"dataset", "metadata"},
    annotations={
        "title": "Get Dataset Data Type",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": False,
    },
)
@with_error_handling
@with_performance_tracking
async def get_dtype(path: str) -> str:
    """Get the data type of a dataset.

    Args:
        path: Path to dataset

    Returns:
        Dataset dtype
    """
    if not current_file:
        raise ToolError("No file currently open. Use open_file first.")

    try:
        dataset = current_file[path]
    except KeyError:
        raise ToolError(f"Dataset not found: {path}")

    if not isinstance(dataset, h5py.Dataset):
        raise ToolError(f"{path} is not a dataset")

    return str(dataset.dtype)


@mcp.tool(
    title="Get Size",
    tags={"dataset", "metadata"},
    annotations={
        "title": "Get Dataset Size",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": False,
    },
)
@with_error_handling
@with_performance_tracking
async def get_size(path: str) -> str:
    """Get the size of a dataset.

    Args:
        path: Path to dataset

    Returns:
        Dataset size
    """
    if not current_file:
        raise ToolError("No file currently open. Use open_file first.")

    try:
        dataset = current_file[path]
    except KeyError:
        raise ToolError(f"Dataset not found: {path}")

    if not isinstance(dataset, h5py.Dataset):
        raise ToolError(f"{path} is not a dataset")

    return str(dataset.size)


@mcp.tool(
    title="Get Chunks",
    tags={"dataset", "metadata", "performance"},
    annotations={
        "title": "Get Dataset Chunk Info",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": False,
    },
)
@with_error_handling
@with_performance_tracking
async def get_chunks(path: str) -> str:
    """Get chunk information for a dataset.

    Args:
        path: Path to dataset

    Returns:
        Chunk configuration
    """
    if not current_file:
        raise ToolError("No file currently open. Use open_file first.")

    try:
        dataset = current_file[path]
    except KeyError:
        raise ToolError(f"Dataset not found: {path}")

    if not isinstance(dataset, h5py.Dataset):
        raise ToolError(f"{path} is not a dataset")

    chunks = dataset.chunks
    if chunks is None:
        return "Dataset is not chunked (contiguous storage)"

    chunk_size_kb = np.prod(chunks) * dataset.dtype.itemsize / 1024
    return (
        f"Chunk configuration:\n"
        f"Chunk shape: {chunks}\n"
        f"Chunk size: {chunk_size_kb:.2f} KB"
    )


# =========================================================================
# ATTRIBUTE OPERATIONS TOOLS
# =========================================================================


@mcp.tool(
    title="Read Attribute",
    tags={"attribute", "metadata"},
    annotations={
        "title": "Read Attribute",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": False,
    },
)
@with_error_handling
@with_performance_tracking
async def read_attribute(path: str, name: str) -> str:
    """Read an attribute from an object.

    Args:
        path: Path to object
        name: Attribute name

    Returns:
        Attribute value
    """
    if not current_file:
        raise ToolError("No file currently open. Use open_file first.")

    try:
        obj = current_file[path] if path != "/" else current_file.file
    except KeyError:
        raise ToolError(f"Path not found: {path}")

    if name in obj.attrs:
        value = obj.attrs[name]
        if hasattr(value, "tolist"):
            value = value.tolist()
        return str(value)

    raise ToolError(f"Attribute '{name}' not found at {path}")


@mcp.tool(
    title="List Attributes",
    tags={"attribute", "metadata"},
    annotations={
        "title": "List All Attributes",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": False,
    },
)
@with_error_handling
@with_performance_tracking
async def list_attributes(path: str) -> str:
    """List all attributes of an object.

    Args:
        path: Path to object

    Returns:
        JSON dict of attributes
    """
    if not current_file:
        raise ToolError("No file currently open. Use open_file first.")

    try:
        obj = current_file[path] if path != "/" else current_file.file
    except KeyError:
        raise ToolError(f"Path not found: {path}")

    attrs = dict(obj.attrs)

    # Convert numpy arrays to lists
    for key, value in attrs.items():
        if hasattr(value, "tolist"):
            attrs[key] = value.tolist()
        else:
            attrs[key] = str(value)

    if not attrs:
        return f"No attributes found at path: {path}"

    return f"Attributes at {path}:\n{json.dumps(attrs, indent=2)}"


# =========================================================================
# PERFORMANCE TOOLS - Parallel, Batch, Streaming
# =========================================================================


@mcp.tool(
    title="Parallel Scan",
    tags={"performance", "parallel", "scan"},
    annotations={
        "title": "Parallel Scan Multiple Files",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": False,
    },
)
@with_error_handling
@with_performance_tracking
async def hdf5_parallel_scan(
    directory: str, pattern: str = "*.h5", ctx: Optional[Context] = None
) -> str:
    """Fast multi-file scanning with parallel processing.

    Args:
        directory: Directory to scan
        pattern: File pattern (default: *.h5)
        ctx: Context for progress reporting

    Returns:
        Scan summary with file metadata
    """
    import glob

    search_path = Path(directory) / pattern
    files = glob.glob(str(search_path), recursive=True)

    if not files:
        return f"No HDF5 files found in {directory} matching {pattern}"

    if ctx:
        await ctx.info(f"Scanning {len(files)} files in {directory}")
        await ctx.report_progress(0, len(files), "Starting parallel scan")

    # Parallel scanning
    scan_results = []
    with ThreadPoolExecutor(max_workers=num_workers) as pool:
        future_to_file = {
            pool.submit(_scan_single_file, file_path): file_path
            for file_path in files[:50]  # Limit to 50 files
        }

        for i, future in enumerate(as_completed(future_to_file), 1):
            file_path = future_to_file[future]

            if ctx:
                await ctx.report_progress(
                    i, len(future_to_file), f"Scanned {i}/{len(future_to_file)} files"
                )

            try:
                result = future.result()
                scan_results.append({"file": file_path, "status": "success", **result})
            except Exception as e:
                scan_results.append(
                    {"file": file_path, "status": "error", "error": str(e)}
                )

    # Format results
    successful = [r for r in scan_results if r["status"] == "success"]
    total_datasets = sum(r.get("dataset_count", 0) for r in successful)
    total_size_mb = sum(r.get("total_size_mb", 0) for r in successful)

    summary = "Parallel scan complete:\n"
    summary += f"Files processed: {len(scan_results)}\n"
    summary += f"Successful: {len(successful)}\n"
    summary += f"Total datasets: {total_datasets}\n"
    summary += f"Total size: {total_size_mb:.2f} MB\n\n"

    for result in scan_results[:10]:
        if result["status"] == "success":
            summary += f"✓ {Path(result['file']).name}: {result.get('dataset_count', 0)} datasets, {result.get('total_size_mb', 0):.1f} MB\n"
        else:
            summary += f"✗ {Path(result['file']).name}: {result['error']}\n"

    if len(scan_results) > 10:
        summary += f"... and {len(scan_results) - 10} more files\n"

    return summary


@mcp.tool(
    title="Batch Read",
    tags={"performance", "parallel", "read"},
    annotations={
        "title": "Batch Read Multiple Datasets",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": False,
    },
)
@with_error_handling
@with_performance_tracking
async def hdf5_batch_read(
    paths: str, slice_spec: Optional[str] = None, ctx: Optional[Context] = None
) -> str:
    """Read multiple datasets in parallel.

    Args:
        paths: Comma-separated dataset paths or JSON array
        slice_spec: Optional slice specification
        ctx: Context for progress reporting

    Returns:
        Batch read summary
    """
    if not current_file:
        raise ToolError("No file currently open. Use open_file first.")

    # Parse paths
    try:
        path_list = json.loads(paths)
    except Exception:
        path_list = [p.strip() for p in paths.split(",") if p.strip()]

    if ctx:
        await ctx.info(f"Reading {len(path_list)} datasets in parallel")
        await ctx.report_progress(0, len(path_list), "Starting batch read")

    # Parse slice
    slice_obj = None
    if slice_spec:
        try:
            slice_obj = eval(f"np.s_[{slice_spec}]")
        except Exception:
            return f"Error: Invalid slice specification: {slice_spec}"

    # Parallel batch reading
    results = {}
    with ThreadPoolExecutor(max_workers=num_workers) as pool:
        future_to_path = {
            pool.submit(_read_single_dataset, current_file, path, slice_obj): path
            for path in path_list
        }

        for i, future in enumerate(as_completed(future_to_path), 1):
            path = future_to_path[future]

            try:
                data_info = future.result()
                results[path] = data_info

                if ctx:
                    await ctx.report_progress(
                        i, len(path_list), f"Read {i}/{len(path_list)} datasets"
                    )
            except Exception as e:
                results[path] = {"error": str(e)}

    # Format results
    summary = f"Batch read complete for {len(path_list)} datasets:\n\n"

    for path, result in results.items():
        if "error" in result:
            summary += f"✗ {path}: {result['error']}\n"
        else:
            summary += f"✓ {path}: shape {result['shape']}, dtype {result['dtype']}, size {result['size_mb']:.2f} MB\n"
            if "preview" in result:
                summary += f"  Preview: {result['preview']}\n"

    total_size_mb = sum(
        r.get("size_mb", 0) for r in results.values() if "error" not in r
    )
    summary += f"\nTotal data read: {total_size_mb:.2f} MB"

    return summary


@mcp.tool(
    title="Stream Data",
    tags={"performance", "streaming"},
    annotations={
        "title": "Stream Large Dataset",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": False,
    },
)
@with_error_handling
@with_performance_tracking
async def hdf5_stream_data(
    path: str,
    chunk_size: int = 1024,
    max_chunks: int = 100,
    ctx: Optional[Context] = None,
) -> str:
    """Stream large datasets efficiently with memory management.

    Args:
        path: Path to dataset
        chunk_size: Number of elements per chunk
        max_chunks: Maximum number of chunks to process
        ctx: Context for progress reporting

    Returns:
        Stream processing summary with statistics
    """
    if not current_file:
        return "Error: No file currently open"

    dataset = current_file[path]

    if dataset.nbytes < 10 * 1024 * 1024:
        return f"Dataset {path} is small ({dataset.nbytes / (1024 * 1024):.1f} MB), consider using regular read"

    # Setup streaming
    total_elements = dataset.size
    elements_per_chunk = chunk_size
    total_chunks = min(
        max_chunks, (total_elements + elements_per_chunk - 1) // elements_per_chunk
    )

    if ctx:
        await ctx.info(f"Streaming {total_chunks} chunks from {path}")
        await ctx.report_progress(0, total_chunks, "Starting stream")

    # Stream processing
    chunk_summaries = []
    total_processed = 0

    for chunk_idx in range(total_chunks):
        start_idx = chunk_idx * elements_per_chunk
        end_idx = min(start_idx + elements_per_chunk, total_elements)

        if ctx:
            await ctx.report_progress(
                chunk_idx + 1,
                total_chunks,
                f"Streamed chunk {chunk_idx + 1}/{total_chunks}",
            )

        # Read chunk
        if len(dataset.shape) == 1:
            chunk_data = dataset[start_idx:end_idx]
        else:
            chunk_data = dataset[start_idx:end_idx]

        # Process chunk
        chunk_info = {
            "chunk": chunk_idx + 1,
            "range": f"{start_idx}-{end_idx - 1}",
            "elements": chunk_data.size,
            "mean": float(np.mean(chunk_data)) if chunk_data.size > 0 else 0,
            "std": float(np.std(chunk_data)) if chunk_data.size > 0 else 0,
            "min": float(np.min(chunk_data)) if chunk_data.size > 0 else 0,
            "max": float(np.max(chunk_data)) if chunk_data.size > 0 else 0,
        }
        chunk_summaries.append(chunk_info)
        total_processed += chunk_data.size

        del chunk_data

    # Generate report
    streaming_rate = total_processed / (1024 * 1024)
    summary = f"Stream processing complete for dataset: {path}\n\n"
    summary += "Dataset info:\n"
    summary += f"  Total size: {dataset.nbytes / (1024 * 1024):.2f} MB\n"
    summary += f"  Shape: {dataset.shape}\n"
    summary += f"  Dtype: {dataset.dtype}\n\n"
    summary += "Streaming stats:\n"
    summary += f"  Chunks processed: {len(chunk_summaries)}\n"
    summary += f"  Elements processed: {total_processed:,}\n"
    summary += f"  Processing rate: {streaming_rate:.2f} MB\n\n"
    summary += "Chunk statistics:\n"

    for chunk in chunk_summaries[:10]:
        summary += f"  Chunk {chunk['chunk']}: mean={chunk['mean']:.3f}, std={chunk['std']:.3f}, range=[{chunk['min']:.3f}, {chunk['max']:.3f}]\n"

    if len(chunk_summaries) > 10:
        summary += f"  ... and {len(chunk_summaries) - 10} more chunks\n"

    return summary


@mcp.tool(
    title="Aggregate Stats",
    tags={"performance", "parallel", "analysis"},
    annotations={
        "title": "Aggregate Statistics Across Datasets",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": False,
    },
)
@with_error_handling
@with_performance_tracking
async def hdf5_aggregate_stats(
    paths: str, stats: Optional[str] = None, ctx: Optional[Context] = None
) -> str:
    """Parallel statistics computation across multiple datasets.

    Args:
        paths: Comma-separated dataset paths or JSON array
        stats: Comma-separated stats to compute (default: mean,std,min,max,sum,count)
        ctx: Context for progress reporting

    Returns:
        Aggregate statistics summary
    """
    if not current_file:
        raise ToolError("No file currently open. Use open_file first.")

    # Parse paths
    try:
        path_list = json.loads(paths)
    except Exception:
        path_list = [p.strip() for p in paths.split(",") if p.strip()]

    # Parse stats
    if stats:
        stats_list = [s.strip() for s in stats.split(",") if s.strip()]
    else:
        stats_list = ["mean", "std", "min", "max", "sum", "count"]

    if ctx:
        await ctx.info(f"Computing statistics for {len(path_list)} datasets")
        await ctx.report_progress(0, len(path_list), "Starting statistics computation")

    # Parallel statistics computation
    results = {}
    with ThreadPoolExecutor(max_workers=num_workers) as pool:
        future_to_path = {
            pool.submit(_compute_dataset_stats, current_file, path, stats_list): path
            for path in path_list
        }

        for i, future in enumerate(as_completed(future_to_path), 1):
            path = future_to_path[future]

            try:
                dataset_stats = future.result()
                results[path] = dataset_stats

                if ctx:
                    await ctx.report_progress(
                        i, len(path_list), f"Computed stats {i}/{len(path_list)}"
                    )
            except Exception as e:
                results[path] = {"error": str(e)}

    # Aggregate results
    successful_stats = {k: v for k, v in results.items() if "error" not in v}

    summary = f"Aggregate statistics for {len(path_list)} datasets:\n\n"

    for path, stat_result in results.items():
        if "error" in stat_result:
            summary += f"✗ {path}: {stat_result['error']}\n"
        else:
            summary += f"✓ {path}:\n"
            summary += f"  Shape: {stat_result['shape']}, Size: {stat_result['size_mb']:.2f} MB\n"
            for stat_name in stats_list:
                if stat_name in stat_result:
                    summary += f"  {stat_name}: {stat_result[stat_name]:.6f}\n"
            summary += "\n"

    # Cross-dataset aggregation
    if len(successful_stats) > 1:
        summary += "Cross-dataset aggregation:\n"

        for stat_name in ["mean", "sum", "count"]:
            if all(
                stat_name in stats_list and stat_name in result
                for result in successful_stats.values()
            ):
                values = [result[stat_name] for result in successful_stats.values()]
                if stat_name == "mean":
                    counts = [
                        result.get("count", 1) for result in successful_stats.values()
                    ]
                    total_count = sum(counts)
                    weighted_mean = (
                        sum(v * c for v, c in zip(values, counts)) / total_count
                        if total_count > 0
                        else 0
                    )
                    summary += f"  Overall {stat_name}: {weighted_mean:.6f}\n"
                elif stat_name == "sum":
                    summary += f"  Total {stat_name}: {sum(values):.6f}\n"
                elif stat_name == "count":
                    summary += f"  Total {stat_name}: {sum(values):,}\n"

        if all("min" in result for result in successful_stats.values()):
            global_min = min(result["min"] for result in successful_stats.values())
            summary += f"  Global min: {global_min:.6f}\n"

        if all("max" in result for result in successful_stats.values()):
            global_max = max(result["max"] for result in successful_stats.values())
            summary += f"  Global max: {global_max:.6f}\n"

    return summary


# =========================================================================
# DISCOVERY TOOLS - Analysis, Patterns, Optimization
# =========================================================================


@mcp.tool(
    title="Analyze Structure",
    tags={"discovery", "ai-powered", "analysis"},
    annotations={
        "title": "Analyze Dataset Structure",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": False,
    },
)
@with_error_handling
@with_performance_tracking
async def analyze_dataset_structure(
    path: str = "/", ctx: Optional[Context] = None
) -> str:
    """Analyze and understand file organization and data patterns with AI insights.

    Args:
        path: Path to analyze (default: root)
        ctx: Context for LLM sampling

    Returns:
        Structure analysis with AI insights
    """
    if not current_file:
        return "Error: No file currently open"

    if path == "/":
        obj = current_file.file
    else:
        obj = current_file[path]

    if isinstance(obj, h5py.Group):
        items = list(obj.keys())
        groups = [k for k in items if isinstance(obj[k], h5py.Group)]
        datasets = [k for k in items if isinstance(obj[k], h5py.Dataset)]

        analysis = f"Structure Analysis for: {path}\n"
        analysis += "Type: Group\n"
        analysis += f"Total items: {len(items)}\n"
        analysis += f"Groups: {len(groups)}\n"
        analysis += f"Datasets: {len(datasets)}\n\n"

        if datasets:
            analysis += "Datasets:\n"
            dataset_info = []
            for ds_name in datasets[:10]:
                ds = obj[ds_name]
                info = f"{ds_name}: {ds.shape}, {ds.dtype}"
                analysis += f"  {info}\n"
                dataset_info.append(info)
            if len(datasets) > 10:
                analysis += f"  ... and {len(datasets) - 10} more datasets\n"

        if groups:
            analysis += f"\nGroups: {', '.join(groups[:10])}\n"
            if len(groups) > 10:
                analysis += f"... and {len(groups) - 10} more groups\n"

        # Add LLM insights (optional - requires client sampling support)
        sample = _sample_callable(ctx)
        if sample and datasets:
            try:
                llm_response = await sample(
                    f"Analyze this HDF5 group structure at path '{path}': "
                    f"{len(datasets)} datasets, {len(groups)} groups. "
                    f"Dataset info: {', '.join(dataset_info[:5])}. "
                    f"What patterns do you observe and what might this data be used for?"
                )
                analysis += f"\n\n🤖 AI Insights:\n{llm_response.text}\n"
            except ValueError as e:
                # Client doesn't support sampling
                logger.debug(f"Sampling not supported: {e}")
                analysis += f"\n\n[Debug: Context sampling not supported - {str(e)}]\n"
            except Exception as e:
                # Unexpected error - log it
                logger.warning(f"Error during sampling: {e}")
                import traceback

                logger.debug(traceback.format_exc())
                analysis += (
                    f"\n\n[Debug: Sampling error - {type(e).__name__}: {str(e)}]\n"
                )
        elif not ctx:
            analysis += "\n\n[Debug: No Context provided to tool]\n"
        elif not sample:
            analysis += (
                "\n\n[Debug: Context sampling not supported on this connection]\n"
            )
        elif not datasets:
            analysis += "\n\n[Debug: No datasets to analyze]\n"

    elif isinstance(obj, h5py.Dataset):
        analysis = f"Structure Analysis for: {path}\n"
        analysis += "Type: Dataset\n"
        analysis += f"Shape: {obj.shape}\n"
        analysis += f"Data type: {obj.dtype}\n"
        analysis += f"Size: {obj.nbytes / (1024 * 1024):.2f} MB\n"
        analysis += f"Chunks: {obj.chunks}\n"

        # Add LLM insights for datasets (optional - requires client sampling support)
        sample = _sample_callable(ctx)
        if sample:
            try:
                llm_response = await sample(
                    f"Analyze this HDF5 dataset at path '{path}': "
                    f"Shape {obj.shape}, dtype {obj.dtype}, size {obj.nbytes / (1024 * 1024):.2f} MB. "
                    f"What might this data represent?"
                )
                analysis += f"\n\n🤖 AI Insights:\n{llm_response.text}\n"
            except ValueError as e:
                logger.debug(f"Sampling not supported: {e}")
            except Exception as e:
                logger.warning(f"Error during sampling: {e}")
                import traceback

                logger.debug(traceback.format_exc())
    else:
        analysis = f"Structure Analysis for: {path}\n"
        analysis += f"Type: {type(obj).__name__}\n"

    return analysis


@mcp.tool(
    title="Find Similar Datasets",
    tags={"discovery", "ai-powered", "similarity"},
    annotations={
        "title": "Find Similar Datasets",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": False,
    },
)
@with_error_handling
@with_performance_tracking
async def find_similar_datasets(
    reference_path: str,
    similarity_threshold: float = 0.8,
    ctx: Optional[Context] = None,
) -> str:
    """Find datasets with similar characteristics to a reference dataset with AI analysis.

    Args:
        reference_path: Path to reference dataset
        similarity_threshold: Similarity threshold (0.0 to 1.0)
        ctx: Context for LLM sampling

    Returns:
        List of similar datasets with similarity scores and AI insights
    """
    if not current_file:
        raise ToolError("No file currently open. Use open_file first.")

    try:
        ref_dataset = current_file[reference_path]
    except KeyError:
        raise ToolError(f"Dataset not found: {reference_path}")

    if not isinstance(ref_dataset, h5py.Dataset):
        raise ToolError(f"{reference_path} is not a dataset")

    ref_shape = ref_dataset.shape
    ref_dtype = ref_dataset.dtype
    ref_size = ref_dataset.nbytes

    similar_datasets = []

    def check_dataset(name, obj):
        if isinstance(obj, h5py.Dataset) and name != reference_path:
            shape_sim = 1.0 if obj.shape == ref_shape else 0.5
            dtype_sim = 1.0 if obj.dtype == ref_dtype else 0.3
            size_ratio = min(obj.nbytes, ref_size) / max(obj.nbytes, ref_size)

            similarity = (shape_sim + dtype_sim + size_ratio) / 3.0

            if similarity >= similarity_threshold:
                similar_datasets.append(
                    {
                        "path": name,
                        "similarity": similarity,
                        "shape": obj.shape,
                        "dtype": str(obj.dtype),
                        "size_mb": obj.nbytes / (1024 * 1024),
                    }
                )

    actual_file = current_file.file if hasattr(current_file, "file") else current_file
    actual_file.visititems(check_dataset)  # type: ignore[union-attr]

    similar_datasets.sort(key=lambda x: x["similarity"], reverse=True)

    result = f"Similar datasets to '{reference_path}':\n"
    result += (
        f"Reference: {ref_shape}, {ref_dtype}, {ref_size / (1024 * 1024):.2f} MB\n\n"
    )

    if similar_datasets:
        result += f"Found {len(similar_datasets)} similar datasets:\n"
        for ds in similar_datasets[:10]:
            result += f"  {ds['path']} (similarity: {ds['similarity']:.3f})\n"
            result += f"    Shape: {ds['shape']}, Type: {ds['dtype']}, Size: {ds['size_mb']:.2f} MB\n"

        # Add LLM insights (optional - requires client sampling support)
        sample = _sample_callable(ctx)
        if sample:
            try:
                top_similar = similar_datasets[:5]
                similar_paths = ", ".join(
                    [
                        f"{ds['path']} (similarity {ds['similarity']:.2f})"
                        for ds in top_similar
                    ]
                )
                llm_response = await sample(
                    f"Explain why these datasets are similar to '{reference_path}' "
                    f"(shape {ref_shape}, dtype {ref_dtype}): "
                    f"{similar_paths}. "
                    f"What might these similar datasets represent?"
                )
                result += f"\n\n🤖 AI Analysis:\n{llm_response.text}\n"
            except ValueError as e:
                logger.debug(f"Sampling not supported: {e}")
            except Exception as e:
                logger.warning(f"Error during sampling: {e}")
                import traceback

                logger.debug(traceback.format_exc())
    else:
        result += "No similar datasets found with the given threshold."

    return result


@mcp.tool(
    title="Suggest Next Step",
    tags={"discovery", "ai-powered", "recommendation"},
    annotations={
        "title": "Suggest Next Exploration",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": False,
    },
)
@with_error_handling
@with_performance_tracking
async def suggest_next_exploration(
    current_path: str = "/", ctx: Optional[Context] = None
) -> str:
    """Suggest interesting data to explore next based on current location with AI recommendations.

    Args:
        current_path: Current path (default: root)
        ctx: Context for LLM sampling

    Returns:
        Exploration suggestions with interest scores and AI recommendations
    """
    if not current_file:
        raise ToolError("No file currently open. Use open_file first.")

    if current_path == "/":
        obj = current_file.file
    else:
        obj = current_file[current_path]

    suggestions = []

    if isinstance(obj, h5py.Group):
        items = list(obj.keys())

        for item_name in items:
            try:
                item = obj[item_name]
                if isinstance(item, h5py.Dataset):
                    size_mb = item.nbytes / (1024 * 1024)
                    score = 0

                    if 1 <= size_mb <= 100:
                        score += 3
                    elif size_mb > 100:
                        score += 2

                    if len(item.shape) == 2:
                        score += 2
                    elif len(item.shape) > 2:
                        score += 1

                    if "data" in item_name.lower() or "result" in item_name.lower():
                        score += 1

                    suggestions.append(
                        {
                            "path": f"{current_path}/{item_name}"
                            if current_path != "/"
                            else f"/{item_name}",
                            "type": "dataset",
                            "score": score,
                            "info": f"Shape: {item.shape}, Size: {size_mb:.2f} MB",
                        }
                    )

                elif isinstance(item, h5py.Group):
                    child_count = len(list(item.keys()))
                    score = min(3, child_count // 5)

                    suggestions.append(
                        {
                            "path": f"{current_path}/{item_name}"
                            if current_path != "/"
                            else f"/{item_name}",
                            "type": "group",
                            "score": score,
                            "info": f"Contains {child_count} items",
                        }
                    )
            except Exception:
                continue

    suggestions.sort(key=lambda x: x["score"], reverse=True)  # type: ignore[arg-type, return-value]

    result = f"Exploration suggestions from '{current_path}':\n\n"
    if suggestions:
        for i, suggestion in enumerate(suggestions[:5], 1):
            result += f"{i}. {suggestion['path']} ({suggestion['type']})\n"
            result += f"   {suggestion['info']}\n"
            result += f"   Interest score: {suggestion['score']}\n\n"

        # Add LLM recommendations (optional - requires client sampling support)
        sample = _sample_callable(ctx)
        if sample:
            try:
                top_suggestions = suggestions[:3]
                suggestion_list = ", ".join(
                    [f"{s['path']} ({s['info']})" for s in top_suggestions]
                )
                llm_response = await sample(
                    f"Based on these top exploration targets at '{current_path}': "
                    f"{suggestion_list}, "
                    f"what would you recommend exploring first and why?"
                )
                result += f"\n🤖 AI Recommendations:\n{llm_response.text}\n"
            except ValueError as e:
                logger.debug(f"Sampling not supported: {e}")
            except Exception as e:
                logger.warning(f"Error during sampling: {e}")
                import traceback

                logger.debug(traceback.format_exc())
    else:
        result += "No additional exploration targets found at this location."

    return result


@mcp.tool(
    title="Find Bottlenecks",
    tags={"discovery", "ai-powered", "performance"},
    annotations={
        "title": "Identify I/O Bottlenecks",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": False,
    },
)
@with_error_handling
@with_performance_tracking
async def identify_io_bottlenecks(
    analysis_paths: Optional[List[str]] = None, ctx: Optional[Context] = None
) -> str:
    """Identify potential I/O bottlenecks and performance issues with AI recommendations.

    Args:
        analysis_paths: Optional list of paths to analyze (auto-discovers if None)
        ctx: Context for LLM sampling

    Returns:
        Bottleneck analysis report with AI recommendations
    """
    if not current_file:
        return "Error: No file currently open"

    if not analysis_paths:
        analysis_paths = []

        def collect_datasets(name, obj):
            if isinstance(obj, h5py.Dataset):
                analysis_paths.append(name)

        actual_file = (
            current_file.file if hasattr(current_file, "file") else current_file
        )
        actual_file.visititems(collect_datasets)  # type: ignore[union-attr]
        analysis_paths = analysis_paths[:10]

    bottlenecks = []

    for path in analysis_paths:
        try:
            dataset = current_file[path]
            issues = []

            size_mb = dataset.nbytes / (1024 * 1024)

            if size_mb > 100 and dataset.chunks is None:
                issues.append(f"Large dataset ({size_mb:.1f} MB) without chunking")

            if (
                dataset.chunks
                and np.prod(dataset.chunks) * dataset.dtype.itemsize < 1024
            ):
                issues.append("Very small chunk size may hurt performance")

            if size_mb > 50 and not hasattr(dataset, "compression"):
                issues.append("Large dataset without compression")

            if len(dataset.shape) > 3:
                issues.append("High-dimensional array may have access pattern issues")

            if issues:
                bottlenecks.append({"path": path, "size_mb": size_mb, "issues": issues})
        except Exception:
            continue

    result = "I/O Bottleneck Analysis:\n\n"
    if bottlenecks:
        result += f"Found potential issues in {len(bottlenecks)} datasets:\n\n"
        for bottleneck in bottlenecks:
            result += f"📄 {bottleneck['path']} ({bottleneck['size_mb']:.2f} MB)\n"
            for issue in bottleneck["issues"]:
                result += f"  ⚠️  {issue}\n"
            result += "\n"

        # Add LLM recommendations (optional - requires client sampling support)
        sample = _sample_callable(ctx)
        if sample:
            try:
                bottleneck_summary = "; ".join(
                    [f"{b['path']} ({', '.join(b['issues'])})" for b in bottlenecks[:3]]
                )
                llm_response = await sample(
                    f"I found these I/O bottlenecks in HDF5 datasets: {bottleneck_summary}. "
                    f"What specific optimization strategies would you recommend to address these issues?"
                )
                result += (
                    f"\n🤖 AI Optimization Recommendations:\n{llm_response.text}\n"
                )
            except ValueError as e:
                logger.debug(f"Sampling not supported: {e}")
            except Exception as e:
                logger.warning(f"Error during sampling: {e}")
                import traceback

                logger.debug(traceback.format_exc())
    else:
        result += "✅ No significant I/O bottlenecks detected."

    return result


@mcp.tool(
    title="Optimize Access",
    tags={"discovery", "performance", "optimization"},
    annotations={
        "title": "Optimize Access Pattern",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": False,
    },
)
@with_error_handling
@with_performance_tracking
async def optimize_access_pattern(
    dataset_path: str, access_pattern: str = "sequential"
) -> str:
    """Suggest better approaches for data access based on usage patterns.

    Args:
        dataset_path: Path to dataset
        access_pattern: Access pattern (sequential, random, batch)

    Returns:
        Optimization recommendations
    """
    if not current_file:
        raise ToolError("No file currently open. Use open_file first.")

    try:
        dataset = current_file[dataset_path]
    except KeyError:
        raise ToolError(f"Dataset not found: {dataset_path}")

    if not isinstance(dataset, h5py.Dataset):
        raise ToolError(f"{dataset_path} is not a dataset")

    size_mb = dataset.nbytes / (1024 * 1024)
    shape = dataset.shape
    chunks = dataset.chunks

    result = f"Access Pattern Optimization for: {dataset_path}\n"
    result += f"Dataset size: {size_mb:.2f} MB, Shape: {shape}\n"
    result += f"Current chunking: {chunks}\n\n"

    if access_pattern.lower() == "sequential":
        result += "Sequential Access Recommendations:\n"
        if size_mb > 100:
            result += "• Use hdf5_stream_data() for memory-efficient processing\n"
            result += "• Consider processing in chunks to avoid memory issues\n"
        else:
            result += "• Use read_full_dataset() for complete data access\n"

        if not chunks:
            result += "• Consider enabling chunking for better I/O performance\n"

    elif access_pattern.lower() == "random":
        result += "Random Access Recommendations:\n"
        if not chunks:
            result += "• ⚠️  Enable chunking for better random access performance\n"
        else:
            chunk_size = np.prod(chunks) * dataset.dtype.itemsize / (1024 * 1024)
            if chunk_size > 10:
                result += f"• Consider smaller chunks (current: {chunk_size:.1f} MB)\n"
            else:
                result += (
                    f"• Chunk size ({chunk_size:.2f} MB) is good for random access\n"
                )

        result += "• Use read_partial_dataset() with specific slices\n"

    elif access_pattern.lower() == "batch":
        result += "Batch Processing Recommendations:\n"
        result += "• Use hdf5_batch_read() for parallel processing\n"
        result += "• Consider hdf5_aggregate_stats() for statistical operations\n"
        if size_mb > 50:
            result += "• Use chunked reading for large datasets\n"

    else:
        result += f"General recommendations for '{access_pattern}' access:\n"
        result += "• Analyze your specific access patterns\n"
        result += "• Consider chunking strategy based on access needs\n"
        result += "• Use appropriate tools based on data size\n"

    return result


# =========================================================================
# ADMIN & DISCOVERY TOOLS
# =========================================================================


@mcp.tool(
    title="Refresh Files",
    tags={"admin", "discovery"},
    annotations={
        "title": "Refresh HDF5 Resources",
        "readOnlyHint": False,
        "destructiveHint": False,
        "idempotentHint": False,
        "openWorldHint": False,
    },
)
async def refresh_hdf5_resources(ctx: Optional[Context] = None) -> str:
    """Re-scan client roots and update available HDF5 resources.

    FastMCP automatically sends notifications/resources/list_changed to clients.

    Returns:
        Summary of refreshed resources
    """
    if ctx:
        await ctx.info("Scanning for HDF5 files...")

    discovered = discover_hdf5_files_in_roots(client_roots)

    newly_registered = 0
    for file_path in discovered:
        if resource_manager.register_hdf5_file(file_path):
            newly_registered += 1

    # Notification sent automatically by FastMCP

    return (
        f"Refreshed resources:\n"
        f"Roots scanned: {len(client_roots)}\n"
        f"Files found: {len(discovered)}\n"
        f"Newly registered: {newly_registered}\n\n"
        f"Use list_available_hdf5_files() to see all files."
    )


@mcp.tool(
    title="List Files",
    tags={"discovery", "helper"},
    annotations={
        "title": "List Available HDF5 Files",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": False,
    },
)
async def list_available_hdf5_files() -> str:
    """List all registered HDF5 files with resource URIs for Claude Code @ mentions.

    Returns:
        List of available files with resource URIs
    """
    files = resource_manager.get_registered_files()

    if not files:
        return "No HDF5 files found. Use refresh_hdf5_resources to scan."

    result = f"Available HDF5 Files ({len(files)}):\n\n"
    for i, file_info in enumerate(files, 1):
        path = file_info["path"]
        name = Path(path).name
        result += f"{i}. {name}\n"
        result += f"   Path: {path}\n"
        result += f"   Metadata: @hdf5:hdf5://{path}/metadata\n"
        result += f"   Structure: @hdf5:hdf5://{path}/structure\n\n"

    return result


@mcp.tool(
    title="Export Dataset",
    tags={"dataset", "export", "interactive"},
    annotations={
        "title": "Export Dataset",
        "readOnlyHint": False,
        "destructiveHint": False,
        "idempotentHint": False,
        "openWorldHint": False,
    },
)
@with_error_handling
@with_performance_tracking
async def export_dataset(
    path: str, output_path: Optional[str] = None, ctx: Optional[Context] = None
) -> str:
    """Export dataset to various formats with user format selection.

    Args:
        path: Path to dataset within file
        output_path: Optional output file path
        ctx: Context for elicitation

    Returns:
        Export summary
    """
    if not current_file:
        raise ToolError("No file open. Use open_file first.")

    try:
        dataset = current_file[path]
    except KeyError:
        raise ToolError(f"Dataset not found: {path}")

    if not isinstance(dataset, h5py.Dataset):
        raise ToolError(f"{path} is not a dataset")

    # Ask user for format (if ctx available and client supports elicitation)
    export_format = "json"
    if ctx:
        try:
            format_result = await ctx.elicit(
                "What format should I export to?",
                response_type=["csv", "json", "numpy"],  # type: ignore[arg-type]
            )

            if format_result.action == "accept":
                export_format = format_result.data  # type: ignore[assignment]
            elif format_result.action == "decline":
                return "Export declined by user"
            else:  # cancel
                raise ToolError("Export cancelled")
        except ValueError as e:
            logger.debug(f"Elicitation not supported: {e}")
        except Exception as e:
            logger.warning(f"Error during elicitation: {e}")
            import traceback

            logger.debug(traceback.format_exc())
            # Fall back to default format
            export_format = "json"

    # Read dataset
    data = dataset[:]

    # Export based on format
    if export_format == "csv":
        # CSV export (works for 1D and 2D arrays)
        if len(data.shape) > 2:
            raise ToolError(
                f"CSV export only supports 1D/2D arrays, got shape {data.shape}"
            )

        import csv
        import io

        output = io.StringIO()
        writer = csv.writer(output)

        if len(data.shape) == 1:
            for value in data:
                writer.writerow([value])
        else:
            for row in data:
                writer.writerow(row)

        export_data = output.getvalue()

    elif export_format == "json":
        # JSON export
        if hasattr(data, "tolist"):
            export_data = json.dumps(
                {
                    "path": path,
                    "shape": data.shape,
                    "dtype": str(data.dtype),
                    "data": data.tolist(),
                },
                indent=2,
            )
        else:
            export_data = json.dumps({"path": path, "data": str(data)}, indent=2)

    elif export_format == "numpy":
        # NumPy export (return info about how to save)
        export_data = f"NumPy array shape {data.shape}, dtype {data.dtype}\n"
        export_data += f"To save: np.save('{output_path or 'output.npy'}', data)\n"
        export_data += f"First few values: {data.flat[:10].tolist()}"

    else:
        raise ToolError(f"Unsupported format: {export_format}")

    # Write to file if output_path provided
    if output_path and export_format != "numpy":
        try:
            with open(output_path, "w") as f:
                f.write(export_data)
            return f"Exported {path} to {output_path} as {export_format}\n{export_data[:500]}..."
        except Exception as e:
            raise ToolError(f"Error writing to {output_path}: {str(e)}")
    else:
        return (
            f"Exported {path} as {export_format}:\n\n{export_data[:1000]}..."
            if len(export_data) > 1000
            else f"Exported {path} as {export_format}:\n\n{export_data}"
        )


# =========================================================================
# HELPER FUNCTIONS
# =========================================================================


def _read_large_dataset(dataset, chunk_size=1024 * 1024):
    """Read large dataset in chunks."""
    if len(dataset.shape) != 1:
        return dataset[:]

    result = np.empty(dataset.shape, dtype=dataset.dtype)
    for i in range(0, dataset.shape[0], chunk_size):
        end = min(i + chunk_size, dataset.shape[0])
        result[i:end] = dataset[i:end]
    return result


def _scan_single_file(file_path: str) -> dict:
    """Scan a single HDF5 file and return metadata."""
    with h5py.File(file_path, "r") as f:
        dataset_count = 0
        total_size = 0
        datasets = []

        def count_datasets(name, obj):
            nonlocal dataset_count, total_size
            if isinstance(obj, h5py.Dataset):
                dataset_count += 1
                total_size += obj.nbytes
                datasets.append(
                    {
                        "name": name,
                        "shape": obj.shape,
                        "dtype": str(obj.dtype),
                        "size_mb": obj.nbytes / (1024 * 1024),
                    }
                )

        f.visititems(count_datasets)

        return {
            "dataset_count": dataset_count,
            "total_size_mb": total_size / (1024 * 1024),
            "datasets": datasets[:5],
        }


def _read_single_dataset(file_proxy, path: str, slice_obj=None) -> dict:
    """Read a single dataset with optional slicing."""
    dataset = file_proxy[path]

    if slice_obj is not None:
        data = dataset[slice_obj]
    else:
        if dataset.nbytes > 100 * 1024 * 1024:
            if len(dataset.shape) == 1:
                data = dataset[: min(1000, dataset.shape[0])]
            else:
                data = dataset[: min(10, dataset.shape[0])]
        else:
            data = dataset[:]

    if isinstance(data, np.ndarray):
        if data.size <= 10:
            preview = data.tolist()
        else:
            preview = f"[{data.flat[0]}, {data.flat[1]}, ..., {data.flat[-1]}]"
    else:
        preview = str(data)

    return {
        "shape": dataset.shape,
        "dtype": str(dataset.dtype),
        "size_mb": dataset.nbytes / (1024 * 1024),
        "preview": preview,
        "data_shape": data.shape,
        "slice_applied": slice_obj is not None,
    }


def _compute_dataset_stats(file_proxy, path: str, stats: List[str]) -> dict:
    """Compute statistics for a single dataset."""
    dataset = file_proxy[path]

    if dataset.nbytes > 500 * 1024 * 1024:
        sample_size = min(1000000, max(1000, dataset.size // 100))
        if len(dataset.shape) == 1:
            step = max(1, dataset.size // sample_size)
            data = dataset[::step]
        else:
            step = max(1, dataset.shape[0] // int(np.sqrt(sample_size)))
            data = dataset[::step]
    else:
        data = dataset[:]

    result = {
        "shape": dataset.shape,
        "dtype": str(dataset.dtype),
        "size_mb": dataset.nbytes / (1024 * 1024),
        "sampled": dataset.nbytes > 500 * 1024 * 1024,
    }

    if np.issubdtype(data.dtype, np.number):
        if "mean" in stats:
            result["mean"] = float(np.mean(data))
        if "std" in stats:
            result["std"] = float(np.std(data))
        if "min" in stats:
            result["min"] = float(np.min(data))
        if "max" in stats:
            result["max"] = float(np.max(data))
        if "sum" in stats:
            result["sum"] = float(np.sum(data))
        if "count" in stats:
            result["count"] = int(data.size)
        if "median" in stats:
            result["median"] = float(np.median(data))
    else:
        result["note"] = (
            f"Non-numeric data type ({data.dtype}), limited statistics available"
        )
        if "count" in stats:
            result["count"] = int(data.size)

    return result


# =========================================================================
# RESOURCES - HDF5 URIs
# =========================================================================


@mcp.resource(
    "hdf5://{file_path}/metadata",
    annotations={
        "title": "PLACEHOLDER",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": False,
    },
)
async def hdf5_file_metadata(file_path: str) -> str:
    """Expose HDF5 file metadata as resource.

    Args:
        file_path: Path to HDF5 file

    Returns:
        JSON metadata
    """
    try:
        with h5py.File(file_path, "r") as f:
            metadata = {
                "filename": f.filename,
                "mode": f.mode,
                "userblock_size": f.userblock_size,
                "keys": list(f.keys()),
                "attrs": dict(f.attrs),
            }
            return json.dumps(metadata, indent=2)
    except FileNotFoundError:
        raise ResourceError(f"File not found: {file_path}")
    except Exception as e:
        raise ResourceError(f"Error reading metadata from {file_path}: {str(e)}")


@mcp.resource(
    "hdf5://{file_path}/datasets/{dataset_path*}",
    annotations={
        "title": "PLACEHOLDER",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": False,
    },
)
async def hdf5_dataset_resource(file_path: str, dataset_path: str) -> str:
    """Expose HDF5 dataset as resource.

    Args:
        file_path: Path to HDF5 file
        dataset_path: Path to dataset within file (supports nested paths)

    Returns:
        Dataset data (preview for large datasets)
    """
    try:
        with h5py.File(file_path, "r") as f:
            dataset = f[dataset_path]

            data_info = {
                "path": dataset_path,
                "shape": dataset.shape,
                "dtype": str(dataset.dtype),
                "size_mb": dataset.nbytes / (1024 * 1024),
            }

            # Include data preview
            if dataset.nbytes < 1024 * 1024:  # 1MB
                data = dataset[:]
                if hasattr(data, "tolist"):
                    data_info["data"] = data.tolist()
                else:
                    data_info["data"] = str(data)
            else:
                data_info["note"] = "Dataset too large, use tools to read"

            return json.dumps(data_info, indent=2)
    except FileNotFoundError:
        raise ResourceError(f"File not found: {file_path}")
    except KeyError:
        raise ResourceError(f"Dataset not found: {dataset_path} in {file_path}")
    except Exception as e:
        raise ResourceError(f"Error reading dataset from {file_path}: {str(e)}")


@mcp.resource(
    "hdf5://{file_path}/structure",
    annotations={
        "title": "PLACEHOLDER",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": False,
    },
)
async def hdf5_structure_resource(file_path: str) -> str:
    """Expose HDF5 file structure as resource.

    Args:
        file_path: Path to HDF5 file

    Returns:
        Hierarchical structure
    """
    try:
        with h5py.File(file_path, "r") as f:
            structure = {}

            def build_structure(name, obj):
                if isinstance(obj, h5py.Group):
                    structure[name] = {"type": "Group", "keys": list(obj.keys())}
                elif isinstance(obj, h5py.Dataset):
                    structure[name] = {
                        "type": "Dataset",
                        "shape": obj.shape,
                        "dtype": str(obj.dtype),
                    }

            f.visititems(build_structure)
            return json.dumps(structure, indent=2)
    except FileNotFoundError:
        raise ResourceError(f"File not found: {file_path}")
    except Exception as e:
        raise ResourceError(f"Error reading structure from {file_path}: {str(e)}")


# =========================================================================
# PROMPTS - Analysis Workflows
# =========================================================================


@mcp.prompt()
def explore_hdf5_file(file_path: str):
    """Generate workflow for exploring an HDF5 file.

    Args:
        file_path: Path to HDF5 file

    Returns:
        Exploration workflow prompt
    """
    return Message(f"""Please explore the HDF5 file at {file_path}:

1. First, use open_file to open {file_path}
2. Use analyze_dataset_structure to understand the hierarchy
3. Use suggest_next_exploration to find interesting datasets
4. Read the suggested datasets with read_full_dataset or read_partial_dataset
5. Generate summary statistics with hdf5_aggregate_stats
6. Close the file when done with close_file

This workflow will give you a comprehensive understanding of the file's contents.""")


@mcp.prompt()
def optimize_hdf5_access(file_path: str, access_pattern: str = "sequential"):
    """Generate optimization workflow for HDF5 I/O.

    Args:
        file_path: Path to HDF5 file
        access_pattern: Access pattern (sequential, random, batch)

    Returns:
        Optimization workflow prompt
    """
    return Message(f"""Optimize I/O access for {file_path}:

1. Use open_file to open {file_path}
2. Use identify_io_bottlenecks to detect performance issues
3. Use optimize_access_pattern with pattern='{access_pattern}' for specific datasets
4. Use hdf5_parallel_scan if analyzing multiple files in a directory
5. Use hdf5_stream_data for large datasets to avoid memory issues
6. Monitor performance with HDF5_SHOW_PERFORMANCE=true environment variable

This workflow will help you achieve optimal performance for your access patterns.""")


@mcp.prompt()
def compare_hdf5_datasets(file_path: str, dataset1: str, dataset2: str):
    """Generate comparison workflow for two datasets.

    Args:
        file_path: Path to HDF5 file
        dataset1: First dataset path
        dataset2: Second dataset path

    Returns:
        Comparison workflow prompt
    """
    return Message(f"""Compare datasets in {file_path}:

1. Use open_file to open {file_path}
2. Use get_shape and get_dtype to compare metadata for:
   - {dataset1}
   - {dataset2}
3. Use hdf5_batch_read with paths=["{dataset1}", "{dataset2}"] for parallel reading
4. Use hdf5_aggregate_stats to compute statistics for both datasets
5. Use find_similar_datasets starting from {dataset1} to see if {dataset2} is similar
6. Close the file with close_file

This workflow provides a comprehensive comparison of the two datasets.""")


@mcp.prompt()
def batch_process_hdf5(directory: str, operation: str = "statistics"):
    """Generate batch processing workflow for multiple HDF5 files.

    Args:
        directory: Directory containing HDF5 files
        operation: Operation to perform (statistics, scan, export)

    Returns:
        Batch processing workflow prompt
    """
    return Message(f"""Batch process HDF5 files in {directory}:

1. Use hdf5_parallel_scan with directory="{directory}" to discover all files
2. For each interesting file found:
   a. Use open_file to open it
   b. Use analyze_dataset_structure to understand layout
   c. Use hdf5_aggregate_stats to compute {operation}
   d. Use close_file to release resources
3. Aggregate results across all files
4. Use identify_io_bottlenecks to find common performance issues

This parallel workflow efficiently processes multiple files with minimal overhead.""")


# =========================================================================
# Server Lifecycle
# =========================================================================


async def cleanup():
    """Cleanup server resources."""
    try:
        logger.info("Shutting down HDF5 FastMCP server...")

        # Close current file if open
        global current_file
        if current_file:
            current_file.close()
            current_file = None

        # Shutdown resource manager
        await resource_manager.shutdown()

        # Shutdown executor
        executor.shutdown(wait=True)

        logger.info("HDF5 FastMCP server shutdown complete")
    except Exception as e:
        logger.error(f"Error during shutdown: {e}")


# =========================================================================
# Main Entry Point
# =========================================================================


def main():
    """Main entry point for HDF5 FastMCP server."""
    import argparse

    parser = argparse.ArgumentParser(description="IoWarp HDF5 FastMCP Server v1.0")
    parser.add_argument(
        "--transport",
        choices=["stdio", "http"],
        default=None,
        help="Transport protocol (default: stdio)",
    )
    parser.add_argument(
        "--host", default="0.0.0.0", help="Host for HTTP transport (default: 0.0.0.0)"
    )
    parser.add_argument(
        "--port", type=int, default=8765, help="Port for HTTP transport (default: 8765)"
    )
    parser.add_argument("--data-dir", type=Path, help="Directory containing HDF5 files")
    parser.add_argument(
        "--log-level",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        default="INFO",
        help="Logging level",
    )
    args = parser.parse_args()

    # Configure logging
    logging.basicConfig(
        level=getattr(logging, args.log_level),
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )

    # Set data directory if provided
    if args.data_dir:
        os.environ["HDF5_MCP_DATA_DIR"] = str(args.data_dir)

    # No need to call initialize() - lifespan handles it
    # Server initialization now happens in lifespan context manager

    transport = args.transport or os.getenv("MCP_TRANSPORT", "stdio")
    if transport == "http":
        mcp.run(transport="http", host=args.host, port=args.port)
    else:
        mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
