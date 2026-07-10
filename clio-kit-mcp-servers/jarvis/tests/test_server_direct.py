"""
Direct tests for server.py tool functions to achieve >90% coverage.
Tests actual function bodies by patching handlers at the capabilities layer.
"""

import pytest
import importlib
import sys
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

        tools = [
            Tool("jarvis_create_pipeline"),
            Tool("jarvis_run"),
            Tool("create_pipeline"),
            Tool("jm_reset"),
        ]
        with patch("jarvis_mcp.server.mcp") as mock_mcp:
            mock_mcp.local_provider._components = {
                f"tool:{tool.name}@": tool for tool in tools
            }

            apply_tool_profile("user")

            removed = [
                call.args[0]
                for call in mock_mcp.local_provider.remove_tool.call_args_list
            ]
            assert removed == ["create_pipeline", "jm_reset"]

    def test_apply_admin_profile_removes_user_tools(self):
        """Admin profile keeps manager tools and hides user pipeline authoring."""
        from jarvis_mcp.server import apply_tool_profile

        class Tool:
            def __init__(self, name):
                self.name = name

        tools = [
            Tool("jarvis_create_pipeline"),
            Tool("create_pipeline"),
            Tool("jm_reset"),
        ]
        with patch("jarvis_mcp.server.mcp") as mock_mcp:
            mock_mcp.local_provider._components = {
                f"tool:{tool.name}@": tool for tool in tools
            }

            apply_tool_profile("admin")

            mock_mcp.local_provider.remove_tool.assert_called_once_with(
                "jarvis_create_pipeline"
            )

    def test_apply_all_profile_keeps_every_tool(self):
        """The compatibility profile leaves the full legacy surface intact."""
        from jarvis_mcp.server import apply_tool_profile

        with patch("jarvis_mcp.server.mcp") as mock_mcp:
            apply_tool_profile("all")

            mock_mcp.local_provider.remove_tool.assert_not_called()


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
    async def test_jarvis_create_pipeline_tool_direct(self):
        """Test user-facing pipeline creation wrapper."""
        with patch("jarvis_mcp.server.create_pipeline") as mock_handler:
            mock_handler.return_value = {"pipeline_id": "new", "status": "created"}

            from jarvis_mcp.server import jarvis_create_pipeline_tool

            result = await jarvis_create_pipeline_tool("new")

            assert result["status"] == "created"
            mock_handler.assert_called_once_with("new")

    @pytest.mark.asyncio
    async def test_jarvis_create_pipeline_with_cluster_execution(self):
        """Cluster execution intent configures native scheduler state."""
        with (
            patch("jarvis_mcp.server.create_pipeline") as create_handler,
            patch("jarvis_mcp.server.configure_pipeline") as configure_handler,
            patch.dict("os.environ", {"JARVIS_MCP_SCHEDULER": "slurm"}),
        ):
            create_handler.return_value = {"pipeline_id": "new", "status": "created"}
            configure_handler.return_value = {
                "pipeline_id": "new",
                "status": "configured",
            }

            from jarvis_mcp.server import jarvis_create_pipeline_tool

            result = await jarvis_create_pipeline_tool(
                "new",
                execution={
                    "mode": "cluster",
                    "nodes": 4,
                    "tasks_per_node": 20,
                    "walltime": "00:30:00",
                    "exclusive": True,
                },
            )

            assert result["created"]["status"] == "created"
            configure_handler.assert_called_once_with(
                "new",
                {
                    "scheduler": {
                        "name": "slurm",
                        "nodes": 4,
                        "ntasks_per_node": 20,
                        "time": "00:30:00",
                        "exclusive": True,
                    }
                },
            )

    @pytest.mark.asyncio
    async def test_jarvis_add_step_tool_direct(self):
        """Test user-facing step addition maps to package append."""
        with patch("jarvis_mcp.server.append_pkg") as mock_handler:
            mock_handler.return_value = {"pipeline_id": "test", "appended": "lammps"}

            from jarvis_mcp.server import jarvis_add_step_tool

            result = await jarvis_add_step_tool(
                "test",
                "builtin.lammps",
                step_id="lammps_1",
                config={"nodes": 4},
            )

            assert result["appended"] == "lammps"
            mock_handler.assert_called_once_with(
                "test",
                "builtin.lammps",
                pkg_id="lammps_1",
                do_configure=True,
                nodes=4,
            )

    @pytest.mark.asyncio
    async def test_jarvis_edit_step_tool_direct(self):
        """Test user-facing step edit maps to package configuration."""
        with patch("jarvis_mcp.server.configure_pkg") as mock_handler:
            mock_handler.return_value = {
                "pipeline_id": "test",
                "configured": "lammps_1",
            }

            from jarvis_mcp.server import jarvis_edit_step_tool

            result = await jarvis_edit_step_tool("test", "lammps_1", {"nodes": 2})

            assert result["configured"] == "lammps_1"
            mock_handler.assert_called_once_with("test", "lammps_1", nodes=2)

    @pytest.mark.asyncio
    async def test_jarvis_remove_step_tool_direct(self):
        """Test user-facing step removal unlinks the package."""
        with patch("jarvis_mcp.server.unlink_pkg") as mock_handler:
            mock_handler.return_value = {"pipeline_id": "test", "unlinked": "lammps_1"}

            from jarvis_mcp.server import jarvis_remove_step_tool

            result = await jarvis_remove_step_tool("test", "lammps_1")

            assert result["unlinked"] == "lammps_1"
            mock_handler.assert_called_once_with("test", "lammps_1")

    @pytest.mark.asyncio
    async def test_jarvis_run_tool_direct(self):
        """Test user-facing run maps to pipeline execution."""
        with patch("jarvis_mcp.server.run_pipeline") as mock_handler:
            mock_handler.return_value = {"pipeline_id": "test", "status": "running"}

            from jarvis_mcp.server import jarvis_run_tool

            result = await jarvis_run_tool("test")

            assert result["status"] == "running"
            mock_handler.assert_called_once_with(
                "test", mode="auto", submit=True, wait=False
            )

    @pytest.mark.asyncio
    async def test_jarvis_run_tool_maps_execution_intent(self):
        """User execution intent maps to JARVIS-native configuration."""
        with (
            patch("jarvis_mcp.server.configure_pipeline") as configure_handler,
            patch("jarvis_mcp.server.run_pipeline") as run_handler,
            patch.dict("os.environ", {"JARVIS_MCP_SCHEDULER": "slurm"}),
        ):
            configure_handler.return_value = {"status": "configured"}
            run_handler.return_value = {"pipeline_id": "test", "status": "submitted"}

            from jarvis_mcp.server import jarvis_run_tool

            result = await jarvis_run_tool(
                "test",
                execution={
                    "mode": "cluster",
                    "nodes": 2,
                    "tasks": 40,
                    "partition": "compute",
                },
            )

            assert result["status"] == "submitted"
            configure_handler.assert_called_once_with(
                "test",
                {
                    "scheduler": {
                        "name": "slurm",
                        "nodes": 2,
                        "ntasks": 40,
                        "partition": "compute",
                    }
                },
            )
            run_handler.assert_called_once_with(
                "test", mode="scheduler", submit=True, wait=False
            )

    @pytest.mark.asyncio
    async def test_jarvis_run_tool_maps_hostfile_hosts(self):
        """Hostfile intent can be supplied as semantic host names."""
        with (
            patch("jarvis_mcp.server.configure_pipeline") as configure_handler,
            patch("jarvis_mcp.server.run_pipeline") as run_handler,
        ):
            configure_handler.return_value = {"status": "configured"}
            run_handler.return_value = {"pipeline_id": "test", "status": "running"}

            from jarvis_mcp.server import jarvis_run_tool

            await jarvis_run_tool(
                "test",
                execution={"mode": "hostfile", "hosts": ["node-a", "node-b"]},
            )

            configure_handler.assert_called_once_with(
                "test",
                {"scheduler": None, "hostfile_entries": ["node-a", "node-b"]},
            )
            run_handler.assert_called_once_with(
                "test", mode="direct", submit=True, wait=False
            )

    def test_execution_intent_local_and_direct_disable_scheduler(self):
        """Local and direct modes select single-node execution without a scheduler."""
        from jarvis_mcp.server import _execution_intent_to_pipeline_config

        assert _execution_intent_to_pipeline_config({"mode": "local"}) == {
            "scheduler": None,
            "hostfile": None,
        }
        assert _execution_intent_to_pipeline_config({"mode": "direct"}) == {
            "scheduler": None,
            "hostfile": None,
        }

    def test_execution_intent_hostfile_path(self):
        """A hostfile path is passed through as a native JARVIS hostfile config."""
        from jarvis_mcp.server import _execution_intent_to_pipeline_config

        assert _execution_intent_to_pipeline_config(
            {"mode": "hostfile", "hostfile": "/tmp/hosts"}
        ) == {"scheduler": None, "hostfile": "/tmp/hosts"}

    def test_execution_intent_hostfile_requires_target(self):
        """Hostfile mode needs either a hostfile path or explicit host names."""
        from jarvis_mcp.server import _execution_intent_to_pipeline_config

        with pytest.raises(ToolError, match="execution.hostfile is required"):
            _execution_intent_to_pipeline_config({"mode": "hostfile"})

    def test_execution_intent_rejects_unknown_mode(self):
        """Unknown execution modes fail before they reach JARVIS."""
        from jarvis_mcp.server import _execution_intent_to_pipeline_config

        with pytest.raises(ToolError, match="execution.mode must be one of"):
            _execution_intent_to_pipeline_config({"mode": "magic"})

    def test_execution_intent_cluster_requires_scheduler(self):
        """Explicit cluster mode fails if no scheduler exists on the MCP host."""
        with (
            patch.dict("os.environ", {}, clear=True),
            patch("shutil.which", return_value=None),
        ):
            from jarvis_mcp.server import _execution_intent_to_pipeline_config

            with pytest.raises(ToolError, match="no supported cluster scheduler"):
                _execution_intent_to_pipeline_config({"mode": "cluster", "nodes": 2})

    def test_execution_intent_auto_without_scheduler_is_noop(self):
        """Auto mode does not overwrite an existing pipeline on non-scheduler hosts."""
        with (
            patch.dict("os.environ", {}, clear=True),
            patch("shutil.which", return_value=None),
        ):
            from jarvis_mcp.server import _execution_intent_to_pipeline_config

            assert _execution_intent_to_pipeline_config({"mode": "auto"}) == {}

    def test_detect_scheduler_name_from_env_and_path(self):
        """Scheduler detection prefers explicit env and otherwise probes sbatch."""
        from jarvis_mcp.server import _detect_scheduler_name

        with patch.dict("os.environ", {"JARVIS_SCHEDULER": "pbs"}, clear=True):
            assert _detect_scheduler_name() == "pbs"
        with (
            patch.dict("os.environ", {}, clear=True),
            patch("shutil.which", return_value="/usr/bin/sbatch"),
        ):
            assert _detect_scheduler_name() == "slurm"

    @pytest.mark.asyncio
    async def test_jarvis_describe_pipeline_tool_direct(self):
        """Test user-facing pipeline description uses pipeline export."""
        with patch("jarvis_mcp.server.export_pipeline") as mock_handler:
            mock_handler.return_value = {"pipeline_id": "test", "packages": []}

            from jarvis_mcp.server import jarvis_describe_tool

            result = await jarvis_describe_tool("pipeline", pipeline_id="test")

            assert result["target"] == "pipeline"
            assert result["pipeline"]["pipeline_id"] == "test"
            mock_handler.assert_called_once_with("test", include_yaml=True)

    @pytest.mark.asyncio
    async def test_jarvis_describe_package_tool_direct(self, tmp_path):
        """Package description is discovered from registered JARVIS repos."""
        repo = tmp_path / "repo"
        pkg_dir = repo / "builtin" / "demo"
        pkg_dir.mkdir(parents=True)
        (pkg_dir / "pkg.py").write_text(
            '"""Demo package for tests."""\nclass Pkg: pass\n',
            encoding="utf-8",
        )
        manager = Mock()
        manager.list_repos.return_value = [repo]

        with (
            patch("jarvis_mcp.server.get_manager", return_value=manager),
            patch("jarvis_mcp.server._package_settings", return_value=None),
        ):
            from jarvis_mcp.server import jarvis_describe_tool

            result = await jarvis_describe_tool("package", package_name="builtin.demo")

            assert result["target"] == "package"
            assert result["package"]["name"] == "builtin.demo"
            assert result["package"]["short_name"] == "demo"
            assert result["package"]["description"] == "Demo package for tests."

    @pytest.mark.asyncio
    async def test_jarvis_describe_packages_skips_missing_repos(self, tmp_path):
        """Package discovery ignores stale repository paths."""
        repo = tmp_path / "missing"
        manager = Mock()
        manager.list_repos.return_value = [repo]

        with patch("jarvis_mcp.server.get_manager", return_value=manager):
            from jarvis_mcp.server import jarvis_describe_tool

            result = await jarvis_describe_tool("packages")

            assert result == {"target": "packages", "packages": []}

    @pytest.mark.asyncio
    async def test_jarvis_describe_step_tool_direct(self):
        """Test user-facing step description includes snapshot and config."""
        with (
            patch("jarvis_mcp.server.export_pipeline") as export_handler,
            patch("jarvis_mcp.server.get_pkg_config") as config_handler,
        ):
            export_handler.return_value = {
                "pipeline_id": "test",
                "packages": [{"pkg_id": "lammps_1", "pkg_type": "builtin.lammps"}],
            }
            config_handler.return_value = {"pkg_id": "lammps_1", "config": {"nodes": 4}}

            from jarvis_mcp.server import jarvis_describe_tool

            result = await jarvis_describe_tool(
                "step", pipeline_id="test", step_id="lammps_1"
            )

            assert result["target"] == "step"
            assert result["step"]["pkg_id"] == "lammps_1"
            assert result["config"]["config"]["nodes"] == 4

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

    @pytest.mark.asyncio
    async def test_jm_list_pipelines_direct(self):
        """Test jm_list_pipelines with mocked manager."""
        with patch("jarvis_mcp.server.manager") as mock_mgr:
            mock_mgr.list_pipelines.return_value = ["p1", "p2"]

            from jarvis_mcp.server import jm_list_pipelines

            result = await jm_list_pipelines()

            assert result == {"pipelines": ["p1", "p2"], "count": 2}
            mock_mgr.list_pipelines.assert_called_once()

    @pytest.mark.asyncio
    async def test_jm_list_pipelines_error_direct(self):
        """Test jm_list_pipelines error handling."""
        with patch("jarvis_mcp.server.manager") as mock_mgr:
            mock_mgr.list_pipelines.side_effect = Exception("List error")

            from jarvis_mcp.server import jm_list_pipelines

            with pytest.raises(ToolError):
                await jm_list_pipelines()

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

    @pytest.mark.asyncio
    async def test_jm_list_repos_direct(self):
        """Test jm_list_repos with mocked manager."""
        with patch("jarvis_mcp.server.manager") as mock_mgr:
            mock_mgr.list_repos.return_value = ["repo1", "repo2"]

            from jarvis_mcp.server import jm_list_repos

            result = await jm_list_repos()

            assert result == {"repos": ["repo1", "repo2"], "count": 2}
            mock_mgr.list_repos.assert_called_once()

    @pytest.mark.asyncio
    async def test_jm_list_repos_error_direct(self):
        """Test jm_list_repos error handling."""
        with patch("jarvis_mcp.server.manager") as mock_mgr:
            mock_mgr.list_repos.side_effect = Exception("List error")

            from jarvis_mcp.server import jm_list_repos

            with pytest.raises(ToolError):
                await jm_list_repos()

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

    @pytest.mark.asyncio
    async def test_jm_get_repo_direct(self):
        """Test jm_get_repo with mocked manager."""
        with patch("jarvis_mcp.server.manager") as mock_mgr:
            mock_repo = Mock()
            mock_repo.__str__ = Mock(return_value="RepoInfo")
            mock_mgr.get_repo.return_value = mock_repo

            from jarvis_mcp.server import jm_get_repo

            result = await jm_get_repo("repo1")

            assert result["repo"] == "RepoInfo"
            mock_mgr.get_repo.assert_called_once_with("repo1")

    @pytest.mark.asyncio
    async def test_jm_get_repo_error_direct(self):
        """Test jm_get_repo error handling."""
        with patch("jarvis_mcp.server.manager") as mock_mgr:
            mock_mgr.get_repo.side_effect = Exception("Get error")

            from jarvis_mcp.server import jm_get_repo

            with pytest.raises(ToolError):
                await jm_get_repo("repo")

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
            patch("jarvis_mcp.server.apply_tool_profile") as mock_profile,
            patch("jarvis_mcp.server.mcp.run") as mock_run,
        ):
            from jarvis_mcp.server import main

            main()

            mock_profile.assert_called_once_with("user")
            # Should be called with stdio transport (default)
            mock_run.assert_called_once_with(transport="stdio")

    def test_admin_main_uses_admin_profile(self):
        """Test admin entry point selects the admin profile."""
        with (
            patch("sys.argv", ["jarvis-admin-mcp"]),
            patch.dict("os.environ", {}, clear=True),
            patch("jarvis_mcp.server.apply_tool_profile") as mock_profile,
            patch("jarvis_mcp.server.mcp.run") as mock_run,
        ):
            from jarvis_mcp.server import admin_main

            admin_main()

            mock_profile.assert_called_once_with("admin")
            mock_run.assert_called_once_with(transport="stdio")

    def test_user_server_entrypoint_applies_user_profile_and_runs_http(self):
        """The user entrypoint exposes user tools and supports HTTP transport."""
        sys.modules.pop("jarvis_mcp.user_server", None)
        with (
            patch("sys.argv", ["jarvis-mcp", "--transport", "http", "--port", "9001"]),
            patch("jarvis_mcp.server.apply_tool_profile") as mock_profile,
            patch("jarvis_mcp.server.mcp.run") as mock_run,
        ):
            module = importlib.import_module("jarvis_mcp.user_server")

            module.main()

            mock_profile.assert_called_once_with("user")
            mock_run.assert_called_once_with(
                transport="http", host="0.0.0.0", port=9001
            )

    def test_admin_server_entrypoint_applies_admin_profile_and_runs_stdio(self):
        """The admin entrypoint exposes admin tools and defaults to stdio."""
        sys.modules.pop("jarvis_mcp.admin_server", None)
        with (
            patch("sys.argv", ["jarvis-admin-mcp"]),
            patch.dict("os.environ", {}, clear=True),
            patch("jarvis_mcp.server.apply_tool_profile") as mock_profile,
            patch("jarvis_mcp.server.mcp.run") as mock_run,
        ):
            module = importlib.import_module("jarvis_mcp.admin_server")

            module.main()

            mock_profile.assert_called_once_with("admin")
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
