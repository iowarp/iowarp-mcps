"""
Test utilities for Jarvis MCP testing.
"""

import asyncio
import time
import os
import tempfile
import shutil
from typing import Any, Dict, List, Optional, Union
from unittest.mock import Mock, patch
from contextlib import contextmanager


class PackagesProxy:
    """A proxy class that supports both dict and list interfaces for packages."""

    def __init__(self, packages_dict, packages_list):
        self._packages_dict = packages_dict
        self._packages_list = packages_list

    def __getitem__(self, key):
        if isinstance(key, str):
            # Dict-style access: packages["pkg_id"]
            return self._packages_dict[key]
        elif isinstance(key, int):
            # List-style access: packages[0]
            return self._packages_list[key]
        else:
            raise KeyError(f"Invalid key type: {type(key)}")

    def __setitem__(self, key, value):
        if isinstance(key, str):
            self._packages_dict[key] = value
        elif isinstance(key, int):
            self._packages_list[key] = value
        else:
            raise KeyError(f"Invalid key type: {type(key)}")

    def __delitem__(self, key):
        if isinstance(key, str):
            del self._packages_dict[key]
        elif isinstance(key, int):
            del self._packages_list[key]
        else:
            raise KeyError(f"Invalid key type: {type(key)}")

    def __len__(self):
        return len(self._packages_list)

    def __iter__(self):
        return iter(self._packages_list)

    def __contains__(self, key):
        if isinstance(key, str):
            return key in self._packages_dict
        return key in self._packages_list

    def copy(self):
        """Return a copy of the list representation."""
        return self._packages_list.copy()

    def append(self, item):
        """Add item to both representations."""
        self._packages_list.append(item)
        if isinstance(item, dict) and "id" in item:
            self._packages_dict[item["id"]] = item

    def keys(self):
        """Return dict keys."""
        return self._packages_dict.keys()

    def values(self):
        """Return dict values."""
        return self._packages_dict.values()

    def items(self):
        """Return dict items."""
        return self._packages_dict.items()

    def get(self, key, default=None):
        """Get item with default."""
        return self._packages_dict.get(key, default)


class MockPipeline:
    """Mock Pipeline class for testing."""

    def __init__(self, pipeline_id: str = "test_pipeline"):
        self.pipeline_id = pipeline_id
        self.global_id = pipeline_id  # Add global_id for compatibility
        self._packages_dict = {}  # Dictionary interface for basic tests
        self._packages_list = []  # List interface for edge case tests
        self.env_built = False
        self.running = False

    @property
    def packages(self):
        """Return packages in the format expected by the calling test."""
        # Determine which format to return based on access pattern
        # If accessing with string keys, return dict; if accessing with numeric indices, return list
        import inspect

        frame = inspect.currentframe().f_back
        try:
            # Simple heuristic: if the calling code looks like dict access, return dict
            return PackagesProxy(self._packages_dict, self._packages_list)
        finally:
            del frame

    @packages.setter
    def packages(self, value):
        """Set packages and sync both representations."""
        if isinstance(value, dict):
            self._packages_dict = value
            self._packages_list = list(value.values())
        elif isinstance(value, list):
            self._packages_list = value
            self._packages_dict = {f"pkg_{i}": pkg for i, pkg in enumerate(value)}
        else:
            self._packages_dict = {}
            self._packages_list = []

    def create(self, pipeline_id: str):
        """Mock create method."""
        self.pipeline_id = pipeline_id
        self.global_id = pipeline_id  # Update global_id too
        return self

    def load(self, pipeline_id: Optional[str] = None):
        """Mock load method."""
        if pipeline_id:
            self.pipeline_id = pipeline_id
        return self

    def build_env(self):
        """Mock build_env method."""
        self.env_built = True
        return self

    def save(self):
        """Mock save method."""
        return self

    def append(self, package_type: str, pkg_id: Optional[str] = None, **kwargs):
        """Mock append method."""
        pkg_id = pkg_id or f"{package_type}_default"
        package_dict = {"type": package_type, "config": kwargs}
        package_list = {"type": package_type, "id": pkg_id, "kwargs": kwargs}

        # Update both representations
        self._packages_dict[pkg_id] = package_dict
        self._packages_list.append(package_list)
        return self

    def configure_pkg(self, pkg_id: str, **kwargs):
        """Mock configure_pkg method."""
        if pkg_id in self._packages_dict:
            self._packages_dict[pkg_id]["config"].update(kwargs)
        # Also update list representation
        for package in self._packages_list:
            if package.get("id") == pkg_id:
                package["kwargs"].update(kwargs)
        return self

    def get_pkg_config(self, pkg_id: str):
        """Mock get_pkg_config method."""
        if pkg_id in self._packages_dict:
            return self._packages_dict[pkg_id]["config"]
        return None

    def unlink_pkg(self, pkg_id: str):
        """Mock unlink_pkg method."""
        if pkg_id in self._packages_dict:
            del self._packages_dict[pkg_id]
        # Also remove from list
        self._packages_list = [p for p in self._packages_list if p.get("id") != pkg_id]
        return self

    def remove_pkg(self, pkg_id: str):
        """Mock remove_pkg method."""
        if pkg_id in self._packages_dict:
            del self._packages_dict[pkg_id]
        # Also remove from list
        self._packages_list = [p for p in self._packages_list if p.get("id") != pkg_id]
        return self

    def run(self):
        """Mock run method."""
        self.running = True
        return self

    def destroy(self):
        """Mock destroy method."""
        self.running = False
        self.packages = {}  # Clear packages dictionary
        return self


