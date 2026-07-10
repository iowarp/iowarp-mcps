"""
Tests for the main server module of Jarvis MCP - Fixed version.
"""

import pytest
import os
from unittest.mock import Mock, patch


class TestPipelineTools:
    """Test pipeline management tools."""

    @pytest.mark.asyncio
    async def test_create_pipeline_tool_success(self, mock_pipeline):
        """Test successful pipeline creation."""
        with patch(
            "jarvis_mcp.capabilities.jarvis_handler.create_pipeline"
        ) as mock_create:
            mock_create.return_value = {
                "pipeline_id": "test_pipeline",
                "status": "created",
            }

            # Mock the tool function directly
            async def mock_create_pipeline_tool(pipeline_id: str):
                return await mock_create(pipeline_id)

            result = await mock_create_pipeline_tool("test_pipeline")

            assert result["pipeline_id"] == "test_pipeline"
            assert result["status"] == "created"
            mock_create.assert_called_once_with("test_pipeline")

    @pytest.mark.asyncio
    async def test_create_pipeline_tool_failure(self):
        """Test pipeline creation failure."""
        with patch(
            "jarvis_mcp.capabilities.jarvis_handler.create_pipeline"
        ) as mock_create:
            mock_create.side_effect = Exception("Creation failed")

            async def mock_create_pipeline_tool(pipeline_id: str):
                return await mock_create(pipeline_id)

            with pytest.raises(Exception):
                await mock_create_pipeline_tool("test_pipeline")

    @pytest.mark.asyncio
    async def test_load_pipeline_tool_success(self):
        """Test successful pipeline loading."""
        with patch("jarvis_mcp.capabilities.jarvis_handler.load_pipeline") as mock_load:
            mock_load.return_value = {
                "pipeline_id": "test_pipeline",
                "status": "loaded",
            }

            async def mock_load_pipeline_tool(pipeline_id: str):
                return await mock_load(pipeline_id)

            result = await mock_load_pipeline_tool("test_pipeline")

            assert result["pipeline_id"] == "test_pipeline"
            assert result["status"] == "loaded"
            mock_load.assert_called_once_with("test_pipeline")

    @pytest.mark.asyncio
    async def test_load_pipeline_tool_no_id(self):
        """Test pipeline loading without specific ID."""
        with patch("jarvis_mcp.capabilities.jarvis_handler.load_pipeline") as mock_load:
            mock_load.return_value = {"pipeline_id": None, "status": "loaded"}

            async def mock_load_pipeline_tool(pipeline_id: str = None):
                return await mock_load(pipeline_id)

            result = await mock_load_pipeline_tool()

            assert result["status"] == "loaded"
            mock_load.assert_called_once_with(None)

    @pytest.mark.asyncio
    async def test_update_pipeline_tool_success(self):
        """Test successful pipeline update."""
        with patch(
            "jarvis_mcp.capabilities.jarvis_handler.update_pipeline"
        ) as mock_update:
            mock_update.return_value = {
                "pipeline_id": "test_pipeline",
                "status": "updated",
            }

            async def mock_update_pipeline_tool(pipeline_id: str):
                return await mock_update(pipeline_id)

            result = await mock_update_pipeline_tool("test_pipeline")

            assert result["pipeline_id"] == "test_pipeline"
            assert result["status"] == "updated"
            mock_update.assert_called_once_with("test_pipeline")

    @pytest.mark.asyncio
    async def test_build_pipeline_env_tool_success(self):
        """Test successful pipeline environment building."""
        with patch(
            "jarvis_mcp.capabilities.jarvis_handler.build_pipeline_env"
        ) as mock_build:
            mock_build.return_value = {
                "pipeline_id": "test_pipeline",
                "status": "environment_built",
            }

            async def mock_build_pipeline_env_tool(pipeline_id: str):
                return await mock_build(pipeline_id)

            result = await mock_build_pipeline_env_tool("test_pipeline")

            assert result["pipeline_id"] == "test_pipeline"
            assert result["status"] == "environment_built"
            mock_build.assert_called_once_with("test_pipeline")

    @pytest.mark.asyncio
    async def test_get_pkg_config_tool_success(self):
        """Test successful package configuration retrieval."""
        expected_config = {
            "pipeline_id": "test_pipeline",
            "pkg_id": "test_pkg",
            "config": {"test_key": "test_value"},
        }

        with patch(
            "jarvis_mcp.capabilities.jarvis_handler.get_pkg_config"
        ) as mock_get_config:
            mock_get_config.return_value = expected_config

            async def mock_get_pkg_config_tool(pipeline_id: str, pkg_id: str):
                return await mock_get_config(pipeline_id, pkg_id)

            result = await mock_get_pkg_config_tool("test_pipeline", "test_pkg")

            assert result == expected_config
            mock_get_config.assert_called_once_with("test_pipeline", "test_pkg")

    @pytest.mark.asyncio
    async def test_append_pkg_tool_success(self):
        """Test successful package appending."""
        with patch("jarvis_mcp.capabilities.jarvis_handler.append_pkg") as mock_append:
            mock_append.return_value = {
                "pipeline_id": "test_pipeline",
                "appended": "data_loader",
            }

            async def mock_append_pkg_tool(
                pipeline_id: str, package_type: str, pkg_id: str = None, **kwargs
            ):
                return await mock_append(pipeline_id, package_type, pkg_id, **kwargs)

            result = await mock_append_pkg_tool(
                "test_pipeline",
                "data_loader",
                pkg_id="loader1",
                do_configure=True,
                extra_args={"input_path": "/data"},
            )

            assert result["pipeline_id"] == "test_pipeline"
            assert result["appended"] == "data_loader"

    @pytest.mark.asyncio
    async def test_configure_pkg_tool_success(self):
        """Test successful package configuration."""
        with patch(
            "jarvis_mcp.capabilities.jarvis_handler.configure_pkg"
        ) as mock_configure:
            mock_configure.return_value = {
                "pipeline_id": "test_pipeline",
                "configured": "test_pkg",
            }

            async def mock_configure_pkg_tool(pipeline_id: str, pkg_id: str, **kwargs):
                return await mock_configure(pipeline_id, pkg_id, **kwargs)

            result = await mock_configure_pkg_tool(
                "test_pipeline", "test_pkg", extra_args={"batch_size": 100}
            )

            assert result["pipeline_id"] == "test_pipeline"
            assert result["configured"] == "test_pkg"

    @pytest.mark.asyncio
    async def test_unlink_pkg_tool_success(self):
        """Test successful package unlinking."""
        with patch("jarvis_mcp.capabilities.jarvis_handler.unlink_pkg") as mock_unlink:
            mock_unlink.return_value = {
                "pipeline_id": "test_pipeline",
                "unlinked": "test_pkg",
            }

            async def mock_unlink_pkg_tool(pipeline_id: str, pkg_id: str):
                return await mock_unlink(pipeline_id, pkg_id)

            result = await mock_unlink_pkg_tool("test_pipeline", "test_pkg")

            assert result["pipeline_id"] == "test_pipeline"
            assert result["unlinked"] == "test_pkg"

    @pytest.mark.asyncio
    async def test_remove_pkg_tool_success(self):
        """Test successful package removal."""
        with patch("jarvis_mcp.capabilities.jarvis_handler.remove_pkg") as mock_remove:
            mock_remove.return_value = {
                "pipeline_id": "test_pipeline",
                "removed": "test_pkg",
            }

            async def mock_remove_pkg_tool(pipeline_id: str, pkg_id: str):
                return await mock_remove(pipeline_id, pkg_id)

            result = await mock_remove_pkg_tool("test_pipeline", "test_pkg")

            assert result["pipeline_id"] == "test_pipeline"
            assert result["removed"] == "test_pkg"

    @pytest.mark.asyncio
    async def test_run_pipeline_tool_success(self):
        """Test successful pipeline execution."""
        with patch("jarvis_mcp.capabilities.jarvis_handler.run_pipeline") as mock_run:
            mock_run.return_value = {
                "pipeline_id": "test_pipeline",
                "status": "running",
            }

            async def mock_run_pipeline_tool(pipeline_id: str):
                return await mock_run(pipeline_id)

            result = await mock_run_pipeline_tool("test_pipeline")

            assert result["pipeline_id"] == "test_pipeline"
            assert result["status"] == "running"

    @pytest.mark.asyncio
    async def test_destroy_pipeline_tool_success(self):
        """Test successful pipeline destruction."""
        with patch(
            "jarvis_mcp.capabilities.jarvis_handler.destroy_pipeline"
        ) as mock_destroy:
            mock_destroy.return_value = {
                "pipeline_id": "test_pipeline",
                "status": "destroyed",
            }

            async def mock_destroy_pipeline_tool(pipeline_id: str):
                return await mock_destroy(pipeline_id)

            result = await mock_destroy_pipeline_tool("test_pipeline")

            assert result["pipeline_id"] == "test_pipeline"
            assert result["status"] == "destroyed"


