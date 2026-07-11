"""
Tests for the jarvis_handler module that contains pipeline operation logic.
"""

import json
import os
import subprocess
import sys

import pytest
from types import ModuleType, SimpleNamespace
from pathlib import Path
from unittest.mock import Mock, patch
from fastapi import HTTPException
from fastmcp.exceptions import ToolError

from jarvis_mcp.capabilities.jarvis_handler import (
    create_pipeline,
    configure_pipeline,
    load_pipeline,
    append_pkg,
    build_pipeline_env,
    update_pipeline,
    configure_pkg,
    get_pkg_config,
    unlink_pkg,
    remove_pkg,
    run_pipeline,
    destroy_pipeline,
)


class ModernPipeline:
    """Small stand-in for the current JARVIS Pipeline API."""

    instances = []

    def __init__(self, name: str | None = None):
        self.name = name or "loaded"
        self.global_id = self.name
        self.scheduler = None
        self.hostfile = None
        self.packages = [{"id": "pkg1", "type": "builtin.echo", "config": {"x": 1}}]
        self.env = {}
        self.config = {"name": self.name, "packages": self.packages}
        self.saved = False
        self.ran = False
        self.submitted = False
        self.last_loaded_file = None
        self.last_submission = None
        self.jarvis = Mock()
        self.jarvis.get_pipeline_shared_dir.return_value = Path("/tmp") / self.name
        ModernPipeline.instances.append(self)

    def load(self, load_type: str | None = None):
        return self

    def save(self):
        self.saved = True

    def run(self):
        self.ran = True

    def submit(self, *, submit: bool = True, wait: bool = False):
        self.submitted = submit
        self.waited = wait
        script_path = Path("/tmp") / self.name / "submit.slurm"
        provider = (
            self.scheduler.get("name") if isinstance(self.scheduler, dict) else None
        )
        self.last_submission = {
            "schema_version": "jarvis.scheduler.submission.v1",
            "provider": provider,
            "script_path": str(script_path),
            "scheduler_job_id": "24680" if submit else None,
            "scheduler_cluster": "ares" if submit else None,
            "identity_source": "scheduler_submit_api" if submit else None,
            "state": "completed"
            if submit and wait
            else "submitted"
            if submit
            else "scripted",
            "submitted": submit,
            "wait": wait,
            "terminal": submit and wait,
            "submission_returncode": 0 if submit else None,
        }
        return script_path


