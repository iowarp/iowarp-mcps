"""Point-cloud reading and gridding into a DEM-like surface.

Reads x/y/z points from CSV / NPY / NPZ (always available) or LAS/LAZ (requires
the optional ``laspy`` extra), then bins them onto a regular grid by averaging
the z values per cell to produce a DEM-like elevation surface.
"""

from __future__ import annotations

import csv
import math
from pathlib import Path
from typing import Any

import numpy as np

from ._common import MAX_DEM_CELLS, MAX_POINT_CLOUD_POINTS, finite_values, summary_stats
from .errors import DependencyMissingError, TerrainError


def _read_csv_points(path: Path, max_points: int) -> np.ndarray:
    """Read up to ``max_points`` x,y,z rows from a CSV file (header optional)."""
    with path.open("r", encoding="utf-8", newline="") as handle:
        sample = handle.read(4096)
        handle.seek(0)
        has_header = csv.Sniffer().has_header(sample)
        if has_header:
            reader = csv.DictReader(handle)
            rows = []
            for index, row in enumerate(reader):
                if index >= max_points:
                    break
                rows.append((float(row["x"]), float(row["y"]), float(row["z"])))
            return np.asarray(rows, dtype=float)
        return np.loadtxt(handle, delimiter=",", dtype=float, max_rows=max_points)


def load_point_cloud(
    path: Path, *, max_points: int
) -> tuple[np.ndarray, dict[str, Any]]:
    """Load up to ``max_points`` finite x,y,z points from ``path``.

    Supported base formats: CSV with ``x,y,z`` columns, ``.npy``, and ``.npz``
    (uses ``x``/``y``/``z`` arrays, else a ``points`` array, else the first
    array). LAS/LAZ requires the optional ``laspy`` dependency.

    Raises:
        DependencyMissingError: LAS/LAZ requested but ``laspy`` is unavailable.
        TerrainError: The data does not have at least three columns (x, y, z).
    """
    suffix = path.suffix.lower()
    metadata: dict[str, Any] = {"source_format": suffix.lstrip(".") or "unknown"}
    if suffix in {".las", ".laz"}:
        try:
            import laspy  # type: ignore[import-untyped,import-not-found]
        except ImportError as exc:
            raise DependencyMissingError(
                "laspy",
                "Install the 'laz' extra (pip install 'terrain-mcp[laz]') "
                "or provide CSV/NPY/NPZ x,y,z points.",
            ) from exc
        las = laspy.read(path)
        total = len(las.x)
        take = min(total, max_points)
        points = np.column_stack((las.x[:take], las.y[:take], las.z[:take])).astype(
            float
        )
        metadata.update(
            {"point_count_total": int(total), "point_count_sampled": int(take)}
        )
    elif suffix == ".npy":
        points = np.asarray(np.load(path), dtype=float)[:max_points]
    elif suffix == ".npz":
        payload = np.load(path)
        if {"x", "y", "z"}.issubset(payload.files):
            points = np.column_stack((payload["x"], payload["y"], payload["z"])).astype(
                float
            )
        else:
            key = "points" if "points" in payload else sorted(payload.files)[0]
            points = np.asarray(payload[key], dtype=float)
            metadata["array_key"] = key
        points = points[:max_points]
    else:
        points = _read_csv_points(path, max_points)
    if points.ndim != 2 or points.shape[1] < 3:
        raise TerrainError("Point cloud must have at least three columns: x, y, z.")
    points = np.asarray(points[:, :3], dtype=float)
    finite = np.isfinite(points).all(axis=1)
    return points[finite], metadata


def grid_points(
    points: np.ndarray, grid_cell_size: float
) -> tuple[np.ndarray, dict[str, Any]]:
    """Bin x,y,z points onto a regular grid, averaging z per cell.

    Returns the DEM-like grid (NaN where empty) and grid metadata (bounds,
    shape, filled/empty cell counts).

    Raises:
        TerrainError: There are no finite points, or the grid exceeds the
            cell-count safety limit.
    """
    if points.size == 0:
        raise TerrainError("Point cloud has no finite x,y,z points.")
    x = points[:, 0]
    y = points[:, 1]
    z = points[:, 2]
    min_x, max_x = float(np.min(x)), float(np.max(x))
    min_y, max_y = float(np.min(y)), float(np.max(y))
    width = int(math.floor((max_x - min_x) / grid_cell_size)) + 1
    height = int(math.floor((max_y - min_y) / grid_cell_size)) + 1
    if width * height > MAX_DEM_CELLS:
        raise TerrainError(
            f"Requested grid has {width * height} cells, "
            f"above the {MAX_DEM_CELLS} cell safety limit."
        )
    xi = np.floor((x - min_x) / grid_cell_size).astype(int)
    yi = np.floor((y - min_y) / grid_cell_size).astype(int)
    sums = np.zeros((height, width), dtype=float)
    counts = np.zeros((height, width), dtype=int)
    np.add.at(sums, (yi, xi), z)
    np.add.at(counts, (yi, xi), 1)
    dem = np.full((height, width), np.nan, dtype=float)
    valid = counts > 0
    dem[valid] = sums[valid] / counts[valid]
    return dem, {
        "bounds": {"min_x": min_x, "min_y": min_y, "max_x": max_x, "max_y": max_y},
        "grid_shape": [height, width],
        "filled_cell_count": int(valid.sum()),
        "empty_cell_count": int((~valid).sum()),
    }


def read_point_cloud(
    filepath: str,
    *,
    grid_cell_size: float = 1.0,
    max_points: int = 100_000,
    output_dem_path: str | None = None,
) -> dict[str, Any]:
    """Read an x/y/z point cloud and grid it into a DEM-like surface.

    If ``output_dem_path`` is provided, the gridded surface is written as a CSV
    DEM (NaN for empty cells) suitable for downstream DEM terrain analysis.

    Raises:
        DependencyMissingError: LAS/LAZ requested but ``laspy`` is unavailable.
        TerrainError: ``grid_cell_size`` is non-positive or the input is invalid.
    """
    if grid_cell_size <= 0:
        raise TerrainError("grid_cell_size must be positive.")
    max_points = max(1, min(int(max_points or 100_000), MAX_POINT_CLOUD_POINTS))
    path = Path(filepath)
    if not path.is_file():
        raise TerrainError(f"Point-cloud file not found: {filepath}")

    points, metadata = load_point_cloud(path, max_points=max_points)
    dem, grid = grid_points(points, grid_cell_size)
    output_path = None
    if output_dem_path:
        out = Path(output_dem_path)
        out.parent.mkdir(parents=True, exist_ok=True)
        np.savetxt(out, dem, delimiter=",", fmt="%.8g")
        output_path = str(out)
    return {
        "ok": True,
        "filepath": str(path),
        "point_count": int(points.shape[0]),
        "grid_cell_size": float(grid_cell_size),
        "metadata": metadata,
        "bounds": grid["bounds"],
        "grid_shape": grid["grid_shape"],
        "filled_cell_count": grid["filled_cell_count"],
        "empty_cell_count": grid["empty_cell_count"],
        "output_dem_path": output_path,
        "x": summary_stats(points[:, 0]),
        "y": summary_stats(points[:, 1]),
        "z": summary_stats(points[:, 2]),
        "gridded_elevation": summary_stats(finite_values(dem)),
    }
