"""Tests for HDF5 connector."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

try:
    import h5py

    HAS_H5PY = True
except ImportError:
    h5py = None  # type: ignore[assignment]
    HAS_H5PY = False


# ---------------------------------------------------------------------------
# Fake h5py objects for mocking
# ---------------------------------------------------------------------------


class _FakeAttrs(dict):
    """Dict subclass that behaves like HDF5 attrs (truthy when non-empty)."""

    pass


class _FakeDataset:
    """Minimal stand-in for h5py.Dataset."""

    def __init__(
        self,
        shape: tuple[int, ...] = (100,),
        dtype: str = "float64",
        attrs: dict[str, object] | None = None,
    ) -> None:
        self.shape = shape
        self.dtype = dtype
        self.attrs = _FakeAttrs(attrs or {})


class _FakeGroup:
    """Minimal stand-in for h5py.Group."""

    def __init__(self, attrs: dict[str, object] | None = None) -> None:
        self.attrs = _FakeAttrs(attrs or {})


class _FakeFile:
    """Minimal stand-in for h5py.File, used as a context manager."""

    def __init__(
        self,
        items: dict[str, _FakeDataset | _FakeGroup],
        root_attrs: dict[str, object] | None = None,
    ) -> None:
        self._items = items
        self.attrs = _FakeAttrs(root_attrs or {})

    def visititems(self, func: object) -> None:
        for name, obj in sorted(self._items.items()):
            func(name, obj)  # type: ignore[operator]

    def __enter__(self) -> _FakeFile:
        return self

    def __exit__(self, *args: object) -> None:
        return None


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@pytest.mark.skipif(not HAS_H5PY, reason="h5py required for isinstance checks")
def test_extract_hdf5_text_basic_structure() -> None:
    """_extract_hdf5_text produces text from groups, datasets, and attributes."""
    from clio_agentic_search.connectors.hdf5.connector import _extract_hdf5_text

    fake_file = _FakeFile(
        items={
            "experiment/pressure": _FakeDataset(
                shape=(1000,),
                dtype="float32",
                attrs={"units": "kPa", "long_name": "Static Pressure"},
            ),
            "experiment": _FakeGroup(
                attrs={"description": "Wind tunnel run 42"},
            ),
        },
        root_attrs={"title": "CFD Benchmark"},
    )

    # Patch h5py.File to return our fake, and h5py.Dataset/Group for isinstance.
    with (
        patch("clio_agentic_search.connectors.hdf5.connector.h5py.File", return_value=fake_file),
        patch("clio_agentic_search.connectors.hdf5.connector.h5py.Dataset", _FakeDataset),
        patch("clio_agentic_search.connectors.hdf5.connector.h5py.Group", _FakeGroup),
    ):
        text = _extract_hdf5_text(Path("/fake/data.h5"))

    assert "Dataset: /experiment/pressure" in text
    assert "Shape: (1000,)" in text
    assert "float32" in text
    assert "units: kPa" in text
    assert "long_name: Static Pressure" in text
    assert "Group: /experiment" in text
    assert "description: Wind tunnel run 42" in text
    # Root attributes
    assert "title: CFD Benchmark" in text


@pytest.mark.skipif(not HAS_H5PY, reason="h5py required for isinstance checks")
def test_extract_hdf5_text_bytes_attrs_decoded() -> None:
    """Byte-string attributes should be decoded to UTF-8."""
    from clio_agentic_search.connectors.hdf5.connector import _extract_hdf5_text

    fake_file = _FakeFile(
        items={
            "data": _FakeDataset(attrs={"label": b"encoded-value"}),
        },
    )

    with (
        patch("clio_agentic_search.connectors.hdf5.connector.h5py.File", return_value=fake_file),
        patch("clio_agentic_search.connectors.hdf5.connector.h5py.Dataset", _FakeDataset),
        patch("clio_agentic_search.connectors.hdf5.connector.h5py.Group", _FakeGroup),
    ):
        text = _extract_hdf5_text(Path("/fake/data.h5"))

    assert "encoded-value" in text


def test_descriptor_returns_hdf5_type() -> None:
    """HDF5Connector.descriptor() should report connector_type='hdf5'."""
    from clio_agentic_search.connectors.hdf5.connector import HDF5Connector

    storage = MagicMock()
    connector = HDF5Connector(namespace="test-ns", root=Path("/data"), storage=storage)
    desc = connector.descriptor()

    assert desc.name == "test-ns"
    assert desc.connector_type == "hdf5"
    assert "/data" in desc.root_uri


@pytest.mark.skipif(not HAS_H5PY, reason="h5py required for isinstance checks")
def test_measurement_extracted_from_attribute_text() -> None:
    """Text with 'pressure_value: 250 kPa' should produce measurement metadata via chunking."""
    from clio_agentic_search.connectors.hdf5.connector import _extract_hdf5_text
    from clio_agentic_search.indexing.scientific import build_structure_aware_chunk_plan

    fake_file = _FakeFile(
        items={
            "sensors/pressure": _FakeDataset(
                shape=(500,),
                dtype="float64",
                attrs={"pressure_value": "250 kPa", "units": "kPa"},
            ),
        },
    )

    with (
        patch("clio_agentic_search.connectors.hdf5.connector.h5py.File", return_value=fake_file),
        patch("clio_agentic_search.connectors.hdf5.connector.h5py.Dataset", _FakeDataset),
        patch("clio_agentic_search.connectors.hdf5.connector.h5py.Group", _FakeGroup),
    ):
        text = _extract_hdf5_text(Path("/fake/data.h5"))

    # The extracted text should mention the measurement.
    assert "250" in text
    assert "kPa" in text or "kpa" in text.lower()

    # When we chunk this text through the scientific pipeline, we should get
    # measurement metadata.
    plan = build_structure_aware_chunk_plan(
        namespace="test",
        document_id="doc1",
        text=text,
        chunk_size=800,
    )
    assert plan.chunks

    # Check if any chunk picked up scientific measurement metadata.
    all_meta_keys: set[str] = set()
    for chunk_meta in plan.metadata_by_chunk_id.values():
        all_meta_keys.update(chunk_meta.keys())

    has_measurement = any("measurement" in k.lower() for k in all_meta_keys)
    assert has_measurement, f"Expected measurement metadata, got keys: {all_meta_keys}"
