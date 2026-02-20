"""Tests for POSIX and MPI-IO operation parsing functions in Darshan parser."""

import pytest
from unittest.mock import patch

from darshan_mcp.capabilities import darshan_parser


@pytest.mark.asyncio
async def test_analyze_posix_operations_success():
    """Test analyze_posix_operations with valid POSIX output."""
    mock_stdout = """
    # POSIX module statistics
    POSIX_OPENS: 150
    POSIX_READS: 5000
    POSIX_WRITES: 3000
    POSIX_SEEKS: 1200
    POSIX_STATS: 75
    POSIX_FSYNCS: 50
    """

    with patch(
        "darshan_mcp.capabilities.darshan_parser._run_darshan_command"
    ) as mock_run:
        mock_run.return_value = (mock_stdout, "", 0)

        result = await darshan_parser.analyze_posix_operations("/test/file.darshan")

        assert result["success"] is True
        assert "operations" in result
        assert result["operations"]["opens"] == 150
        assert result["operations"]["reads"] == 5000
        assert result["operations"]["writes"] == 3000
        assert result["operations"]["seeks"] == 1200

        # Verify the command was called with correct arguments
        mock_run.assert_called_once_with(["--module", "POSIX"], "/test/file.darshan")


@pytest.mark.asyncio
async def test_analyze_posix_operations_partial_data():
    """Test analyze_posix_operations with partial POSIX data (some counters missing)."""
    mock_stdout = """
    # POSIX module statistics
    POSIX_OPENS: 100
    POSIX_READS: 2000
    # POSIX_WRITES and POSIX_SEEKS are missing
    """

    with patch(
        "darshan_mcp.capabilities.darshan_parser._run_darshan_command"
    ) as mock_run:
        mock_run.return_value = (mock_stdout, "", 0)

        result = await darshan_parser.analyze_posix_operations("/test/file.darshan")

        assert result["success"] is True
        assert result["operations"]["opens"] == 100
        assert result["operations"]["reads"] == 2000
        # These should remain at their default value of 0
        assert result["operations"]["writes"] == 0
        assert result["operations"]["seeks"] == 0


@pytest.mark.asyncio
async def test_analyze_posix_operations_command_failure():
    """Test analyze_posix_operations with command failure (returncode != 0)."""
    mock_stderr = "Error: Failed to parse POSIX module"

    with patch(
        "darshan_mcp.capabilities.darshan_parser._run_darshan_command"
    ) as mock_run:
        mock_run.return_value = ("", mock_stderr, 1)

        result = await darshan_parser.analyze_posix_operations("/test/file.darshan")

        assert result["success"] is False
        assert result["error"] == "Failed to extract POSIX module data"
        assert result["message"] == mock_stderr


@pytest.mark.asyncio
async def test_analyze_posix_operations_empty_output():
    """Test analyze_posix_operations with empty output."""
    with patch(
        "darshan_mcp.capabilities.darshan_parser._run_darshan_command"
    ) as mock_run:
        mock_run.return_value = ("", "", 0)

        result = await darshan_parser.analyze_posix_operations("/test/file.darshan")

        assert result["success"] is True
        # All operations should be 0 with empty output
        assert result["operations"]["opens"] == 0
        assert result["operations"]["reads"] == 0
        assert result["operations"]["writes"] == 0
        assert result["operations"]["seeks"] == 0


@pytest.mark.asyncio
async def test_analyze_posix_operations_exception_handling():
    """Test analyze_posix_operations exception handling."""
    with patch(
        "darshan_mcp.capabilities.darshan_parser._run_darshan_command"
    ) as mock_run:
        mock_run.side_effect = Exception("Unexpected error occurred")

        result = await darshan_parser.analyze_posix_operations("/test/file.darshan")

        assert result["success"] is False
        assert "Error analyzing POSIX operations" in result["error"]
        assert "Unexpected error occurred" in result["error"]