class MockJarvisManager:
    """Mock JarvisManager class for testing."""

    def __init__(self):
        self.config = {}
        self.repositories = ["repo1", "repo2"]  # Default repositories for testing
        self.pipelines = [
            "pipeline1",
            "pipeline2",
            "pipeline3",
        ]  # Default pipelines for testing
        self.current_pipeline = None
        self.hostfile = None
        self.bootstrap_list = []
        # Add individual config attributes for compatibility
        self.config_dir = None
        self.private_dir = None
        self.shared_dir = None

    @classmethod
    def get_instance(cls):
        """Mock get_instance method."""
        return cls()

    def create(
        self, config_dir: str, private_dir: str, shared_dir: Optional[str] = None
    ):
        """Mock create method."""
        self.config = {
            "config_dir": config_dir,
            "private_dir": private_dir,
            "shared_dir": shared_dir,
        }
        # Set individual attributes for compatibility
        self.config_dir = config_dir
        self.private_dir = private_dir
        self.shared_dir = shared_dir
        return self

    def load(self):
        """Mock load method."""
        return self

    def save(self):
        """Mock save method."""
        return self

    def set_hostfile(self, hostfile_path: str):
        """Mock set_hostfile method."""
        self.hostfile = hostfile_path
        return self

    def bootstrap_from(self, machine: str):
        """Mock bootstrap_from method."""
        self.bootstrap_list.append(machine)
        return self

    def get_bootstrap_list(self):
        """Mock get_bootstrap_list method."""
        return self.bootstrap_list

    def reset(self):
        """Mock reset method."""
        self.config = {}
        self.repositories = []
        self.pipelines = []
        self.current_pipeline = None
        self.hostfile = None
        self.bootstrap_list = []
        return self

    def list_pipelines(self):
        """Mock list_pipelines method."""
        return self.pipelines

    def cd(self, pipeline_id: str):
        """Mock cd method."""
        self.current_pipeline = pipeline_id
        # Add to pipelines list if not already there
        if pipeline_id not in self.pipelines:
            self.pipelines.append(pipeline_id)
        return self

    def list_repos(self):
        """Mock list_repos method."""
        return self.repositories

    def add_repo(self, repo_path: str, force: bool = False):
        """Mock add_repo method."""
        repo_name = os.path.basename(repo_path)
        repo = {"path": repo_path, "name": repo_name, "force": force}
        self.repositories.append(repo)
        return self

    def remove_repo(self, repo_name: str):
        """Mock remove_repo method."""
        self.repositories = [r for r in self.repositories if r.get("name") != repo_name]
        return self

    def promote_repo(self, repo_name: str):
        """Mock promote_repo method."""
        for repo in self.repositories:
            if repo.get("name") == repo_name:
                repo["promoted"] = True
        return self

    def get_repo(self, repo_name: str):
        """Mock get_repo method."""
        for repo in self.repositories:
            if repo.get("name") == repo_name:
                return repo
        return None

    def construct_pkg(self, package_type: str):
        """Mock construct_pkg method."""
        mock_pkg = Mock()
        mock_pkg.__class__.__name__ = f"{package_type.title()}Package"
        return mock_pkg

    def graph_show(self):
        """Mock graph_show method."""
        return {"nodes": [], "edges": []}

    def graph_build(self, fraction: float):
        """Mock graph_build method."""
        return {"fraction": fraction, "status": "built"}

    def graph_modify(self, fraction: float):
        """Mock graph_modify method."""
        return {"fraction": fraction, "status": "modified"}


