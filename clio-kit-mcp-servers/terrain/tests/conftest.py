"""Shared pytest fixtures: small synthetic terrain fixtures on disk."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest


@pytest.fixture
def dem_csv(tmp_path: Path) -> Path:
    """A small 5x5 tilted-plane DEM written as a CSV numeric grid.

    Elevation increases left-to-right so slope and aspect are well defined and
    a subset of cells satisfy reasonable elevation/slope criteria.
    """
    rows, cols = 5, 5
    grid = np.zeros((rows, cols), dtype=float)
    for c in range(cols):
        grid[:, c] = 10.0 + 2.0 * c
    path = tmp_path / "dem.csv"
    np.savetxt(path, grid, delimiter=",", fmt="%.6g")
    return path


@pytest.fixture
def dem_npz(tmp_path: Path) -> Path:
    """A small DEM stored under the 'dem' key in an NPZ archive."""
    grid = np.arange(16, dtype=float).reshape(4, 4)
    path = tmp_path / "dem.npz"
    np.savez(path, dem=grid)
    return path


@pytest.fixture
def points_csv(tmp_path: Path) -> Path:
    """A small x,y,z point cloud with a header, spanning a 4x4 footprint."""
    lines = ["x,y,z"]
    for x in range(4):
        for y in range(4):
            z = 100.0 + x + y
            lines.append(f"{float(x)},{float(y)},{z}")
    path = tmp_path / "points.csv"
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path
