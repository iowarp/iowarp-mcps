"""High-level SAC analysis operations backing the MCP tools.

These functions keep ``server.py`` thin: they own all path handling, bounds,
parsing, statistics, and plotting. Every failure path raises
:class:`SacAnalysisError`, which the server translates into ``ToolError``.
"""

from __future__ import annotations

import time
from pathlib import Path
from typing import Any

from .sac_io import (
    SacAnalysisError,
    clean_positive_int,
    iter_archive_sac_members,
    load_sac_traces,
    member_phase,
    member_station,
    normalize_member_filter,
    resolve_read_path,
    resolve_write_path,
    trace_statistics,
)


def inspect_archive(
    filepath: str,
    member_filter: str | None = None,
    max_members: int | str | None = 12,
) -> dict[str, Any]:
    """Inspect a staged SAC file or TAR archive and summarize waveform members.

    Args:
        filepath: A ``.sac`` file or a TAR archive containing SAC files.
        member_filter: Optional case-insensitive substring filter on names.
        max_members: Maximum number of members/sizes to list (1-100).

    Returns:
        A summary dict with the member count, a sample of member names/sizes,
        inferred phases and stations, and a truncation flag.

    Raises:
        SacAnalysisError: If the file or archive cannot be read.
    """
    safe_path = resolve_read_path(filepath)
    limit = clean_positive_int(max_members, default=12, max_value=100)
    normalized_filter = normalize_member_filter(member_filter)
    if safe_path.suffix.lower() == ".sac":
        members = (
            [safe_path.name]
            if not normalized_filter or normalized_filter in safe_path.name.lower()
            else []
        )
        sizes = [safe_path.stat().st_size] if members else []
    else:
        tar_members = iter_archive_sac_members(
            safe_path, member_filter=normalized_filter
        )
        members = [member.name for member in tar_members]
        sizes = [member.size for member in tar_members]
    sample_members = members[:limit]
    phases = sorted({member_phase(member) for member in members})
    stations = sorted({member_station(member) for member in members})
    return {
        "status": "success",
        "filepath": str(safe_path),
        "sac_trace_count": len(members),
        "sample_members": sample_members,
        "sample_sizes_bytes": sizes[:limit],
        "phases": phases[:20],
        "stations": stations[:20],
        "members_truncated": len(members) > limit,
    }


def compute_trace_statistics(
    filepath: str,
    member_filter: str | None = None,
    max_traces: int | str | None = 6,
) -> dict[str, Any]:
    """Compute per-trace statistics for SAC traces in a file or archive.

    Args:
        filepath: A ``.sac`` file or a TAR archive containing SAC files.
        member_filter: Optional case-insensitive substring filter on names.
        max_traces: Maximum number of traces to analyze (1-25).

    Returns:
        A dict with the total matching trace count, the number analyzed, and a
        list of per-trace statistics dicts.

    Raises:
        SacAnalysisError: If no traces match or the input cannot be parsed.
    """
    limit = clean_positive_int(max_traces, default=6, max_value=25)
    safe_path, total, traces = load_sac_traces(
        filepath,
        member_filter=member_filter,
        max_traces=limit,
    )
    if not traces:
        raise SacAnalysisError(
            "No SAC traces matched the requested file/filter. Inspect the archive "
            "first and choose a member_filter that matches SAC files."
        )
    return {
        "status": "success",
        "filepath": str(safe_path),
        "sac_trace_count": total,
        "traces_analyzed": len(traces),
        "traces": [trace_statistics(trace) for trace in traces],
        "traces_truncated": total > len(traces),
    }


def plot_traces(
    filepath: str,
    member_filter: str | None = None,
    max_traces: int | str | None = 3,
    output_path: str = "",
) -> dict[str, Any]:
    """Plot selected SAC traces from a file or archive to a PNG artifact.

    Args:
        filepath: A ``.sac`` file or a TAR archive containing SAC files.
        member_filter: Optional case-insensitive substring filter on names.
        max_traces: Maximum number of traces to plot (1-8).
        output_path: Destination PNG path; a default under the current working
            directory is used when empty.

    Returns:
        A dict with the output path, total/plotted trace counts, plotted member
        names, and the render duration in milliseconds.

    Raises:
        SacAnalysisError: If no traces match or rendering fails.
    """
    start = time.time()
    limit = clean_positive_int(max_traces, default=3, max_value=8)
    safe_path, total, traces = load_sac_traces(
        filepath,
        member_filter=member_filter,
        max_traces=limit,
    )
    if not traces:
        raise SacAnalysisError(
            "No SAC traces matched the requested file/filter. Inspect the archive "
            "first and choose a member_filter that matches SAC files."
        )
    if not output_path:
        default_dir = Path.cwd() / "sac-artifacts" / "charts"
        output_path = str(default_dir / f"sac_traces_{safe_path.stem}.png")
    safe_output = resolve_write_path(output_path)

    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    fig, ax = plt.subplots(figsize=(10, max(4, 1.6 * len(traces))))
    offset = 0.0
    for trace in traces:
        samples = trace.samples
        peak = max(max(abs(value) for value in samples), 1.0)
        normalized = [value / peak + offset for value in samples]
        times = [
            trace.begin_s + index * trace.delta_s if trace.delta_s > 0 else float(index)
            for index in range(len(samples))
        ]
        label = f"{trace.station} {trace.phase}"
        ax.plot(times, normalized, linewidth=0.8, label=label)
        offset += 1.4
    ax.set_xlabel(
        "Time (s)" if any(trace.delta_s > 0 for trace in traces) else "Sample"
    )
    ax.set_ylabel("Normalized trace offset")
    ax.set_title(f"SAC waveform traces: {safe_path.name}")
    ax.grid(alpha=0.25)
    ax.legend(fontsize=8, loc="upper right")
    fig.savefig(safe_output, dpi=150, bbox_inches="tight")
    plt.close(fig)

    return {
        "status": "success",
        "filepath": str(safe_path),
        "output_path": str(safe_output),
        "sac_trace_count": total,
        "traces_plotted": len(traces),
        "members": [trace.member for trace in traces],
        "duration_ms": (time.time() - start) * 1000,
    }
