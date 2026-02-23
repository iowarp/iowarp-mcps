"""
Basic tests to validate the test setup and core functionality.
These tests can run without external dependencies.
"""

import pytest
import asyncio
import os
from unittest.mock import Mock, patch


class TestBasicFunctionality:
    """Basic tests that don't require external dependencies."""

    def test_basic_setup(self):
        """Test that the basic test setup works."""
        assert True

    def test_python_version(self):
        """Test that we're running on a supported Python version."""
        import sys

        assert sys.version_info >= (3, 10)

    def test_asyncio_support(self):
        """Test that asyncio is working."""
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        async def test_async():
            return "async works"

        result = loop.run_until_complete(test_async())
        assert result == "async works"
        loop.close()

    @pytest.mark.asyncio
    async def test_pytest_asyncio(self):
        """Test that pytest-asyncio is working."""

        async def async_operation():
            await asyncio.sleep(0.01)
            return "pytest-asyncio works"

        result = await async_operation()
        assert result == "pytest-asyncio works"

    def test_mock_functionality(self):
        """Test that mocking works."""
        mock_obj = Mock()
        mock_obj.test_method.return_value = "mocked"

        result = mock_obj.test_method()
        assert result == "mocked"
        mock_obj.test_method.assert_called_once()

    def test_patch_functionality(self):
        """Test that patching works."""
        with patch("os.path.exists") as mock_exists:
            mock_exists.return_value = True

            result = os.path.exists("/fake/path")
            assert result is True
            mock_exists.assert_called_once_with("/fake/path")


class TestJarvisBasics:
    """Basic tests for Jarvis MCP structure."""

    def test_project_structure(self):
        """Test that the project has the expected structure."""
        # Get the project root (parent of tests directory)
        tests_dir = os.path.dirname(__file__)
        project_root = os.path.dirname(tests_dir)

        # Check for expected directories and files
        expected_paths = [
            os.path.join(project_root, "src"),
            os.path.join(project_root, "src", "jarvis_mcp", "server.py"),
            os.path.join(project_root, "src", "jarvis_mcp", "capabilities"),
            os.path.join(project_root, "pyproject.toml"),
            os.path.join(project_root, "README.md"),
        ]

        for path in expected_paths:
            assert os.path.exists(path), f"Expected path not found: {path}"

    def test_pyproject_toml_content(self):
        """Test that pyproject.toml has expected content."""
        tests_dir = os.path.dirname(__file__)
        project_root = os.path.dirname(tests_dir)
        pyproject_path = os.path.join(project_root, "pyproject.toml")

        with open(pyproject_path, "r") as f:
            content = f.read()

        # Check for key sections
        assert "[project]" in content
        assert 'name = "jarvis-mcp"' in content
        assert "fastmcp" in content
        assert "pytest" in content


class TestMockPipeline:
    """Test our mock pipeline functionality."""

    def test_mock_pipeline_creation(self):
        """Test creating a mock pipeline."""
        from tests.utils import MockPipeline

        pipeline = MockPipeline("test_pipeline")
        assert pipeline.global_id == "test_pipeline"
        assert len(pipeline.packages) == 0  # Check length instead of equality

    def test_mock_pipeline_operations(self):
        """Test mock pipeline operations."""
        from tests.utils import MockPipeline

        pipeline = MockPipeline()

        # Test chaining operations
        result = pipeline.create("test").build_env().save()
        assert result is pipeline
        assert pipeline.global_id == "test"

        # Test package operations
        pipeline.append("data_loader", pkg_id="loader1", config_value="test")
        assert "loader1" in pipeline.packages
        assert pipeline.packages["loader1"]["type"] == "data_loader"
        assert pipeline.packages["loader1"]["config"]["config_value"] == "test"


