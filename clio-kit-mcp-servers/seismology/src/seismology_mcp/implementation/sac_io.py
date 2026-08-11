"""SAC waveform parsing and archive inspection (pure stdlib + numpy).

The tools cover a narrow, dependency-light surface: staged SAC files or TAR
archives that contain SAC files. They do not support MiniSEED, SEGY, or remote
object stores, and they retrieve nothing - they only read files the user
already has on disk.

SAC binary headers are 632 bytes: 70 float32 fields, 40 int32 fields, then
character fields, followed by ``npts`` float32 samples. Endianness is detected
heuristically by scoring both little- and big-endian interpretations.
"""

from __future__ import annotations

import math
import struct
import tarfile
from dataclasses import dataclass
from pathlib import Path

import numpy as np

_SAC_HEADER_BYTES = 632
_MAX_SAC_BYTES = 8 * 1024 * 1024
_ARCHIVE_SUFFIXES = {".tar", ".tgz", ".gz"}


class SacAnalysisError(Exception):
    """Raised when a SAC file/archive cannot be read or parsed."""


@dataclass(frozen=True)
class SacTrace:
    """Parsed SAC trace samples and metadata."""

    member: str
    station: str
    phase: str
    npts: int
    delta_s: float
    begin_s: float
    end_s: float
    samples: tuple[float, ...]


def resolve_read_path(filepath: str) -> Path:
    """Resolve and validate a readable input file path.

    Args:
        filepath: Path to a SAC file or TAR archive.

    Returns:
        The resolved absolute path.

    Raises:
        SacAnalysisError: If the path is empty, missing, or not a file.
    """
    text = str(filepath or "").strip()
    if not text:
        raise SacAnalysisError("No filepath provided.")
    path = Path(text).expanduser().resolve()
    if not path.exists():
        raise SacAnalysisError(f"File does not exist: {path}")
    if not path.is_file():
        raise SacAnalysisError(f"Path is not a regular file: {path}")
    return path


def resolve_write_path(output_path: str) -> Path:
    """Resolve an output file path, creating parent directories.

    Args:
        output_path: Destination path for a generated artifact.

    Returns:
        The resolved absolute path with its parent directory ensured.

    Raises:
        SacAnalysisError: If the path is empty or its parent cannot be created.
    """
    text = str(output_path or "").strip()
    if not text:
        raise SacAnalysisError("No output_path provided.")
    path = Path(text).expanduser().resolve()
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        raise SacAnalysisError(
            f"Could not create output directory {path.parent}: {exc}"
        ) from exc
    return path


def normalize_member_filter(value: str | None) -> str:
    """Return a case-insensitive substring filter for archive member names."""
    return str(value or "").strip().lower()


def clean_positive_int(value: int | str | None, *, default: int, max_value: int) -> int:
    """Normalize a positive integer argument into ``[1, max_value]``."""
    if value is None or value == "":
        return default
    try:
        if isinstance(value, bool):
            return default
        if isinstance(value, int):
            parsed = value
        elif isinstance(value, str):
            parsed = int(value)
        else:
            return default
    except (TypeError, ValueError):
        return default
    return max(1, min(parsed, max_value))


def _is_sac_member(name: str) -> bool:
    """Return whether an archive member looks like a SAC waveform file."""
    return name.lower().endswith(".sac")


def member_phase(member: str) -> str:
    """Infer a phase/group label from the archive path."""
    parts = [part for part in member.replace("\\", "/").split("/") if part]
    if len(parts) >= 2:
        parent = parts[-2]
        if parent:
            return parent
    stem = Path(member).stem
    bits = stem.split(".")
    return bits[-3] if len(bits) >= 3 else "unknown"


def member_station(member: str) -> str:
    """Infer a station label from common SAC file naming conventions."""
    stem = Path(member).stem
    bits = stem.split(".")
    if len(bits) >= 3:
        return bits[-3]
    return "unknown"


def iter_archive_sac_members(
    filepath: Path, *, member_filter: str
) -> list[tarfile.TarInfo]:
    """Return SAC members in a TAR archive without extracting them.

    Args:
        filepath: Path to the TAR archive.
        member_filter: Lower-cased substring filter applied to member names.

    Raises:
        SacAnalysisError: If the archive cannot be read.
    """
    try:
        with tarfile.open(filepath, "r:*") as archive:
            members = [
                member
                for member in archive.getmembers()
                if member.isfile()
                and _is_sac_member(member.name)
                and (not member_filter or member_filter in member.name.lower())
            ]
    except tarfile.TarError as exc:
        raise SacAnalysisError(f"Could not read TAR archive: {exc}") from exc
    return members


def _read_archive_member(filepath: Path, member: tarfile.TarInfo) -> bytes:
    """Read one bounded member from a TAR archive."""
    if member.size > _MAX_SAC_BYTES:
        raise SacAnalysisError(
            f"SAC member {member.name!r} is {member.size} bytes, above "
            f"the per-trace limit of {_MAX_SAC_BYTES} bytes."
        )
    with tarfile.open(filepath, "r:*") as archive:
        handle = archive.extractfile(member)
        if handle is None:
            raise SacAnalysisError(f"Could not open archive member {member.name!r}.")
        return handle.read()