class TestHandlerHelpers:
    """Test helper branches used by the semantic MCP contract."""

    def test_jsonable_and_config_arg_helpers(self):
        """Non-JSON values are normalized and config args preserve bool spelling."""
        from jarvis_mcp.capabilities.jarvis_handler import (
            _jsonable,
            _kwargs_to_config_args,
        )

        assert _jsonable({"path": Path("/tmp/x"), "items": (Path("/tmp/y"),)}) == {
            "path": repr(Path("/tmp/x")),
            "items": [repr(Path("/tmp/y"))],
        }
        assert _kwargs_to_config_args(
            {"enabled": True, "disabled": False, "skip": None, "count": 2}
        ) == ["enabled=true", "disabled=false", "count=2"]

    def test_pipeline_snapshot_helpers_fallback_to_current_api_fields(self, tmp_path):
        """Current Pipeline objects expose config, package, and path fallbacks."""
        from jarvis_mcp.capabilities.jarvis_handler import (
            _get_package,
            _package_config,
            _package_snapshot,
            _pipeline_config,
            _pipeline_config_path,
            _pipeline_env_path,
            _pipeline_packages,
        )

        jarvis = Mock()
        jarvis.get_pipeline_dir.return_value = tmp_path / "pipe"
        pipeline = SimpleNamespace(
            name="pipe",
            config=None,
            packages=[{"id": "step1", "type": "builtin.echo", "config": {"x": 1}}],
            sub_pkgs=None,
            scheduler={"name": "slurm"},
            hostfile="hosts.txt",
            interceptors=None,
            jarvis=jarvis,
        )

        assert _pipeline_packages(pipeline) == pipeline.packages
        assert _get_package(pipeline, "step1") == pipeline.packages[0]
        assert _package_config(pipeline.packages[0]) == {"x": 1}
        assert _package_snapshot(pipeline.packages[0])["pkg_type"] == "builtin.echo"
        assert _pipeline_config(pipeline)["scheduler"] == {"name": "slurm"}
        assert _pipeline_config_path(pipeline) == tmp_path / "pipe" / "pipeline.yaml"
        assert _pipeline_env_path(pipeline) == tmp_path / "pipe" / "environment.yaml"

    def test_pipeline_class_requirement_reports_missing_import(self):
        """Missing JARVIS pipeline support fails with actionable detail."""
        from jarvis_mcp.capabilities import jarvis_handler

        with (
            patch.object(jarvis_handler, "Pipeline", None),
            patch.object(
                jarvis_handler,
                "_PIPELINE_IMPORT_ERROR",
                ModuleNotFoundError("jarvis_cd"),
            ),
            pytest.raises(
                RuntimeError, match="JARVIS-CD Pipeline API is not available"
            ),
        ):
            jarvis_handler._require_pipeline_class()

    def test_apply_pipeline_config_validation_branches(self):
        """Pipeline config validation rejects unsupported scheduler/env shapes."""
        from jarvis_mcp.capabilities.jarvis_handler import _apply_pipeline_config

        pipeline = ModernPipeline("configured")
        with pytest.raises(ValueError, match="scheduler must be an object"):
            _apply_pipeline_config(pipeline, {"scheduler": "slurm"})
        with pytest.raises(ValueError, match="hostfile_entries must be"):
            _apply_pipeline_config(pipeline, {"hostfile_entries": "node1"})
        with pytest.raises(ValueError, match="env must be an object"):
            _apply_pipeline_config(pipeline, {"env": "OMP=4"})

    def test_spack_environment_is_merged_and_persisted_for_scheduler_reload(
        self, tmp_path
    ):
        """Spack state becomes durable pipeline state, not process-local state."""
        from jarvis_mcp.capabilities.jarvis_handler import _apply_spack_environment

        pipeline = ModernPipeline("spack-runtime")
        pipeline.jarvis.get_pipeline_dir.return_value = tmp_path / pipeline.name
        pipeline.env = {"UNCHANGED": "value"}
        pipeline.last_loaded_file = "/tmp/source.yaml"

        with patch(
            "jarvis_mcp.capabilities.jarvis_handler._capture_spack_environment",
            return_value={"PATH": "/spack/bin", "SPACK_ROOT": "/opt/spack"},
        ) as capture:
            metadata = _apply_spack_environment(pipeline, ["lammps@2025 +mpi"])

        capture.assert_called_once_with(["lammps@2025 +mpi"])
        assert pipeline.env == {
            "UNCHANGED": "value",
            "PATH": "/spack/bin",
            "SPACK_ROOT": "/opt/spack",
        }
        assert pipeline.last_loaded_file is None
        assert pipeline.saved is True
        assert metadata is not None
        assert metadata["persisted"] is True
        assert metadata["scheduler_reload"] == "saved_pipeline_environment"
        assert metadata["variable_names"] == ["PATH", "SPACK_ROOT"]
        assert metadata["removed_variable_names"] == []

    def test_spack_environment_replaces_prior_owned_variables_across_reloads(
        self, tmp_path
    ):
        """A later spec set cannot retain variables owned only by an earlier set."""
        from jarvis_mcp.capabilities.jarvis_handler import _apply_spack_environment

        pipeline_dir = tmp_path / "spack-runtime"
        first = ModernPipeline("spack-runtime")
        first.jarvis.get_pipeline_dir.return_value = pipeline_dir
        first.env = {"SITE_SETTING": "preserved", "PATH": "/site/bin"}
        second = ModernPipeline("spack-runtime")
        second.jarvis.get_pipeline_dir.return_value = pipeline_dir

        with patch(
            "jarvis_mcp.capabilities.jarvis_handler._capture_spack_environment",
            side_effect=[
                {"PATH": "/spack/old/bin", "OLD_SPEC_ONLY": "old"},
                {"NEW_SPEC_ONLY": "new"},
            ],
        ):
            _apply_spack_environment(first, ["old-spec"])
            second.env = dict(first.env)
            metadata = _apply_spack_environment(second, ["new-spec"])

        assert second.env == {
            "SITE_SETTING": "preserved",
            "PATH": "/site/bin",
            "NEW_SPEC_ONLY": "new",
        }
        assert metadata is not None
        assert metadata["removed_variable_names"] == ["OLD_SPEC_ONLY", "PATH"]

    def test_jarvis_spack_specs_reject_option_injection(self):
        """Spack specs cannot be reinterpreted as Spack command options."""
        from jarvis_mcp.capabilities.jarvis_handler import _validate_spack_specs

        with pytest.raises(ValueError, match="cannot begin"):
            _validate_spack_specs(["--help"])

    def test_spack_capture_is_bounded_while_draining_both_streams(self):
        """Large child output retains a bounded tail without a pipe deadlock."""
        from jarvis_mcp.capabilities import jarvis_handler

        with patch.object(jarvis_handler, "_MAX_SPACK_CAPTURE_BYTES", 64):
            result = jarvis_handler._run_bounded_process(
                [
                    sys.executable,
                    "-c",
                    "import sys; sys.stdout.buffer.write(b'a' * 4096 + b'TAIL'); "
                    "sys.stderr.buffer.write(b'b' * 4096 + b'ERR')",
                ],
                env=os.environ.copy(),
                timeout_seconds=10,
            )

        assert result.stdout_truncated is True
        assert result.stderr_truncated is True
        assert len(result.stdout) == 64
        assert len(result.stderr) == 64
        assert result.stdout.endswith(b"TAIL")
        assert result.stderr.endswith(b"ERR")

    def test_spack_capture_timeout_terminates_child(self):
        """A timed-out environment child is explicitly terminated."""
        from jarvis_mcp.capabilities.jarvis_handler import _run_bounded_process

        with pytest.raises(subprocess.TimeoutExpired):
            _run_bounded_process(
                [sys.executable, "-c", "import time; time.sleep(30)"],
                env=os.environ.copy(),
                timeout_seconds=1,
            )

    def test_spack_environment_rejects_truncated_script(self):
        """JARVIS never evaluates an incomplete Spack-generated shell script."""
        from jarvis_mcp.capabilities import jarvis_handler

        truncated = jarvis_handler._BoundedProcessResult(
            returncode=0,
            stdout=b"export PATH=/spack/bin",
            stderr=b"",
            stdout_truncated=True,
        )
        with (
            patch.object(jarvis_handler, "_spack_executable", return_value="spack"),
            patch.object(
                jarvis_handler,
                "_run_bounded_process",
                return_value=truncated,
            ),
            pytest.raises(RuntimeError, match="script exceeded the output limit"),
        ):
            jarvis_handler._capture_spack_environment(["lammps"])

    def test_spack_environment_uses_integrity_marker_and_filters_secrets(self):
        """Only marker-delimited, filtered environment values become pipeline state."""
        from jarvis_mcp.capabilities import jarvis_handler

        loaded = jarvis_handler._BoundedProcessResult(
            returncode=0,
            stdout=b"export PATH=/spack/bin:$PATH",
            stderr=b"",
        )
        captured = jarvis_handler._BoundedProcessResult(
            returncode=0,
            stdout=(
                b"ignored warning\n"
                + jarvis_handler._SPACK_ENVIRONMENT_MARKER
                + b"SPACK_ROOT=/spack\0PATH=/spack/bin\0API_TOKEN=secret\0"
            ),
            stderr=b"",
        )
        with (
            patch.object(jarvis_handler, "_spack_executable", return_value="spack"),
            patch.object(
                jarvis_handler,
                "_run_bounded_process",
                side_effect=[loaded, captured],
            ),
        ):
            environment = jarvis_handler._capture_spack_environment(["lammps"])

        assert environment == {"PATH": "/spack/bin", "SPACK_ROOT": "/spack"}

    def test_apply_pipeline_config_hostfiles_env_and_hooks(self, tmp_path):
        """Hostfile, env, scheduler, and launcher hooks map to current Pipeline fields."""
        from jarvis_mcp.capabilities.jarvis_handler import _apply_pipeline_config

        class FakeHostfile:
            def __init__(self, path: str):
                self.path = path

        hostfile_module = ModuleType("hostfile")
        hostfile_module.Hostfile = FakeHostfile

        pipeline = ModernPipeline("configured")
        pipeline.jarvis.get_pipeline_shared_dir.return_value = tmp_path
        pipeline._apply_scheduler_hostfile = Mock()
        pipeline._apply_launcher_overrides = Mock()

        with patch.dict(
            "sys.modules",
            {"jarvis_cd.util.hostfile": hostfile_module},
        ):
            _apply_pipeline_config(
                pipeline,
                {
                    "scheduler": {"name": "slurm"},
                    "hostfile": tmp_path / "hosts.txt",
                    "hostfile_entries": ["n1", "n2"],
                    "env": None,
                    "container_image": "image.sif",
                },
            )

        assert pipeline.scheduler == {"name": "slurm"}
        pipeline._apply_scheduler_hostfile.assert_called_once_with()
        pipeline._apply_launcher_overrides.assert_called_once_with()
        assert pipeline.env == {}
        assert pipeline.container_image == "image.sif"
        assert pipeline.hostfile.path == str(tmp_path / "mcp-hostfile.txt")
        assert (tmp_path / "mcp-hostfile.txt").read_text(encoding="utf-8") == "n1\nn2\n"

    def test_load_and_env_helpers_cover_current_api_branches(self):
        """Current Pipeline load and environment helpers handle optional APIs."""
        from jarvis_mcp.capabilities import jarvis_handler

        class LoadedPipeline(ModernPipeline):
            def __init__(self, name: str | None = None):
                super().__init__(name)
                self.build_calls = 0

            def load(self, load_type: str | None = None):
                self.loaded_type = load_type
                return self

            def build_env(self, env_track_dict=None):
                self.build_calls += 1
                if env_track_dict is not None:
                    raise TypeError("old signature")
                built = ModernPipeline("built")
                built.saved = False
                return built

        with patch.object(jarvis_handler, "Pipeline", LoadedPipeline):
            loaded = jarvis_handler._load_pipeline(None)
            assert isinstance(loaded, LoadedPipeline)
            jarvis_handler._build_pipeline_env(loaded)

        assert loaded.build_calls == 2
        assert ModernPipeline.instances[-1].saved is True

        no_env = SimpleNamespace()
        jarvis_handler._build_pipeline_env(no_env)

    def test_package_lookup_object_and_missing_path_fallbacks(self):
        """Package and path helpers handle object packages and missing Jarvis paths."""
        from jarvis_mcp.capabilities.jarvis_handler import (
            _get_package,
            _package_config,
            _pipeline_config_path,
            _pipeline_env_path,
        )

        pkg = SimpleNamespace(pkg_id="step1", config={"alpha": 1})
        pipeline = SimpleNamespace(packages=[pkg], sub_pkgs=None)

        assert _get_package(pipeline, "step1") is pkg
        assert _package_config(pkg) == {"alpha": 1}
        assert _get_package(pipeline, "missing") is None
        assert (
            _pipeline_config_path(SimpleNamespace(name="pipe", jarvis=object())) is None
        )
        assert _pipeline_env_path(SimpleNamespace(name="pipe", jarvis=object())) is None


