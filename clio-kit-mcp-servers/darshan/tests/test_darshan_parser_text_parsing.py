"""Tests for Darshan parser text parsing fallback functions."""

import pytest
from unittest.mock import patch, AsyncMock

from darshan_mcp.capabilities import darshan_parser


@pytest.mark.asyncio
async def test_run_darshan_command_successful_execution():
    """Test successful execution of darshan command."""
    mock_process = AsyncMock()
    mock_process.communicate.return_value = (
        b'{"job": {"job_id": "12345"}}',
        b"",
    )
    mock_process.returncode = 0

    with patch(
        "darshan_mcp.capabilities.darshan_parser.asyncio.create_subprocess_exec"
    ) as mock_exec:
        mock_exec.return_value = mock_process

        stdout, stderr, returncode = await darshan_parser._run_darshan_command(
            ["--json"], "/test/file.darshan"
        )

        assert returncode == 0
        assert stdout == '{"job": {"job_id": "12345"}}'
        assert stderr == ""
        # Verify command was called correctly
        mock_exec.assert_called_once()
        call_args = mock_exec.call_args[0]
        assert call_args[0] == "darshan-parser"
        assert "--json" in call_args
        assert "/test/file.darshan" in call_args


@pytest.mark.asyncio
async def test_parse_darshan_json_success():
    """Test _parse_darshan_json when JSON parsing succeeds."""
    mock_json_output = {
        "job": {
            "job_id": "12345",
            "user_id": "testuser",
            "nprocs": 64,
            "start_time": "2024-01-01T10:00:00Z",
            "end_time": "2024-01-01T11:00:00Z",
        },
        "modules": ["POSIX", "MPIIO"],
        "files": {
            "/data/file1.dat": {"bytes_read": 1000, "bytes_written": 0},
            "/data/file2.dat": {"bytes_read": 0, "bytes_written": 2000},
        },
    }

    mock_process = AsyncMock()
    mock_process.communicate.return_value = (
        str(mock_json_output).replace("'", '"').encode("utf-8"),
        b"",
    )
    mock_process.returncode = 0

    with patch(
        "darshan_mcp.capabilities.darshan_parser.asyncio.create_subprocess_exec"
    ) as mock_exec:
        mock_exec.return_value = mock_process

        result = await darshan_parser._parse_darshan_json("/test/file.darshan")

        assert "job" in result
        assert result["job"]["job_id"] == "12345"
        assert result["job"]["nprocs"] == 64
        assert "modules" in result
        assert "POSIX" in result["modules"]
        assert "files" in result


@pytest.mark.asyncio
async def test_parse_darshan_json_fallback_on_json_error():
    """Test _parse_darshan_json fallback to text parsing on JSON decode error."""
    # Mock JSON parsing failure, then text parsing success
    text_output = """
Job ID: 67890
User ID: testuser2
Start time: 2024-01-01 12:00:00
End time: 2024-01-01 13:00:00
Number of processes: 32
Modules in log:
- POSIX
- STDIO
"""

    # First call (JSON) returns invalid JSON, second call (text) succeeds
    mock_process_json = AsyncMock()
    mock_process_json.communicate.return_value = (
        b"invalid json {not valid}",
        b"",
    )
    mock_process_json.returncode = 0

    mock_process_text = AsyncMock()
    mock_process_text.communicate.return_value = (
        text_output.encode("utf-8"),
        b"",
    )
    mock_process_text.returncode = 0

    with patch(
        "darshan_mcp.capabilities.darshan_parser.asyncio.create_subprocess_exec"
    ) as mock_exec:
        mock_exec.side_effect = [mock_process_json, mock_process_text]

        result = await darshan_parser._parse_darshan_json("/test/file.darshan")

        assert result["success"] is True
        assert result["job"]["job_id"] == "67890"
        assert result["job"]["user_id"] == "testuser2"
        assert result["job"]["nprocs"] == 32
        assert "POSIX" in result["modules"]
        assert "STDIO" in result["modules"]