@pytest.mark.asyncio
async def test_analyze_posix_operations_invalid_data_format():
    """Test analyze_posix_operations with invalid data format (non-integer values)."""
    mock_stdout = """
    POSIX_OPENS: invalid_number
    POSIX_READS: 2000
    """

    with patch(
        "darshan_mcp.capabilities.darshan_parser._run_darshan_command"
    ) as mock_run:
        mock_run.return_value = (mock_stdout, "", 0)

        result = await darshan_parser.analyze_posix_operations("/test/file.darshan")

        # Should catch the exception and return error
        assert result["success"] is False
        assert "Error analyzing POSIX operations" in result["error"]


@pytest.mark.asyncio
async def test_analyze_posix_operations_whitespace_handling():
    """Test analyze_posix_operations with various whitespace formats."""
    mock_stdout = """
    POSIX_OPENS:    250
       POSIX_READS:6000
    	POSIX_WRITES: 	4000
    POSIX_SEEKS :1500
    """

    with patch(
        "darshan_mcp.capabilities.darshan_parser._run_darshan_command"
    ) as mock_run:
        mock_run.return_value = (mock_stdout, "", 0)

        result = await darshan_parser.analyze_posix_operations("/test/file.darshan")

        assert result["success"] is True
        assert result["operations"]["opens"] == 250
        assert result["operations"]["reads"] == 6000
        assert result["operations"]["writes"] == 4000
        # POSIX_SEEKS with space before colon won't match, should be 0
        assert result["operations"]["seeks"] == 0


@pytest.mark.asyncio
async def test_analyze_mpiio_operations_success():
    """Test analyze_mpiio_operations with valid MPI-IO output."""
    mock_stdout = """
    # MPI-IO module statistics
    MPIIO_COLL_READS: 1000
    MPIIO_COLL_WRITES: 2000
    MPIIO_INDEP_READS: 500
    MPIIO_INDEP_WRITES: 750
    MPIIO_VIEWS: 10
    """

    with patch(
        "darshan_mcp.capabilities.darshan_parser._run_darshan_command"
    ) as mock_run:
        mock_run.return_value = (mock_stdout, "", 0)

        result = await darshan_parser.analyze_mpiio_operations("/test/file.darshan")

        assert result["success"] is True
        assert "collective_operations" in result
        assert "independent_operations" in result
        assert result["collective_operations"]["reads"] == 1000
        assert result["collective_operations"]["writes"] == 2000
        assert result["independent_operations"]["reads"] == 500
        assert result["independent_operations"]["writes"] == 750

        # Verify the command was called with correct arguments
        mock_run.assert_called_once_with(["--module", "MPIIO"], "/test/file.darshan")


@pytest.mark.asyncio
async def test_analyze_mpiio_operations_partial_data():
    """Test analyze_mpiio_operations with partial MPI-IO data."""
    mock_stdout = """
    # MPI-IO module statistics - only collective operations
    MPIIO_COLL_READS: 800
    MPIIO_COLL_WRITES: 1200
    """

    with patch(
        "darshan_mcp.capabilities.darshan_parser._run_darshan_command"
    ) as mock_run:
        mock_run.return_value = (mock_stdout, "", 0)

        result = await darshan_parser.analyze_mpiio_operations("/test/file.darshan")

        assert result["success"] is True
        assert result["collective_operations"]["reads"] == 800
        assert result["collective_operations"]["writes"] == 1200
        # Independent operations should be 0 (default values)
        assert result["independent_operations"]["reads"] == 0
        assert result["independent_operations"]["writes"] == 0


@pytest.mark.asyncio
async def test_analyze_mpiio_operations_no_data():
    """Test analyze_mpiio_operations with no MPI-IO data (returncode != 0)."""
    mock_stderr = "No MPI-IO data in log file"

    with patch(
        "darshan_mcp.capabilities.darshan_parser._run_darshan_command"
    ) as mock_run:
        mock_run.return_value = ("", mock_stderr, 1)

        result = await darshan_parser.analyze_mpiio_operations("/test/file.darshan")

        # Note: The function returns success=True when MPI-IO data is not found
        # This is intentional design as MPI-IO is optional
        assert result["success"] is True
        assert result["message"] == "No MPI-IO operations found in trace"
        assert result["operations"] == {}


