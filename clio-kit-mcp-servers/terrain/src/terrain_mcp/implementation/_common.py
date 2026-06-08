"""Shared numeric helpers for terrain analysis."""

from __future__ import annotations

import numpy as np

# Safety limits to keep tool calls bounded in memory and time.
MAX_DEM_CELLS = 2_000_000
MAX_POINT_CLOUD_POINTS = 500_000


def finite_values(array: np.ndarray) -> np.ndarray:
    """Return a flat 1-D array of only the finite (non-NaN/inf) values."""
    values = np.asarray(array, dtype=float).ravel()
    return values[np.isfinite(values)]


def summary_stats(values: np.ndarray) -> dict[str, float | int | None]:
    """Compute count/min/max/mean/median/std over an array of values.

    NaN/inf are not stripped here; pass values through :func:`finite_values`
    first when the input may contain non-finite entries.
    """
    values = np.asarray(values, dtype=float).ravel()
    if values.size == 0:
        return {
            "count": 0,
            "min": None,
            "max": None,
            "mean": None,
            "median": None,
            "std": None,
        }
    return {
        "count": int(values.size),
        "min": float(np.min(values)),
        "max": float(np.max(values)),
        "mean": float(np.mean(values)),
        "median": float(np.median(values)),
        "std": float(np.std(values)),
    }