@pytest.mark.asyncio
async def test_parse_darshan_json_fallback_on_nonzero_returncode():
    """Test _parse_darshan_json fallback to text when returncode != 0."""
    text_output = """
Job ID: 11111
User ID: user123
Number of processes: 16
"""

    # First call (JSON) fails with non-zero returncode
    mock_process_json = AsyncMock()
    mock_process_json.communicate.return_value = (
        b"",
        b"JSON output not supported",
    )
    mock_process_json.returncode = 1

    mock_process_text = AsyncMock()
    mock_process_text.communicate.return_value = (
        text_output.encode("utf-8"),
        b"",
    )
    mock_process_text.returncode = 0

    with patch(
        "darshan_mcp.capabilities.darshan_parser.asyncio.create_subprocess_exec"
    ) as mock_exec:
        mock_exec.side_effect = [mock_process_json, mock_process_text]

        result = await darshan_parser._parse_darshan_json("/test/file.darshan")

        assert result["success"] is True
        assert result["job"]["job_id"] == "11111"
        assert result["job"]["user_id"] == "user123"
        assert result["job"]["nprocs"] == 16


@pytest.mark.asyncio
async def test_parse_darshan_text_complete_output():
    """Test _parse_darshan_text with complete text output containing all fields."""
    complete_text_output = """
Darshan Log Analysis
====================
Job ID: 98765
User ID: research_user
Start time: 2024-03-15 09:30:00
End time: 2024-03-15 10:45:00
Number of processes: 128

Modules in log:
- POSIX
- MPIIO
- STDIO
- HDF5

File Statistics:
Total files opened: 42
"""

    mock_process = AsyncMock()
    mock_process.communicate.return_value = (
        complete_text_output.encode("utf-8"),
        b"",
    )
    mock_process.returncode = 0

    with patch(
        "darshan_mcp.capabilities.darshan_parser.asyncio.create_subprocess_exec"
    ) as mock_exec:
        mock_exec.return_value = mock_process

        result = await darshan_parser._parse_darshan_text("/test/file.darshan")

        assert result["success"] is True
        assert result["job"]["job_id"] == "98765"
        assert result["job"]["user_id"] == "research_user"
        assert result["job"]["start_time"] == "2024-03-15 09:30:00"
        assert result["job"]["end_time"] == "2024-03-15 10:45:00"
        assert result["job"]["nprocs"] == 128
        assert len(result["modules"]) == 4
        assert "POSIX" in result["modules"]
        assert "MPIIO" in result["modules"]
        assert "STDIO" in result["modules"]
        assert "HDF5" in result["modules"]
        assert result["files"] == {}


@pytest.mark.asyncio
async def test_parse_darshan_text_minimal_output():
    """Test _parse_darshan_text with minimal text output."""
    minimal_text_output = """
Job ID: 55555
Number of processes: 8
"""

    mock_process = AsyncMock()
    mock_process.communicate.return_value = (
        minimal_text_output.encode("utf-8"),
        b"",
    )
    mock_process.returncode = 0

    with patch(
        "darshan_mcp.capabilities.darshan_parser.asyncio.create_subprocess_exec"
    ) as mock_exec:
        mock_exec.return_value = mock_process

        result = await darshan_parser._parse_darshan_text("/test/file.darshan")

        assert result["success"] is True
        assert result["job"]["job_id"] == "55555"
        assert result["job"]["nprocs"] == 8
        # Other fields should not be present
        assert "user_id" not in result["job"]
        assert "start_time" not in result["job"]
        assert "end_time" not in result["job"]
        assert result["modules"] == []
        assert result["files"] == {}


@pytest.mark.asyncio
async def test_parse_darshan_text_command_failure():
    """Test _parse_darshan_text when command execution fails."""
    mock_process = AsyncMock()
    mock_process.communicate.return_value = (
        b"",
        b"Error: Unable to open log file",
    )
    mock_process.returncode = 1

    with patch(
        "darshan_mcp.capabilities.darshan_parser.asyncio.create_subprocess_exec"
    ) as mock_exec:
        mock_exec.return_value = mock_process

        result = await darshan_parser._parse_darshan_text("/test/file.darshan")

        assert result["success"] is False
        assert "error" in result
        assert "Unable to open log file" in result["error"]