class TestPipelineOperations:
    """Test core pipeline operations."""

    @pytest.mark.asyncio
    async def test_create_pipeline_success(self, mock_pipeline):
        """Test successful pipeline creation."""
        result = await create_pipeline("test_pipeline")

        assert result["pipeline_id"] == "test_pipeline"
        assert result["status"] == "created"

        # Verify the chain of operations
        mock_pipeline.create.assert_called_once_with("test_pipeline")
        mock_pipeline.build_env.assert_called_once()
        mock_pipeline.save.assert_called_once()

    @pytest.mark.asyncio
    async def test_create_pipeline_failure(self, mock_pipeline):
        """Test pipeline creation failure."""
        mock_pipeline.create.side_effect = Exception("Creation failed")

        with pytest.raises(HTTPException) as exc_info:
            await create_pipeline("test_pipeline")

        assert exc_info.value.status_code == 500
        assert "Create failed" in str(exc_info.value.detail)

    @pytest.mark.asyncio
    async def test_load_pipeline_success(self, mock_pipeline):
        """Test successful pipeline loading."""
        result = await load_pipeline("test_pipeline")

        assert result["pipeline_id"] == "test_pipeline"
        assert result["status"] == "loaded"
        mock_pipeline.load.assert_called_once_with("test_pipeline")

    @pytest.mark.asyncio
    async def test_load_pipeline_with_none_id(self, mock_pipeline):
        """Test pipeline loading with None ID."""
        result = await load_pipeline(None)

        assert result["pipeline_id"] is None
        assert result["status"] == "loaded"
        mock_pipeline.load.assert_called_once_with(None)

    @pytest.mark.asyncio
    async def test_load_pipeline_failure(self, mock_pipeline):
        """Test pipeline loading failure."""
        mock_pipeline.load.side_effect = Exception("Load failed")

        with pytest.raises(HTTPException) as exc_info:
            await load_pipeline("test_pipeline")

        assert exc_info.value.status_code == 500
        assert "Load failed" in str(exc_info.value.detail)

    @pytest.mark.asyncio
    async def test_append_pkg_success(self, mock_pipeline):
        """Test successful package appending."""
        result = await append_pkg(
            "test_pipeline",
            "data_loader",
            pkg_id="loader1",
            do_configure=True,
            extra_param="value",
        )

        assert result["pipeline_id"] == "test_pipeline"
        assert result["appended"] == "data_loader"

        mock_pipeline.load.assert_called_once_with("test_pipeline")
        mock_pipeline.append.assert_called_once_with(
            "data_loader", pkg_id="loader1", do_configure=True, extra_param="value"
        )
        mock_pipeline.save.assert_called_once()

    @pytest.mark.asyncio
    async def test_append_pkg_with_do_configure_in_kwargs(self, mock_pipeline):
        """Test package appending with do_configure in kwargs."""
        # Test that explicit parameter works without conflict
        kwargs_without_conflict = {"extra_param": "value"}

        result = await append_pkg(
            "test_pipeline",
            "data_loader",
            do_configure=False,  # This should be used
            **kwargs_without_conflict,
        )

        assert result["pipeline_id"] == "test_pipeline"
        assert result["appended"] == "data_loader"

        # Should use the parameter value
        mock_pipeline.append.assert_called_once_with(
            "data_loader", pkg_id=None, do_configure=False, extra_param="value"
        )

    @pytest.mark.asyncio
    async def test_append_pkg_failure(self, mock_pipeline):
        """Test package appending failure."""
        mock_pipeline.append.side_effect = Exception("Append failed")

        with pytest.raises(HTTPException) as exc_info:
            await append_pkg("test_pipeline", "data_loader")

        assert exc_info.value.status_code == 500
        assert "Append failed" in str(exc_info.value.detail)

    @pytest.mark.asyncio
    async def test_build_pipeline_env_success(self, mock_pipeline):
        """Test successful pipeline environment building."""
        result = await build_pipeline_env("test_pipeline")

        assert result["pipeline_id"] == "test_pipeline"
        assert result["status"] == "environment_built"

        mock_pipeline.load.assert_called_once_with("test_pipeline")
        mock_pipeline.build_env.assert_called_once_with(
            {"CMAKE_PREFIX_PATH": True, "PATH": True}
        )
        mock_pipeline.save.assert_called_once()

    @pytest.mark.asyncio
    async def test_build_pipeline_env_failure(self, mock_pipeline):
        """Test pipeline environment building failure."""
        mock_pipeline.build_env.side_effect = Exception("Build env failed")

        with pytest.raises(HTTPException) as exc_info:
            await build_pipeline_env("test_pipeline")

        assert exc_info.value.status_code == 500
        assert "Build env failed" in str(exc_info.value.detail)

    @pytest.mark.asyncio
    async def test_update_pipeline_success(self, mock_pipeline):
        """Test successful pipeline update."""
        result = await update_pipeline("test_pipeline")

        assert result["pipeline_id"] == "test_pipeline"
        assert result["status"] == "updated"

        mock_pipeline.load.assert_called_once_with("test_pipeline")
        mock_pipeline.update.assert_called_once()
        mock_pipeline.save.assert_called_once()

    @pytest.mark.asyncio
    async def test_update_pipeline_failure(self, mock_pipeline):
        """Test pipeline update failure."""
        mock_pipeline.update.side_effect = Exception("Update failed")

        with pytest.raises(HTTPException) as exc_info:
            await update_pipeline("test_pipeline")

        assert exc_info.value.status_code == 500
        assert "Update failed" in str(exc_info.value.detail)


