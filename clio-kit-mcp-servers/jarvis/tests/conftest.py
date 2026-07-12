"""
Test configuration and fixtures for Jarvis MCP tests.
"""

import pytest
import tempfile
import shutil
import os
from unittest.mock import Mock, patch
from typing import Dict, Any
from fastmcp import FastMCP


class _NativeHandle:
    def __init__(self, execution_id: str, pipeline_id: str) -> None:
        self.document = {
            "schema_version": "jarvis.execution.handle.v1",
            "execution_id": execution_id,
            "pipeline_id": pipeline_id,
            "mode": "direct",
            "scheduler_provider": None,
            "scheduler_native_id": None,
            "cluster": None,
        }

    def to_dict(self) -> dict[str, object]:
        return dict(self.document)


class _NativeRecord:
    def __init__(self, handle: _NativeHandle, *, terminal: bool) -> None:
        self.handle = handle
        self.state = "completed" if terminal else "running"
        self.terminal = terminal

    def to_dict(self) -> dict[str, object]:
        handle = self.handle.to_dict()
        return {
            "schema_version": "jarvis.execution.record.v1",
            "execution_id": handle["execution_id"],
            "pipeline_id": handle["pipeline_id"],
            "pipeline_name": handle["pipeline_id"],
            "mode": "direct",
            "scheduler_provider": None,
            "scheduler_native_id": None,
            "cluster": None,
            "state": self.state,
            "submitted": False,
            "terminal": self.terminal,
            "created_at": "2026-07-12T12:00:00Z",
            "updated_at": "2026-07-12T12:01:00Z",
            "return_code": 0 if self.terminal else None,
            "error": None,
            "metadata": {},
        }


@pytest.fixture(autouse=True)
def reset_server_manager_cache():
    """Clear the lazy server manager cache around every test."""
    with patch("jarvis_mcp.server._manager", None):
        yield


@pytest.fixture
def temp_dir():
    """Create a temporary directory for test files."""
    temp_dir = tempfile.mkdtemp()
    yield temp_dir
    shutil.rmtree(temp_dir)


@pytest.fixture
def mock_jarvis_manager():
    """Mock JarvisManager instance."""
    with (
        patch("jarvis_mcp.server.JarvisManager") as mock_manager_class,
        patch("jarvis_mcp.server._manager", None),
        patch("jarvis_mcp.server.manager", None),
    ):
        mock_manager = Mock()
        mock_manager_class.get_instance.return_value = mock_manager

        # Mock common methods
        mock_manager.create.return_value = None
        mock_manager.save.return_value = None
        mock_manager.load.return_value = None
        mock_manager.set_hostfile.return_value = None
        mock_manager.bootstrap_from.return_value = None
        mock_manager.bootstrap_list.return_value = ["machine1", "machine2"]
        mock_manager.reset.return_value = None
        mock_manager.list_pipelines.return_value = ["pipeline1", "pipeline2"]
        mock_manager.cd.return_value = None
        mock_manager.list_repos.return_value = ["repo1", "repo2"]
        mock_manager.add_repo.return_value = None
        mock_manager.remove_repo.return_value = None
        mock_manager.promote_repo.return_value = None
        mock_manager.get_repo.return_value = Mock()
        mock_manager.construct_pkg.return_value = Mock()
        mock_manager.resource_graph_show.return_value = None
        mock_manager.resource_graph_build.return_value = None
        mock_manager.resource_graph_modify.return_value = None

        yield mock_manager