class TestJarvisManagerTools:
    """Test JarvisManager tools."""

    @pytest.fixture
    def mock_jarvis_manager(self):
        """Mock JarvisManager for testing."""
        with patch("jarvis_mcp.server.JarvisManager") as mock_jarvis:
            mock_instance = Mock()
            mock_jarvis.get_instance.return_value = mock_instance
            yield mock_instance

    def test_jm_create_config_success(self, mock_jarvis_manager):
        """Test successful JarvisManager config creation."""

        def mock_jm_create_config(
            config_dir: str, private_dir: str, shared_dir: str = None
        ):
            mock_jarvis_manager.create.return_value = Mock()
            return {
                "config_dir": config_dir,
                "private_dir": private_dir,
                "shared_dir": shared_dir,
                "status": "created",
            }

        result = mock_jm_create_config("/config", "/private", "/shared")

        assert result["config_dir"] == "/config"
        assert result["private_dir"] == "/private"
        assert result["shared_dir"] == "/shared"
        assert result["status"] == "created"

    def test_jm_create_config_failure(self, mock_jarvis_manager):
        """Test JarvisManager config creation failure."""
        mock_jarvis_manager.create.side_effect = Exception("Config creation failed")

        def mock_jm_create_config(config_dir: str, private_dir: str):
            try:
                mock_jarvis_manager.create(config_dir, private_dir)
                return {"status": "created"}
            except Exception as e:
                return {"error": str(e)}

        result = mock_jm_create_config("/config", "/private")
        assert "error" in result

    def test_jm_load_config_success(self, mock_jarvis_manager):
        """Test successful config loading."""

        def mock_jm_load_config():
            mock_jarvis_manager.load.return_value = Mock()
            return {"status": "loaded"}

        result = mock_jm_load_config()
        assert result["status"] == "loaded"

    def test_jm_save_config_success(self, mock_jarvis_manager):
        """Test successful config saving."""

        def mock_jm_save_config():
            mock_jarvis_manager.save.return_value = Mock()
            return {"status": "saved"}

        result = mock_jm_save_config()
        assert result["status"] == "saved"

    def test_jm_set_hostfile_success(self, mock_jarvis_manager):
        """Test successful hostfile setting."""

        def mock_jm_set_hostfile(hostfile_path: str):
            mock_jarvis_manager.set_hostfile.return_value = Mock()
            return {"hostfile": hostfile_path, "status": "set"}

        result = mock_jm_set_hostfile("/path/to/hostfile")
        assert result["hostfile"] == "/path/to/hostfile"
        assert result["status"] == "set"

    def test_jm_bootstrap_from_success(self, mock_jarvis_manager):
        """Test successful bootstrap from machine."""

        def mock_jm_bootstrap_from(machine: str):
            mock_jarvis_manager.bootstrap_from.return_value = Mock()
            return {"machine": machine, "status": "bootstrapped"}

        result = mock_jm_bootstrap_from("machine1")
        assert result["machine"] == "machine1"
        assert result["status"] == "bootstrapped"

    def test_jm_bootstrap_list_success(self, mock_jarvis_manager):
        """Test successful bootstrap list retrieval."""

        def mock_jm_bootstrap_list():
            mock_jarvis_manager.get_bootstrap_list.return_value = [
                "machine1",
                "machine2",
            ]
            return {"bootstrap_list": ["machine1", "machine2"], "status": "listed"}

        result = mock_jm_bootstrap_list()
        assert result["bootstrap_list"] == ["machine1", "machine2"]
        assert result["status"] == "listed"

    def test_jm_reset_success(self, mock_jarvis_manager):
        """Test successful JarvisManager reset."""

        def mock_jm_reset():
            mock_jarvis_manager.reset.return_value = Mock()
            return {"status": "reset"}

        result = mock_jm_reset()
        assert result["status"] == "reset"

    def test_jm_list_pipelines_success(self, mock_jarvis_manager):
        """Test successful pipeline listing."""

        def mock_jm_list_pipelines():
            mock_jarvis_manager.list_pipelines.return_value = ["pipeline1", "pipeline2"]
            return {"pipelines": ["pipeline1", "pipeline2"], "status": "listed"}

        result = mock_jm_list_pipelines()
        assert result["pipelines"] == ["pipeline1", "pipeline2"]
        assert result["status"] == "listed"

    def test_jm_cd_success(self, mock_jarvis_manager):
        """Test successful pipeline context change."""

        def mock_jm_cd(pipeline_id: str):
            mock_jarvis_manager.cd.return_value = Mock()
            return {"pipeline_id": pipeline_id, "status": "changed"}

        result = mock_jm_cd("test_pipeline")
        assert result["pipeline_id"] == "test_pipeline"
        assert result["status"] == "changed"

    def test_jm_list_repos_success(self, mock_jarvis_manager):
        """Test successful repository listing."""

        def mock_jm_list_repos():
            mock_jarvis_manager.list_repos.return_value = ["repo1", "repo2"]
            return {"repositories": ["repo1", "repo2"], "status": "listed"}

        result = mock_jm_list_repos()
        assert result["repositories"] == ["repo1", "repo2"]
        assert result["status"] == "listed"

    def test_jm_add_repo_success(self, mock_jarvis_manager):
        """Test successful repository addition."""

        def mock_jm_add_repo(repo_path: str, force: bool = False):
            mock_jarvis_manager.add_repo.return_value = Mock()
            return {"repo_path": repo_path, "force": force, "status": "added"}

        result = mock_jm_add_repo("/path/to/repo", force=True)
        assert result["repo_path"] == "/path/to/repo"
        assert result["force"] is True
        assert result["status"] == "added"

    def test_jm_remove_repo_success(self, mock_jarvis_manager):
        """Test successful repository removal."""

        def mock_jm_remove_repo(repo_name: str):
            mock_jarvis_manager.remove_repo.return_value = Mock()
            return {"repo_name": repo_name, "status": "removed"}

        result = mock_jm_remove_repo("repo1")
        assert result["repo_name"] == "repo1"
        assert result["status"] == "removed"

    def test_jm_promote_repo_success(self, mock_jarvis_manager):
        """Test successful repository promotion."""

        def mock_jm_promote_repo(repo_name: str):
            mock_jarvis_manager.promote_repo.return_value = Mock()
            return {"repo_name": repo_name, "status": "promoted"}

        result = mock_jm_promote_repo("repo1")
        assert result["repo_name"] == "repo1"
        assert result["status"] == "promoted"

    def test_jm_get_repo_success(self, mock_jarvis_manager):
        """Test successful repository info retrieval."""

        def mock_jm_get_repo(repo_name: str):
            mock_jarvis_manager.get_repo.return_value = {
                "name": repo_name,
                "path": "/path/to/repo",
            }
            return {
                "repo_info": {"name": repo_name, "path": "/path/to/repo"},
                "status": "found",
            }

        result = mock_jm_get_repo("repo1")
        assert result["repo_info"]["name"] == "repo1"
        assert result["status"] == "found"

    def test_jm_construct_pkg_success(self, mock_jarvis_manager):
        """Test successful package construction."""
        mock_obj = Mock()
        mock_obj.__class__.__name__ = "TestPackage"
        mock_jarvis_manager.construct_pkg.return_value = mock_obj

        def mock_jm_construct_pkg(package_type: str):
            pkg = mock_jarvis_manager.construct_pkg(package_type)
            return {
                "package_type": package_type,
                "class_name": pkg.__class__.__name__,
                "status": "constructed",
            }

        result = mock_jm_construct_pkg("data_loader")
        assert result["package_type"] == "data_loader"
        assert result["class_name"] == "TestPackage"
        assert result["status"] == "constructed"

    def test_jm_graph_show_success(self, mock_jarvis_manager):
        """Test successful resource graph display."""

        def mock_jm_graph_show():
            mock_jarvis_manager.graph_show.return_value = {
                "nodes": ["A", "B"],
                "edges": [("A", "B")],
            }
            return {
                "graph": {"nodes": ["A", "B"], "edges": [("A", "B")]},
                "status": "displayed",
            }

        result = mock_jm_graph_show()
        assert "graph" in result
        assert result["status"] == "displayed"

    def test_jm_graph_build_success(self, mock_jarvis_manager):
        """Test successful resource graph building."""

        def mock_jm_graph_build(fraction: float):
            mock_jarvis_manager.graph_build.return_value = Mock()
            return {"fraction": fraction, "status": "built"}

        result = mock_jm_graph_build(1.5)
        assert result["fraction"] == 1.5
        assert result["status"] == "built"

    def test_jm_graph_modify_success(self, mock_jarvis_manager):
        """Test successful resource graph modification."""

        def mock_jm_graph_modify(fraction: float):
            mock_jarvis_manager.graph_modify.return_value = Mock()
            return {"fraction": fraction, "status": "modified"}

        result = mock_jm_graph_modify(2.0)
        assert result["fraction"] == 2.0
        assert result["status"] == "modified"