class TestPackageOperations:
    """Test package-specific operations."""

    @pytest.mark.asyncio
    async def test_configure_pkg_success(self, mock_pipeline):
        """Test successful package configuration."""
        result = await configure_pkg(
            "test_pipeline", "test_pkg", batch_size=100, debug=True
        )

        assert result["pipeline_id"] == "test_pipeline"
        assert result["configured"] == "test_pkg"

        mock_pipeline.load.assert_called_once_with("test_pipeline")
        mock_pipeline.configure.assert_called_once_with(
            "test_pkg", batch_size=100, debug=True
        )
        mock_pipeline.save.assert_called_once()

    @pytest.mark.asyncio
    async def test_configure_pkg_failure(self, mock_pipeline):
        """Test package configuration failure."""
        mock_pipeline.configure.side_effect = Exception("Configure failed")

        with pytest.raises(HTTPException) as exc_info:
            await configure_pkg("test_pipeline", "test_pkg")

        assert exc_info.value.status_code == 500
        assert "Configure failed" in str(exc_info.value.detail)

    @pytest.mark.asyncio
    async def test_get_pkg_config_success(self, mock_pipeline):
        """Test successful package configuration retrieval."""
        mock_pkg = Mock()
        mock_pkg.config = {"batch_size": 100, "debug": True}
        mock_pipeline.get_pkg.return_value = mock_pkg
        mock_pipeline.global_id = "test_pipeline"

        result = await get_pkg_config("test_pipeline", "test_pkg")

        assert result["pipeline_id"] == "test_pipeline"
        assert result["pkg_id"] == "test_pkg"
        assert result["config"] == {"batch_size": 100, "debug": True}

        mock_pipeline.load.assert_called_once_with("test_pipeline")
        mock_pipeline.get_pkg.assert_called_once_with("test_pkg")

    @pytest.mark.asyncio
    async def test_get_pkg_config_package_not_found(self, mock_pipeline):
        """Test package configuration retrieval when package not found."""
        mock_pipeline.get_pkg.return_value = None

        with pytest.raises(HTTPException) as exc_info:
            await get_pkg_config("test_pipeline", "nonexistent_pkg")

        assert exc_info.value.status_code == 404
        assert "Package 'nonexistent_pkg' not found" in str(exc_info.value.detail)

    @pytest.mark.asyncio
    async def test_get_pkg_config_failure(self, mock_pipeline):
        """Test package configuration retrieval failure."""
        mock_pipeline.get_pkg.side_effect = Exception("Get config failed")

        with pytest.raises(HTTPException) as exc_info:
            await get_pkg_config("test_pipeline", "test_pkg")

        assert exc_info.value.status_code == 500
        assert "Get config failed" in str(exc_info.value.detail)

    @pytest.mark.asyncio
    async def test_unlink_pkg_success(self, mock_pipeline):
        """Test successful package unlinking."""
        result = await unlink_pkg("test_pipeline", "test_pkg")

        assert result["pipeline_id"] == "test_pipeline"
        assert result["unlinked"] == "test_pkg"

        mock_pipeline.load.assert_called_once_with("test_pipeline")
        mock_pipeline.unlink.assert_called_once_with("test_pkg")
        mock_pipeline.save.assert_called_once()

    @pytest.mark.asyncio
    async def test_unlink_pkg_failure(self, mock_pipeline):
        """Test package unlinking failure."""
        mock_pipeline.unlink.side_effect = Exception("Unlink failed")

        with pytest.raises(HTTPException) as exc_info:
            await unlink_pkg("test_pipeline", "test_pkg")

        assert exc_info.value.status_code == 500
        assert "Unlink failed" in str(exc_info.value.detail)

    @pytest.mark.asyncio
    async def test_unlink_pkg_rejects_unknown_package(self, mock_pipeline):
        """Unlink never reports success when the requested package is absent."""
        mock_pipeline.get_pkg.return_value = None

        with pytest.raises(HTTPException) as exc_info:
            await unlink_pkg("test_pipeline", "missing")

        assert exc_info.value.status_code == 404
        mock_pipeline.unlink.assert_not_called()
        mock_pipeline.save.assert_not_called()

    @pytest.mark.asyncio
    async def test_remove_pkg_success(self, mock_pipeline):
        """Test successful package removal."""
        result = await remove_pkg("test_pipeline", "test_pkg")

        assert result["pipeline_id"] == "test_pipeline"
        assert result["removed"] == "test_pkg"

        mock_pipeline.load.assert_called_once_with("test_pipeline")
        mock_pipeline.remove.assert_called_once_with("test_pkg")
        mock_pipeline.save.assert_called_once()

    @pytest.mark.asyncio
    async def test_remove_pkg_failure(self, mock_pipeline):
        """Test package removal failure."""
        mock_pipeline.remove.side_effect = Exception("Remove failed")

        with pytest.raises(HTTPException) as exc_info:
            await remove_pkg("test_pipeline", "test_pkg")

        assert exc_info.value.status_code == 500
        assert "Remove failed" in str(exc_info.value.detail)

    @pytest.mark.asyncio
    async def test_remove_pkg_rejects_unknown_package(self, mock_pipeline):
        """Destructive removal distinguishes an absent package from success."""
        mock_pipeline.get_pkg.return_value = None

        with pytest.raises(HTTPException) as exc_info:
            await remove_pkg("test_pipeline", "missing")

        assert exc_info.value.status_code == 404
        mock_pipeline.remove.assert_not_called()
        mock_pipeline.save.assert_not_called()


