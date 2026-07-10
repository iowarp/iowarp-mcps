"""
HDF5 FastMCP Resource Management

@file       resources.py
@brief      Resource manager with caching, lazy loading, and file discovery
@author     IoWarp Scientific MCPs Team
@version    2.1.0
@date       2025
@license    MIT

@description
    Part of the IoWarp MCP Server Collection for AI-powered scientific computing.

    This module implements the resource management layer for the HDF5 MCP server,
    providing efficient file handle caching, lazy loading, and automatic file
    discovery from client-provided roots.

    Key Components:
    - LRU Cache: Thread-safe caching with configurable capacity
    - LazyHDF5Proxy: Deferred file loading for efficiency
    - ResourceManager: Centralized resource tracking and cleanup
    - File Discovery: Automatic HDF5 file discovery in client roots

    Features:
    - LRU caching for 100-1000x speedup on repeated access
    - Lazy loading to minimize memory footprint
    - Thread-safe operations with locks
    - Automatic cleanup on shutdown
    - Storage index persistence
    - Client roots integration

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
import json
from pathlib import Path
from typing import Any, Dict, List, Optional
from datetime import datetime
from collections import OrderedDict
from threading import Lock
import weakref
import time
import asyncio

import h5py
import numpy as np

from .utils import HDF5Manager

logger = logging.getLogger(__name__)

# =========================================================================
# Cache Implementation
# =========================================================================


class LRUCache:
    """LRU Cache implementation for HDF5 datasets."""

    def __init__(self, capacity: int = 1000):
        self.cache: OrderedDict[str, Any] = OrderedDict()
        self.capacity = capacity
        self.lock = Lock()

    def get(self, key: str) -> Optional[Any]:
        """Get item from cache with thread safety."""
        with self.lock:
            if key not in self.cache:
                return None
            self.cache.move_to_end(key)
            return self.cache[key]

    def put(self, key: str, value: Any) -> None:
        """Put item in cache with thread safety."""
        with self.lock:
            if key in self.cache:
                self.cache.move_to_end(key)
            self.cache[key] = value
            if len(self.cache) > self.capacity:
                self.cache.popitem(last=False)


# =========================================================================
# Lazy Loading Implementation
# =========================================================================


class LazyHDF5Proxy:
    """Proxy object for lazy loading of HDF5 files."""

    def __init__(self, file_path: Path, resource_manager: "ResourceManager"):
        self._file_path = file_path
        self._resource_manager = resource_manager
        self._file: Optional[h5py.File] = None
        self._last_access = 0.0
        self._lock = Lock()

    @property
    def file(self) -> h5py.File:
        """Get the HDF5 file handle, loading it if necessary."""
        with self._lock:
            current_time = time.time()
            if self._file is None:
                try:
                    self._file = h5py.File(self._file_path, "r")
                except Exception as e:
                    logger.error(f"Error opening HDF5 file {self._file_path}: {e}")
                    return None
            self._last_access = current_time
            return self._file

    @property
    def filename(self) -> str:
        """Get the filename of the HDF5 file."""
        return str(self._file_path)

    @property
    def mode(self) -> str:
        """Get the file access mode."""
        if self.file is not None:
            return self.file.mode
        return "r"

    @property
    def attrs(self):
        """Get the attributes of the HDF5 file."""
        if self.file is not None:
            return self.file.attrs
        return None

    def __getitem__(self, key: str) -> Any:
        """Access items in the HDF5 file."""
        return self.file[key]

    def __contains__(self, key: str) -> bool:
        """Check if key exists in the HDF5 file."""
        return key in self.file

    def close(self):
        """Close the file handle if it's open."""
        with self._lock:
            if self._file is not None:
                self._file.close()
                self._file = None

    def __del__(self):
        """Close the file handle when the proxy is collected."""
        self.close()