@pytest.fixture
def mock_pipeline():
    """Mock Pipeline instance."""
    with patch(
        "jarvis_mcp.capabilities.jarvis_handler.Pipeline"
    ) as mock_pipeline_class:
        mock_pipeline = Mock()
        mock_pipeline_class.return_value = mock_pipeline

        # Make methods chainable
        mock_pipeline.create.return_value = mock_pipeline
        mock_pipeline.load.return_value = mock_pipeline
        mock_pipeline.build_env.return_value = mock_pipeline
        mock_pipeline.save.return_value = mock_pipeline
        mock_pipeline.append.return_value = mock_pipeline
        mock_pipeline.configure.return_value = None
        mock_pipeline.unlink.return_value = mock_pipeline
        mock_pipeline.remove.return_value = mock_pipeline
        mock_pipeline.destroy.return_value = None
        mock_pipeline.update.return_value = None

        # Mock pipeline attributes
        mock_pipeline.global_id = "test_pipeline"
        mock_pipeline.config_path = (
            "/tmp/jarvis-config/test_pipeline/test_pipeline.yaml"
        )
        mock_pipeline.env_path = "/tmp/jarvis-config/test_pipeline/env.yaml"
        mock_pipeline.config = {"sub_pkgs": [["builtin.lammps", "lammps"]]}
        mock_pipeline.env = {"PATH": "/usr/bin"}

        # Mock get_pkg method
        mock_pkg = Mock()
        mock_pkg.pkg_id = "lammps"
        mock_pkg.pkg_type = "builtin.lammps"
        mock_pkg.global_id = "test_pipeline.lammps"
        mock_pkg.config_path = "/tmp/jarvis-config/test_pipeline/lammps/lammps.yaml"
        mock_pkg.config = {"test_config": "test_value"}
        mock_pipeline.get_pkg.return_value = mock_pkg
        mock_pipeline.sub_pkgs = [mock_pkg]

        records: dict[str, _NativeRecord] = {}

        def run(*, execution_id: str, wait: bool) -> _NativeHandle:
            handle = _NativeHandle(execution_id, "test_pipeline")
            records[execution_id] = _NativeRecord(handle, terminal=wait)
            return handle

        def get_execution(execution_id: str) -> _NativeRecord:
            return records[execution_id]

        def get_progress(execution_id: str) -> dict[str, object]:
            record = records[execution_id]
            return {
                "schema_version": "jarvis.execution.progress.v1",
                "execution_id": execution_id,
                "pipeline_id": "test_pipeline",
                "execution_state": record.state,
                "terminal": record.terminal,
                "packages": [],
            }

        mock_pipeline.run.side_effect = run
        mock_pipeline.get_execution.side_effect = get_execution
        mock_pipeline.get_execution_progress.side_effect = get_progress

        yield mock_pipeline


@pytest.fixture
def sample_pipeline_data():
    """Sample pipeline data for tests."""
    return {
        "pipeline_id": "test_pipeline",
        "packages": [
            {"pkg_type": "data_loader", "pkg_id": "loader1"},
            {"pkg_type": "processor", "pkg_id": "proc1"},
        ],
        "config": {
            "environment": {"CMAKE_PREFIX_PATH": "/usr/local", "PATH": "/usr/bin"},
            "settings": {"debug": True, "verbose": False},
        },
    }


@pytest.fixture
def sample_package_config():
    """Sample package configuration for tests."""
    return {
        "pkg_id": "test_package",
        "pkg_type": "data_loader",
        "config": {
            "input_path": "/data/input",
            "output_path": "/data/output",
            "batch_size": 100,
            "parallel": True,
        },
    }


@pytest.fixture
def mock_fastmcp():
    """Mock FastMCP instance."""
    with patch("jarvis_mcp.server.FastMCP") as mock_mcp_class:
        mock_mcp = Mock(spec=FastMCP)
        mock_mcp_class.return_value = mock_mcp
        yield mock_mcp


@pytest.fixture
def mock_environment_vars():
    """Mock environment variables for testing."""
    env_vars = {
        "MCP_TRANSPORT": "stdio",
        "MCP_HTTP_HOST": "127.0.0.1",
        "MCP_HTTP_PORT": "8000",
    }

    with patch.dict(os.environ, env_vars):
        yield env_vars


@pytest.fixture
def error_scenarios():
    """Common error scenarios for testing."""
    return {
        "pipeline_not_found": Exception("Pipeline 'nonexistent' not found"),
        "package_not_found": Exception("Package 'nonexistent' not found"),
        "configuration_error": Exception("Invalid configuration provided"),
        "permission_error": PermissionError("Access denied"),
        "connection_error": ConnectionError("Failed to connect to service"),
        "timeout_error": TimeoutError("Operation timed out"),
    }


class MockAsyncContext:
    """Helper class for async context management in tests."""

    def __init__(self, return_value=None, exception=None):
        self.return_value = return_value
        self.exception = exception

    async def __aenter__(self):
        if self.exception:
            raise self.exception
        return self.return_value

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        return False


def create_mock_response(status: str, data: Dict[str, Any] = None) -> Dict[str, Any]:
    """Create a standardized mock response."""
    response = {"status": status}
    if data:
        response.update(data)
    return response


@pytest.fixture
def mock_dotenv():
    """Mock dotenv loading."""
    with patch("jarvis_mcp.server.load_dotenv") as mock_load:
        mock_load.return_value = True
        yield mock_load
