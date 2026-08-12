"""
Direct tests for server.py tool functions to achieve >90% coverage.
Tests actual function bodies by patching handlers at the capabilities layer.
"""

import pytest
import hashlib
import importlib
import inspect
import json
import os
import runpy
import sys
from copy import deepcopy
from unittest.mock import Mock, call, patch
from fastmcp.exceptions import ToolError
from fastmcp.prompts import Message


def test_service_runtime_response_model_is_closed_and_fingerprint_bound() -> None:
    """The MCP response preserves JARVIS's exact service and dataset identity."""
    from jarvis_mcp.capabilities.jarvis_handler import (
        _service_runtime_snapshot_document,
    )
    from jarvis_mcp.server import JarvisServiceRuntimeSnapshotDocument

    intrinsic = {
        "schema_version": "jarvis.dataset-descriptor.v1",
        "dataset_id": "asteroid-subset",
        "kind": "temporal-volume-series",
        "format": "vtk-image-data",
        "members": [
            {
                "index": 0,
                "location": "/datasets/asteroid/frame-0000.vti",
                "timestep": 0.0,
            }
        ],
        "arrays": [
            {
                "name": "pressure",
                "association": "point",
                "components": 1,
            }
        ],
        "bounds": [0.0, 1.0, 0.0, 1.0, 0.0, 1.0],
        "source_artifact": None,
    }
    fingerprint = hashlib.sha256(
        json.dumps(
            intrinsic,
            allow_nan=False,
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        ).encode("utf-8")
    ).hexdigest()
    descriptor = {
        **intrinsic,
        "fingerprint": {"algorithm": "sha256", "digest": fingerprint},
    }
    snapshot = {
        "schema_version": "jarvis.execution.service-runtimes.v1",
        "execution_id": "execution-1",
        "pipeline_id": "pipeline",
        "execution_state": "running",
        "terminal": False,
        "service_runtimes": [
            {
                "schema_version": "jarvis.service-runtime.v1",
                "execution_id": "execution-1",
                "package_name": "builtin.paraview",
                "package_id": "viewer",
                "service_instance_id": "service-1",
                "revision": 1,
                "lifecycle": "ready",
                "host": "127.0.0.1",
                "port": 21000,
                "protocol": "http",
                "health_path": "/healthz",
                "live_data_path": "/live-data",
                "events_path": "/events",
                "state_path": "/state",
                "command_path": "/commands",
                "delivery_mode": "push",
                "dataset_descriptor": descriptor,
                "message": None,
                "observed_at_epoch": 1.0,
            }
        ],
    }

    parsed = JarvisServiceRuntimeSnapshotDocument.model_validate(snapshot)
    assert (
        parsed.service_runtimes[0].dataset_descriptor.fingerprint.digest == fingerprint
    )

    token_sha256 = "a" * 64
    authenticated = deepcopy(snapshot)
    authenticated_runtime = authenticated["service_runtimes"][0]
    authenticated_runtime["schema_version"] = "jarvis.service-runtime.v2"
    authenticated_runtime["authorization"] = {
        "scheme": "bearer",
        "token_sha256": token_sha256,
    }
    authenticated_parsed = JarvisServiceRuntimeSnapshotDocument.model_validate(
        authenticated
    )
    assert authenticated_parsed.service_runtimes[0].schema_version == (
        "jarvis.service-runtime.v2"
    )
    assert authenticated_parsed.model_dump(mode="json")["service_runtimes"][0][
        "authorization"
    ] == {"scheme": "bearer", "token_sha256": token_sha256}

    v1_with_authorization = deepcopy(authenticated)
    v1_with_authorization["service_runtimes"][0]["schema_version"] = (
        "jarvis.service-runtime.v1"
    )
    with pytest.raises(ValueError, match="Extra inputs"):
        JarvisServiceRuntimeSnapshotDocument.model_validate(v1_with_authorization)

    v2_without_authorization = deepcopy(authenticated)
    v2_without_authorization["service_runtimes"][0].pop("authorization")
    with pytest.raises(ValueError, match="Field required"):
        JarvisServiceRuntimeSnapshotDocument.model_validate(v2_without_authorization)

    invalid_fingerprint = "NOT-A-LOWERCASE-SHA256"
    invalid_authorization = deepcopy(authenticated)
    invalid_authorization["service_runtimes"][0]["authorization"]["token_sha256"] = (
        invalid_fingerprint
    )
    with pytest.raises(ValueError) as invalid_error:
        JarvisServiceRuntimeSnapshotDocument.model_validate(invalid_authorization)
    assert invalid_fingerprint not in str(invalid_error.value)
    with pytest.raises(ValueError) as normalized_error:
        _service_runtime_snapshot_document(
            invalid_authorization,
            expected_execution_id="execution-1",
            expected_pipeline_id="pipeline",
        )
    assert invalid_fingerprint not in str(normalized_error.value)

    raw_token = "b" * 64
    raw_authorization = deepcopy(authenticated)
    raw_authorization["service_runtimes"][0]["authorization"] = {
        "scheme": "bearer",
        "token": raw_token,
    }
    with pytest.raises(ValueError) as raw_model_error:
        JarvisServiceRuntimeSnapshotDocument.model_validate(raw_authorization)
    assert raw_token not in str(raw_model_error.value)
    with pytest.raises(ValueError) as raw_handler_error:
        _service_runtime_snapshot_document(
            raw_authorization,
            expected_execution_id="execution-1",
            expected_pipeline_id="pipeline",
        )
    assert raw_token not in str(raw_handler_error.value)

    changed = deepcopy(snapshot)
    changed["service_runtimes"][0]["dataset_descriptor"]["dataset_id"] = "changed"
    with pytest.raises(ValueError, match="fingerprint"):
        JarvisServiceRuntimeSnapshotDocument.model_validate(changed)

    extended = deepcopy(snapshot)
    extended["service_runtimes"][0]["unversioned"] = True
    with pytest.raises(ValueError, match="Extra inputs"):
        JarvisServiceRuntimeSnapshotDocument.model_validate(extended)