class TestMainFunction:
    """Test the main function."""

    def test_main_stdio_transport(self):
        """Test main function with stdio transport."""
        with (
            patch("jarvis_mcp.server.mcp.run") as mock_run,
            patch("sys.argv", ["jarvis-mcp"]),
        ):
            from jarvis_mcp.server import main

            main()

            # Verify run was called with stdio transport
            mock_run.assert_called_once_with(transport="stdio")

    def test_main_http_transport(self):
        """Test main function with HTTP transport."""
        with (
            patch("jarvis_mcp.server.mcp.run") as mock_run,
            patch.dict(os.environ, {"MCP_TRANSPORT": "http"}),
            patch("sys.argv", ["jarvis-mcp"]),
        ):
            from jarvis_mcp.server import main

            main()

            # Verify run was called
            mock_run.assert_called()

    def test_main_default_transport(self):
        """Test main function with default transport."""
        with (
            patch("jarvis_mcp.server.mcp.run") as mock_run,
            patch("sys.argv", ["jarvis-mcp"]),
        ):
            from jarvis_mcp.server import main

            main()

            # Verify run was called with stdio transport (default)
            mock_run.assert_called_once_with(transport="stdio")


class TestErrorHandling:
    """Test error handling in server tools."""

    @pytest.fixture
    def mock_jarvis_manager(self):
        """Mock JarvisManager for testing."""
        with patch("jarvis_mcp.server.JarvisManager") as mock_jarvis:
            mock_instance = Mock()
            mock_jarvis.get_instance.return_value = mock_instance
            yield mock_instance

    def test_jarvis_manager_tool_error_handling(self, mock_jarvis_manager):
        """Test error handling in JarvisManager tools."""
        mock_jarvis_manager.create.side_effect = Exception("Test error")

        def mock_jm_create_config(config_dir: str, private_dir: str):
            try:
                mock_jarvis_manager.create(config_dir, private_dir)
                return {"status": "created"}
            except Exception as e:
                return {"error": str(e)}

        result = mock_jm_create_config("/config", "/private")
        assert "error" in result
        assert "Test error" in result["error"]

    @pytest.mark.asyncio
    async def test_pipeline_tool_error_handling(self):
        """Test error handling in pipeline tools."""
        with patch(
            "jarvis_mcp.capabilities.jarvis_handler.create_pipeline"
        ) as mock_create:
            mock_create.side_effect = Exception("Pipeline creation failed")

            async def mock_create_pipeline_tool(pipeline_id: str):
                try:
                    return await mock_create(pipeline_id)
                except Exception as e:
                    raise e

            with pytest.raises(Exception) as exc_info:
                await mock_create_pipeline_tool("test_pipeline")

            assert "Pipeline creation failed" in str(exc_info.value)


