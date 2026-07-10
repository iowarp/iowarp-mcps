"""
HDF5 FastMCP Utility Functions

@file       utils.py
@brief      Performance monitoring, caching, and HDF5 management utilities
@author     IoWarp Scientific MCPs Team
@version    2.1.0
@date       2024
@license    MIT

@description
    Part of the IoWarp MCP Server Collection for AI-powered scientific computing.

    This module provides utility functions and classes for HDF5 operations,
    including performance monitoring, file handle caching, and context managers
    for safe HDF5 file access.

    Key Components:
    - PerformanceMonitor: Track operation timing, memory, and cache statistics
    - FileHandleCache: LRU cache with time-based expiry for file handles
    - HDF5Manager: Context manager for safe HDF5 file operations

    Features:
    - Nanosecond-precision performance tracking
    - Adaptive units (ns, μs, ms, s) for timing
    - Memory usage monitoring with psutil
    - Cache hit/miss statistics
    - Thread-safe operations
    - Automatic handle expiry and cleanup

@see https://github.com/iowarp/clio-kit
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
import h5py
from typing import Dict, Any, Tuple, Optional, Callable
from pathlib import Path
import time
import os
import psutil
from functools import wraps
from threading import Lock, RLock
import json
from collections import OrderedDict
import threading
import weakref

logger = logging.getLogger(__name__)


def setup_logging(log_level="INFO"):
    """Configure logging with the specified level."""
    logging.basicConfig(
        level=getattr(logging, log_level.upper()),
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )


# =========================================================================
# Performance Monitoring
# =========================================================================


class PerformanceMonitor:
    """Monitor and track performance metrics."""

    def __init__(self, metrics_dir: Optional[Path] = None):
        self.metrics_dir = metrics_dir or Path.home() / ".hdf5_mcp" / "metrics"
        self.metrics_dir.mkdir(parents=True, exist_ok=True)
        self.metrics: Dict[str, Any] = {  # type: ignore[assignment]
            "operations": {},
            "memory": [],
            "cache_stats": {"hits": 0, "misses": 0},
        }
        self.lock = Lock()

    def track_operation(
        self, operation: str, duration: float, size: Optional[int] = None
    ):
        """Track operation timing and size."""
        with self.lock:
            if operation not in self.metrics["operations"]:
                self.metrics["operations"][operation] = {
                    "count": 0,
                    "total_time": 0.0,
                    "avg_time": 0.0,
                    "total_size": 0,
                }

            stats = self.metrics["operations"][operation]
            stats["count"] += 1
            stats["total_time"] += duration
            stats["avg_time"] = stats["total_time"] / stats["count"]
            if size:
                stats["total_size"] += size

    def track_memory(self):
        """Track current memory usage."""
        process = psutil.Process(os.getpid())
        memory_info = process.memory_info()

        with self.lock:
            self.metrics["memory"].append(
                {
                    "timestamp": time.time(),
                    "rss": memory_info.rss,
                    "vms": memory_info.vms,
                }
            )

            # Keep only last 1000 memory measurements
            if len(self.metrics["memory"]) > 1000:
                self.metrics["memory"] = self.metrics["memory"][-1000:]

    def track_cache(self, hit: bool):
        """Track cache hit/miss statistics."""
        with self.lock:
            if hit:
                self.metrics["cache_stats"]["hits"] += 1
            else:
                self.metrics["cache_stats"]["misses"] += 1

    def save_metrics(self):
        """Save metrics to disk."""
        with self.lock:
            timestamp = time.strftime("%Y%m%d-%H%M%S")
            metrics_file = self.metrics_dir / f"metrics-{timestamp}.json"
            with open(metrics_file, "w") as f:
                json.dump(self.metrics, f, indent=2)

    def get_summary(self) -> Dict[str, Any]:
        """Get a summary of current metrics."""
        with self.lock:
            total_ops = sum(op["count"] for op in self.metrics["operations"].values())
            cache_hits = self.metrics["cache_stats"]["hits"]
            cache_misses = self.metrics["cache_stats"]["misses"]
            cache_ratio = (
                cache_hits / (cache_hits + cache_misses)
                if cache_hits + cache_misses > 0
                else 0
            )

            if self.metrics["memory"]:
                current_memory = self.metrics["memory"][-1]["rss"] / (1024 * 1024)  # type: ignore[index]  # MB
            else:
                current_memory = 0

            return {
                "total_operations": total_ops,
                "cache_hit_ratio": cache_ratio,
                "current_memory_mb": current_memory,
                "operation_stats": self.metrics["operations"],
            }


# =========================================================================
# Performance Decorators
# =========================================================================


def monitor_performance(monitor: PerformanceMonitor):
    """Decorator to monitor function performance."""

    def decorator(func: Callable):
        @wraps(func)
        def wrapper(*args, **kwargs):
            start_time = time.time()
            try:
                result = func(*args, **kwargs)
                duration = time.time() - start_time

                # Track operation
                size = None
                if hasattr(result, "nbytes"):
                    size = result.nbytes
                elif isinstance(result, (bytes, str)):
                    size = len(result)

                monitor.track_operation(
                    operation=func.__name__, duration=duration, size=size
                )

                # Track memory periodically
                if time.time() % 60 < 1:  # Once per minute
                    monitor.track_memory()

                return result

            except Exception as e:
                logger.error(f"Error in {func.__name__}: {e}")
                raise

        return wrapper

    return decorator


# =========================================================================
# File Handle Cache
# =========================================================================


class FileHandleCache:
    """LRU cache for HDF5 file handles with time-based expiry."""

    _instances: "weakref.WeakSet[FileHandleCache]" = weakref.WeakSet()

    def __init__(self, max_size: int = 1024, expiry_time: float = 300):
        """
        Initialize the file handle cache.

        Args:
            max_size: Maximum number of file handles to keep open (default: 1024)
            expiry_time: Time in seconds after which unused handles are closed (default: 300)
        """
        self._cache: OrderedDict[str, Tuple[h5py.File, float]] = OrderedDict()
        self._max_size = max_size
        self._expiry_time = expiry_time
        self._lock = RLock()
        self._monitor = PerformanceMonitor()

        # Start expiry checker thread
        self._stop_checker = threading.Event()
        self._checker_thread = threading.Thread(target=self._check_expiry, daemon=True)
        self._checker_thread.start()
        self._instances.add(self)

    def get(self, file_path: str, mode: str = "r") -> h5py.File:
        """Get a file handle from cache or create a new one."""
        with self._lock:
            current_time = time.time()

            # Try to get from cache
            if file_path in self._cache:
                handle, _ = self._cache[file_path]
                # Move to end (most recently used)
                self._cache.move_to_end(file_path)
                self._cache[file_path] = (handle, current_time)
                self._monitor.track_cache(hit=True)
                return handle

            # Create new handle
            self._monitor.track_cache(hit=False)
            handle = h5py.File(file_path, mode)

            # If cache is full, remove oldest
            if len(self._cache) >= self._max_size:
                oldest = next(iter(self._cache))
                self._close_handle(oldest)

            # Add to cache
            self._cache[file_path] = (handle, current_time)
            return handle

    def _close_handle(self, file_path: str):
        """Close a file handle and remove from cache."""
        if file_path in self._cache:
            handle, _ = self._cache[file_path]
            handle.close()
            del self._cache[file_path]

    def _check_expiry(self):
        """Periodically check for expired handles."""
        while not self._stop_checker.is_set():
            with self._lock:
                current_time = time.time()
                expired = [
                    path
                    for path, (_, timestamp) in self._cache.items()
                    if current_time - timestamp > self._expiry_time
                ]
                for path in expired:
                    self._close_handle(path)
            time.sleep(60)  # Check every minute

    def close_all(self):
        """Close all file handles."""
        with self._lock:
            for file_path in list(self._cache.keys()):
                self._close_handle(file_path)
            self._stop_checker.set()

    @classmethod
    def close_all_instances(cls):
        """Close all file handles owned by live cache instances."""
        for cache in list(cls._instances):
            cache.close_all()

    def __del__(self):
        """Ensure all handles are closed on deletion."""
        self.close_all()


# Create a global file handle cache
file_handle_cache = FileHandleCache()

# =========================================================================
# HDF5 Manager
# =========================================================================


class HDF5Manager:
    """Manager for HDF5 file operations."""

    def __init__(self, file_path: Path):
        """
        Initialize HDF5 manager.

        Args:
            file_path: Path to the HDF5 file
        """
        self.file_path = file_path
        self.file = None
        self.monitor = PerformanceMonitor()

    def __enter__(self):
        """Context manager entry."""
        try:
            self.file = file_handle_cache.get(str(self.file_path), "r")
            return self
        except Exception as e:
            logger.error(f"Error opening HDF5 file: {e}")
            raise

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        # Don't close the file here, let the cache handle it
        self.file = None

    def get_object_info(self, obj) -> Dict[str, Any]:
        """
        Get information about an HDF5 object.

        Args:
            obj: HDF5 object (File, Group, or Dataset)

        Returns:
            Dictionary with object information
        """
        info = {
            "name": obj.name,
            "type": type(obj).__name__,
        }

        if isinstance(obj, h5py.Group):
            info["keys"] = list(obj.keys())
            info["attrs"] = dict(obj.attrs)
        elif isinstance(obj, h5py.Dataset):
            info["shape"] = obj.shape
            info["dtype"] = str(obj.dtype)
            info["size"] = obj.size
            if obj.chunks:
                info["chunks"] = obj.chunks
            info["attrs"] = dict(obj.attrs)
            # Include a small sample of the data if it's not too large
            if obj.size < 10:
                info["data"] = (
                    obj[()].tolist() if hasattr(obj[()], "tolist") else obj[()]
                )

        return info

    @monitor_performance(PerformanceMonitor())
    def read_dataset(self, dataset_path: str, **kwargs) -> Any:
        """Read a dataset with performance monitoring."""
        return self.file[dataset_path][()]  # type: ignore[index]

    @monitor_performance(PerformanceMonitor())
    def write_dataset(self, dataset_path: str, data: Any, **kwargs):
        """Write a dataset with performance monitoring."""
        if dataset_path in self.file:  # type: ignore[operator]
            del self.file[dataset_path]  # type: ignore[attr-defined]
        self.file.create_dataset(dataset_path, data=data, **kwargs)  # type: ignore[attr-defined]

    def get_performance_summary(self) -> Dict[str, Any]:
        """Get a summary of performance metrics."""
        return self.monitor.get_summary()

    def save_performance_metrics(self):
        """Save current performance metrics to disk."""
        self.monitor.save_metrics()