def test_progress_response_models_are_closed_and_identity_checked():
    """Public progress models expose the exact stable JARVIS package schema."""
    from jarvis_mcp.server import (
        JarvisPackageProgressDocument,
        JarvisProgressEventDocument,
        JarvisProgressSnapshotDocument,
    )

    event = {
        "schema_version": "jarvis.progress.v1",
        "package_name": "builtin.gray_scott",
        "package_id": "simulation",
        "execution_id": "execution-1",
        "label": "timestep",
        "state": "running",
        "current": 4.0,
        "total": 10.0,
        "unit": "step",
        "message": "advanced simulation",
        "sequence": 3,
        "observed_at_epoch": 1.0,
        "determinate": True,
        "metadata": {"output": "gray-scott.bp"},
    }
    document = {
        "schema_version": "jarvis.execution.progress.v1",
        "execution_id": "execution-1",
        "pipeline_id": "pipeline-1",
        "execution_state": "running",
        "terminal": False,
        "packages": [
            {
                "package_id": "simulation",
                "package_name": "builtin.gray_scott",
                "event_count": 4,
                "latest": event,
            }
        ],
    }

    snapshot = JarvisProgressSnapshotDocument.model_validate(document)

    assert isinstance(snapshot.packages[0], JarvisPackageProgressDocument)
    assert isinstance(snapshot.packages[0].latest, JarvisProgressEventDocument)
    assert snapshot.packages[0].latest.current == 4.0

    extended = deepcopy(document)
    extended["packages"][0]["untrusted"] = True
    with pytest.raises(ValueError, match="Extra inputs are not permitted"):
        JarvisProgressSnapshotDocument.model_validate(extended)

    forged = deepcopy(document)
    forged["packages"][0]["latest"]["execution_id"] = "other-execution"
    with pytest.raises(ValueError, match="execution identity did not match"):
        JarvisProgressSnapshotDocument.model_validate(forged)

    inconsistent = deepcopy(document)
    inconsistent["packages"][0]["latest"]["determinate"] = False
    with pytest.raises(ValueError, match="determinate must match"):
        JarvisProgressSnapshotDocument.model_validate(inconsistent)


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