@pytest.mark.asyncio
async def test_parse_darshan_text_empty_output():
    """Test _parse_darshan_text with empty output."""
    mock_process = AsyncMock()
    mock_process.communicate.return_value = (
        b"",
        b"",
    )
    mock_process.returncode = 0

    with patch(
        "darshan_mcp.capabilities.darshan_parser.asyncio.create_subprocess_exec"
    ) as mock_exec:
        mock_exec.return_value = mock_process

        result = await darshan_parser._parse_darshan_text("/test/file.darshan")

        assert result["success"] is True
        assert result["job"] == {}
        assert result["modules"] == []
        assert result["files"] == {}


@pytest.mark.asyncio
async def test_parse_darshan_text_modules_section():
    """Test _parse_darshan_text parsing of modules section with various formats."""
    text_with_modules = """
Job ID: 12345
Modules in log:
- POSIX
- MPIIO
- STDIO
- HDF5
- PNETCDF

Some other output
"""

    mock_process = AsyncMock()
    mock_process.communicate.return_value = (
        text_with_modules.encode("utf-8"),
        b"",
    )
    mock_process.returncode = 0

    with patch(
        "darshan_mcp.capabilities.darshan_parser.asyncio.create_subprocess_exec"
    ) as mock_exec:
        mock_exec.return_value = mock_process

        result = await darshan_parser._parse_darshan_text("/test/file.darshan")

        assert result["success"] is True
        assert len(result["modules"]) == 5
        assert result["modules"] == ["POSIX", "MPIIO", "STDIO", "HDF5", "PNETCDF"]


@pytest.mark.asyncio
async def test_parse_darshan_text_whitespace_handling():
    """Test _parse_darshan_text handles extra whitespace correctly."""
    text_with_whitespace = """

    Job ID:     99999
    User ID:   whitespace_test
    Number of processes:    256
    Start time:   2024-12-01 00:00:00
    End time:   2024-12-01 01:00:00

    Modules in log:
    -   POSIX
    -   MPIIO

"""

    mock_process = AsyncMock()
    mock_process.communicate.return_value = (
        text_with_whitespace.encode("utf-8"),
        b"",
    )
    mock_process.returncode = 0

    with patch(
        "darshan_mcp.capabilities.darshan_parser.asyncio.create_subprocess_exec"
    ) as mock_exec:
        mock_exec.return_value = mock_process

        result = await darshan_parser._parse_darshan_text("/test/file.darshan")

        assert result["success"] is True
        assert result["job"]["job_id"] == "99999"
        assert result["job"]["user_id"] == "whitespace_test"
        assert result["job"]["nprocs"] == 256
        assert result["job"]["start_time"] == "2024-12-01 00:00:00"
        assert result["job"]["end_time"] == "2024-12-01 01:00:00"
        assert result["modules"] == ["POSIX", "MPIIO"]


@pytest.mark.asyncio
async def test_parse_darshan_text_nprocs_parsing():
    """Test _parse_darshan_text correctly parses number of processes as integer."""
    text_output = """
Job ID: 12345
Number of processes: 1024
"""

    mock_process = AsyncMock()
    mock_process.communicate.return_value = (
        text_output.encode("utf-8"),
        b"",
    )
    mock_process.returncode = 0

    with patch(
        "darshan_mcp.capabilities.darshan_parser.asyncio.create_subprocess_exec"
    ) as mock_exec:
        mock_exec.return_value = mock_process

        result = await darshan_parser._parse_darshan_text("/test/file.darshan")

        assert result["success"] is True
        assert result["job"]["nprocs"] == 1024
        assert isinstance(result["job"]["nprocs"], int)


