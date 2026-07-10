"""
Direct tests for server.py tool functions to achieve >90% coverage.
Tests actual function bodies by patching handlers at the capabilities layer.
"""

import pytest
from unittest.mock import Mock, patch
from fastmcp.exceptions import ToolError
from fastmcp.prompts import Message


class TestServerProfiles:
    """Test user/admin profile filtering."""

    def test_apply_user_profile_removes_admin_tools(self):
        """User profile keeps pipeline authoring tools and hides admin tools."""
        from jarvis_mcp.server import apply_tool_profile

        class Tool:
            def __init__(self, name):
                self.name = name

        tools = [Tool("create_pipeline"), Tool("jm_reset"), Tool("export_pipeline")]
        with patch("jarvis_mcp.server.mcp") as mock_mcp:
            mock_mcp.list_tools.return_value = tools

            apply_tool_profile("user")

            mock_mcp.remove_tool.assert_called_once_with("jm_reset")

    def test_apply_admin_profile_removes_user_tools(self):
        """Admin profile keeps manager tools and hides user pipeline authoring."""
        from jarvis_mcp.server import apply_tool_profile

        class Tool:
            def __init__(self, name):
                self.name = name

        tools = [Tool("create_pipeline"), Tool("jm_reset"), Tool("jm_add_repo")]
        with patch("jarvis_mcp.server.mcp") as mock_mcp:
            mock_mcp.list_tools.return_value = tools

            apply_tool_profile("admin")

            mock_mcp.remove_tool.assert_called_once_with("create_pipeline")


