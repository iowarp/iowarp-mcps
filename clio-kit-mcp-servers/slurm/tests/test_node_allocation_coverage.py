"""
Enhanced coverage tests for node_allocation.py module.
Targets missing lines to improve coverage from 71% to 85%+.
"""

from unittest.mock import Mock, patch
from slurm_mcp.implementation.node_allocation import (
    allocate_nodes,
    deallocate_nodes,
    get_allocation_status,
    _expand_node_list,
    _get_allocation_nodes,
    _parse_salloc_output,
    _get_recent_allocation_id,
)


class TestNodeAllocationCoverage:
    """Enhanced coverage tests for node_allocation.py missing lines."""

    def test_allocate_nodes_with_memory_specification(self):
        """Test allocate_nodes with memory specification."""
        with patch(
            "slurm_mcp.implementation.node_allocation.check_slurm_available",
            return_value=True,
        ):
            with patch("slurm_mcp.implementation.node_allocation.subprocess.run") as mock_run:
                mock_run.return_value = Mock(
                    returncode=0, stdout="Granted job allocation 12345\n", stderr=""
                )

                result = allocate_nodes(
                    nodes=2,
                    cores=4,
                    memory="8G",
                    time_limit="2:00:00",
                    partition="compute",
                )

                assert result is not None
                assert mock_run.called

    def test_allocate_nodes_without_slurm(self):
        """Test allocate_nodes when Slurm is not available."""
        with patch(
            "slurm_mcp.implementation.node_allocation.check_slurm_available",
            return_value=False,
        ):
            result = allocate_nodes(nodes=1, cores=1)
            assert "error" in result
            assert not result["real_slurm"]

    def test_allocate_nodes_immediate_mode(self):
        """Test immediate allocation mode."""
        with patch(
            "slurm_mcp.implementation.node_allocation.check_slurm_available",
            return_value=True,
        ):
            with patch("slurm_mcp.implementation.node_allocation.subprocess.run") as mock_run:
                mock_run.return_value = Mock(returncode=0, stdout="", stderr="")
                with patch(
                    "slurm_mcp.implementation.node_allocation._get_recent_allocation_id",
                    return_value="12345",
                ):
                    with patch(
                        "slurm_mcp.implementation.node_allocation._get_allocation_nodes",
                        return_value={"nodes": ["node01"]},
                    ):
                        result = allocate_nodes(nodes=1, cores=2, immediate=True)

                        assert result is not None

    def test_allocate_nodes_timeout_error(self):
        """Test allocation timeout handling."""
        import subprocess

        with patch(
            "slurm_mcp.implementation.node_allocation.check_slurm_available",
            return_value=True,
        ):
            with patch("slurm_mcp.implementation.node_allocation.subprocess.run") as mock_run:
                mock_run.side_effect = subprocess.TimeoutExpired("salloc", 60)

                result = allocate_nodes(nodes=1, cores=1)
                assert "error" in result

    def test_allocate_nodes_policy_violation(self):
        """Test allocation policy violation error."""
        with patch(
            "slurm_mcp.implementation.node_allocation.check_slurm_available",
            return_value=True,
        ):
            with patch("slurm_mcp.implementation.node_allocation.subprocess.run") as mock_run:
                mock_run.return_value = Mock(
                    returncode=1, stdout="", stderr="Job violates accounting/QOS policy"
                )

                result = allocate_nodes(nodes=100, cores=64)
                assert "error" in result
                assert "policy" in result["error"].lower()

    def test_allocate_nodes_insufficient_resources(self):
        """Test insufficient resources error."""
        with patch(
            "slurm_mcp.implementation.node_allocation.check_slurm_available",
            return_value=True,
        ):
            with patch("slurm_mcp.implementation.node_allocation.subprocess.run") as mock_run:
                mock_run.return_value = Mock(
                    returncode=1, stdout="", stderr="Unable to allocate resources"
                )

                result = allocate_nodes(nodes=1000, cores=128)
                assert "error" in result
                assert "resources" in result["error"].lower()

    def test_expand_node_list_complex_ranges(self):
        """Test _expand_node_list with complex node ranges."""
        # Test simple range
        result = _expand_node_list("node[01-03]")
        expected = ["node01", "node02", "node03"]
        assert result == expected

        # Test single node
        result = _expand_node_list("node01")
        assert result == ["node01"]

        # Test range with different padding
        result = _expand_node_list("gpu[001-003]")
        expected = ["gpu001", "gpu002", "gpu003"]
        assert result == expected

    def test_expand_node_list_edge_cases(self):
        """Test _expand_node_list with edge cases."""
        # Empty string
        result = _expand_node_list("")
        assert result == [
            ""
        ]  # Function returns the input as-is for non-matching patterns

        # Malformed range - the function will treat it as a single node name
        result = _expand_node_list("node[")
        assert result == ["node["]

    def test_parse_salloc_output_various_formats(self):
        """Test _parse_salloc_output with different output formats."""
        # Test normal allocation output
        output = "Granted job allocation 12345\nnode[01-02] allocated"
        result = _parse_salloc_output(output)
        assert isinstance(result, dict)

        # Test empty output
        result = _parse_salloc_output("")
        assert isinstance(result, dict)

        # Test output with job ID
        output = "salloc: Granted job allocation 67890"
        result = _parse_salloc_output(output)
        assert isinstance(result, dict)

    def test_get_allocation_nodes_with_valid_id(self):
        """Test _get_allocation_nodes with valid allocation ID."""
        with patch("slurm_mcp.implementation.node_allocation.subprocess.run") as mock_run:
            mock_run.return_value = Mock(
                returncode=0, stdout="node01,node02 RUNNING 8 16000", stderr=""
            )

            result = _get_allocation_nodes("12345")
            assert result is not None

    def test_get_allocation_nodes_with_invalid_id(self):
        """Test _get_allocation_nodes with invalid allocation ID."""
        with patch("slurm_mcp.implementation.node_allocation.subprocess.run") as mock_run:
            mock_run.return_value = Mock(
                returncode=1, stdout="", stderr="Invalid job id specified"
            )

            result = _get_allocation_nodes("invalid")
            assert result is None

    def test_get_recent_allocation_id_found(self):
        """Test _get_recent_allocation_id when allocation exists."""
        with patch("slurm_mcp.implementation.node_allocation.subprocess.run") as mock_run:
            with patch(
                "slurm_mcp.implementation.node_allocation.os.getenv", return_value="testuser"
            ):
                mock_run.return_value = Mock(
                    returncode=0,
                    stdout="12345,RUNNING,mcp_allocation\n67890,PENDING,other_job",
                    stderr="",
                )

                result = _get_recent_allocation_id()
                assert result == "12345"

    def test_get_recent_allocation_id_not_found(self):
        """Test _get_recent_allocation_id when no allocation exists."""
        with patch("slurm_mcp.implementation.node_allocation.subprocess.run") as mock_run:
            mock_run.return_value = Mock(returncode=0, stdout="", stderr="")

            result = _get_recent_allocation_id()
            assert result is None

    def test_deallocate_nodes_success(self):
        """Test deallocate_nodes with successful deallocation."""
        with patch(
            "slurm_mcp.implementation.node_allocation.check_slurm_available",
            return_value=True,
        ):
            with patch("slurm_mcp.implementation.node_allocation.subprocess.run") as mock_run:
                mock_run.return_value = Mock(returncode=0, stdout="", stderr="")

                result = deallocate_nodes("12345")
                assert "status" in result
                assert result.get("real_slurm", True)

    def test_deallocate_nodes_without_slurm(self):
        """Test deallocate_nodes when Slurm is not available."""
        with patch(
            "slurm_mcp.implementation.node_allocation.check_slurm_available",
            return_value=False,
        ):
            result = deallocate_nodes("12345")
            assert "error" in result
            assert not result["real_slurm"]

    def test_deallocate_nodes_failure(self):
        """Test deallocate_nodes with failed deallocation."""
        with patch(
            "slurm_mcp.implementation.node_allocation.check_slurm_available",
            return_value=True,
        ):
            with patch("slurm_mcp.implementation.node_allocation.subprocess.run") as mock_run:
                mock_run.return_value = Mock(
                    returncode=1, stdout="", stderr="scancel: Invalid job id 99999"
                )

                result = deallocate_nodes("99999")
                assert "error" in result

    def test_get_allocation_status_success(self):
        """Test get_allocation_status with valid allocation."""
        with patch(
            "slurm_mcp.implementation.node_allocation.check_slurm_available",
            return_value=True,
        ):
            with patch("slurm_mcp.implementation.node_allocation.subprocess.run") as mock_run:
                mock_run.return_value = Mock(
                    returncode=0, stdout="12345 RUNNING node[01-02] user 2 8", stderr=""
                )

                result = get_allocation_status("12345")
                assert "status" in result
                assert result.get("real_slurm", True)

    def test_get_allocation_status_without_slurm(self):
        """Test get_allocation_status when Slurm is not available."""
        with patch(
            "slurm_mcp.implementation.node_allocation.check_slurm_available",
            return_value=False,
        ):
            result = get_allocation_status("12345")
            assert "error" in result
            assert not result["real_slurm"]

    def test_get_allocation_status_not_found(self):
        """Test get_allocation_status with non-existent allocation."""
        with patch(
            "slurm_mcp.implementation.node_allocation.check_slurm_available",
            return_value=True,
        ):
            with patch("slurm_mcp.implementation.node_allocation.subprocess.run") as mock_run:
                mock_run.return_value = Mock(
                    returncode=1, stdout="", stderr="Invalid job id specified"
                )

                result = get_allocation_status("99999")
                # The function returns status info even for not found allocations
                assert "status" in result
                assert result["status"] == "not_found"

    def test_allocate_nodes_with_job_name(self):
        """Test allocate_nodes with custom job name."""
        with patch(
            "slurm_mcp.implementation.node_allocation.check_slurm_available",
            return_value=True,
        ):
            with patch("slurm_mcp.implementation.node_allocation.subprocess.run") as mock_run:
                mock_run.return_value = Mock(returncode=0, stdout="", stderr="")
                with patch(
                    "slurm_mcp.implementation.node_allocation._get_recent_allocation_id",
                    return_value="12345",
                ):
                    allocate_nodes(nodes=1, cores=1, job_name="test_job")

                    # The function makes multiple subprocess calls - check the first one (salloc)
                    salloc_call = mock_run.call_args_list[0][0][0]
                    assert "--job-name=test_job" in salloc_call

    def test_allocate_nodes_default_job_name(self):
        """Test allocate_nodes with default job name."""
        with patch(
            "slurm_mcp.implementation.node_allocation.check_slurm_available",
            return_value=True,
        ):
            with patch("slurm_mcp.implementation.node_allocation.subprocess.run") as mock_run:
                mock_run.return_value = Mock(returncode=0, stdout="", stderr="")
                with patch(
                    "slurm_mcp.implementation.node_allocation._get_recent_allocation_id",
                    return_value="12345",
                ):
                    allocate_nodes(nodes=1, cores=1)

                    # Check the salloc command for default job name
                    salloc_call = mock_run.call_args_list[0][0][0]
                    assert "--job-name=mcp_allocation" in salloc_call