def iter_sac_payloads(
    filepath: Path,
    *,
    member_filter: str,
    max_traces: int,
) -> tuple[int, list[tuple[str, bytes]]]:
    """Return total available SAC traces and bounded payloads.

    Args:
        filepath: A direct ``.sac`` file or a TAR archive.
        member_filter: Lower-cased substring filter for member names.
        max_traces: Maximum number of payloads to materialize.

    Returns:
        ``(total_matching, payloads)`` where ``payloads`` is bounded by
        ``max_traces`` and each entry is ``(member_name, raw_bytes)``.

    Raises:
        SacAnalysisError: For unsupported inputs or oversized files.
    """
    suffix = filepath.suffix.lower()
    if suffix == ".sac":
        if member_filter and member_filter not in filepath.name.lower():
            return 0, []
        size = filepath.stat().st_size
        if size > _MAX_SAC_BYTES:
            raise SacAnalysisError(
                f"SAC file {filepath.name!r} is {size} bytes, above "
                f"the per-trace limit of {_MAX_SAC_BYTES} bytes."
            )
        return 1, [(filepath.name, filepath.read_bytes())]

    if suffix not in _ARCHIVE_SUFFIXES:
        raise SacAnalysisError(
            f"Unsupported seismic input {filepath}. Use a .sac, .tar, .tar.gz, or .tgz file."
        )

    members = iter_archive_sac_members(filepath, member_filter=member_filter)
    payloads = [
        (member.name, _read_archive_member(filepath, member))
        for member in members[:max_traces]
    ]
    return len(members), payloads


def _unpack_sac_header(
    payload: bytes,
) -> tuple[str, tuple[float, ...], tuple[int, ...]]:
    """Unpack a SAC binary header using the more plausible endian variant."""
    if len(payload) < _SAC_HEADER_BYTES:
        raise SacAnalysisError("SAC payload is smaller than the 632-byte SAC header.")
    header = payload[:440]
    data_floats = (len(payload) - _SAC_HEADER_BYTES) // 4
    candidates: list[tuple[str, tuple[float, ...], tuple[int, ...], int]] = []
    for endian in ("<", ">"):
        floats = struct.unpack(f"{endian}70f", header[:280])
        ints = struct.unpack(f"{endian}40i", header[280:440])
        npts = ints[9] if len(ints) > 9 else 0
        delta = floats[0] if floats else -1.0
        score = 0
        if npts == data_floats:
            score += 4
        if 0 < npts <= data_floats:
            score += 2
        if 0 < delta < 1000:
            score += 1
        candidates.append((endian, floats, ints, score))
    endian, floats, ints, _score = max(candidates, key=lambda item: item[3])
    return endian, floats, ints


def parse_sac_trace(member: str, payload: bytes) -> SacTrace:
    """Parse one SAC trace from bytes.

    Args:
        member: Logical name of the trace (file or archive member name).
        payload: Raw SAC binary bytes (header + samples).

    Raises:
        SacAnalysisError: If the payload is malformed or contains no samples.
    """
    endian, floats, ints = _unpack_sac_header(payload)
    available_npts = (len(payload) - _SAC_HEADER_BYTES) // 4
    header_npts = ints[9] if len(ints) > 9 else available_npts
    npts = header_npts if 0 < header_npts <= available_npts else available_npts
    if npts <= 0:
        raise SacAnalysisError(f"SAC member {member!r} contains no samples.")
    data_start = _SAC_HEADER_BYTES
    samples = struct.unpack(
        f"{endian}{npts}f",
        payload[data_start : data_start + npts * 4],
    )
    delta_s = float(floats[0]) if floats and math.isfinite(float(floats[0])) else 0.0
    begin_s = (
        float(floats[5]) if len(floats) > 5 and math.isfinite(float(floats[5])) else 0.0
    )
    end_s = (
        float(floats[6])
        if len(floats) > 6 and math.isfinite(float(floats[6]))
        else begin_s
    )
    if end_s <= begin_s and delta_s > 0:
        end_s = begin_s + delta_s * max(0, npts - 1)
    return SacTrace(
        member=member,
        station=member_station(member),
        phase=member_phase(member),
        npts=npts,
        delta_s=delta_s,
        begin_s=begin_s,
        end_s=end_s,
        samples=tuple(float(value) for value in samples),
    )


def load_sac_traces(
    filepath: str,
    *,
    member_filter: str | None,
    max_traces: int,
) -> tuple[Path, int, list[SacTrace]]:
    """Load bounded SAC traces from a direct file or archive.

    Args:
        filepath: A ``.sac`` file or a TAR archive of SAC files.
        member_filter: Optional case-insensitive substring filter.
        max_traces: Maximum number of traces to parse.

    Returns:
        ``(resolved_path, total_matching, traces)``.

    Raises:
        SacAnalysisError: If the input cannot be read or parsed.
    """
    safe_path = resolve_read_path(filepath)
    normalized_filter = normalize_member_filter(member_filter)
    total, payloads = iter_sac_payloads(
        safe_path,
        member_filter=normalized_filter,
        max_traces=max_traces,
    )
    traces = [parse_sac_trace(member, payload) for member, payload in payloads]
    return safe_path, total, traces


def trace_statistics(trace: SacTrace) -> dict[str, object]:
    """Return compact numeric statistics for one trace.

    Args:
        trace: A parsed :class:`SacTrace`.

    Returns:
        A dict of header metadata plus min/max/mean/std/peak_abs amplitude
        statistics computed with numpy.
    """
    samples = np.asarray(trace.samples, dtype=np.float64)
    return {
        "member": trace.member,
        "station": trace.station,
        "phase": trace.phase,
        "npts": trace.npts,
        "delta_s": trace.delta_s,
        "begin_s": trace.begin_s,
        "end_s": trace.end_s,
        "min": float(samples.min()),
        "max": float(samples.max()),
        "mean": float(samples.mean()),
        "std": float(samples.std()),
        "peak_abs": float(np.abs(samples).max()),
    }