class TestPipelineToolsDirect:
    """Test pipeline tool implementations directly."""

    @pytest.mark.asyncio
    async def test_update_pipeline_tool_direct(self):
        """Test update_pipeline_tool with mocked handler."""
        with patch("jarvis_mcp.server.update_pipeline") as mock_handler:
            mock_handler.return_value = {"pipeline_id": "test", "status": "updated"}

            # Import and call after patching
            from jarvis_mcp.server import update_pipeline_tool

            result = await update_pipeline_tool("test")

            assert result["pipeline_id"] == "test"
            mock_handler.assert_called_once()

    @pytest.mark.asyncio
    async def test_build_pipeline_env_tool_direct(self):
        """Test build_pipeline_env_tool with mocked handler."""
        with patch("jarvis_mcp.server.build_pipeline_env") as mock_handler:
            mock_handler.return_value = {
                "pipeline_id": "test",
                "status": "environment_built",
            }

            from jarvis_mcp.server import build_pipeline_env_tool

            result = await build_pipeline_env_tool("test")

            assert result["status"] == "environment_built"
            mock_handler.assert_called_once()

    @pytest.mark.asyncio
    async def test_create_pipeline_tool_direct(self):
        """Test create_pipeline_tool with mocked handler."""
        with patch("jarvis_mcp.server.create_pipeline") as mock_handler:
            mock_handler.return_value = {"pipeline_id": "new", "status": "created"}

            from jarvis_mcp.server import create_pipeline_tool

            result = await create_pipeline_tool("new")

            assert result["pipeline_id"] == "new"
            mock_handler.assert_called_once()

    @pytest.mark.asyncio
    async def test_load_pipeline_tool_direct(self):
        """Test load_pipeline_tool with mocked handler."""
        with patch("jarvis_mcp.server.load_pipeline") as mock_handler:
            mock_handler.return_value = {"pipeline_id": "loaded", "status": "loaded"}

            from jarvis_mcp.server import load_pipeline_tool

            result = await load_pipeline_tool("loaded")

            assert result["status"] == "loaded"
            mock_handler.assert_called_once()

    @pytest.mark.asyncio
    async def test_load_pipeline_tool_no_id_direct(self):
        """Test load_pipeline_tool without ID."""
        with patch("jarvis_mcp.server.load_pipeline") as mock_handler:
            mock_handler.return_value = {"pipeline_id": None, "status": "loaded"}

            from jarvis_mcp.server import load_pipeline_tool

            result = await load_pipeline_tool(None)

            assert result["status"] == "loaded"
            mock_handler.assert_called_once()

    @pytest.mark.asyncio
    async def test_export_pipeline_tool_direct(self):
        """Test export_pipeline_tool with mocked handler."""
        with patch("jarvis_mcp.server.export_pipeline") as mock_handler:
            mock_handler.return_value = {
                "pipeline_id": "test",
                "packages": [{"pkg_id": "lammps"}],
            }

            from jarvis_mcp.server import export_pipeline_tool

            result = await export_pipeline_tool("test", include_yaml=False)

            assert result["pipeline_id"] == "test"
            assert result["packages"] == [{"pkg_id": "lammps"}]
            mock_handler.assert_called_once_with("test", include_yaml=False)

    @pytest.mark.asyncio
    async def test_get_pkg_config_tool_direct(self):
        """Test get_pkg_config_tool with mocked handler."""
        with patch("jarvis_mcp.server.get_pkg_config") as mock_handler:
            mock_handler.return_value = {
                "pipeline_id": "test",
                "pkg_id": "pkg1",
                "config": {},
            }

            from jarvis_mcp.server import get_pkg_config_tool

            result = await get_pkg_config_tool("test", "pkg1")

            assert result["pkg_id"] == "pkg1"
            mock_handler.assert_called_once()

    @pytest.mark.asyncio
    async def test_append_pkg_tool_direct(self):
        """Test append_pkg_tool with mocked handler."""
        with patch("jarvis_mcp.server.append_pkg") as mock_handler:
            mock_handler.return_value = {"pipeline_id": "test", "appended": "pkg"}

            from jarvis_mcp.server import append_pkg_tool

            result = await append_pkg_tool("test", "pkg_type")

            assert result["appended"] == "pkg"
            mock_handler.assert_called_once()

    @pytest.mark.asyncio
    async def test_append_pkg_tool_with_args_direct(self):
        """Test append_pkg_tool with optional args."""
        with patch("jarvis_mcp.server.append_pkg") as mock_handler:
            mock_handler.return_value = {"pipeline_id": "test", "appended": "pkg"}

            from jarvis_mcp.server import append_pkg_tool

            result = await append_pkg_tool(
                "test",
                "pkg_type",
                pkg_id="pkg1",
                do_configure=False,
                extra_args={"key": "val"},
            )

            assert result["appended"] == "pkg"
            mock_handler.assert_called_once()

    @pytest.mark.asyncio
    async def test_configure_pkg_tool_direct(self):
        """Test configure_pkg_tool with mocked handler."""
        with patch("jarvis_mcp.server.configure_pkg") as mock_handler:
            mock_handler.return_value = {"pipeline_id": "test", "configured": "pkg"}

            from jarvis_mcp.server import configure_pkg_tool

            result = await configure_pkg_tool("test", "pkg")

            assert result["configured"] == "pkg"
            mock_handler.assert_called_once()

    @pytest.mark.asyncio
    async def test_unlink_pkg_tool_direct(self):
        """Test unlink_pkg_tool with mocked handler."""
        with patch("jarvis_mcp.server.unlink_pkg") as mock_handler:
            mock_handler.return_value = {"pipeline_id": "test", "unlinked": "pkg"}

            from jarvis_mcp.server import unlink_pkg_tool

            result = await unlink_pkg_tool("test", "pkg")

            assert result["unlinked"] == "pkg"
            mock_handler.assert_called_once()

    @pytest.mark.asyncio
    async def test_remove_pkg_tool_direct(self):
        """Test remove_pkg_tool with mocked handler."""
        with patch("jarvis_mcp.server.remove_pkg") as mock_handler:
            mock_handler.return_value = {"pipeline_id": "test", "removed": "pkg"}

            from jarvis_mcp.server import remove_pkg_tool

            result = await remove_pkg_tool("test", "pkg")

            assert result["removed"] == "pkg"
            mock_handler.assert_called_once()

    @pytest.mark.asyncio
    async def test_run_pipeline_tool_direct(self):
        """Test run_pipeline_tool with mocked handler."""
        with patch("jarvis_mcp.server.run_pipeline") as mock_handler:
            mock_handler.return_value = {"pipeline_id": "test", "status": "running"}

            from jarvis_mcp.server import run_pipeline_tool

            result = await run_pipeline_tool("test")

            assert result["status"] == "running"
            mock_handler.assert_called_once()

    @pytest.mark.asyncio
    async def test_destroy_pipeline_tool_direct(self):
        """Test destroy_pipeline_tool with mocked handler."""
        with patch("jarvis_mcp.server.destroy_pipeline") as mock_handler:
            mock_handler.return_value = {"pipeline_id": "test", "status": "destroyed"}

            from jarvis_mcp.server import destroy_pipeline_tool

            result = await destroy_pipeline_tool("test")

            assert result["status"] == "destroyed"
            mock_handler.assert_called_once()


