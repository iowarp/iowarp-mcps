"""Metadata discovery must not require the optional native ADIOS2 runtime."""

from __future__ import annotations

import subprocess
import sys


def test_server_import_does_not_load_adios2() -> None:
    """Import the FastMCP surface while an ADIOS2 import is forced to fail."""
    script = """
import builtins

original_import = builtins.__import__

def guarded_import(name, *args, **kwargs):
    if name == "adios2" or name.startswith("adios2."):
        raise AssertionError("metadata import attempted to load adios2")
    return original_import(name, *args, **kwargs)

builtins.__import__ = guarded_import
from adios_mcp.server import mcp
assert mcp.name == "adios"
"""

    result = subprocess.run(
        [sys.executable, "-c", script],
        check=False,
        capture_output=True,
        text=True,
        timeout=30,
    )

    assert result.returncode == 0, result.stderr