class TestMockJarvisManager:
    """Test our mock JarvisManager functionality."""

    def test_mock_manager_creation(self):
        """Test creating a mock JarvisManager."""
        from tests.utils import MockJarvisManager

        manager = MockJarvisManager()
        assert manager.pipelines == ["pipeline1", "pipeline2", "pipeline3"]
        assert manager.repositories == ["repo1", "repo2"]

    def test_mock_manager_operations(self):
        """Test mock manager operations."""
        from tests.utils import MockJarvisManager

        manager = MockJarvisManager()

        # Test configuration
        manager.create("/config", "/private", "/shared")
        assert manager.config_dir == "/config"
        assert manager.private_dir == "/private"
        assert manager.shared_dir == "/shared"

        # Test pipeline operations
        initial_count = len(manager.list_pipelines())
        manager.cd("new_pipeline")
        assert len(manager.list_pipelines()) == initial_count + 1
        assert "new_pipeline" in manager.list_pipelines()


class TestUtilities:
    """Test utility functions."""

    def test_test_data_generator(self):
        """Test the test data generator."""
        from tests.utils import TestDataGenerator

        # Test pipeline config generation
        config = TestDataGenerator.generate_pipeline_config("test_pipeline", 2)
        assert config["pipeline_id"] == "test_pipeline"
        assert len(config["packages"]) == 2
        assert "environment" in config
        assert "metadata" in config

        # Test package configs generation
        configs = TestDataGenerator.generate_package_configs(3)
        assert len(configs) == 3
        for config in configs:
            assert "pkg_id" in config
            assert "pkg_type" in config
            assert "config" in config

    def test_async_helper(self):
        """Test async helper functions."""
        from tests.utils import AsyncTestHelper

        # Test timeout functionality exists
        assert hasattr(AsyncTestHelper, "run_with_timeout")
        assert hasattr(AsyncTestHelper, "wait_for_condition")
        assert hasattr(AsyncTestHelper, "gather_with_exceptions")


class TestResponseValidation:
    """Test response validation functions."""

    def test_pipeline_response_validation(self):
        """Test pipeline response validation."""
        from tests.utils import assert_valid_pipeline_response

        valid_response = {"pipeline_id": "test_pipeline", "status": "created"}

        # Should not raise any exceptions
        assert_valid_pipeline_response(valid_response, "test_pipeline", "created")

    def test_manager_response_validation(self):
        """Test manager response validation."""
        from tests.utils import assert_valid_manager_response

        valid_response = [{"type": "text", "text": "Test message"}]

        # Should not raise any exceptions
        assert_valid_manager_response(valid_response)


@pytest.mark.integration
class TestIntegrationReadiness:
    """Test that integration testing infrastructure is ready."""

    def test_context_managers_available(self):
        """Test that context managers are available."""
        from tests.utils import temporary_directory, mock_environment

        # Test temporary directory
        with temporary_directory() as temp_dir:
            assert os.path.exists(temp_dir)
            test_file = os.path.join(temp_dir, "test.txt")
            with open(test_file, "w") as f:
                f.write("test")
            assert os.path.exists(test_file)

        # Test environment mocking
        with mock_environment(TEST_VAR="test_value"):
            assert os.environ.get("TEST_VAR") == "test_value"


@pytest.mark.performance
class TestPerformanceInfrastructure:
    """Test that performance testing infrastructure is ready."""

    def test_metrics_collection(self):
        """Test metrics collection infrastructure."""
        from tests.utils import TestMetrics

        metrics = TestMetrics()

        # Record some operations
        metrics.record_operation("test_op", 0.1, True)
        metrics.record_operation("test_op", 0.2, True)
        metrics.record_operation("test_op", 0.3, False)

        # Check metrics (using approximate comparison for floating point)
        assert (
            abs(metrics.get_average_time("test_op") - 0.15) < 1e-10
        )  # (0.1 + 0.2) / 2
        assert (
            abs(metrics.get_success_rate("test_op") - 0.6666666666666666) < 1e-10
        )  # 2/3

        summary = metrics.get_summary()
        assert "test_op" in summary
        assert summary["test_op"]["total_attempts"] == 3


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