@pytest.mark.asyncio
async def test_parse_darshan_text_with_colon_in_values():
    """Test _parse_darshan_text handles values containing colons."""
    text_output = """
Job ID: abc:def:12345
Start time: 2024-01-01 10:30:45
User ID: user:group:123
"""

    mock_process = AsyncMock()
    mock_process.communicate.return_value = (
        text_output.encode("utf-8"),
        b"",
    )
    mock_process.returncode = 0

    with patch(
        "darshan_mcp.capabilities.darshan_parser.asyncio.create_subprocess_exec"
    ) as mock_exec:
        mock_exec.return_value = mock_process

        result = await darshan_parser._parse_darshan_text("/test/file.darshan")

        assert result["success"] is True
        # Should split on first colon only, preserving remaining colons
        assert result["job"]["job_id"] == "abc:def:12345"
        assert result["job"]["start_time"] == "2024-01-01 10:30:45"
        assert result["job"]["user_id"] == "user:group:123"


@pytest.mark.asyncio
async def test_run_darshan_command_with_empty_stdout():
    """Test _run_darshan_command when command returns empty stdout."""
    mock_process = AsyncMock()
    mock_process.communicate.return_value = (
        b"",
        b"Warning: No data found",
    )
    mock_process.returncode = 0

    with patch(
        "darshan_mcp.capabilities.darshan_parser.asyncio.create_subprocess_exec"
    ) as mock_exec:
        mock_exec.return_value = mock_process

        stdout, stderr, returncode = await darshan_parser._run_darshan_command(
            ["-l"], "/test/file.darshan"
        )

        assert returncode == 0
        assert stdout == ""
        assert stderr == "Warning: No data found"


@pytest.mark.asyncio
async def test_run_darshan_command_with_exception():
    """Test _run_darshan_command handles general exceptions."""
    with patch(
        "darshan_mcp.capabilities.darshan_parser.asyncio.create_subprocess_exec"
    ) as mock_exec:
        mock_exec.side_effect = RuntimeError("Unexpected error")

        stdout, stderr, returncode = await darshan_parser._run_darshan_command(
            ["--json"], "/test/file.darshan"
        )

        assert returncode == 1
        assert stdout == ""
        assert "Error running darshan command" in stderr
        assert "Unexpected error" in stderr


@pytest.mark.asyncio
async def test_parse_darshan_text_modules_section_edge_cases():
    """Test _parse_darshan_text modules section with edge cases."""
    # Test modules section immediately followed by non-module line
    text_output = """
Job ID: 12345
Modules in log:
- POSIX
Not a module line
- MPIIO
"""

    mock_process = AsyncMock()
    mock_process.communicate.return_value = (
        text_output.encode("utf-8"),
        b"",
    )
    mock_process.returncode = 0

    with patch(
        "darshan_mcp.capabilities.darshan_parser.asyncio.create_subprocess_exec"
    ) as mock_exec:
        mock_exec.return_value = mock_process

        result = await darshan_parser._parse_darshan_text("/test/file.darshan")

        assert result["success"] is True
        # Should only capture POSIX (before the non-module line breaks the section)
        # Note: The current implementation continues to check for modules throughout
        # the file, so both POSIX and MPIIO should be captured
        assert "POSIX" in result["modules"]
        # MPIIO might not be captured depending on implementation
        # Actually checking the code, it continues parsing, so MPIIO should be there
        assert "MPIIO" in result["modules"]


@pytest.mark.asyncio
async def test_parse_darshan_json_with_stderr_and_returncode_zero():
    """Test _parse_darshan_json when returncode is 0 but there's stderr output."""
    valid_json = '{"job": {"job_id": "12345"}, "modules": [], "files": {}}'

    mock_process = AsyncMock()
    mock_process.communicate.return_value = (
        valid_json.encode("utf-8"),
        b"Warning: Some non-critical warning",
    )
    mock_process.returncode = 0

    with patch(
        "darshan_mcp.capabilities.darshan_parser.asyncio.create_subprocess_exec"
    ) as mock_exec:
        mock_exec.return_value = mock_process

        result = await darshan_parser._parse_darshan_json("/test/file.darshan")

        # Should successfully parse JSON despite stderr
        assert "job" in result
        assert result["job"]["job_id"] == "12345"
