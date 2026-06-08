"""Digital Elevation Model (DEM) loading and terrain analysis.

Loads a 2-D elevation grid from CSV / NPY / NPZ (always available) or GeoTIFF
(requires the optional ``rasterio`` extra), then derives slope, aspect, and a
site-suitability mask from elevation and slope criteria.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import numpy as np

from ._common import MAX_DEM_CELLS, finite_values, summary_stats
from .errors import DependencyMissingError, TerrainError


def load_dem(path: Path, *, nodata: float | None) -> tuple[np.ndarray, dict[str, Any]]:
    """Load a 2-D DEM grid from ``path``.

    Supported base formats: CSV numeric grid, ``.npy``, and ``.npz`` (uses a
    ``dem`` array if present, else the first array). GeoTIFF (``.tif``/``.tiff``)
    requires the optional ``rasterio`` dependency.

    Raises:
        DependencyMissingError: GeoTIFF requested but ``rasterio`` is unavailable.
        TerrainError: The grid is not 2-D or exceeds the cell-count safety limit.
    """
    suffix = path.suffix.lower()
    metadata: dict[str, Any] = {"source_format": suffix.lstrip(".") or "unknown"}
    if suffix in {".tif", ".tiff"}:
        try:
            import rasterio  # type: ignore[import-untyped,import-not-found]
        except ImportError as exc:
            raise DependencyMissingError(
                "rasterio",
                "Install the 'geotiff' extra (pip install 'terrain-mcp[geotiff]') "
                "or provide a CSV/NPY/NPZ DEM grid.",
            ) from exc
        with rasterio.open(path) as dataset:
            dem = dataset.read(1).astype(float)
            metadata.update(
                {
                    "crs": str(dataset.crs) if dataset.crs else None,
                    "bounds": list(dataset.bounds),
                    "transform": tuple(dataset.transform),
                    "nodata": dataset.nodata,
                }
            )
            if nodata is None and dataset.nodata is not None:
                nodata = float(dataset.nodata)
    elif suffix == ".npy":
        dem = np.load(path).astype(float)
    elif suffix == ".npz":
        payload = np.load(path)
        key = "dem" if "dem" in payload else sorted(payload.files)[0]
        dem = np.asarray(payload[key], dtype=float)
        metadata["array_key"] = key
    else:
        dem = np.loadtxt(path, delimiter=",", dtype=float)

    if dem.ndim != 2:
        raise TerrainError(
            f"DEM must be a two-dimensional grid, got shape {tuple(dem.shape)}."
        )
    if dem.size > MAX_DEM_CELLS:
        raise TerrainError(
            f"DEM has {dem.size} cells, above the {MAX_DEM_CELLS} cell safety limit."
        )
    if nodata is not None:
        dem = dem.astype(float, copy=True)
        dem[np.isclose(dem, float(nodata), equal_nan=False)] = np.nan
        metadata["nodata"] = float(nodata)
    return dem, metadata


def slope_degrees(dem: np.ndarray, cell_size: float) -> np.ndarray:
    """Compute per-cell slope in degrees from elevation using a gradient."""
    filled = np.array(dem, dtype=float, copy=True)
    if not np.isfinite(filled).all():
        finite = finite_values(filled)
        fill_value = float(np.median(finite)) if finite.size else 0.0
        filled[~np.isfinite(filled)] = fill_value
    gy, gx = np.gradient(filled, float(cell_size), float(cell_size))
    return np.degrees(np.arctan(np.hypot(gx, gy)))


def aspect_degrees(dem: np.ndarray, cell_size: float) -> np.ndarray:
    """Compute per-cell aspect (downslope compass direction) in degrees [0, 360)."""
    filled = np.array(dem, dtype=float, copy=True)
    finite = finite_values(filled)
    filled[~np.isfinite(filled)] = float(np.median(finite)) if finite.size else 0.0
    gy, gx = np.gradient(filled, float(cell_size), float(cell_size))
    aspect = np.degrees(np.arctan2(-gx, gy))
    return (aspect + 360.0) % 360.0


def suitability_mask(
    dem: np.ndarray,
    slope: np.ndarray,
    *,
    elevation_min: float | None,
    elevation_max: float | None,
    slope_max_degrees: float | None,
) -> np.ndarray:
    """Boolean mask of cells meeting the given elevation/slope criteria."""
    mask = np.isfinite(dem) & np.isfinite(slope)
    if elevation_min is not None:
        mask &= dem >= float(elevation_min)
    if elevation_max is not None:
        mask &= dem <= float(elevation_max)
    if slope_max_degrees is not None:
        mask &= slope <= float(slope_max_degrees)
    return mask


def analyze_dem(
    filepath: str,
    *,
    cell_size: float = 1.0,
    elevation_min: float | None = None,
    elevation_max: float | None = None,
    slope_max_degrees: float | None = None,
    nodata: float | None = None,
) -> dict[str, Any]:
    """Analyze a DEM grid for elevation, slope, aspect, and site suitability.

    Returns a structured result with grid shape, summary statistics for
    elevation/slope/aspect, suitability counts, and up to ten representative
    suitable cells.

    Raises:
        DependencyMissingError: GeoTIFF requested but ``rasterio`` is unavailable.
        TerrainError: ``cell_size`` is non-positive or the grid is invalid.
    """
    if cell_size <= 0:
        raise TerrainError("cell_size must be positive.")
    path = Path(filepath)
    if not path.is_file():
        raise TerrainError(f"DEM file not found: {filepath}")

    dem, metadata = load_dem(path, nodata=nodata)
    slope = slope_degrees(dem, cell_size)
    aspect = aspect_degrees(dem, cell_size)
    mask = suitability_mask(
        dem,
        slope,
        elevation_min=elevation_min,
        elevation_max=elevation_max,
        slope_max_degrees=slope_max_degrees,
    )
    valid_cell_count = int(np.isfinite(dem).sum())
    suitable_cell_count = int(mask.sum())
    suitable_fraction = (
        suitable_cell_count / valid_cell_count if valid_cell_count else 0.0
    )
    rows, cols = np.where(mask)
    examples = [
        {
            "row": int(row),
            "col": int(col),
            "elevation": float(dem[row, col]),
            "slope_degrees": float(slope[row, col]),
            "aspect_degrees": float(aspect[row, col]),
        }
        for row, col in list(zip(rows, cols, strict=False))[:10]
    ]
    return {
        "ok": True,
        "filepath": str(path),
        "shape": [int(dem.shape[0]), int(dem.shape[1])],
        "cell_size": float(cell_size),
        "metadata": metadata,
        "criteria": {
            "elevation_min": elevation_min,
            "elevation_max": elevation_max,
            "slope_max_degrees": slope_max_degrees,
        },
        "valid_cell_count": valid_cell_count,
        "nodata_cell_count": int(dem.size - valid_cell_count),
        "suitable_cell_count": suitable_cell_count,
        "suitable_fraction": suitable_fraction,
        "elevation": summary_stats(finite_values(dem)),
        "slope_degrees": summary_stats(finite_values(slope)),
        "aspect_degrees": summary_stats(finite_values(aspect)),
        "representative_suitable_cells": examples,
    }