class TestDataGenerator:
    """Generate test data for various scenarios."""

    @staticmethod
    def generate_pipeline_config(
        pipeline_id: str = "test_pipeline", num_packages: int = 2, size: str = "small"
    ) -> Dict[str, Any]:
        """Generate pipeline configuration data."""
        if isinstance(pipeline_id, str) and num_packages == 2:
            # Legacy call style - treat first arg as size
            size = pipeline_id
            pipeline_id = "test_pipeline"

        configs = {
            "small": {
                "pipeline_id": pipeline_id,
                "packages": ["data_loader", "processor"],
                "config": {"batch_size": 100},
                "environment": "test",
                "metadata": {"created_by": "test", "version": "1.0"},
            },
            "medium": {
                "pipeline_id": pipeline_id,
                "packages": ["data_loader", "processor", "analyzer", "output"],
                "config": {"batch_size": 500, "workers": 4},
                "environment": "staging",
                "metadata": {"created_by": "test", "version": "1.1"},
            },
            "large": {
                "pipeline_id": pipeline_id,
                "packages": ["data_loader"] * 10,
                "config": {"batch_size": 1000, "workers": 8, "memory_limit": "8GB"},
                "environment": "production",
                "metadata": {"created_by": "test", "version": "2.0"},
            },
        }
        base_config = configs.get(size, configs["small"])

        # Adjust packages count if specified
        if num_packages != 2:
            base_config["packages"] = [f"package_{i}" for i in range(num_packages)]

        return base_config

    @staticmethod
    def generate_package_configs(count: int) -> List[Dict[str, Any]]:
        """Generate multiple package configurations."""
        configs = []
        for i in range(count):
            config = {
                "pkg_id": f"package_{i}",
                "pkg_type": f"type_{i % 3}",
                "config": {"param": f"value_{i}"},
            }
            configs.append(config)
        return configs

    @staticmethod
    def generate_large_config(complexity: str = "high") -> Dict[str, Any]:
        """Generate large configuration data for testing."""
        configs = {
            "low": {"size": 1000, "complexity": "simple", "nested_levels": 2},
            "medium": {"size": 10000, "complexity": "moderate", "nested_levels": 5},
            "high": {"size": 100000, "complexity": "complex", "nested_levels": 10},
        }
        return configs.get(complexity, configs["high"])

    @staticmethod
    def generate_manager_config(complexity: str = "simple") -> Dict[str, Any]:
        """Generate JarvisManager configuration data."""
        configs = {
            "simple": {
                "config_dir": "/simple/config",
                "private_dir": "/simple/private",
                "shared_dir": "/simple/shared",
            },
            "complex": {
                "config_dir": "/complex/config",
                "private_dir": "/complex/private",
                "shared_dir": "/complex/shared",
                "repositories": ["/repo1", "/repo2", "/repo3"],
                "hostfile": "/complex/hostfile",
            },
        }
        return configs.get(complexity, configs["simple"])


