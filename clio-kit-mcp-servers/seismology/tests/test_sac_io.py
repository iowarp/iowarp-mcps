"""Unit tests for SAC parsing, archive iteration, and statistics."""

from __future__ import annotations

import struct
import tarfile
from pathlib import Path

import pytest

from seismology_mcp.implementation import (
    SacAnalysisError,
    load_sac_traces,
    trace_statistics,
)
from seismology_mcp.implementation.sac_io import (
    clean_positive_int,
    iter_archive_sac_members,
    member_phase,
    member_station,
    parse_sac_trace,
)

from .conftest import make_sac_bytes


def test_parse_roundtrip() -> None:
    samples = [float(i) for i in range(-5, 5)]
    trace = parse_sac_trace(
        "X/IU.ANMO.00.BHZ.sac", make_sac_bytes(samples, delta=0.02, begin=1.0)
    )
    assert trace.npts == 10
    assert trace.delta_s == pytest.approx(0.02)
    assert trace.begin_s == pytest.approx(1.0)
    assert trace.station == "ANMO"  # bits[-3] of IU.ANMO.00.BHZ
    assert trace.phase == "X"
    assert trace.samples[0] == pytest.approx(-5.0)


def test_big_endian_detection() -> None:
    # Construct a big-endian SAC payload and confirm it still parses.
    le = make_sac_bytes([1.0, 2.0, 3.0])
    floats = list(struct.unpack("<70f", le[:280]))
    ints = list(struct.unpack("<40i", le[280:440]))
    header = struct.pack(">70f", *floats) + struct.pack(">40i", *ints) + le[440:632]
    payload = header + struct.pack(">3f", 1.0, 2.0, 3.0)
    trace = parse_sac_trace("a.sac", payload)
    assert trace.npts == 3
    assert trace.samples == pytest.approx((1.0, 2.0, 3.0))


def test_too_small_payload_raises() -> None:
    with pytest.raises(SacAnalysisError):
        parse_sac_trace("a.sac", b"\x00" * 100)


def test_statistics_values() -> None:
    trace = parse_sac_trace("a.sac", make_sac_bytes([-2.0, 0.0, 2.0]))
    stats = trace_statistics(trace)
    assert stats["min"] == pytest.approx(-2.0)
    assert stats["max"] == pytest.approx(2.0)
    assert stats["mean"] == pytest.approx(0.0)
    assert stats["peak_abs"] == pytest.approx(2.0)


def test_iter_archive_members(sac_archive: Path) -> None:
    members = iter_archive_sac_members(sac_archive, member_filter="")
    assert len(members) == 3
    assert all(m.name.endswith(".sac") for m in members)


def test_load_traces_unsupported_suffix(tmp_path: Path) -> None:
    bad = tmp_path / "data.bin"
    bad.write_bytes(b"\x00" * 1000)
    with pytest.raises(SacAnalysisError):
        load_sac_traces(str(bad), member_filter=None, max_traces=1)


def test_load_traces_corrupt_archive(tmp_path: Path) -> None:
    fake = tmp_path / "broken.tar"
    fake.write_bytes(b"not a tar archive at all")
    with pytest.raises(SacAnalysisError):
        load_sac_traces(str(fake), member_filter=None, max_traces=1)


def test_member_helpers() -> None:
    assert member_phase("P/IU.ANMO.00.BHZ.sac") == "P"
    assert member_station("IU.ANMO.00.BHZ.sac") == "ANMO"  # bits[-3]
    assert member_station("flat.sac") == "unknown"


def test_clean_positive_int_bounds() -> None:
    assert clean_positive_int(None, default=5, max_value=10) == 5
    assert clean_positive_int("100", default=5, max_value=10) == 10
    assert clean_positive_int(0, default=5, max_value=10) == 1
    assert clean_positive_int("nope", default=5, max_value=10) == 5
    assert clean_positive_int(True, default=5, max_value=10) == 5


def test_corrupt_archive_via_tarfile(tmp_path: Path) -> None:
    # A valid tar with only a non-SAC member yields zero SAC traces.
    txt = tmp_path / "x.txt"
    txt.write_text("hi", encoding="utf-8")
    arc = tmp_path / "only_text.tar"
    with tarfile.open(arc, "w") as tf:
        tf.add(txt, arcname="x.txt")
    _, total, traces = load_sac_traces(str(arc), member_filter=None, max_traces=5)
    assert total == 0
    assert traces == []
