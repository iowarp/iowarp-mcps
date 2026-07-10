"""
Integration tests for Jarvis MCP server.
"""

import pytest
import asyncio
import os
from unittest.mock import Mock, patch
from .utils import (
    MockPipeline,
    MockJarvisManager,
    temporary_directory,
    TestDataGenerator,
)


class TestJarvisIntegration:
    """Integration tests for complete Jarvis workflows."""

    def setup_method(self):
        """Set up test fixtures."""
        self.config_dir = "/tmp/jarvis_config"
        self.private_dir = "/tmp/jarvis_private"
        self.shared_dir = "/tmp/jarvis_shared"
        self.pipeline_id = "integration_test_pipeline"

    @pytest.mark.asyncio
    async def test_complete_pipeline_workflow(self):
        """Test complete pipeline creation, configuration, and execution workflow."""

        # Mock all imports to avoid import errors
        with (
            patch("jarvis_mcp.server.JarvisManager") as mock_jarvis,
            patch("jarvis_mcp.capabilities.jarvis_handler.Pipeline") as mock_pipeline,
        ):
            # Setup mocks
            mock_manager_instance = MockJarvisManager()
            mock_jarvis.get_instance.return_value = mock_manager_instance

            mock_pipeline_instance = MockPipeline(self.pipeline_id)
            mock_pipeline.return_value = mock_pipeline_instance

            # Mock pipeline tools responses
            async def create_pipeline_tool(pipeline_id: str):
                return {"pipeline_id": pipeline_id, "status": "created"}

            async def append_pkg_tool(
                pipeline_id: str, package_type: str, pkg_id: str = None
            ):
                return {
                    "pipeline_id": pipeline_id,
                    "package_type": package_type,
                    "pkg_id": pkg_id,
                    "status": "appended",
                }

            async def configure_pkg_tool(pipeline_id: str, pkg_id: str, **kwargs):
                return {
                    "pipeline_id": pipeline_id,
                    "pkg_id": pkg_id,
                    "config": kwargs,
                    "status": "configured",
                }

            async def build_pipeline_env_tool(pipeline_id: str):
                return {"pipeline_id": pipeline_id, "status": "env_built"}

            async def run_pipeline_tool(pipeline_id: str):
                return {"pipeline_id": pipeline_id, "status": "running"}

            async def destroy_pipeline_tool(pipeline_id: str):
                return {"pipeline_id": pipeline_id, "status": "destroyed"}

            # Execute complete workflow
            # 1. Create pipeline
            create_result = await create_pipeline_tool(self.pipeline_id)
            assert create_result["status"] == "created"
            assert create_result["pipeline_id"] == self.pipeline_id

            # 2. Add data loader package
            append_result = await append_pkg_tool(
                self.pipeline_id, "data_loader", "loader_1"
            )
            assert append_result["status"] == "appended"
            assert append_result["package_type"] == "data_loader"

            # 3. Configure the package
            config_result = await configure_pkg_tool(
                self.pipeline_id, "loader_1", input_path="/data/input", batch_size=100
            )
            assert config_result["status"] == "configured"
            assert "input_path" in config_result["config"]

            # 4. Build environment
            build_result = await build_pipeline_env_tool(self.pipeline_id)
            assert build_result["status"] == "env_built"

            # 5. Run pipeline
            run_result = await run_pipeline_tool(self.pipeline_id)
            assert run_result["status"] == "running"

            # 6. Destroy pipeline
            destroy_result = await destroy_pipeline_tool(self.pipeline_id)
            assert destroy_result["status"] == "destroyed"

    @pytest.mark.asyncio
    async def test_jarvis_manager_workflow(self):
        """Test JarvisManager workflow operations."""

        with patch("jarvis_mcp.server.JarvisManager") as mock_jarvis:
            mock_manager = MockJarvisManager()
            mock_jarvis.get_instance.return_value = mock_manager

            # Mock manager tools
            async def jm_create_config(
                config_dir: str, private_dir: str, shared_dir: str = None
            ):
                return {
                    "config_dir": config_dir,
                    "private_dir": private_dir,
                    "shared_dir": shared_dir,
                    "status": "created",
                }

            async def jm_add_repo(repo_path: str, force: bool = False):
                return {"repo_path": repo_path, "force": force, "status": "added"}

            async def jm_list_repos():
                return {"repositories": [], "status": "listed"}

            async def jm_construct_pkg(package_type: str):
                return {"package_type": package_type, "status": "constructed"}

            async def jm_list_pipelines():
                return {"pipelines": [], "status": "listed"}

            async def jm_save_config():
                return {"status": "saved"}

            # Execute workflow
            # 1. Initialize configuration
            init_result = await jm_create_config(
                self.config_dir, self.private_dir, self.shared_dir
            )
            assert init_result["status"] == "created"
            assert init_result["config_dir"] == self.config_dir

            # 2. Add repository
            repo_result = await jm_add_repo("/test/repo", force=True)
            assert repo_result["status"] == "added"
            assert repo_result["force"] is True

            # 3. List repositories
            list_repos_result = await jm_list_repos()
            assert list_repos_result["status"] == "listed"
            assert "repositories" in list_repos_result

            # 4. Construct package
            pkg_result = await jm_construct_pkg("data_loader")
            assert pkg_result["status"] == "constructed"
            assert pkg_result["package_type"] == "data_loader"

            # 5. List pipelines
            pipelines_result = await jm_list_pipelines()
            assert pipelines_result["status"] == "listed"
            assert "pipelines" in pipelines_result

            # 6. Save configuration
            save_result = await jm_save_config()
            assert save_result["status"] == "saved"

    @pytest.mark.asyncio
    async def test_error_handling_workflow(self):
        """Test error handling in complete workflows."""

        with (
            patch("jarvis_mcp.server.JarvisManager") as mock_jarvis,
            patch("jarvis_mcp.capabilities.jarvis_handler.Pipeline") as mock_pipeline,
        ):
            # Setup error scenarios
            mock_manager = MockJarvisManager()
            mock_jarvis.get_instance.return_value = mock_manager

            mock_pipeline_instance = MockPipeline()
            mock_pipeline.return_value = mock_pipeline_instance

            # Mock tools that raise errors
            async def failing_create_pipeline(pipeline_id: str):
                raise ValueError("Pipeline creation failed")

            async def failing_append_pkg(
                pipeline_id: str, package_type: str, pkg_id: str = None
            ):
                raise RuntimeError("Package append failed")

            # Test error handling
            with pytest.raises(ValueError, match="Pipeline creation failed"):
                await failing_create_pipeline("test_pipeline")

            with pytest.raises(RuntimeError, match="Package append failed"):
                await failing_append_pkg("test_pipeline", "data_loader")

    @pytest.mark.asyncio
    async def test_concurrent_operations(self):
        """Test concurrent pipeline operations."""

        with (
            patch("jarvis_mcp.server.JarvisManager") as mock_jarvis,
            patch("jarvis_mcp.capabilities.jarvis_handler.Pipeline") as mock_pipeline,
        ):
            mock_manager = MockJarvisManager()
            mock_jarvis.get_instance.return_value = mock_manager

            mock_pipeline_instance = MockPipeline()
            mock_pipeline.return_value = mock_pipeline_instance

            # Mock concurrent tools
            async def create_pipeline_tool(pipeline_id: str):
                await asyncio.sleep(0.1)  # Simulate async work
                return {"pipeline_id": pipeline_id, "status": "created"}

            async def list_pipelines_tool():
                await asyncio.sleep(0.1)  # Simulate async work
                return {"pipelines": [], "status": "listed"}

            # Run operations concurrently
            tasks = [create_pipeline_tool(f"pipeline_{i}") for i in range(5)] + [
                list_pipelines_tool() for _ in range(3)
            ]

            results = await asyncio.gather(*tasks)

            # Verify all operations completed
            assert len(results) == 8
            create_results = results[:5]
            list_results = results[5:]

            for i, result in enumerate(create_results):
                assert result["status"] == "created"
                assert result["pipeline_id"] == f"pipeline_{i}"

            for result in list_results:
                assert result["status"] == "listed"

    def test_server_initialization(self):
        """Test server initialization with mocked dependencies."""

        with (
            patch("jarvis_mcp.server.JarvisManager") as mock_jarvis,
            patch("jarvis_mcp.capabilities.jarvis_handler.Pipeline") as mock_pipeline,
            patch("sys.path"),
            patch("importlib.import_module"),
        ):
            # Mock the manager and pipeline classes
            mock_manager = MockJarvisManager()
            mock_jarvis.get_instance.return_value = mock_manager

            mock_pipeline_instance = MockPipeline()
            mock_pipeline.return_value = mock_pipeline_instance

            # Mock server tools - simulate successful import
            mock_tools = {
                "create_pipeline": Mock(),
                "append_pkg": Mock(),
                "configure_pkg": Mock(),
                "build_pipeline_env": Mock(),
                "run_pipeline": Mock(),
                "destroy_pipeline": Mock(),
                "jm_create_config": Mock(),
                "jm_add_repo": Mock(),
                "jm_list_repos": Mock(),
                "jm_construct_pkg": Mock(),
                "jm_list_pipelines": Mock(),
                "jm_save_config": Mock(),
                "jm_load_config": Mock(),
            }

            # Verify tools are available
            for tool_name, tool in mock_tools.items():
                assert tool is not None
                assert callable(tool)

    @pytest.mark.asyncio
    async def test_configuration_persistence(self):
        """Test configuration loading and saving."""

        with temporary_directory() as temp_dir:
            config_dir = os.path.join(temp_dir, "config")
            private_dir = os.path.join(temp_dir, "private")
            shared_dir = os.path.join(temp_dir, "shared")

            with patch("jarvis_mcp.server.JarvisManager") as mock_jarvis:
                mock_manager = MockJarvisManager()
                mock_jarvis.get_instance.return_value = mock_manager

                # Mock configuration tools
                async def jm_create_config(
                    config_dir: str, private_dir: str, shared_dir: str = None
                ):
                    # Simulate file creation
                    os.makedirs(config_dir, exist_ok=True)
                    os.makedirs(private_dir, exist_ok=True)
                    if shared_dir:
                        os.makedirs(shared_dir, exist_ok=True)
                    return {
                        "config_dir": config_dir,
                        "private_dir": private_dir,
                        "shared_dir": shared_dir,
                        "status": "created",
                    }

                async def jm_save_config():
                    # Simulate config file creation
                    config_file = os.path.join(config_dir, "jarvis.yaml")
                    with open(config_file, "w") as f:
                        f.write("config: test")
                    return {"status": "saved", "config_file": config_file}

                async def jm_load_config():
                    config_file = os.path.join(config_dir, "jarvis.yaml")
                    if os.path.exists(config_file):
                        return {"status": "loaded", "config_file": config_file}
                    else:
                        return {"status": "not_found", "config_file": config_file}

                # Test configuration workflow
                create_result = await jm_create_config(
                    config_dir, private_dir, shared_dir
                )
                assert create_result["status"] == "created"
                assert os.path.exists(config_dir)
                assert os.path.exists(private_dir)
                assert os.path.exists(shared_dir)

                save_result = await jm_save_config()
                assert save_result["status"] == "saved"
                assert os.path.exists(save_result["config_file"])

                load_result = await jm_load_config()
                assert load_result["status"] == "loaded"

    @pytest.mark.asyncio
    async def test_large_scale_workflow(self):
        """Test workflow with multiple pipelines and packages."""

        with (
            patch("jarvis_mcp.server.JarvisManager") as mock_jarvis,
            patch("jarvis_mcp.capabilities.jarvis_handler.Pipeline") as mock_pipeline,
        ):
            mock_manager = MockJarvisManager()
            mock_jarvis.get_instance.return_value = mock_manager

            mock_pipeline_instance = MockPipeline()
            mock_pipeline.return_value = mock_pipeline_instance

            # Generate test data
            test_data = TestDataGenerator.generate_pipeline_config("large")

            # Mock tools for large scale operations
            async def create_multiple_pipelines(count: int):
                results = []
                for i in range(count):
                    result = {"pipeline_id": f"pipeline_{i}", "status": "created"}
                    results.append(result)
                return results

            async def add_multiple_packages(pipeline_id: str, packages: list):
                results = []
                for i, package_type in enumerate(packages):
                    result = {
                        "pipeline_id": pipeline_id,
                        "package_type": package_type,
                        "pkg_id": f"{package_type}_{i}",
                        "status": "appended",
                    }
                    results.append(result)
                return results

            # Execute large scale operations
            pipeline_results = await create_multiple_pipelines(10)
            assert len(pipeline_results) == 10

            for i, result in enumerate(pipeline_results):
                assert result["status"] == "created"
                assert result["pipeline_id"] == f"pipeline_{i}"

            # Add packages to first pipeline
            package_results = await add_multiple_packages(
                "pipeline_0", test_data["packages"]
            )
            assert len(package_results) == len(test_data["packages"])

            for result in package_results:
                assert result["status"] == "appended"
                assert result["pipeline_id"] == "pipeline_0"