class TestJarvisManagerToolsDirect:
    """Test JarvisManager tool implementations directly."""

    def test_jm_create_config_direct(self):
        """Test jm_create_config with mocked manager."""
        with patch("jarvis_mcp.server.manager") as mock_mgr:
            mock_mgr.create.return_value = None
            mock_mgr.save.return_value = None

            from jarvis_mcp.server import jm_create_config

            result = jm_create_config("/cfg", "/priv", "/share")

            assert len(result) == 1
            assert "initialized" in result[0]["text"].lower()
            mock_mgr.create.assert_called_once()
            mock_mgr.save.assert_called_once()

    def test_jm_create_config_error_direct(self):
        """Test jm_create_config error handling."""
        with patch("jarvis_mcp.server.manager") as mock_mgr:
            mock_mgr.create.side_effect = Exception("Error")

            from jarvis_mcp.server import jm_create_config

            with pytest.raises(ToolError):
                jm_create_config("/cfg", "/priv")

    def test_jm_load_config_direct(self):
        """Test jm_load_config with mocked manager."""
        with patch("jarvis_mcp.server.manager") as mock_mgr:
            mock_mgr.load.return_value = None

            from jarvis_mcp.server import jm_load_config

            result = jm_load_config()

            assert len(result) == 1
            assert "loaded" in result[0]["text"].lower()
            mock_mgr.load.assert_called_once()

    def test_jm_load_config_error_direct(self):
        """Test jm_load_config error handling."""
        with patch("jarvis_mcp.server.manager") as mock_mgr:
            mock_mgr.load.side_effect = Exception("Load error")

            from jarvis_mcp.server import jm_load_config

            with pytest.raises(ToolError):
                jm_load_config()

    def test_jm_save_config_direct(self):
        """Test jm_save_config with mocked manager."""
        with patch("jarvis_mcp.server.manager") as mock_mgr:
            mock_mgr.save.return_value = None

            from jarvis_mcp.server import jm_save_config

            result = jm_save_config()

            assert "saved" in result[0]["text"].lower()
            mock_mgr.save.assert_called_once()

    def test_jm_save_config_error_direct(self):
        """Test jm_save_config error handling."""
        with patch("jarvis_mcp.server.manager") as mock_mgr:
            mock_mgr.save.side_effect = Exception("Save error")

            from jarvis_mcp.server import jm_save_config

            with pytest.raises(ToolError):
                jm_save_config()

    def test_jm_set_hostfile_direct(self):
        """Test jm_set_hostfile with mocked manager."""
        with patch("jarvis_mcp.server.manager") as mock_mgr:
            mock_mgr.set_hostfile.return_value = None
            mock_mgr.save.return_value = None

            from jarvis_mcp.server import jm_set_hostfile

            result = jm_set_hostfile("/path/host")

            assert "/path/host" in result[0]["text"]
            mock_mgr.set_hostfile.assert_called_once()
            mock_mgr.save.assert_called_once()

    def test_jm_set_hostfile_error_direct(self):
        """Test jm_set_hostfile error handling."""
        with patch("jarvis_mcp.server.manager") as mock_mgr:
            mock_mgr.set_hostfile.side_effect = Exception("Hostfile error")

            from jarvis_mcp.server import jm_set_hostfile

            with pytest.raises(ToolError):
                jm_set_hostfile("/path")

    def test_jm_bootstrap_from_direct(self):
        """Test jm_bootstrap_from with mocked manager."""
        with patch("jarvis_mcp.server.manager") as mock_mgr:
            mock_mgr.bootstrap_from.return_value = None

            from jarvis_mcp.server import jm_bootstrap_from

            result = jm_bootstrap_from("machine1")

            assert "machine1" in result[0]["text"].lower()
            mock_mgr.bootstrap_from.assert_called_once()

    def test_jm_bootstrap_from_error_direct(self):
        """Test jm_bootstrap_from error handling."""
        with patch("jarvis_mcp.server.manager") as mock_mgr:
            mock_mgr.bootstrap_from.side_effect = Exception("Bootstrap error")

            from jarvis_mcp.server import jm_bootstrap_from

            with pytest.raises(ToolError):
                jm_bootstrap_from("machine")

    def test_jm_bootstrap_list_direct(self):
        """Test jm_bootstrap_list with mocked manager."""
        with patch("jarvis_mcp.server.manager") as mock_mgr:
            mock_mgr.bootstrap_list.return_value = ["m1", "m2"]

            from jarvis_mcp.server import jm_bootstrap_list

            result = jm_bootstrap_list()

            assert len(result) == 2
            assert result[0]["text"] == "m1"
            mock_mgr.bootstrap_list.assert_called_once()

    def test_jm_bootstrap_list_error_direct(self):
        """Test jm_bootstrap_list error handling."""
        with patch("jarvis_mcp.server.manager") as mock_mgr:
            mock_mgr.bootstrap_list.side_effect = Exception("List error")

            from jarvis_mcp.server import jm_bootstrap_list

            with pytest.raises(ToolError):
                jm_bootstrap_list()

    def test_jm_reset_direct(self):
        """Test jm_reset with mocked manager."""
        with patch("jarvis_mcp.server.manager") as mock_mgr:
            mock_mgr.reset.return_value = None

            from jarvis_mcp.server import jm_reset

            result = jm_reset()

            assert "reset" in result[0]["text"].lower()
            mock_mgr.reset.assert_called_once()

    def test_jm_reset_error_direct(self):
        """Test jm_reset error handling."""
        with patch("jarvis_mcp.server.manager") as mock_mgr:
            mock_mgr.reset.side_effect = Exception("Reset error")

            from jarvis_mcp.server import jm_reset

            with pytest.raises(ToolError):
                jm_reset()

    def test_jm_list_pipelines_direct(self):
        """Test jm_list_pipelines with mocked manager."""
        with patch("jarvis_mcp.server.manager") as mock_mgr:
            mock_mgr.list_pipelines.return_value = ["p1", "p2"]

            from jarvis_mcp.server import jm_list_pipelines

            result = jm_list_pipelines()

            assert len(result) == 2
            mock_mgr.list_pipelines.assert_called_once()

    def test_jm_list_pipelines_error_direct(self):
        """Test jm_list_pipelines error handling."""
        with patch("jarvis_mcp.server.manager") as mock_mgr:
            mock_mgr.list_pipelines.side_effect = Exception("List error")

            from jarvis_mcp.server import jm_list_pipelines

            with pytest.raises(ToolError):
                jm_list_pipelines()

    def test_jm_cd_direct(self):
        """Test jm_cd with mocked manager."""
        with patch("jarvis_mcp.server.manager") as mock_mgr:
            mock_mgr.cd.return_value = None
            mock_mgr.save.return_value = None

            from jarvis_mcp.server import jm_cd

            result = jm_cd("pipe1")

            assert "pipe1" in result[0]["text"]
            mock_mgr.cd.assert_called_once()

    def test_jm_cd_error_direct(self):
        """Test jm_cd error handling."""
        with patch("jarvis_mcp.server.manager") as mock_mgr:
            mock_mgr.cd.side_effect = Exception("CD error")

            from jarvis_mcp.server import jm_cd

            with pytest.raises(ToolError):
                jm_cd("pipe")

    def test_jm_list_repos_direct(self):
        """Test jm_list_repos with mocked manager."""
        with patch("jarvis_mcp.server.manager") as mock_mgr:
            mock_mgr.list_repos.return_value = ["repo1", "repo2"]

            from jarvis_mcp.server import jm_list_repos

            result = jm_list_repos()

            assert len(result) == 2
            mock_mgr.list_repos.assert_called_once()

    def test_jm_list_repos_error_direct(self):
        """Test jm_list_repos error handling."""
        with patch("jarvis_mcp.server.manager") as mock_mgr:
            mock_mgr.list_repos.side_effect = Exception("List error")

            from jarvis_mcp.server import jm_list_repos

            with pytest.raises(ToolError):
                jm_list_repos()

    def test_jm_add_repo_direct(self):
        """Test jm_add_repo with mocked manager."""
        with patch("jarvis_mcp.server.manager") as mock_mgr:
            mock_mgr.add_repo.return_value = None
            mock_mgr.save.return_value = None

            from jarvis_mcp.server import jm_add_repo

            result = jm_add_repo("/repo", True)

            assert "/repo" in result[0]["text"]
            mock_mgr.add_repo.assert_called_once()

    def test_jm_add_repo_error_direct(self):
        """Test jm_add_repo error handling."""
        with patch("jarvis_mcp.server.manager") as mock_mgr:
            mock_mgr.add_repo.side_effect = Exception("Add error")

            from jarvis_mcp.server import jm_add_repo

            with pytest.raises(ToolError):
                jm_add_repo("/repo")

    def test_jm_remove_repo_direct(self):
        """Test jm_remove_repo with mocked manager."""
        with patch("jarvis_mcp.server.manager") as mock_mgr:
            mock_mgr.remove_repo.return_value = None
            mock_mgr.save.return_value = None

            from jarvis_mcp.server import jm_remove_repo

            result = jm_remove_repo("repo1")

            assert "repo1" in result[0]["text"]
            mock_mgr.remove_repo.assert_called_once()

    def test_jm_remove_repo_error_direct(self):
        """Test jm_remove_repo error handling."""
        with patch("jarvis_mcp.server.manager") as mock_mgr:
            mock_mgr.remove_repo.side_effect = Exception("Remove error")

            from jarvis_mcp.server import jm_remove_repo

            with pytest.raises(ToolError):
                jm_remove_repo("repo")

    def test_jm_promote_repo_direct(self):
        """Test jm_promote_repo with mocked manager."""
        with patch("jarvis_mcp.server.manager") as mock_mgr:
            mock_mgr.promote_repo.return_value = None
            mock_mgr.save.return_value = None

            from jarvis_mcp.server import jm_promote_repo

            result = jm_promote_repo("repo1")

            assert "repo1" in result[0]["text"]
            mock_mgr.promote_repo.assert_called_once()

    def test_jm_promote_repo_error_direct(self):
        """Test jm_promote_repo error handling."""
        with patch("jarvis_mcp.server.manager") as mock_mgr:
            mock_mgr.promote_repo.side_effect = Exception("Promote error")

            from jarvis_mcp.server import jm_promote_repo

            with pytest.raises(ToolError):
                jm_promote_repo("repo")

    def test_jm_get_repo_direct(self):
        """Test jm_get_repo with mocked manager."""
        with patch("jarvis_mcp.server.manager") as mock_mgr:
            mock_repo = Mock()
            mock_repo.__str__ = Mock(return_value="RepoInfo")
            mock_mgr.get_repo.return_value = mock_repo

            from jarvis_mcp.server import jm_get_repo

            result = jm_get_repo("repo1")

            assert "RepoInfo" in result[0]["text"]
            mock_mgr.get_repo.assert_called_once()

    def test_jm_get_repo_error_direct(self):
        """Test jm_get_repo error handling."""
        with patch("jarvis_mcp.server.manager") as mock_mgr:
            mock_mgr.get_repo.side_effect = Exception("Get error")

            from jarvis_mcp.server import jm_get_repo

            with pytest.raises(ToolError):
                jm_get_repo("repo")

    def test_jm_construct_pkg_direct(self):
        """Test jm_construct_pkg with mocked manager."""
        with patch("jarvis_mcp.server.manager") as mock_mgr:
            mock_pkg = Mock()
            mock_pkg.__class__.__name__ = "TestPkg"
            mock_mgr.construct_pkg.return_value = mock_pkg

            from jarvis_mcp.server import jm_construct_pkg

            result = jm_construct_pkg("test_type")

            assert "TestPkg" in result[0]["text"]
            mock_mgr.construct_pkg.assert_called_once()

    def test_jm_construct_pkg_error_direct(self):
        """Test jm_construct_pkg error handling."""
        with patch("jarvis_mcp.server.manager") as mock_mgr:
            mock_mgr.construct_pkg.side_effect = Exception("Construct error")

            from jarvis_mcp.server import jm_construct_pkg

            with pytest.raises(ToolError):
                jm_construct_pkg("type")

    def test_jm_graph_show_direct(self):
        """Test jm_graph_show with mocked manager."""
        with patch("jarvis_mcp.server.manager") as mock_mgr:
            mock_mgr.resource_graph_show.return_value = None

            from jarvis_mcp.server import jm_graph_show

            result = jm_graph_show()

            assert "Resource graph" in result[0]["text"]
            mock_mgr.resource_graph_show.assert_called_once()

    def test_jm_graph_show_error_direct(self):
        """Test jm_graph_show error handling."""
        with patch("jarvis_mcp.server.manager") as mock_mgr:
            mock_mgr.resource_graph_show.side_effect = Exception("Show error")

            from jarvis_mcp.server import jm_graph_show

            with pytest.raises(ToolError):
                jm_graph_show()

    def test_jm_graph_build_direct(self):
        """Test jm_graph_build with mocked manager."""
        with patch("jarvis_mcp.server.manager") as mock_mgr:
            mock_mgr.resource_graph_build.return_value = None

            from jarvis_mcp.server import jm_graph_build

            result = jm_graph_build(0.5)

            assert "built" in result[0]["text"].lower()
            mock_mgr.resource_graph_build.assert_called_once()

    def test_jm_graph_build_error_direct(self):
        """Test jm_graph_build error handling."""
        with patch("jarvis_mcp.server.manager") as mock_mgr:
            mock_mgr.resource_graph_build.side_effect = Exception("Build error")

            from jarvis_mcp.server import jm_graph_build

            with pytest.raises(ToolError):
                jm_graph_build(1.0)

    def test_jm_graph_modify_direct(self):
        """Test jm_graph_modify with mocked manager."""
        with patch("jarvis_mcp.server.manager") as mock_mgr:
            mock_mgr.resource_graph_modify.return_value = None

            from jarvis_mcp.server import jm_graph_modify

            result = jm_graph_modify(0.75)

            assert "modified" in result[0]["text"].lower()
            mock_mgr.resource_graph_modify.assert_called_once()

    def test_jm_graph_modify_error_direct(self):
        """Test jm_graph_modify error handling."""
        with patch("jarvis_mcp.server.manager") as mock_mgr:
            mock_mgr.resource_graph_modify.side_effect = Exception("Modify error")

            from jarvis_mcp.server import jm_graph_modify

            with pytest.raises(ToolError):
                jm_graph_modify(1.0)


class TestMainFunctionDirect:
    """Test the main() function entry point."""

    def test_main_stdio_default(self):
        """Test main() with stdio transport."""
        with (
            patch("sys.argv", ["jarvis-mcp"]),
            patch("jarvis_mcp.server.mcp.run") as mock_run,
        ):
            from jarvis_mcp.server import main

            main()

            # Should be called with stdio transport (default)
            mock_run.assert_called_once_with(transport="stdio")


class TestResourceAndPrompt:
    """Test the new resource and prompt additions."""

    def test_jarvis_capabilities_resource(self):
        """Test the jarvis capabilities resource."""
        from jarvis_mcp.server import jarvis_capabilities

        result = jarvis_capabilities()

        assert "pipeline_types" in result
        assert "streaming" in result["pipeline_types"]
        assert "batch" in result["pipeline_types"]
        assert "real-time" in result["pipeline_types"]
        assert "operations" in result
        assert "create" in result["operations"]
        assert "destroy" in result["operations"]

    def test_create_pipeline_workflow_prompt(self):
        """Test the create pipeline workflow prompt."""
        from jarvis_mcp.server import create_pipeline_workflow

        result = create_pipeline_workflow("my_pipeline")

        assert len(result) == 1
        assert isinstance(result[0], Message)