@pytest.mark.asyncio
async def test_analyze_mpiio_operations_empty_output():
    """Test analyze_mpiio_operations with empty output."""
    with patch(
        "darshan_mcp.capabilities.darshan_parser._run_darshan_command"
    ) as mock_run:
        mock_run.return_value = ("", "", 0)

        result = await darshan_parser.analyze_mpiio_operations("/test/file.darshan")

        assert result["success"] is True
        # All operations should be 0 with empty output
        assert result["collective_operations"]["reads"] == 0
        assert result["collective_operations"]["writes"] == 0
        assert result["independent_operations"]["reads"] == 0
        assert result["independent_operations"]["writes"] == 0


@pytest.mark.asyncio
async def test_analyze_mpiio_operations_exception_handling():
    """Test analyze_mpiio_operations exception handling."""
    with patch(
        "darshan_mcp.capabilities.darshan_parser._run_darshan_command"
    ) as mock_run:
        mock_run.side_effect = Exception("Network timeout")

        result = await darshan_parser.analyze_mpiio_operations("/test/file.darshan")

        assert result["success"] is False
        assert "Error analyzing MPI-IO operations" in result["error"]
        assert "Network timeout" in result["error"]


@pytest.mark.asyncio
async def test_analyze_mpiio_operations_invalid_data_format():
    """Test analyze_mpiio_operations with invalid data format (non-integer values)."""
    mock_stdout = """
    MPIIO_COLL_READS: not_a_number
    MPIIO_COLL_WRITES: 1000
    """

    with patch(
        "darshan_mcp.capabilities.darshan_parser._run_darshan_command"
    ) as mock_run:
        mock_run.return_value = (mock_stdout, "", 0)

        result = await darshan_parser.analyze_mpiio_operations("/test/file.darshan")

        # Should catch the exception and return error
        assert result["success"] is False
        assert "Error analyzing MPI-IO operations" in result["error"]


@pytest.mark.asyncio
async def test_analyze_mpiio_operations_collective_only():
    """Test analyze_mpiio_operations with only collective operations."""
    mock_stdout = """
    MPIIO_COLL_READS: 5000
    MPIIO_COLL_WRITES: 3000
    """

    with patch(
        "darshan_mcp.capabilities.darshan_parser._run_darshan_command"
    ) as mock_run:
        mock_run.return_value = (mock_stdout, "", 0)

        result = await darshan_parser.analyze_mpiio_operations("/test/file.darshan")

        assert result["success"] is True
        assert result["collective_operations"]["reads"] == 5000
        assert result["collective_operations"]["writes"] == 3000
        assert result["independent_operations"]["reads"] == 0
        assert result["independent_operations"]["writes"] == 0


@pytest.mark.asyncio
async def test_analyze_mpiio_operations_independent_only():
    """Test analyze_mpiio_operations with only independent operations."""
    mock_stdout = """
    MPIIO_INDEP_READS: 2500
    MPIIO_INDEP_WRITES: 1800
    """

    with patch(
        "darshan_mcp.capabilities.darshan_parser._run_darshan_command"
    ) as mock_run:
        mock_run.return_value = (mock_stdout, "", 0)

        result = await darshan_parser.analyze_mpiio_operations("/test/file.darshan")

        assert result["success"] is True
        assert result["collective_operations"]["reads"] == 0
        assert result["collective_operations"]["writes"] == 0
        assert result["independent_operations"]["reads"] == 2500
        assert result["independent_operations"]["writes"] == 1800