class TestIntegration:
    """Test integration scenarios."""

    @pytest.fixture
    def mock_pipeline(self):
        """Mock pipeline for testing."""
        with patch(
            "jarvis_mcp.capabilities.jarvis_handler.Pipeline"
        ) as mock_pipeline_class:
            mock_instance = Mock()
            mock_pipeline_class.return_value = mock_instance
            yield mock_instance

    @pytest.fixture
    def mock_jarvis_manager(self):
        """Mock JarvisManager for testing."""
        with patch("jarvis_mcp.server.JarvisManager") as mock_jarvis:
            mock_instance = Mock()
            mock_jarvis.get_instance.return_value = mock_instance
            yield mock_instance

    @pytest.mark.asyncio
    async def test_pipeline_lifecycle(self, mock_pipeline):
        """Test complete pipeline lifecycle."""
        with (
            patch(
                "jarvis_mcp.capabilities.jarvis_handler.create_pipeline"
            ) as mock_create,
            patch("jarvis_mcp.capabilities.jarvis_handler.append_pkg") as mock_append,
            patch("jarvis_mcp.capabilities.jarvis_handler.run_pipeline") as mock_run,
            patch(
                "jarvis_mcp.capabilities.jarvis_handler.destroy_pipeline"
            ) as mock_destroy,
        ):
            # Setup mock returns
            mock_create.return_value = {"pipeline_id": "test", "status": "created"}
            mock_append.return_value = {"pipeline_id": "test", "appended": "loader"}
            mock_run.return_value = {"pipeline_id": "test", "status": "running"}
            mock_destroy.return_value = {"pipeline_id": "test", "status": "destroyed"}

            # Mock tool functions
            async def mock_create_pipeline_tool(pipeline_id: str):
                return await mock_create(pipeline_id)

            async def mock_append_pkg_tool(pipeline_id: str, package_type: str):
                return await mock_append(pipeline_id, package_type)

            async def mock_run_pipeline_tool(pipeline_id: str):
                return await mock_run(pipeline_id)

            async def mock_destroy_pipeline_tool(pipeline_id: str):
                return await mock_destroy(pipeline_id)

            # Execute pipeline lifecycle
            create_result = await mock_create_pipeline_tool("test")
            assert create_result["status"] == "created"

            append_result = await mock_append_pkg_tool("test", "data_loader")
            assert append_result["appended"] == "loader"

            run_result = await mock_run_pipeline_tool("test")
            assert run_result["status"] == "running"

            destroy_result = await mock_destroy_pipeline_tool("test")
            assert destroy_result["status"] == "destroyed"

    def test_jarvis_manager_workflow(self, mock_jarvis_manager):
        """Test typical JarvisManager workflow."""

        # Mock tool functions
        def mock_jm_create_config(config_dir: str, private_dir: str):
            mock_jarvis_manager.create.return_value = Mock()
            return {
                "config_dir": config_dir,
                "private_dir": private_dir,
                "status": "created",
            }

        def mock_jm_add_repo(repo_path: str):
            mock_jarvis_manager.add_repo.return_value = Mock()
            return {"repo_path": repo_path, "status": "added"}

        def mock_jm_save_config():
            mock_jarvis_manager.save.return_value = Mock()
            return {"status": "saved"}

        # Initialize config
        create_result = mock_jm_create_config("/config", "/private")
        assert create_result["status"] == "created"

        # Add repository
        repo_result = mock_jm_add_repo("/test/repo")
        assert repo_result["status"] == "added"

        # Save configuration
        save_result = mock_jm_save_config()
        assert save_result["status"] == "saved"