class TestPipelineExecutionOperations:
    """Test pipeline execution and lifecycle operations."""

    @pytest.mark.asyncio
    async def test_run_pipeline_success(self, mock_pipeline):
        """Test successful pipeline execution."""
        result = await run_pipeline("test_pipeline")

        assert result["pipeline_id"] == "test_pipeline"
        assert result["status"] == "completed"
        assert result["runtime_metadata"]["terminal"]["terminal"] is True

        mock_pipeline.load.assert_called_once_with("test_pipeline")
        mock_pipeline.run.assert_called_once()

    @pytest.mark.asyncio
    async def test_run_pipeline_failure(self, mock_pipeline):
        """Test pipeline execution failure."""
        mock_pipeline.run.side_effect = Exception("Run failed")

        with pytest.raises(ToolError) as exc_info:
            await run_pipeline("test_pipeline")

        error = json.loads(str(exc_info.value))
        assert error["schema_version"] == "jarvis.error.v1"
        assert "Run failed" in error["error"]["message"]

    @pytest.mark.asyncio
    async def test_run_pipeline_scheduler_mode_submits_modern_pipeline(self):
        """Scheduler mode delegates to native Pipeline.submit."""

        class ScheduledPipeline(ModernPipeline):
            def __init__(self, name: str | None = None):
                super().__init__(name)
                self.scheduler = {"name": "slurm", "nodes": 1}

        ModernPipeline.instances = []
        with patch(
            "jarvis_mcp.capabilities.jarvis_handler.Pipeline", ScheduledPipeline
        ):
            result = await run_pipeline(
                "scheduled", mode="scheduler", submit=True, wait=True
            )

        pipeline = ModernPipeline.instances[-1]
        assert result["pipeline_id"] == "scheduled"
        assert result["status"] == "completed"
        assert result["mode"] == "scheduler"
        assert result["runtime_metadata"]["scheduler_job_id"] == "24680"
        assert result["runtime_metadata"]["terminal"]["terminal"] is True
        assert (
            result["runtime_metadata"]["details"]["scheduler_submission"]
            == pipeline.last_submission
        )
        assert pipeline.submitted is True
        assert pipeline.waited is True

    @pytest.mark.asyncio
    async def test_run_pipeline_scheduler_script_only(self):
        """Scheduler mode can render the scheduler script without submitting it."""

        class ScheduledPipeline(ModernPipeline):
            def __init__(self, name: str | None = None):
                super().__init__(name)
                self.scheduler = {"name": "slurm"}

        ModernPipeline.instances = []
        with patch(
            "jarvis_mcp.capabilities.jarvis_handler.Pipeline", ScheduledPipeline
        ):
            result = await run_pipeline(
                "scripted", mode="scheduler", submit=False, wait=False
            )

        assert result["status"] == "scripted"
        assert result["mode"] == "scheduler"
        assert ModernPipeline.instances[-1].submitted is False
        assert result["runtime_metadata"]["scheduler_job_id"] is None

    @pytest.mark.asyncio
    async def test_waited_workload_failure_preserves_scheduler_identity(self):
        """A failed waited job remains a structured, attributable terminal result."""

        class FailedWaitPipeline(ModernPipeline):
            def __init__(self, name: str | None = None):
                super().__init__(name)
                self.scheduler = {
                    "name": "slurm",
                    "output": "/tmp/job-%j.out",
                    "error": "/tmp/job-%j.err",
                }

            def submit(self, *, submit: bool = True, wait: bool = False):
                assert submit is True
                assert wait is True
                script_path = Path("/tmp") / self.name / "submit.slurm"
                self.last_submission = {
                    "schema_version": "jarvis.scheduler.submission.v1",
                    "provider": "slurm",
                    "script_path": str(script_path),
                    "scheduler_job_id": "97531",
                    "scheduler_cluster": "ares",
                    "identity_source": "scheduler_submit_api",
                    "state": "workload_failed",
                    "submitted": True,
                    "wait": True,
                    "terminal": True,
                    "submission_returncode": 42,
                    "terminal_returncode": 42,
                }
                raise RuntimeError("scheduler workload exited 42")

        with patch(
            "jarvis_mcp.capabilities.jarvis_handler.Pipeline", FailedWaitPipeline
        ):
            with pytest.raises(ToolError) as exc_info:
                await run_pipeline(
                    "failed-wait",
                    mode="scheduler",
                    submit=True,
                    wait=True,
                )

        error = json.loads(str(exc_info.value))
        assert error["error"]["code"] == "jarvis_workload_failed"
        metadata = error["runtime_metadata"]
        assert metadata["scheduler_provider"] == "slurm"
        assert metadata["scheduler_job_id"] == "97531"
        assert metadata["scheduler_phase"] == "workload_failed"
        assert metadata["terminal"] == {
            "state": "failed",
            "terminal": True,
            "returncode": 42,
            "reason": "scheduler workload exited 42",
            "started_at": metadata["terminal"]["started_at"],
            "finished_at": metadata["terminal"]["finished_at"],
        }
        assert metadata["details"]["scheduler_submission"]["state"] == (
            "workload_failed"
        )
        assert metadata["details"]["scheduler_submission"]["scheduler_cluster"] == (
            "ares"
        )

    @pytest.mark.asyncio
    async def test_run_pipeline_auto_uses_scheduler_when_configured(self):
        """Auto mode submits when the loaded pipeline already has scheduler config."""

        class ScheduledPipeline(ModernPipeline):
            def __init__(self, name: str | None = None):
                super().__init__(name)
                self.scheduler = {"name": "slurm", "nodes": 1}

        with patch(
            "jarvis_mcp.capabilities.jarvis_handler.Pipeline", ScheduledPipeline
        ):
            result = await run_pipeline("auto-scheduled")

        assert result["mode"] == "scheduler"
        assert result["scheduler"] == {"name": "slurm", "nodes": 1}

    @pytest.mark.asyncio
    async def test_run_pipeline_rejects_unknown_mode(self):
        """Invalid execution modes fail explicitly."""
        with patch("jarvis_mcp.capabilities.jarvis_handler.Pipeline", ModernPipeline):
            with pytest.raises(ToolError) as exc_info:
                await run_pipeline("bad", mode="unknown")

        assert "mode must be one of" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_run_pipeline_rejects_scheduler_without_owned_identity(self):
        """A successful submit cannot fall back to parsing arbitrary stdout."""

        class LegacySubmissionPipeline(ModernPipeline):
            def __init__(self, name: str | None = None):
                super().__init__(name)
                self.scheduler = {"name": "slurm"}

            def submit(self, *, submit: bool = True, wait: bool = False):
                del submit, wait
                self.last_submission = None
                return Path("/tmp") / self.name / "submit.slurm"

        with patch(
            "jarvis_mcp.capabilities.jarvis_handler.Pipeline",
            LegacySubmissionPipeline,
        ):
            with pytest.raises(
                ToolError, match="provider-owned scheduler job identity"
            ):
                await run_pipeline("legacy", mode="scheduler")

    @pytest.mark.asyncio
    async def test_run_pipeline_rejects_baseline_jarvis_cd_before_submission(self):
        """The pinned baseline cannot silently submit without the new API."""

        class BaselinePipeline(ModernPipeline):
            def __init__(self, name: str | None = None):
                super().__init__(name)
                self.scheduler = {"name": "slurm"}
                del self.last_submission

            def submit(self, *, submit: bool = True, wait: bool = False):
                self.submitted = submit
                self.waited = wait
                return Path("/tmp") / self.name / "submit.slurm"

        ModernPipeline.instances = []
        with patch("jarvis_mcp.capabilities.jarvis_handler.Pipeline", BaselinePipeline):
            with pytest.raises(
                ToolError,
                match="does not expose the structured scheduler submission API",
            ):
                await run_pipeline("baseline", mode="scheduler")

        assert ModernPipeline.instances[-1].submitted is False

    @pytest.mark.asyncio
    async def test_configure_pipeline_applies_scheduler_env_and_launcher(self):
        """Pipeline-level config updates native scheduler/env/launcher fields."""
        ModernPipeline.instances = []
        with patch("jarvis_mcp.capabilities.jarvis_handler.Pipeline", ModernPipeline):
            result = await configure_pipeline(
                "configured",
                {
                    "scheduler": {"name": "slurm", "nodes": 2},
                    "env": {"OMP_NUM_THREADS": "4"},
                    "base_deploy_mode": "scheduler",
                    "mpi_cmd": "srun",
                },
            )

        pipeline = ModernPipeline.instances[-1]
        assert result["status"] == "configured"
        assert pipeline.scheduler == {"name": "slurm", "nodes": 2}
        assert pipeline.env == {"OMP_NUM_THREADS": "4"}
        assert pipeline.base_deploy_mode == "scheduler"
        assert pipeline.mpi_cmd == "srun"
        assert pipeline.saved is True

    @pytest.mark.asyncio
    async def test_configure_pipeline_rejects_unknown_keys(self):
        """Unsupported config keys fail before mutating pipeline state."""
        with patch("jarvis_mcp.capabilities.jarvis_handler.Pipeline", ModernPipeline):
            with pytest.raises(HTTPException) as exc_info:
                await configure_pipeline("configured", {"not_supported": True})

        assert exc_info.value.status_code == 500
        assert "unsupported pipeline config keys" in str(exc_info.value.detail)

    @pytest.mark.asyncio
    async def test_modern_package_operations_use_current_pipeline_api(self):
        """Current JARVIS unlinks explicitly and rejects fake destructive removal."""

        class PackagePipeline(ModernPipeline):
            instances = []

            def __init__(self, name: str | None = None):
                super().__init__(name)
                self.packages = [
                    {
                        "pkg_id": "echo",
                        "pkg_type": "builtin.echo",
                        "config": {},
                    }
                ]
                PackagePipeline.instances.append(self)

            def append(self, pkg_type, package_alias=None, config_args=None):
                self.appended = (pkg_type, package_alias, config_args)

            def configure_package(self, pkg_id, config_args):
                self.configured = (pkg_id, config_args)

            def rm(self, pkg_id):
                self.removed = pkg_id

        with patch("jarvis_mcp.capabilities.jarvis_handler.Pipeline", PackagePipeline):
            append_result = await append_pkg(
                "pipe",
                "builtin.echo",
                pkg_id="echo",
                do_configure=False,
                message="hello",
                enabled=True,
            )
            configure_result = await configure_pkg("pipe", "echo", message="updated")
            unlink_result = await unlink_pkg("pipe", "echo")
            with pytest.raises(HTTPException) as remove_error:
                await remove_pkg("pipe", "echo")

        assert append_result["appended"] == "builtin.echo"
        assert PackagePipeline.instances[0].appended == (
            "builtin.echo",
            "echo",
            ["message=hello", "enabled=true", "do_configure=false"],
        )
        assert configure_result["configured"] == "echo"
        assert PackagePipeline.instances[1].configured == ("echo", ["message=updated"])
        assert unlink_result["unlinked"] == "echo"
        assert PackagePipeline.instances[2].removed == "echo"
        assert remove_error.value.status_code == 501
        assert "does not provide destructive package removal" in str(
            remove_error.value.detail
        )

    @pytest.mark.asyncio
    async def test_destroy_pipeline_success(self, mock_pipeline):
        """Test successful pipeline destruction."""
        result = await destroy_pipeline("test_pipeline")

        assert result["pipeline_id"] == "test_pipeline"
        assert result["status"] == "destroyed"

        mock_pipeline.load.assert_called_once_with("test_pipeline")
        mock_pipeline.destroy.assert_called_once()

    @pytest.mark.asyncio
    async def test_destroy_pipeline_failure(self, mock_pipeline):
        """Test pipeline destruction failure."""
        mock_pipeline.destroy.side_effect = Exception("Destroy failed")

        with pytest.raises(HTTPException) as exc_info:
            await destroy_pipeline("test_pipeline")

        assert exc_info.value.status_code == 500
        assert "Destroy failed" in str(exc_info.value.detail)