class TestCurrentJarvisManagerAdapter:
    """Test the compatibility adapter for current JARVIS-CD manager APIs."""

    def test_adapter_delegates_stateful_manager_operations(self, tmp_path):
        """The current manager adapter maps legacy manager calls to Jarvis APIs."""
        from jarvis_mcp.server import _CurrentJarvisManager

        pipelines_dir = tmp_path / "pipelines"
        pipelines_dir.mkdir()
        (pipelines_dir / "pipe-b").mkdir()
        (pipelines_dir / "pipe-a").mkdir()
        repo = tmp_path / "repo"
        repo.mkdir()

        jarvis = Mock()
        jarvis.config = {"loaded": True}
        jarvis.repos = {"repos": [str(repo), "/missing/repo"]}
        jarvis._config = {"loaded": True}
        jarvis._repos = jarvis.repos
        jarvis.get_pipelines_dir.return_value = pipelines_dir
        jarvis.resource_graph = {"nodes": []}

        adapter = _CurrentJarvisManager(jarvis)
        assert adapter.create("cfg", "priv", "shared") is adapter
        jarvis.initialize.assert_called_once_with(
            config_dir="cfg", private_dir="priv", shared_dir="shared"
        )
        assert adapter.load() is adapter
        assert adapter.save() is adapter
        jarvis.save_config.assert_called_once_with(jarvis.config)
        jarvis.save_repos.assert_called_once_with(jarvis.repos)
        assert adapter.set_hostfile("/tmp/hosts") is adapter
        jarvis.set_hostfile.assert_called_once_with("/tmp/hosts")
        assert adapter.list_pipelines() == ["pipe-a", "pipe-b"]
        assert adapter.cd("pipe-a") is adapter
        jarvis.set_current_pipeline.assert_called_once_with("pipe-a")
        assert adapter.list_repos() == [str(repo), "/missing/repo"]
        assert adapter.get_repo(repo.name) == {
            "index": 1,
            "name": repo.name,
            "path": str(repo),
            "exists": True,
        }
        assert adapter.resource_graph_show() == {"nodes": []}

    def test_adapter_handles_repo_mutation_and_unsupported_calls(self, tmp_path):
        """Repo matching works by path or directory name and unsupported calls fail."""
        from jarvis_mcp.server import _CurrentJarvisManager

        repo = tmp_path / "repo"
        repo.mkdir()
        jarvis = Mock()
        jarvis.repos = {"repos": [str(repo), "/other/other-repo"]}
        adapter = _CurrentJarvisManager(jarvis)

        assert adapter.add_repo(str(repo), force=True) is adapter
        jarvis.add_repo.assert_called_once_with(str(repo), force=True)
        assert adapter.remove_repo(repo.name) is adapter
        jarvis.remove_repo.assert_called_with(str(repo))
        assert adapter.promote_repo("repo") is adapter
        jarvis.save_repos.assert_called_with(
            {"repos": [str(repo), "/other/other-repo"]}
        )

        with pytest.raises(ValueError, match="repository not found"):
            adapter.promote_repo("missing")
        with pytest.raises(NotImplementedError, match="bootstrap templates"):
            adapter.bootstrap_from("ares")
        with pytest.raises(NotImplementedError, match="reset"):
            adapter.reset()
        assert adapter.bootstrap_list() == []


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
            mock_handler.assert_called_once_with("new", initial_config=None)

    @pytest.mark.asyncio
    async def test_jarvis_create_pipeline_with_cluster_execution(self):
        """Cluster execution intent configures native scheduler state."""
        with (
            patch("jarvis_mcp.server.create_pipeline") as create_handler,
            patch.dict("os.environ", {"JARVIS_MCP_SCHEDULER": "slurm"}),
        ):
            create_handler.return_value = {"pipeline_id": "new", "status": "created"}

            from jarvis_mcp.server import (
                ExecutionIntent,
                jarvis_create_pipeline_tool,
            )

            result = await jarvis_create_pipeline_tool(
                "new",
                execution=ExecutionIntent.model_validate(
                    {
                        "mode": "cluster",
                        "nodes": 4,
                        "tasks_per_node": 20,
                        "walltime": "00:30:00",
                        "exclusive": True,
                    }
                ),
            )

            assert result["status"] == "created"
            create_handler.assert_called_once_with(
                "new",
                initial_config={
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
        """User-facing step addition always runs package-owned validation."""
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
                agent_visible_only=True,
                nodes=4,
            )

    @pytest.mark.asyncio
    async def test_jarvis_add_step_preserves_structured_json_config(self):
        """JSON documents stay structured until the generic handler serializes them."""
        descriptor = {
            "schema_version": "jarvis.dataset-descriptor.v1",
            "dataset_id": "scientific-run",
            "members": [{"index": 0, "location": "/data/frame-0000.vti"}],
        }
        with patch("jarvis_mcp.server.append_pkg") as mock_handler:
            mock_handler.return_value = {
                "pipeline_id": "test",
                "appended": "builtin.paraview",
            }

            from jarvis_mcp.server import jarvis_add_step_tool

            await jarvis_add_step_tool(
                "test",
                "builtin.paraview",
                config={"dataset_descriptor": descriptor},
            )

            mock_handler.assert_called_once_with(
                "test",
                "builtin.paraview",
                pkg_id=None,
                do_configure=True,
                agent_visible_only=True,
                dataset_descriptor=descriptor,
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
            mock_handler.assert_called_once_with(
                "test",
                "lammps_1",
                agent_visible_only=True,
                nodes=2,
            )

    @pytest.mark.asyncio
    async def test_jarvis_edit_step_remove_operation_unlinks(self):
        """The compact edit tool owns user-facing remove semantics."""
        with patch("jarvis_mcp.server.unlink_pkg") as mock_handler:
            mock_handler.return_value = {"pipeline_id": "test", "unlinked": "step"}

            from jarvis_mcp.server import jarvis_edit_step_tool

            result = await jarvis_edit_step_tool("test", "step", operation="remove")

        assert result["unlinked"] == "step"
        mock_handler.assert_called_once_with("test", "step")

    @pytest.mark.asyncio
    async def test_jarvis_edit_step_enforces_conditional_config(self):
        """Edit requires config and remove rejects it."""
        from jarvis_mcp.server import jarvis_edit_step_tool

        with pytest.raises(ToolError, match="config is required"):
            await jarvis_edit_step_tool("test", "step", operation="edit")
        with pytest.raises(ToolError, match="config is not accepted"):
            await jarvis_edit_step_tool(
                "test", "step", {"nodes": 2}, operation="remove"
            )

    @pytest.mark.asyncio
    async def test_jarvis_run_tool_direct(self):
        """Test user-facing run maps to pipeline execution."""
        with patch("jarvis_mcp.server.run_pipeline") as mock_handler:
            mock_handler.return_value = {"pipeline_id": "test", "status": "running"}

            from jarvis_mcp.server import jarvis_run_tool

            assert "wait" not in inspect.signature(jarvis_run_tool).parameters
            result = await jarvis_run_tool("test")

            assert result["status"] == "running"
            mock_handler.assert_called_once_with(
                "test",
                mode="auto",
                submit=True,
                wait=False,
                execution_id=None,
                spack_specs=None,
                pipeline_config=None,
            )

    @pytest.mark.asyncio
    async def test_jarvis_run_only_enables_progress_for_an_explicit_token(self):
        """A Context without a negotiated progress token keeps execution unchanged."""
        from types import SimpleNamespace
        from typing import cast

        from fastmcp import Context

        from jarvis_mcp.server import jarvis_run_tool

        class FakeContext:
            request_context = SimpleNamespace(meta={"progressToken": None})

            async def report_progress(self, *_args: object, **_kwargs: object) -> None:
                raise AssertionError("progress must not be reported without a token")

        with patch("jarvis_mcp.server.run_pipeline") as run_handler:
            run_handler.return_value = {"pipeline_id": "test", "status": "running"}

            await jarvis_run_tool("test", ctx=cast(Context, FakeContext()))

        run_handler.assert_called_once_with(
            "test",
            mode="auto",
            submit=True,
            wait=False,
            execution_id=None,
            spack_specs=None,
            pipeline_config=None,
        )

    @pytest.mark.asyncio
    async def test_jarvis_run_forwards_progress_for_an_explicit_token(self):
        """A negotiated token attaches a reporter to the JARVIS operation."""
        from types import SimpleNamespace
        from typing import cast

        from fastmcp import Context

        from jarvis_mcp.server import jarvis_run_tool

        reports: list[tuple[float, float | None, str]] = []

        class FakeContext:
            request_context = SimpleNamespace(meta={"progressToken": "live-token"})

            async def report_progress(
                self, current: float, total: float | None, message: str
            ) -> None:
                reports.append((current, total, message))

        with patch("jarvis_mcp.server.run_pipeline") as run_handler:
            run_handler.return_value = {"pipeline_id": "test", "status": "running"}

            await jarvis_run_tool("test", ctx=cast(Context, FakeContext()))

        arguments = dict(run_handler.call_args.kwargs)
        reporter = arguments.pop("progress_reporter")
        await reporter(1.0, 2.0, "live")
        assert run_handler.call_args.args == ("test",)
        assert arguments == {
            "mode": "auto",
            "submit": True,
            "wait": False,
            "execution_id": None,
            "spack_specs": None,
            "pipeline_config": None,
        }
        assert reports == [(1.0, 2.0, "live")]

    @pytest.mark.asyncio
    async def test_jarvis_run_tool_maps_execution_intent(self):
        """User execution intent maps to JARVIS-native configuration."""
        with (
            patch("jarvis_mcp.server.run_pipeline") as run_handler,
            patch.dict("os.environ", {"JARVIS_MCP_SCHEDULER": "slurm"}),
        ):
            run_handler.return_value = {"pipeline_id": "test", "status": "submitted"}

            from jarvis_mcp.server import ExecutionIntent, jarvis_run_tool

            result = await jarvis_run_tool(
                "test",
                execution=ExecutionIntent.model_validate(
                    {
                        "mode": "cluster",
                        "nodes": 2,
                        "tasks": 40,
                        "partition": "compute",
                    }
                ),
            )

            assert result["status"] == "submitted"
            run_handler.assert_called_once_with(
                "test",
                mode="scheduler",
                submit=True,
                wait=False,
                execution_id=None,
                spack_specs=None,
                pipeline_config={
                    "scheduler": {
                        "name": "slurm",
                        "nodes": 2,
                        "ntasks": 40,
                        "partition": "compute",
                    }
                },
            )

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        ("requested_mode", "native_mode", "pipeline_config"),
        [
            (
                "scheduler",
                "scheduler",
                {"scheduler": {"name": "slurm"}},
            ),
            (
                "cluster",
                "scheduler",
                {"scheduler": {"name": "slurm"}},
            ),
            ("auto", "auto", {}),
            (
                "direct",
                "direct",
                {"scheduler": None, "hostfile": None},
            ),
        ],
    )
    async def test_jarvis_run_tool_preserves_explicit_execution_mode(
        self,
        requested_mode: str,
        native_mode: str,
        pipeline_config: dict[str, object],
    ) -> None:
        """A mode-only intent reaches JARVIS with its complete backend selection."""
        with (
            patch("jarvis_mcp.server.run_pipeline") as run_handler,
            patch.dict("os.environ", {"JARVIS_MCP_SCHEDULER": "slurm"}, clear=True),
        ):
            run_handler.return_value = {"pipeline_id": "test", "status": "submitted"}

            from jarvis_mcp.server import ExecutionIntent, jarvis_run_tool

            await jarvis_run_tool(
                "test",
                execution=ExecutionIntent.model_validate({"mode": requested_mode}),
            )

        run_handler.assert_called_once_with(
            "test",
            mode=native_mode,
            submit=True,
            wait=False,
            execution_id=None,
            spack_specs=None,
            pipeline_config=pipeline_config,
        )

    @pytest.mark.asyncio
    async def test_jarvis_run_tool_maps_hostfile_hosts(self):
        """Hostfile intent can be supplied as semantic host names."""
        with patch("jarvis_mcp.server.run_pipeline") as run_handler:
            run_handler.return_value = {"pipeline_id": "test", "status": "running"}

            from jarvis_mcp.server import ExecutionIntent, jarvis_run_tool

            await jarvis_run_tool(
                "test",
                execution=ExecutionIntent.model_validate(
                    {"mode": "hostfile", "hosts": ["node-a", "node-b"]}
                ),
            )

            run_handler.assert_called_once_with(
                "test",
                mode="direct",
                submit=True,
                wait=False,
                execution_id=None,
                spack_specs=None,
                pipeline_config={
                    "scheduler": None,
                    "hostfile_entries": ["node-a", "node-b"],
                },
            )

    @pytest.mark.asyncio
    async def test_jarvis_run_forwards_spack_specs(self):
        """Runtime package specs are owned by jarvis_run and persisted by JARVIS."""
        with patch("jarvis_mcp.server.run_pipeline") as run_handler:
            run_handler.return_value = {"pipeline_id": "test", "status": "completed"}

            from jarvis_mcp.server import jarvis_run_tool

            await jarvis_run_tool("test", spack_specs=["lammps@2025 +mpi"])

        run_handler.assert_called_once_with(
            "test",
            mode="auto",
            submit=True,
            wait=False,
            execution_id=None,
            spack_specs=["lammps@2025 +mpi"],
            pipeline_config=None,
        )

    @pytest.mark.asyncio
    async def test_execution_query_tools_delegate_to_native_handlers(self):
        """One user tool selects progress and artifact views in one query."""
        from jarvis_mcp.server import (
            ExecutionArtifactQuery,
            jarvis_get_execution_tool,
        )

        with patch("jarvis_mcp.server.get_execution") as get_handler:
            get_handler.return_value = {
                "schema_version": "clio-kit.jarvis-execution.v2",
                "pipeline_id": "pipeline",
                "execution_id": "execution-1",
                "execution_handle": {
                    "schema_version": "jarvis.execution.handle.v1",
                    "execution_id": "execution-1",
                    "pipeline_id": "pipeline",
                    "mode": "direct",
                    "scheduler_provider": None,
                    "scheduler_native_id": None,
                    "cluster": None,
                },
                "execution_record": {
                    "schema_version": "jarvis.execution.record.v1",
                    "execution_id": "execution-1",
                    "pipeline_id": "pipeline",
                    "pipeline_name": "pipeline",
                    "mode": "direct",
                    "scheduler_provider": None,
                    "scheduler_native_id": None,
                    "cluster": None,
                    "state": "running",
                    "submitted": False,
                    "terminal": False,
                    "created_at": "2026-01-01T00:00:00Z",
                    "updated_at": "2026-01-01T00:00:00Z",
                    "return_code": None,
                    "error": None,
                    "metadata": {},
                },
                "runtime_metadata": {},
                "progress": None,
                "artifact_page": None,
                "service_runtimes": None,
            }

            record = await jarvis_get_execution_tool("pipeline", "execution-1")
            filtered = await jarvis_get_execution_tool(
                "pipeline",
                "execution-1",
                include_progress=False,
                artifacts=ExecutionArtifactQuery(
                    package_id="jarvis-core",
                    role="log",
                    state="finalized",
                    artifact_id="art_AAAAAAAAAAAAAAAAAAAAAA",
                    page_size=25,
                    cursor="opaque-cursor",
                ),
            )

        assert record.schema_version == "clio-kit.jarvis-execution.v2"
        assert record.progress is None
        assert record.artifact_page is None
        assert filtered.schema_version == "clio-kit.jarvis-execution.v2"
        assert get_handler.await_args_list == [
            call(
                "pipeline",
                "execution-1",
                include_progress=True,
                include_service_runtimes=False,
                artifacts=None,
            ),
            call(
                "pipeline",
                "execution-1",
                include_progress=False,
                include_service_runtimes=False,
                artifacts={
                    "package_id": "jarvis-core",
                    "role": "log",
                    "state": "finalized",
                    "artifact_id": "art_AAAAAAAAAAAAAAAAAAAAAA",
                    "page_size": 25,
                    "cursor": "opaque-cursor",
                    "content_max_bytes": None,
                },
            ),
        ]

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

        with pytest.raises(ToolError, match="exactly one of hostfile or hosts"):
            _execution_intent_to_pipeline_config({"mode": "hostfile"})

    def test_execution_intent_rejects_unknown_mode(self):
        """Unknown execution modes fail before they reach JARVIS."""
        from jarvis_mcp.server import _execution_intent_to_pipeline_config

        with pytest.raises(ToolError, match="execution.mode must be one of"):
            _execution_intent_to_pipeline_config({"mode": "magic"})

    def test_execution_intent_schema_is_closed_and_typed(self):
        """The MCP schema advertises a finite mode enum and forbids unknown keys."""
        from jarvis_mcp.server import ExecutionIntent

        schema = ExecutionIntent.model_json_schema()

        assert schema["additionalProperties"] is False
        assert set(schema["properties"]["mode"]["enum"]) == {
            "auto",
            "local",
            "direct",
            "cluster",
            "scheduler",
            "hostfile",
        }

    def test_execution_intent_rejects_unknown_and_incompatible_fields(self):
        """Typos and fields that a selected backend cannot honor fail closed."""
        from jarvis_mcp.server import _execution_intent_to_pipeline_config

        with pytest.raises(ToolError, match="Extra inputs are not permitted"):
            _execution_intent_to_pipeline_config({"mode": "cluster", "nodez": 2})
        with pytest.raises(ToolError, match="does not accept fields: nodes"):
            _execution_intent_to_pipeline_config({"mode": "local", "nodes": 2})
        with pytest.raises(ToolError, match="exactly one of hostfile or hosts"):
            _execution_intent_to_pipeline_config(
                {
                    "mode": "hostfile",
                    "hostfile": "/tmp/hosts",
                    "hosts": ["n1"],
                }
            )

    def test_execution_intent_rejects_nonpositive_resources(self):
        """Invalid resource counts fail before scheduler configuration is persisted."""
        from jarvis_mcp.server import _execution_intent_to_pipeline_config

        with pytest.raises(ToolError, match="greater than 0"):
            _execution_intent_to_pipeline_config({"mode": "cluster", "nodes": 0})

    @pytest.mark.parametrize(
        "execution",
        [
            {"mode": "cluster", "job_name": "safe\n#SBATCH --exclusive"},
            {"mode": "cluster", "output": "out.log\nrm -rf /"},
            {"mode": "hostfile", "hostfile": "/tmp/hosts\nmalicious"},
            {"mode": "hostfile", "hosts": ["node-a\nattacker"]},
            {"mode": "hostfile", "hosts": ["--malicious"]},
        ],
    )
    def test_execution_intent_rejects_scheduler_and_host_injection(
        self,
        execution: dict[str, object],
    ) -> None:
        """Controls and option-shaped hosts fail before files or YAML are written."""
        from jarvis_mcp.server import _execution_intent_to_pipeline_config

        with pytest.raises(ToolError):
            _execution_intent_to_pipeline_config(execution)

    @pytest.mark.parametrize("mode", ["cluster", "scheduler"])
    def test_explicit_scheduler_intent_requires_detected_scheduler(
        self,
        mode: str,
    ) -> None:
        """Explicit scheduler modes fail if no scheduler exists on the MCP host."""
        with (
            patch.dict("os.environ", {}, clear=True),
            patch("shutil.which", return_value=None),
        ):
            from jarvis_mcp.server import _execution_intent_to_pipeline_config

            with pytest.raises(ToolError, match="no supported cluster scheduler"):
                _execution_intent_to_pipeline_config({"mode": mode})

    def test_execution_intent_auto_without_scheduler_is_noop(self):
        """Auto mode does not overwrite an existing pipeline on non-scheduler hosts."""
        with (
            patch.dict("os.environ", {}, clear=True),
            patch("shutil.which", return_value=None),
        ):
            from jarvis_mcp.server import _execution_intent_to_pipeline_config

            assert _execution_intent_to_pipeline_config({"mode": "auto"}) == {}

    def test_execution_intent_auto_does_not_discard_resource_fields(self):
        """Auto mode fails if resource intent cannot be represented on this host."""
        with (
            patch.dict("os.environ", {}, clear=True),
            patch("shutil.which", return_value=None),
        ):
            from jarvis_mcp.server import _execution_intent_to_pipeline_config

            with pytest.raises(ToolError, match="no supported cluster scheduler"):
                _execution_intent_to_pipeline_config({"mode": "auto", "nodes": 2})

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

    @pytest.mark.parametrize("mode", ["cluster", "scheduler"])
    def test_explicit_scheduler_intent_without_options_selects_detected_scheduler(
        self,
        mode: str,
    ) -> None:
        """Explicit scheduler modes persist backend selection without resource overrides."""
        from jarvis_mcp.server import _execution_intent_to_pipeline_config

        with (
            patch.dict("os.environ", {}, clear=True),
            patch("shutil.which", return_value="/usr/bin/sbatch"),
        ):
            assert _execution_intent_to_pipeline_config({"mode": mode}) == {
                "scheduler": {"name": "slurm"}
            }

    def test_execution_intent_auto_with_scheduler_preserves_pipeline(self):
        """Auto mode without overrides leaves existing scheduler configuration intact."""
        from jarvis_mcp.server import _execution_intent_to_pipeline_config

        with (
            patch.dict("os.environ", {}, clear=True),
            patch("shutil.which", return_value="/usr/bin/sbatch"),
        ):
            assert _execution_intent_to_pipeline_config({"mode": "auto"}) == {}

    def test_execution_intent_hostfile_entries(self):
        """Hostfile mode can materialize explicit host entries."""
        from jarvis_mcp.server import _execution_intent_to_pipeline_config

        assert _execution_intent_to_pipeline_config(
            {"mode": "hostfile", "hosts": ["n1", "n2"]}
        ) == {"scheduler": None, "hostfile_entries": ["n1", "n2"]}

    def test_apply_tool_profile_rejects_unknown_profile(self):
        """Unknown profile names fail explicitly."""
        from jarvis_mcp.server import apply_tool_profile

        with pytest.raises(ValueError, match="profile must be one of"):
            apply_tool_profile("operator")

    def test_package_description_helpers_cover_docstrings_comments_and_settings(
        self, tmp_path
    ):
        """Package helper functions extract descriptions and optional settings."""
        from jarvis_mcp.server import (
            _PackageAgentMetadata,
            _first_docstring_or_comment,
            _package_from_pkg_file,
            _setting_from_menu_item,
        )

        comment_pkg = tmp_path / "comment_pkg.py"
        comment_pkg.write_text("\n# comment description\nclass Pkg: pass\n")
        assert _first_docstring_or_comment(comment_pkg) == "comment description"

        multiline_pkg = tmp_path / "multiline_pkg.py"
        multiline_pkg.write_text('"""\nfirst line\nsecond line\n"""\nclass Pkg: pass\n')
        assert _first_docstring_or_comment(multiline_pkg) == "first line second line"
        assert _first_docstring_or_comment(tmp_path) is None
        assert _setting_from_menu_item(
            {"name": "nodes", "msg": "Node count", "type": int, "default": 1}
        ) == {
            "name": "nodes",
            "description": "Node count",
            "type": "int",
            "default": 1,
            "required": False,
            "nullable": False,
        }

        repo = tmp_path / "repo"
        pkg_dir = repo / "builtin" / "demo"
        pkg_dir.mkdir(parents=True)
        pkg_file = pkg_dir / "pkg.py"
        pkg_file.write_text('"""Demo."""\n')
        with patch(
            "jarvis_mcp.package_discovery._package_agent_metadata",
            return_value=_PackageAgentMetadata(
                settings=[{"name": "x"}],
                deployment=None,
            ),
        ):
            assert _package_from_pkg_file(repo, pkg_file)["settings"] == [{"name": "x"}]

    @pytest.mark.asyncio
    async def test_package_lookup_and_step_snapshot_edge_cases(self, tmp_path):
        """Package lookup handles duplicates/misses and step snapshots skip invalid rows."""
        from jarvis_mcp.server import (
            _find_package_description,
            _step_snapshot,
            jarvis_describe_tool,
        )

        assert (
            _step_snapshot({"packages": ["bad", {"pkg_id": "ok"}]}, "missing") is None
        )
        assert _step_snapshot({"packages": ["bad", {"global_id": "ok"}]}, "ok") == {
            "global_id": "ok"
        }

        repo = tmp_path / "repo"
        for subdir in ("builtin/demo", "duplicate/demo"):
            pkg_dir = repo / subdir
            pkg_dir.mkdir(parents=True)
            (pkg_dir / "pkg.py").write_text('"""Demo."""\n')
        manager = Mock()
        manager.list_repos.return_value = [repo]
        with patch("jarvis_mcp.server.get_manager", return_value=manager):
            assert _find_package_description("missing") is None
            packages = await jarvis_describe_tool("packages")
            assert packages["target"] == "packages"

    @pytest.mark.asyncio
    async def test_package_discovery_supports_package_py_layout(self, tmp_path):
        """JARVIS repositories using package.py are exposed like pkg.py repositories."""
        repo = tmp_path / "repo"
        package_dir = repo / "site" / "solver"
        package_dir.mkdir(parents=True)
        package_file = package_dir / "package.py"
        package_file.write_text('"""Site solver."""\n', encoding="utf-8")
        manager = Mock()
        manager.list_repos.return_value = [repo]
        from jarvis_mcp.server import _PackageAgentMetadata, jarvis_describe_tool

        with (
            patch("jarvis_mcp.server.get_manager", return_value=manager),
            patch(
                "jarvis_mcp.package_discovery._package_agent_metadata",
                return_value=_PackageAgentMetadata(settings=None, deployment=None),
            ),
        ):
            result = await jarvis_describe_tool("packages")

        assert result["packages"] == [
            {
                "schema_version": "jarvis.package-description.v1",
                "name": "site.solver",
                "short_name": "solver",
                "description": "Site solver.",
                "deployment": None,
            }
        ]

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
        from jarvis_mcp.server import _PackageAgentMetadata, jarvis_describe_tool

        with (
            patch("jarvis_mcp.server.get_manager", return_value=manager),
            patch(
                "jarvis_mcp.package_discovery._package_agent_metadata",
                return_value=_PackageAgentMetadata(settings=None, deployment=None),
            ),
        ):
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

    @pytest.mark.parametrize("profile", ["admin", "all"])
    def test_main_accepts_compatibility_profile_overrides(self, profile):
        """The packaged jarvis-mcp entry point can select admin and all surfaces."""
        with (
            patch("sys.argv", ["jarvis-mcp", "--profile", profile]),
            patch("jarvis_mcp.server.apply_tool_profile") as mock_profile,
            patch("jarvis_mcp.server.mcp.run") as mock_run,
        ):
            from jarvis_mcp.server import main

            main()

        mock_profile.assert_called_once_with(profile)
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

    def test_user_server_entrypoint_defaults_to_stdio(self):
        """The user entrypoint defaults to stdio when no transport is configured."""
        sys.modules.pop("jarvis_mcp.user_server", None)
        with (
            patch("sys.argv", ["jarvis-mcp"]),
            patch.dict("os.environ", {}, clear=True),
            patch("jarvis_mcp.server.apply_tool_profile") as mock_profile,
            patch("jarvis_mcp.server.mcp.run") as mock_run,
        ):
            module = importlib.import_module("jarvis_mcp.user_server")

            module.main()

            mock_profile.assert_called_once_with("user")
            mock_run.assert_called_once_with(transport="stdio")

    def test_user_server_sets_validated_spack_command(self, tmp_path):
        """The packaged user entrypoint accepts an explicit audited Spack path."""
        command = tmp_path / "spack"
        command.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
        command.chmod(0o755)
        sys.modules.pop("jarvis_mcp.user_server", None)
        with (
            patch(
                "sys.argv",
                ["jarvis-mcp", "--spack-command", str(command)],
            ),
            patch.dict("os.environ", {}, clear=True),
            patch("jarvis_mcp.server.apply_tool_profile"),
            patch("jarvis_mcp.server.mcp.run") as mock_run,
        ):
            module = importlib.import_module("jarvis_mcp.user_server")

            module.main()

            assert os.environ["JARVIS_MCP_SPACK_COMMAND"] == str(command.resolve())
            mock_run.assert_called_once_with(transport="stdio")

    def test_admin_server_entrypoint_runs_http(self):
        """The admin entrypoint supports HTTP transport when requested."""
        sys.modules.pop("jarvis_mcp.admin_server", None)
        with (
            patch("sys.argv", ["jarvis-admin-mcp", "--transport", "http"]),
            patch("jarvis_mcp.server.apply_tool_profile") as mock_profile,
            patch("jarvis_mcp.server.mcp.run") as mock_run,
        ):
            module = importlib.import_module("jarvis_mcp.admin_server")

            module.main()

            mock_profile.assert_called_once_with("admin")
            mock_run.assert_called_once_with(
                transport="http", host="0.0.0.0", port=8000
            )

    def test_admin_server_rejects_missing_spack_command(self, tmp_path):
        """The packaged admin entrypoint validates an explicit Spack path."""
        sys.modules.pop("jarvis_mcp.admin_server", None)
        with (
            patch(
                "sys.argv",
                [
                    "jarvis-admin-mcp",
                    "--spack-command",
                    str(tmp_path / "missing-spack"),
                ],
            ),
            patch("jarvis_mcp.server.apply_tool_profile"),
        ):
            module = importlib.import_module("jarvis_mcp.admin_server")
            with pytest.raises(SystemExit) as error:
                module.main()

        assert error.value.code == 2

    def test_user_server_module_main_guard(self):
        """Running the user module as __main__ delegates through its main guard."""
        sys.modules.pop("jarvis_mcp.user_server", None)
        with (
            patch("sys.argv", ["jarvis-mcp"]),
            patch("jarvis_mcp.server.apply_tool_profile"),
            patch("jarvis_mcp.server.mcp.run") as mock_run,
        ):
            runpy.run_module("jarvis_mcp.user_server", run_name="__main__")

        mock_run.assert_called_with(transport="stdio")

    def test_admin_server_module_main_guard(self):
        """Running the admin module as __main__ delegates through its main guard."""
        sys.modules.pop("jarvis_mcp.admin_server", None)
        with (
            patch("sys.argv", ["jarvis-admin-mcp"]),
            patch("jarvis_mcp.server.apply_tool_profile"),
            patch("jarvis_mcp.server.mcp.run") as mock_run,
        ):
            runpy.run_module("jarvis_mcp.admin_server", run_name="__main__")

        mock_run.assert_called_with(transport="stdio")


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