@pytest.mark.asyncio
async def test_analyze_mpiio_operations_large_values():
    """Test analyze_mpiio_operations with large operation counts."""
    mock_stdout = """
    MPIIO_COLL_READS: 1000000000
    MPIIO_COLL_WRITES: 2000000000
    MPIIO_INDEP_READS: 500000000
    MPIIO_INDEP_WRITES: 750000000
    """

    with patch(
        "darshan_mcp.capabilities.darshan_parser._run_darshan_command"
    ) as mock_run:
        mock_run.return_value = (mock_stdout, "", 0)

        result = await darshan_parser.analyze_mpiio_operations("/test/file.darshan")

        assert result["success"] is True
        assert result["collective_operations"]["reads"] == 1000000000
        assert result["collective_operations"]["writes"] == 2000000000
        assert result["independent_operations"]["reads"] == 500000000
        assert result["independent_operations"]["writes"] == 750000000


@pytest.mark.asyncio
async def test_analyze_posix_operations_zero_values():
    """Test analyze_posix_operations with zero values (no operations)."""
    mock_stdout = """
    POSIX_OPENS: 0
    POSIX_READS: 0
    POSIX_WRITES: 0
    POSIX_SEEKS: 0
    """

    with patch(
        "darshan_mcp.capabilities.darshan_parser._run_darshan_command"
    ) as mock_run:
        mock_run.return_value = (mock_stdout, "", 0)

        result = await darshan_parser.analyze_posix_operations("/test/file.darshan")

        assert result["success"] is True
        assert result["operations"]["opens"] == 0
        assert result["operations"]["reads"] == 0
        assert result["operations"]["writes"] == 0
        assert result["operations"]["seeks"] == 0


@pytest.mark.asyncio
async def test_analyze_mpiio_operations_zero_values():
    """Test analyze_mpiio_operations with zero values (no operations)."""
    mock_stdout = """
    MPIIO_COLL_READS: 0
    MPIIO_COLL_WRITES: 0
    MPIIO_INDEP_READS: 0
    MPIIO_INDEP_WRITES: 0
    """

    with patch(
        "darshan_mcp.capabilities.darshan_parser._run_darshan_command"
    ) as mock_run:
        mock_run.return_value = (mock_stdout, "", 0)

        result = await darshan_parser.analyze_mpiio_operations("/test/file.darshan")

        assert result["success"] is True
        assert result["collective_operations"]["reads"] == 0
        assert result["collective_operations"]["writes"] == 0
        assert result["independent_operations"]["reads"] == 0
        assert result["independent_operations"]["writes"] == 0


@pytest.mark.asyncio
async def test_analyze_posix_operations_structure():
    """Test analyze_posix_operations returns correct data structure."""
    mock_stdout = """
    POSIX_OPENS: 10
    POSIX_READS: 20
    """

    with patch(
        "darshan_mcp.capabilities.darshan_parser._run_darshan_command"
    ) as mock_run:
        mock_run.return_value = (mock_stdout, "", 0)

        result = await darshan_parser.analyze_posix_operations("/test/file.darshan")

        # Verify the complete structure
        assert result["success"] is True
        assert "operations" in result
        assert "timing" in result
        assert "patterns" in result

        # Verify all expected operation keys exist
        operations = result["operations"]
        assert "opens" in operations
        assert "closes" in operations
        assert "reads" in operations
        assert "writes" in operations
        assert "seeks" in operations
        assert "stats" in operations
        assert "fsyncs" in operations


@pytest.mark.asyncio
async def test_analyze_mpiio_operations_structure():
    """Test analyze_mpiio_operations returns correct data structure."""
    mock_stdout = """
    MPIIO_COLL_READS: 100
    """

    with patch(
        "darshan_mcp.capabilities.darshan_parser._run_darshan_command"
    ) as mock_run:
        mock_run.return_value = (mock_stdout, "", 0)

        result = await darshan_parser.analyze_mpiio_operations("/test/file.darshan")

        # Verify the complete structure
        assert result["success"] is True
        assert "collective_operations" in result
        assert "independent_operations" in result
        assert "file_views" in result
        assert "performance_metrics" in result

        # Verify operation keys exist
        assert "reads" in result["collective_operations"]
        assert "writes" in result["collective_operations"]
        assert "reads" in result["independent_operations"]
        assert "writes" in result["independent_operations"]