class TestErrorHandling:
    """Test comprehensive error handling scenarios."""

    @pytest.mark.asyncio
    async def test_various_exception_types(self, mock_pipeline):
        """Test handling of different exception types."""
        test_cases = [
            (ValueError("Invalid value"), "Create failed"),
            (PermissionError("Access denied"), "Create failed"),
            (FileNotFoundError("File not found"), "Create failed"),
            (ConnectionError("Connection failed"), "Create failed"),
            (TimeoutError("Operation timed out"), "Create failed"),
        ]

        for exception, expected_message in test_cases:
            mock_pipeline.create.side_effect = exception

            with pytest.raises(HTTPException) as exc_info:
                await create_pipeline("test_pipeline")

            assert exc_info.value.status_code == 500
            assert expected_message in str(exc_info.value.detail)

    @pytest.mark.asyncio
    async def test_http_exception_preservation(self, mock_pipeline):
        """Test that HTTPExceptions are preserved and re-raised."""
        original_exception = HTTPException(status_code=404, detail="Not found")

        with patch(
            "jarvis_mcp.capabilities.jarvis_handler.Pipeline"
        ) as mock_pipeline_class:
            mock_pipeline_instance = Mock()
            mock_pipeline_class.return_value = mock_pipeline_instance
            mock_pipeline_instance.load.side_effect = original_exception

            with pytest.raises(HTTPException) as exc_info:
                await get_pkg_config("test_pipeline", "test_pkg")

            # Should preserve the original HTTPException
            assert exc_info.value.status_code == 404
            assert exc_info.value.detail == "Not found"


