"""
Utility functions for Slurm capabilities.
Common functions used across multiple Slurm capabilities.
"""

import shutil
import os
import re
import stat
import subprocess
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from typing import BinaryIO, Callable, Sequence, cast

MAX_JOB_SCRIPT_BYTES = 8 * 1024 * 1024
DEFAULT_SLURM_COMMAND_TIMEOUT_SECONDS = 30.0
DEFAULT_SLURM_OUTPUT_BYTES = 2 * 1024 * 1024
SLURM_FIELD_SEPARATOR = "\x1f"
_ORIGINAL_SUBPROCESS_RUN = subprocess.run
_ORIGINAL_SUBPROCESS_POPEN = subprocess.Popen
_SAFE_SBATCH_TOKEN = re.compile(r"^[A-Za-z0-9_.-]+$")
_SBATCH_MEMORY = re.compile(
    r"^[1-9][0-9]*(?:\.[0-9]+)?(?:[KMGTP](?:i?B)?|B)?$", re.IGNORECASE
)
_SBATCH_WALLTIME = re.compile(r"^(?:[0-9]+-)?[0-9]{1,3}:[0-5][0-9]:[0-5][0-9]$")
_SBATCH_ARRAY = re.compile(
    r"^[0-9]+(?:-[0-9]+(?::[1-9][0-9]*)?)?(?:%[1-9][0-9]*)?"
    r"(?:,[0-9]+(?:-[0-9]+(?::[1-9][0-9]*)?)?(?:%[1-9][0-9]*)?)*$"
)


def check_slurm_available() -> bool:
    """Check if Slurm is available on the system."""
    return shutil.which("sbatch") is not None


def ensure_logs_directory() -> str:
    """
    Ensure the logs/slurm_output directory exists.

    Returns:
        Path to the logs/slurm_output directory
    """
    logs_dir = "logs/slurm_output"
    os.makedirs(logs_dir, exist_ok=True)
    return logs_dir


def read_regular_job_script(path: str, *, max_bytes: int = MAX_JOB_SCRIPT_BYTES) -> str:
    """Read one regular UTF-8 job script through a bounded open descriptor.

    Descriptor metadata and the bounded read are used together so replacing or
    growing the path after it is opened cannot turn validation into an
    unbounded allocation.
    """
    if max_bytes < 1:
        raise ValueError("max_bytes must be positive")
    try:
        descriptor = os.open(path, os.O_RDONLY | getattr(os, "O_BINARY", 0))
    except FileNotFoundError as exc:
        raise FileNotFoundError(f"Script file '{path}' not found") from exc
    except (IsADirectoryError, PermissionError) as exc:
        raise ValueError(f"Script path '{path}' is not a regular file") from exc
    try:
        metadata = os.fstat(descriptor)
        if not stat.S_ISREG(metadata.st_mode):
            raise ValueError(f"Script path '{path}' is not a regular file")
        if metadata.st_size > max_bytes:
            raise ValueError(f"Script file '{path}' exceeds the {max_bytes}-byte limit")
        with os.fdopen(descriptor, "rb") as stream:
            descriptor = -1
            payload = stream.read(max_bytes + 1)
    finally:
        if descriptor >= 0:
            os.close(descriptor)
    if len(payload) > max_bytes:
        raise ValueError(f"Script file '{path}' exceeds the {max_bytes}-byte limit")
    try:
        return payload.decode("utf-8", errors="strict")
    except UnicodeDecodeError as exc:
        raise ValueError(f"Script file '{path}' is not valid UTF-8") from exc


def validate_sbatch_token(value: str | None, *, field: str) -> str | None:
    """Validate a single-token SBATCH name before script interpolation."""
    if value is None:
        return None
    normalized = value.strip()
    if (
        not normalized
        or len(normalized) > 128
        or _SAFE_SBATCH_TOKEN.fullmatch(normalized) is None
    ):
        raise ValueError(f"{field} contains unsupported characters")
    return normalized


def validate_sbatch_memory(value: str | None) -> str | None:
    """Validate a positive Slurm memory request before interpolation."""
    if value is None:
        return None
    normalized = value.strip()
    if _SBATCH_MEMORY.fullmatch(normalized) is None:
        raise ValueError("memory must be a positive Slurm size such as 4096M or 16G")
    return normalized


def validate_sbatch_time_limit(value: str | None) -> str | None:
    """Validate a Slurm walltime before interpolation."""
    if value is None:
        return None
    normalized = value.strip()
    if _SBATCH_WALLTIME.fullmatch(normalized) is None:
        raise ValueError(
            "time_limit must use Slurm [days-]hours:minutes:seconds syntax"
        )
    return normalized