class LazyDatasetProxy:
    """Proxy object for lazy loading of HDF5 datasets."""

    def __init__(self, file_proxy: LazyHDF5Proxy, dataset_path: str):
        self._file_proxy = file_proxy
        self._dataset_path = dataset_path
        self._dataset: Optional[h5py.Dataset] = None
        self._lock = Lock()

    @property
    def dataset(self) -> h5py.Dataset:
        """Get the dataset, loading it if necessary."""
        with self._lock:
            if self._dataset is None:
                self._dataset = self._file_proxy.file[self._dataset_path]
            return self._dataset

    @property
    def shape(self) -> tuple:
        """Get dataset shape."""
        return self.dataset.shape

    @property
    def dtype(self) -> np.dtype:
        """Get dataset dtype."""
        return self.dataset.dtype

    def __getitem__(self, key) -> np.ndarray:
        """Get data from the dataset."""
        return self.dataset[key]


# =========================================================================
# Resource Management
# =========================================================================


class ResourceManager:
    """Manages resources for the HDF5 MCP server."""

    def __init__(self, data_dir: Optional[Path] = None, cache_capacity: int = 1000):
        """
        Initialize resource manager.

        Args:
            data_dir: Directory to store metadata
            cache_capacity: Maximum number of datasets to cache
        """
        self.data_dir = data_dir or Path("data")
        self.cache_capacity = cache_capacity
        self.file_cache: LRUCache = LRUCache(capacity=cache_capacity)
        self.storage_index_path = self.data_dir / ".storage_index.json"
        self.cache_db_path = self.data_dir / ".cache_db.json"
        self.history_db_path = self.data_dir / ".history_db.json"

        # Initialize paths
        if not self.data_dir.exists():
            self.data_dir.mkdir(parents=True)
        if not self.storage_index_path.exists():
            self.storage_index_path.touch()
        if not self.cache_db_path.exists():
            self.cache_db_path.touch()
        if not self.history_db_path.exists():
            self.history_db_path.touch()

        # Initialize data structures immediately (before any operations)
        self.storage_index: Dict[str, Any] = self._load_storage_index()
        self.cache_db: Dict[str, Any] = self._load_cache_db()
        self.history_db: Dict[str, Any] = self._load_history_db()
        self.active_sessions: Dict[str, Dict[str, Any]] = {}
        self.tool_calls: Dict[str, List[Dict[str, Any]]] = {}
        self.requests: Dict[str, List[Dict[str, Any]]] = {}
        self.errors: Dict[str, List[Dict[str, Any]]] = {}
        self._lock = asyncio.Lock()

        logger.info("Resource manager initialized")

        # Storage for tracking opened HDF5 files
        self.hdf5_files: Dict[str, LazyHDF5Proxy] = {}

        # LRU cache for frequently accessed datasets
        self.dataset_cache = LRUCache(cache_capacity)

        # Weak references to open file handles
        self.file_handles: Any = weakref.WeakValueDictionary()

        # Lock for thread safety
        self.lock = Lock()

    def _load_storage_index(self) -> Dict[str, Any]:
        """Load the storage index from disk."""
        if self.storage_index_path.exists():
            try:
                with open(self.storage_index_path, "r") as f:
                    return json.load(f)
            except Exception as e:
                logger.error(f"Error loading storage index: {e}")

        # Initialize empty storage index
        return {"files": {}, "last_updated": datetime.now().isoformat()}

    def _save_storage_index(self):
        """Save the storage index to disk."""
        try:
            self.storage_index["last_updated"] = datetime.now().isoformat()
            with open(self.storage_index_path, "w") as f:
                json.dump(self.storage_index, f, indent=2)
        except Exception as e:
            logger.error(f"Error saving storage index: {e}")

    def _load_cache_db(self) -> Dict[str, Any]:
        """Load the cache database from disk."""
        if self.cache_db_path.exists():
            try:
                with open(self.cache_db_path, "r") as f:
                    return json.load(f)
            except Exception as e:
                logger.error(f"Error loading cache database: {e}")

        # Initialize empty cache database
        return {
            "datasets": {},
            "attributes": {},
            "last_updated": datetime.now().isoformat(),
        }

    def _save_cache_db(self):
        """Save the cache database to disk."""
        try:
            self.cache_db["last_updated"] = datetime.now().isoformat()
            with open(self.cache_db_path, "w") as f:
                json.dump(self.cache_db, f, indent=2)
        except Exception as e:
            logger.error(f"Error saving cache database: {e}")

    def _load_history_db(self) -> Dict[str, Any]:
        """Load the history database from disk."""
        if self.history_db_path.exists():
            try:
                with open(self.history_db_path, "r") as f:
                    return json.load(f)
            except Exception as e:
                logger.error(f"Error loading history database: {e}")

        # Initialize empty history database
        return {"sessions": [], "tool_calls": [], "requests": [], "errors": []}

    def _save_history_db(self):
        """Save the history database to disk."""
        try:
            with open(self.history_db_path, "w") as f:
                json.dump(self.history_db, f, indent=2)
        except Exception as e:
            logger.error(f"Error saving history database: {e}")

    def register_hdf5_file(self, file_path: Path) -> bool:
        """
        Register an HDF5 file in the storage index.

        Args:
            file_path: Path to the HDF5 file

        Returns:
            True if registration was successful
        """
        file_path = Path(file_path).resolve()
        if not file_path.exists():
            logger.error(f"File not found: {file_path}")
            return False

        try:
            # Get basic file information
            with HDF5Manager(file_path) as h5m:
                root_info = h5m.get_object_info(h5m.file["/"])

                # Store in storage index
                self.storage_index["files"][str(file_path)] = {
                    "path": str(file_path),
                    "uri": f"hdf5://{file_path}",
                    "last_accessed": datetime.now().isoformat(),
                    "root_info": root_info,
                }

                self._save_storage_index()
                logger.info(f"Registered HDF5 file: {file_path}")
                return True

        except Exception as e:
            logger.error(f"Error registering HDF5 file: {e}")
            return False

    def get_registered_files(self) -> List[Dict[str, Any]]:
        """
        Get a list of all registered HDF5 files.

        Returns:
            List of file information dictionaries
        """
        return list(self.storage_index["files"].values())

    def add_session(self, session_id: str, client_info: Dict[str, Any]) -> None:
        """
        Add a new session to the history database.

        Args:
            session_id: Unique session identifier
            client_info: Client information
        """
        self.history_db["sessions"].append(
            {
                "session_id": session_id,
                "client_info": client_info,
                "start_time": datetime.now().isoformat(),
                "active": True,
            }
        )
        self._save_history_db()

    def add_tool_call(
        self, session_id: str, tool_name: str, arguments: Dict[str, Any]
    ) -> None:
        """
        Record a tool call in the history database.

        Args:
            session_id: Session identifier
            tool_name: Name of the tool being called
            arguments: Tool arguments
        """
        self.history_db["tool_calls"].append(
            {
                "session_id": session_id,
                "tool_name": tool_name,
                "arguments": arguments,
                "timestamp": datetime.now().isoformat(),
            }
        )
        # Only save periodically to avoid excessive writes
        if len(self.history_db["tool_calls"]) % 10 == 0:
            self._save_history_db()

    def add_request(self, session_id: str, request_info: Dict[str, Any]) -> None:
        """
        Record a client request in the history database.

        Args:
            session_id: Session identifier
            request_info: Request information
        """
        self.history_db["requests"].append(
            {
                "session_id": session_id,
                "request_info": request_info,
                "timestamp": datetime.now().isoformat(),
            }
        )
        # Only save periodically
        if len(self.history_db["requests"]) % 10 == 0:
            self._save_history_db()

    def add_error(self, session_id: str, error_type: str, error_message: str) -> None:
        """
        Record an error in the history database.

        Args:
            session_id: Session identifier
            error_type: Type of error
            error_message: Error message
        """
        self.history_db["errors"].append(
            {
                "session_id": session_id,
                "error_type": error_type,
                "error_message": error_message,
                "timestamp": datetime.now().isoformat(),
            }
        )
        # Save immediately for errors
        self._save_history_db()

    def cache_dataset(self, file_path: str, dataset_path: str, data: Any) -> None:
        """
        Cache dataset data for quick access.

        Args:
            file_path: Path to the HDF5 file
            dataset_path: Path to the dataset within the file
            data: Dataset data or metadata to cache
        """
        key = f"{file_path}:{dataset_path}"
        self.cache_db["datasets"][key] = {
            "data": data if not hasattr(data, "tolist") else data.tolist(),
            "timestamp": datetime.now().isoformat(),
        }
        # Save periodically
        if len(self.cache_db["datasets"]) % 5 == 0:
            self._save_cache_db()

    def get_cached_dataset(self, file_path: str, dataset_path: str) -> Optional[Any]:
        """
        Get cached dataset data if available.

        Args:
            file_path: Path to the HDF5 file
            dataset_path: Path to the dataset within the file

        Returns:
            Cached data or None if not in cache
        """
        key = f"{file_path}:{dataset_path}"
        if key in self.cache_db["datasets"]:
            return self.cache_db["datasets"][key]["data"]
        return None

    def get_hdf5_file(self, file_path: str) -> Optional[LazyHDF5Proxy]:
        """
        Get a lazy-loaded HDF5 file handle.

        Args:
            file_path: Path to the HDF5 file

        Returns:
            LazyHDF5Proxy object or None if file not found
        """
        file_path = str(Path(file_path).resolve())

        with self.lock:
            if file_path not in self.hdf5_files:
                if not Path(file_path).exists():
                    logger.error(f"File not found: {file_path}")
                    return None

                # Create new lazy proxy
                self.hdf5_files[file_path] = LazyHDF5Proxy(Path(file_path), self)

            return self.hdf5_files[file_path]

    def get_dataset(
        self,
        file_path: str,
        dataset_path: str,
        start: Optional[tuple] = None,
        count: Optional[tuple] = None,
    ) -> Optional[np.ndarray]:
        """
        Get dataset from HDF5 file with lazy loading.

        Args:
            file_path: Path to HDF5 file
            dataset_path: Path to dataset within file
            start: Starting indices for slicing
            count: Number of elements to retrieve

        Returns:
            NumPy array or None if dataset not found
        """
        try:
            # Check cache first
            if start is None and count is None:
                cached_data = self.get_cached_dataset(file_path, dataset_path)
                if cached_data is not None:
                    return cached_data

            # Get file handle
            h5_file = self.get_hdf5_file(file_path)
            if h5_file is None:
                return None

            # Create dataset proxy
            dataset_proxy = LazyDatasetProxy(h5_file, dataset_path)

            # Get data
            if start is not None and count is not None:
                slices = tuple(slice(s, s + c) for s, c in zip(start, count))
                data = dataset_proxy[slices]
            else:
                data = dataset_proxy[:]

            # Cache complete datasets
            if start is None and count is None:
                self.cache_dataset(file_path, dataset_path, data)

            return data

        except Exception as e:
            logger.error(f"Error reading dataset: {e}")
            return None

    async def initialize(self):
        """Initialize the resource manager (already done in __init__)."""
        # Data structures are already loaded in __init__
        # This method exists for compatibility but does nothing
        pass

    async def shutdown(self):
        """Shutdown the resource manager and clean up resources."""
        try:
            # Save any pending changes
            self._save_storage_index()
            self._save_cache_db()
            self._save_history_db()

            # Close all open HDF5 files
            for file_proxy in self.hdf5_files.values():
                file_proxy.close()
            self.hdf5_files.clear()

            # Clear caches
            self.file_cache = LRUCache(capacity=self.cache_capacity)
            self.dataset_cache = LRUCache(self.cache_capacity)

            logger.info("Resource manager shutdown complete")
        except Exception as e:
            logger.error(f"Error during resource manager shutdown: {e}")


# =========================================================================
# File Discovery Functions
# =========================================================================


def discover_hdf5_files_in_roots(roots: List[Path]) -> List[Path]:
    """Discover all HDF5 files within client-provided roots.

    Args:
        roots: Client root directories

    Returns:
        List of discovered HDF5 file paths
    """
    patterns = ["*.h5", "*.hdf5", "*.he5"]
    discovered = []

    for root in roots:
        root_path = Path(root).resolve()

        if not root_path.exists():
            logger.warning(f"Root does not exist: {root_path}")
            continue

        logger.info(f"Scanning {root_path}")

        for pattern in patterns:
            files = list(root_path.rglob(pattern))
            discovered.extend(files)
            logger.debug(f"  Found {len(files)} {pattern} files")

    unique = sorted(set(discovered))
    logger.info(f"Total discovered: {len(unique)} HDF5 files")

    return unique