class TestIntegrationScenarios:
    """Test integration scenarios and workflows."""

    @pytest.mark.asyncio
    async def test_complete_pipeline_workflow(self, mock_pipeline):
        """Test a complete pipeline workflow from creation to destruction."""
        # Create pipeline
        create_result = await create_pipeline("workflow_test")
        assert create_result["status"] == "created"

        # Append packages
        append_result1 = await append_pkg(
            "workflow_test", "data_loader", pkg_id="loader1"
        )
        assert append_result1["appended"] == "data_loader"

        append_result2 = await append_pkg("workflow_test", "processor", pkg_id="proc1")
        assert append_result2["appended"] == "processor"

        # Configure packages
        config_result = await configure_pkg(
            "workflow_test", "loader1", input_path="/data"
        )
        assert config_result["configured"] == "loader1"

        # Update pipeline
        update_result = await update_pipeline("workflow_test")
        assert update_result["status"] == "updated"

        # Build environment
        env_result = await build_pipeline_env("workflow_test")
        assert env_result["status"] == "environment_built"

        # Run pipeline
        run_result = await run_pipeline("workflow_test")
        assert run_result["status"] == "completed"

        # Destroy pipeline
        destroy_result = await destroy_pipeline("workflow_test")
        assert destroy_result["status"] == "destroyed"

    @pytest.mark.asyncio
    async def test_package_management_workflow(self, mock_pipeline):
        """Test package management operations."""
        pipeline_id = "pkg_test"

        # Add multiple packages
        await append_pkg(pipeline_id, "data_loader", pkg_id="loader1")
        await append_pkg(pipeline_id, "processor", pkg_id="proc1")
        await append_pkg(pipeline_id, "output_writer", pkg_id="writer1")

        # Configure each package
        await configure_pkg(pipeline_id, "loader1", input_path="/data/input")
        await configure_pkg(pipeline_id, "proc1", algorithm="fast")
        await configure_pkg(pipeline_id, "writer1", output_path="/data/output")

        # Get package configurations
        mock_pkg = Mock()
        mock_pkg.config = {"input_path": "/data/input"}
        mock_pipeline.get_pkg.return_value = mock_pkg

        config_result = await get_pkg_config(pipeline_id, "loader1")
        assert config_result["config"]["input_path"] == "/data/input"

        # Unlink a package
        unlink_result = await unlink_pkg(pipeline_id, "proc1")
        assert unlink_result["unlinked"] == "proc1"

        # Remove a package
        remove_result = await remove_pkg(pipeline_id, "writer1")
        assert remove_result["removed"] == "writer1"

    @pytest.mark.asyncio
    async def test_error_recovery_scenarios(self, mock_pipeline):
        """Test error recovery and handling in complex scenarios."""
        # Test pipeline creation after previous failure
        mock_pipeline.create.side_effect = [
            Exception("First attempt failed"),
            Mock(),  # Second attempt succeeds
        ]

        # First attempt should fail
        with pytest.raises(HTTPException):
            await create_pipeline("recovery_test")

        # Reset the side effect for second attempt
        mock_pipeline.create.side_effect = None
        mock_pipeline.create.return_value = mock_pipeline

        # Second attempt should succeed
        result = await create_pipeline("recovery_test")
        assert result["status"] == "created"
