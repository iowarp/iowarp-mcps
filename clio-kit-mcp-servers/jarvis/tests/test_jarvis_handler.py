"""
Tests for the jarvis_handler module that contains pipeline operation logic.
"""

import pytest
from pathlib import Path
from unittest.mock import Mock, patch
from fastapi import HTTPException

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
        return Path("/tmp") / self.name / "submit.slurm"


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


class TestPipelineExecutionOperations:
    """Test pipeline execution and lifecycle operations."""

    @pytest.mark.asyncio
    async def test_run_pipeline_success(self, mock_pipeline):
        """Test successful pipeline execution."""
        result = await run_pipeline("test_pipeline")

        assert result["pipeline_id"] == "test_pipeline"
        assert result["status"] == "running"

        mock_pipeline.load.assert_called_once_with("test_pipeline")
        mock_pipeline.run.assert_called_once()

    @pytest.mark.asyncio
    async def test_run_pipeline_failure(self, mock_pipeline):
        """Test pipeline execution failure."""
        mock_pipeline.run.side_effect = Exception("Run failed")

        with pytest.raises(HTTPException) as exc_info:
            await run_pipeline("test_pipeline")

        assert exc_info.value.status_code == 500
        assert "Run failed" in str(exc_info.value.detail)

    @pytest.mark.asyncio
    async def test_run_pipeline_scheduler_mode_submits_modern_pipeline(self):
        """Scheduler mode delegates to native Pipeline.submit."""
        ModernPipeline.instances = []
        with patch("jarvis_mcp.capabilities.jarvis_handler.Pipeline", ModernPipeline):
            result = await run_pipeline(
                "scheduled", mode="scheduler", submit=True, wait=True
            )

        pipeline = ModernPipeline.instances[-1]
        assert result == {
            "pipeline_id": "scheduled",
            "status": "submitted",
            "mode": "scheduler",
            "scheduler": None,
            "script_path": str(Path("/tmp") / "scheduled" / "submit.slurm"),
            "wait": True,
        }
        assert pipeline.submitted is True
        assert pipeline.waited is True

    @pytest.mark.asyncio
    async def test_run_pipeline_scheduler_script_only(self):
        """Scheduler mode can render the scheduler script without submitting it."""
        ModernPipeline.instances = []
        with patch("jarvis_mcp.capabilities.jarvis_handler.Pipeline", ModernPipeline):
            result = await run_pipeline(
                "scripted", mode="scheduler", submit=False, wait=False
            )

        assert result["status"] == "scripted"
        assert result["mode"] == "scheduler"
        assert ModernPipeline.instances[-1].submitted is False

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
            with pytest.raises(HTTPException) as exc_info:
                await run_pipeline("bad", mode="unknown")

        assert exc_info.value.status_code == 500
        assert "mode must be one of" in str(exc_info.value.detail)

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
        assert run_result["status"] == "running"

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
