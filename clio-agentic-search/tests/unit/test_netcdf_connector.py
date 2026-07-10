"""Tests for NetCDF connector."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import pytest

# ---------------------------------------------------------------------------
# Helpers: lightweight fake xarray objects
# ---------------------------------------------------------------------------


class _FakeVariable:
    """Minimal stand-in for an xarray DataArray (variable)."""

    def __init__(
        self,
        dims: tuple[str, ...] = ("time",),
        shape: tuple[int, ...] = (100,),
        dtype: str = "float64",
        attrs: dict[str, object] | None = None,
        values: object = None,
    ) -> None:
        self.dims = dims
        self.shape = shape
        self.dtype = dtype
        self.attrs = attrs or {}
        self.values = values if values is not None else []
        self.size = shape[0] if shape else 0


class _FakeDataset:
    """Minimal stand-in for an xarray Dataset."""

    def __init__(
        self,
        data_vars: dict[str, _FakeVariable] | None = None,
        coords: dict[str, _FakeVariable] | None = None,
        dims: dict[str, int] | None = None,
        attrs: dict[str, object] | None = None,
    ) -> None:
        self.data_vars = data_vars or {}
        self.coords = coords or {}
        self.dims = dims or {}
        self.attrs = attrs or {}

    def close(self) -> None:
        pass


# ---------------------------------------------------------------------------
# Tests for _dataset_to_text (no xarray import needed)
# ---------------------------------------------------------------------------


def test_dataset_to_text_basic() -> None:
    """_dataset_to_text should render variables, coords, dims, and global attrs."""
    from clio_agentic_search.connectors.netcdf.connector import _dataset_to_text

    ds = _FakeDataset(
        data_vars={
            "temperature": _FakeVariable(
                dims=("time", "lat", "lon"),
                shape=(365, 180, 360),
                dtype="float32",
                attrs={
                    "units": "K",
                    "long_name": "Air Temperature",
                    "standard_name": "air_temperature",
                },
            ),
        },
        coords={
            "time": _FakeVariable(dims=("time",), shape=(365,), dtype="datetime64[ns]"),
            "lat": _FakeVariable(dims=("lat",), shape=(180,), dtype="float64"),
        },
        dims={"time": 365, "lat": 180, "lon": 360},
        attrs={"title": "ERA5 Reanalysis", "Conventions": "CF-1.8"},
    )

    text = _dataset_to_text(ds, "era5.nc")

    assert "NetCDF Dataset: era5.nc" in text
    assert "Variable: temperature" in text
    assert "Units: K" in text
    assert "Long Name: Air Temperature" in text
    assert "Standard Name: air_temperature" in text
    assert "Dimensions:" in text
    assert "time: 365" in text


def test_dataset_to_text_global_attrs() -> None:
    """Standard global attributes should appear in output."""
    from clio_agentic_search.connectors.netcdf.connector import _dataset_to_text

    ds = _FakeDataset(
        attrs={
            "title": "Climate Model Output",
            "institution": "NCAR",
            "source": "CESM2",
            "history": "created 2025-01-01",
        },
    )

    text = _dataset_to_text(ds, "model.nc")

    assert "Title: Climate Model Output" in text
    assert "Institution: NCAR" in text
    assert "Source: CESM2" in text
    assert "History: created 2025-01-01" in text


def test_dataset_to_text_cf_attributes() -> None:
    """CF metadata attributes like cell_methods should be rendered."""
    from clio_agentic_search.connectors.netcdf.connector import _dataset_to_text

    ds = _FakeDataset(
        data_vars={
            "precip": _FakeVariable(
                attrs={
                    "units": "mm/day",
                    "cell_methods": "time: mean",
                },
            ),
        },
    )

    text = _dataset_to_text(ds, "precip.nc")

    assert "Units: mm/day" in text
    assert "cell_methods: time: mean" in text


# ---------------------------------------------------------------------------
# Descriptor
# ---------------------------------------------------------------------------


def test_descriptor_returns_netcdf_type() -> None:
    """NetCDFConnector.descriptor() should report connector_type='netcdf'."""
    from clio_agentic_search.connectors.netcdf.connector import NetCDFConnector

    storage = MagicMock()
    connector = NetCDFConnector(namespace="climate", root=Path("/data"), storage=storage)
    desc = connector.descriptor()

    assert desc.name == "climate"
    assert desc.connector_type == "netcdf"
    assert "/data" in desc.root_uri


# ---------------------------------------------------------------------------
# Measurement extraction through the scientific chunk pipeline
# ---------------------------------------------------------------------------


def test_measurement_extracted_from_netcdf_text() -> None:
    """Text describing a variable with '250 kPa' should yield measurement metadata."""
    from clio_agentic_search.connectors.netcdf.connector import _dataset_to_text
    from clio_agentic_search.indexing.scientific import build_structure_aware_chunk_plan

    ds = _FakeDataset(
        data_vars={
            "pressure": _FakeVariable(
                dims=("time", "level"),
                shape=(100, 37),
                dtype="float32",
                attrs={"units": "kPa", "long_name": "Atmospheric Pressure"},
            ),
        },
        attrs={"title": "Pressure at 250 kPa level"},
    )

    text = _dataset_to_text(ds, "pressure.nc")
    assert "250" in text
    assert "kPa" in text or "kpa" in text.lower()

    plan = build_structure_aware_chunk_plan(
        namespace="test",
        document_id="doc1",
        text=text,
        chunk_size=800,
    )
    assert plan.chunks

    all_meta_keys: set[str] = set()
    for chunk_meta in plan.metadata_by_chunk_id.values():
        all_meta_keys.update(chunk_meta.keys())

    has_measurement = any("measurement" in k.lower() for k in all_meta_keys)
    assert has_measurement, f"Expected measurement metadata, got keys: {all_meta_keys}"


# ---------------------------------------------------------------------------
# connect() guard
# ---------------------------------------------------------------------------


def test_connect_without_xarray_uses_storage(monkeypatch: pytest.MonkeyPatch) -> None:
    """NetCDFConnector.connect() should call storage.connect() and succeed
    even if xarray is absent (xarray is only needed at index time, not connect)."""
    from clio_agentic_search.connectors.netcdf import connector as nc_mod

    storage = MagicMock()
    conn = nc_mod.NetCDFConnector(
        namespace="ns",
        root=Path("/tmp"),
        storage=storage,
        warmup_async=False,
    )
    # connect should call through to storage
    conn.connect()
    storage.connect.assert_called_once()
    conn.teardown()
    storage.teardown.assert_called_once()
