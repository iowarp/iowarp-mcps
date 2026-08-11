"""Shared pytest fixtures: synthesize real SAC binary files and a TAR archive.

A SAC binary file is a 632-byte header (70 float32, 40 int32, then character
fields) followed by ``npts`` float32 samples. These fixtures write genuine SAC
bytes so the parser, statistics, and plotting code run against real data.
"""

from __future__ import annotations

import csv
import json
import math
import struct
import tarfile
from pathlib import Path

import numpy as np

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


# --- earthquake-catalog fixtures, ported from the seismic MCP (#357) ---

DAY_MS = 86_400_000


def mainshock_aftershock_events(base_ms: int = 1_700_000_000_000) -> list[dict]:
    """A dominant event followed by Omori-decaying smaller aftershocks."""
    events = [
        {
            "mag": 6.5,
            "time_ms": base_ms,
            "lon": -68.7,
            "lat": -22.4,
            "depth_km": 30.0,
            "place": "x",
            "id": "m",
        }
    ]
    # decaying counts over successive days, all well below the mainshock
    per_day = [12, 6, 3, 2, 1]
    eid = 0
    for d, count in enumerate(per_day):
        for k in range(count):
            events.append(
                {
                    "mag": round(3.0 + (k % 5) * 0.2, 1),
                    "time_ms": base_ms + d * DAY_MS + k * 3_600_000,
                    "lon": -68.7 + 0.01 * k,
                    "lat": -22.4 + 0.01 * d,
                    "depth_km": 25.0,
                    "place": "x",
                    "id": f"a{eid}",
                }
            )
            eid += 1
    return events


def gr_magnitudes(
    b: float = 1.0, mc: float = 2.0, n: int = 4000, seed: int = 7
) -> list[float]:
    """Synthetic magnitudes drawn from a Gutenberg-Richter distribution."""
    rng = np.random.default_rng(seed)
    u = rng.uniform(1e-9, 1.0, n)
    mags = mc - np.log10(u) / b
    return [round(float(m), 1) for m in mags]


def gr_catalog_events(
    b: float = 1.0, mc: float = 2.0, n: int = 4000, seed: int = 7
) -> list[dict]:
    """A full event catalog whose magnitudes follow Gutenberg-Richter."""
    base_ms = 1_700_000_000_000
    events: list[dict] = []
    for i, mag in enumerate(gr_magnitudes(b=b, mc=mc, n=n, seed=seed)):
        events.append(
            {
                "mag": mag,
                "time_ms": base_ms + i * 3_600_000,
                "lon": -120.0 + 0.001 * (i % 100),
                "lat": 36.0 + 0.001 * (i % 100),
                "depth_km": 10.0,
                "place": "synthetic",
                "id": f"g{i}",
            }
        )
    return events


def _write_events_geojson(path: Path, events: list[dict]) -> Path:
    """Write events as a saved {'events': [...]} JSON wrapper."""
    path.write_text(json.dumps({"events": events}), encoding="utf-8")
    return path


def _write_feature_collection(path: Path, events: list[dict]) -> Path:
    """Write events as a catalog-style GeoJSON FeatureCollection."""
    features = [
        {
            "type": "Feature",
            "id": e["id"],
            "properties": {
                "mag": e["mag"],
                "time": e["time_ms"],
                "type": "earthquake",
                "place": e["place"],
            },
            "geometry": {
                "type": "Point",
                "coordinates": [e["lon"], e["lat"], e["depth_km"]],
            },
        }
        for e in events
    ]
    path.write_text(
        json.dumps({"type": "FeatureCollection", "features": features}),
        encoding="utf-8",
    )
    return path


def _write_csv(path: Path, events: list[dict]) -> Path:
    """Write events as a CSV with mag/time/lon/lat columns."""
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(
            ["id", "magnitude", "time_ms", "longitude", "latitude", "depth_km", "place"]
        )
        for e in events:
            writer.writerow(
                [
                    e["id"],
                    e["mag"],
                    e["time_ms"],
                    e["lon"],
                    e["lat"],
                    e["depth_km"],
                    e["place"],
                ],
            )
    return path


@pytest.fixture
def aftershock_geojson(tmp_path: Path) -> Path:
    """A mainshock-aftershock catalog saved as an {'events': [...]} JSON wrapper."""
    # Neutral filename: the data-vs-verdict test scans the result blob, which
    # echoes catalog_path, for words like "aftershock"/"swarm".
    return _write_events_geojson(tmp_path / "cat_a.json", mainshock_aftershock_events())


@pytest.fixture
def aftershock_feature_collection(tmp_path: Path) -> Path:
    """A mainshock-aftershock catalog saved as a GeoJSON FeatureCollection."""
    return _write_feature_collection(
        tmp_path / "cat_fc.geojson", mainshock_aftershock_events()
    )


@pytest.fixture
def aftershock_csv(tmp_path: Path) -> Path:
    """A mainshock-aftershock catalog saved as a CSV."""
    return _write_csv(tmp_path / "cat_c.csv", mainshock_aftershock_events())


@pytest.fixture
def gr_geojson(tmp_path: Path) -> Path:
    """A Gutenberg-Richter catalog (b=1, Mc=2) saved as a JSON wrapper."""
    return _write_events_geojson(tmp_path / "gr.json", gr_catalog_events())


@pytest.fixture
def empty_geojson(tmp_path: Path) -> Path:
    """An empty (quiet-region) catalog saved as a JSON wrapper."""
    return _write_events_geojson(tmp_path / "empty.json", [])