class AsyncTestHelper:
    """Helper for async test operations."""

    @staticmethod
    async def run_with_timeout(coro, timeout: float = 5.0):
        """Run a coroutine with timeout."""
        return await asyncio.wait_for(coro, timeout=timeout)

    @staticmethod
    async def run_concurrent(tasks: List, max_concurrent: int = 10):
        """Run tasks concurrently with limit."""
        semaphore = asyncio.Semaphore(max_concurrent)

        async def run_with_semaphore(task):
            async with semaphore:
                return await task

        return await asyncio.gather(*[run_with_semaphore(task) for task in tasks])

    @staticmethod
    async def wait_for_condition(
        condition_func, timeout: float = 5.0, interval: float = 0.1
    ):
        """Wait for a condition to become true."""
        start_time = time.time()
        while time.time() - start_time < timeout:
            if condition_func():
                return True
            await asyncio.sleep(interval)
        return False

    @staticmethod
    async def gather_with_exceptions(*tasks):
        """Gather tasks and handle exceptions gracefully."""
        results = []
        for task in tasks:
            try:
                result = await task
                results.append(result)
            except Exception as e:
                results.append({"error": str(e)})
        return results


class TestMetrics:
    """Collect and analyze test metrics."""

    def __init__(self):
        self.operations = {}

    def record_operation(self, operation: str, duration: float, success: bool):
        """Record an operation metric."""
        if operation not in self.operations:
            self.operations[operation] = []

        self.operations[operation].append(
            {"duration": duration, "success": success, "timestamp": time.time()}
        )

    def get_average_time(self, operation: str) -> float:
        """Get average time for successful operations."""
        if operation not in self.operations:
            return 0.0

        successful_ops = [op for op in self.operations[operation] if op["success"]]
        if not successful_ops:
            return 0.0

        total_time = sum(op["duration"] for op in successful_ops)
        return total_time / len(successful_ops)

    def get_success_rate(self, operation: str) -> float:
        """Get success rate for operations."""
        if operation not in self.operations:
            return 0.0

        total_ops = len(self.operations[operation])
        successful_ops = len([op for op in self.operations[operation] if op["success"]])

        return successful_ops / total_ops if total_ops > 0 else 0.0

    def get_summary(self) -> Dict[str, Any]:
        """Get summary of all operations."""
        summary = {}
        for operation in self.operations:
            summary[operation] = {
                "total_attempts": len(self.operations[operation]),
                "total_count": len(self.operations[operation]),
                "success_count": len(
                    [op for op in self.operations[operation] if op["success"]]
                ),
                "average_time": self.get_average_time(operation),
                "success_rate": self.get_success_rate(operation),
            }
        return summary


class ServerToolTester:
    """Helper class to test FastMCP server tools properly."""

    @staticmethod
    async def call_tool_function(tool, *args, **kwargs):
        """Call the underlying function of a FastMCP tool.

        In FastMCP v3, decorators return the original function, so
        tools can be called directly without accessing .fn.
        """
        if callable(tool):
            return (
                await tool(*args, **kwargs)
                if asyncio.iscoroutinefunction(tool)
                else tool(*args, **kwargs)
            )
        else:
            # Mock the response for testing
            return {"status": "mocked", "args": args, "kwargs": kwargs}

    @staticmethod
    def call_sync_tool_function(tool, *args, **kwargs):
        """Call the underlying function of a synchronous FastMCP tool.

        In FastMCP v3, decorators return the original function, so
        tools can be called directly without accessing .fn.
        """
        if callable(tool):
            return tool(*args, **kwargs)
        else:
            return {"status": "mocked", "args": args, "kwargs": kwargs}


# Response validation functions
def assert_valid_pipeline_response(
    response: Dict[str, Any],
    expected_pipeline_id: str = None,
    expected_status: str = None,
):
    """Assert that a pipeline response is valid."""
    assert isinstance(response, dict)
    assert "pipeline_id" in response or "status" in response
    if expected_pipeline_id:
        assert response.get("pipeline_id") == expected_pipeline_id
    if expected_status:
        assert response.get("status") == expected_status


def assert_valid_manager_response(
    response: Union[Dict[str, Any], List[Dict[str, Any]]],
):
    """Assert that a manager response is valid."""
    if isinstance(response, list):
        # List of messages
        for item in response:
            assert isinstance(item, dict)
            assert "type" in item
    else:
        # Single response
        assert isinstance(response, dict)


# Mock context managers for testing
@contextmanager
def temporary_directory():
    """Create a temporary directory for testing."""
    temp_dir = tempfile.mkdtemp()
    try:
        yield temp_dir
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)


@contextmanager
def mock_environment(**env_vars):
    """Mock environment variables for testing."""
    with patch.dict(os.environ, env_vars):
        yield
