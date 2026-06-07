"""Shared pytest fixtures: synthesize real SAC binary files and a TAR archive.

A SAC binary file is a 632-byte header (70 float32, 40 int32, then character
fields) followed by ``npts`` float32 samples. These fixtures write genuine SAC
bytes so the parser, statistics, and plotting code run against real data.
"""

from __future__ import annotations

import math
import struct
import tarfile
from pathlib import Path

import pytest

_SAC_HEADER_BYTES = 632


def make_sac_bytes(
    samples: list[float], *, delta: float = 0.01, begin: float = 0.0
) -> bytes:
    """Build a valid little-endian SAC binary payload from samples.

    Args:
        samples: Float samples for the trace.
        delta: Sample spacing in seconds (header field 0).
        begin: Begin time in seconds (header field 5).

    Returns:
        Raw SAC bytes: a 632-byte header followed by float32 samples.
    """
    npts = len(samples)
    floats = [-12345.0] * 70
    floats[0] = delta
    floats[5] = begin
    floats[6] = begin + delta * max(0, npts - 1)
    ints = [-12345] * 40
    ints[9] = npts  # NPTS
    ints[6] = 6  # NVHDR (SAC header version)

    header = bytearray()
    header += struct.pack("<70f", *floats)
    header += struct.pack("<40i", *ints)
    # Character section: 24 fields totaling 192 bytes (440 -> 632).
    header += b" " * (_SAC_HEADER_BYTES - len(header))
    assert len(header) == _SAC_HEADER_BYTES
    return bytes(header) + struct.pack(f"<{npts}f", *samples)


@pytest.fixture
def sac_file(tmp_path: Path) -> Path:
    """A single on-disk SAC file with a sine-wave trace."""
    samples = [math.sin(i * 0.1) for i in range(200)]
    path = tmp_path / "IU.ANMO.00.BHZ.sac"
    path.write_bytes(make_sac_bytes(samples))
    return path


@pytest.fixture
def sac_archive(tmp_path: Path) -> Path:
    """A TAR archive containing several SAC files under phase subdirectories."""
    members = {
        "P/IU.ANMO.00.BHZ.sac": [math.sin(i * 0.1) for i in range(150)],
        "P/IU.COLA.00.BHZ.sac": [math.cos(i * 0.05) for i in range(180)],
        "S/IU.ANMO.00.BHN.sac": [0.5 * math.sin(i * 0.2) for i in range(120)],
        "notes.txt": [],  # non-SAC member must be ignored
    }
    raw_dir = tmp_path / "raw"
    raw_dir.mkdir()
    archive_path = tmp_path / "events.tar.gz"
    with tarfile.open(archive_path, "w:gz") as archive:
        for name, samples in members.items():
            file_path = raw_dir / Path(name).name
            if name.endswith(".sac"):
                file_path.write_bytes(make_sac_bytes(samples))
            else:
                file_path.write_text("not a sac file", encoding="utf-8")
            archive.add(file_path, arcname=name)
    return archive_path
