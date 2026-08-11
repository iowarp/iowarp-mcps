"""Implementation helpers for the seismology MCP server.

Two families live here. The ``sac_io``/``analysis`` modules read SAC waveform
files and archives; the ``catalog_*`` modules analyse and plot earthquake
catalogs, ported from the seismic MCP server when it merged in (clio-kit #357).
"""

from .analysis import compute_trace_statistics, inspect_archive, plot_traces
from .catalog_analysis import (
    _b_value,
    _haversine_km,
    _magnitude_of_completeness,
    _omori_decay,
    analyze_sequence,
)
from .catalog_io import CatalogError, _normalize_events, load_catalog
from .catalog_plotting import plot_sequence
from .sac_io import SacAnalysisError, SacTrace, load_sac_traces, trace_statistics

__all__ = [
    "CatalogError",
    "SacAnalysisError",
    "SacTrace",
    "_b_value",
    "_haversine_km",
    "_magnitude_of_completeness",
    "_normalize_events",
    "_omori_decay",
    "analyze_sequence",
    "compute_trace_statistics",
    "inspect_archive",
    "load_catalog",
    "load_sac_traces",
    "plot_sequence",
    "plot_traces",
    "trace_statistics",
]