def validate_sbatch_array(value: str) -> str:
    """Validate an array expression before interpolation into an SBATCH script."""
    normalized = value.strip()
    if len(normalized) > 256 or _SBATCH_ARRAY.fullmatch(normalized) is None:
        raise ValueError(
            "array_range must be a Slurm task expression such as 0-31 or 0-99%8"
        )
    return normalized


@dataclass(frozen=True)
class SlurmCommandResult:
    """Bounded result from one Slurm command invocation."""

    args: Sequence[str]
    returncode: int
    stdout: str
    stderr: str
    stdout_truncated: bool = False
    stderr_truncated: bool = False


def run_slurm_command(
    command: Sequence[str],
    *,
    timeout: float = DEFAULT_SLURM_COMMAND_TIMEOUT_SECONDS,
    max_stdout_bytes: int = DEFAULT_SLURM_OUTPUT_BYTES,
    max_stderr_bytes: int = 64 * 1024,
    test_runner: Callable[..., object] | None = None,
) -> SlurmCommandResult:
    """Run a Slurm CLI with a timeout and bounded in-memory output.

    Both pipes are drained concurrently to avoid child-process deadlock. Bytes
    beyond the retained limits are discarded while the pipe continues to be
    drained, so a noisy controller cannot force an unbounded allocation.
    ``test_runner`` preserves deterministic unit tests that patch
    ``subprocess.run``; production callers leave it unset.
    """
    if timeout <= 0 or max_stdout_bytes < 1 or max_stderr_bytes < 1:
        raise ValueError("timeout and output limits must be positive")
    args = [str(item) for item in command]
    if test_runner is not None and test_runner is not _ORIGINAL_SUBPROCESS_RUN:
        completed = test_runner(
            args,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        returncode = int(getattr(completed, "returncode"))
        stdout = str(getattr(completed, "stdout", "") or "")
        stderr = str(getattr(completed, "stderr", "") or "")
        stdout, stdout_truncated = _bounded_text(stdout, max_stdout_bytes)
        stderr, stderr_truncated = _bounded_text(stderr, max_stderr_bytes)
        return SlurmCommandResult(
            args=args,
            returncode=returncode,
            stdout=stdout,
            stderr=stderr,
            stdout_truncated=stdout_truncated,
            stderr_truncated=stderr_truncated,
        )

    process = _ORIGINAL_SUBPROCESS_POPEN(
        args,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        stdin=subprocess.DEVNULL,
    )
    assert process.stdout is not None
    assert process.stderr is not None
    with ThreadPoolExecutor(max_workers=2) as executor:
        stdout_future = executor.submit(
            _drain_bounded_pipe, cast(BinaryIO, process.stdout), max_stdout_bytes
        )
        stderr_future = executor.submit(
            _drain_bounded_pipe, cast(BinaryIO, process.stderr), max_stderr_bytes
        )
        try:
            returncode = process.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait()
            _ = stdout_future.result()
            _ = stderr_future.result()
            raise
        stdout_bytes, stdout_truncated = stdout_future.result()
        stderr_bytes, stderr_truncated = stderr_future.result()
    return SlurmCommandResult(
        args=args,
        returncode=returncode,
        stdout=stdout_bytes.decode("utf-8", errors="replace"),
        stderr=stderr_bytes.decode("utf-8", errors="replace"),
        stdout_truncated=stdout_truncated,
        stderr_truncated=stderr_truncated,
    )


def _drain_bounded_pipe(stream: BinaryIO, limit: int) -> tuple[bytes, bool]:
    retained = bytearray()
    truncated = False
    while chunk := stream.read(64 * 1024):
        remaining = limit - len(retained)
        if remaining > 0:
            retained.extend(chunk[:remaining])
        if len(chunk) > remaining:
            truncated = True
    return bytes(retained), truncated


def _bounded_text(value: str, max_bytes: int) -> tuple[str, bool]:
    encoded = value.encode("utf-8")
    if len(encoded) <= max_bytes:
        return value, False
    return encoded[:max_bytes].decode("utf-8", errors="replace"), True


def complete_stdout_lines(result: SlurmCommandResult) -> list[str]:
    """Return complete retained stdout lines, excluding a truncated tail."""
    lines = result.stdout.splitlines()
    if (
        result.stdout_truncated
        and result.stdout
        and not result.stdout.endswith(("\n", "\r"))
        and lines
    ):
        lines.pop()
    return lines


def split_slurm_fields(line: str) -> list[str]:
    """Split a Slurm row using the requested control-character delimiter.

    The comma fallback preserves compatibility with old fixtures and Slurm
    wrappers that ignore the requested format. Production commands request the
    unit separator, which cannot collide with node lists, features, GRES, job
    names, or scheduler reasons.
    """
    if SLURM_FIELD_SEPARATOR in line:
        return line.split(SLURM_FIELD_SEPARATOR)
    return line.split(",")
