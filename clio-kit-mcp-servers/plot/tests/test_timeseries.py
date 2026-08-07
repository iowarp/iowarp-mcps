"""Tests for the generic time-series line-plot capability and MCP tool.

All tests are self-contained: they build temporary CSV/Excel files on disk and
render PNGs into temporary paths. No network access is required (the plot server
operates entirely on local files), so no network mocking is needed; file I/O is
isolated to temp files that are cleaned up after each test.
"""

import os
import tempfile

import pandas as pd
import pytest
from fastmcp.exceptions import ToolError
from fastmcp.tools import ToolResult

from plot_mcp import server
from plot_mcp.implementation.plot_capabilities import (
    _infer_x_axis,
    _parse_datetime_text,
    _to_float,
    create_timeseries_plot,
)


@pytest.fixture
def datetime_csv():
    """CSV with an ISO date column and two numeric series."""
    data = pd.DataFrame(
        {
            "timestamp": [
                "2024-01-01",
                "2024-01-02",
                "2024-01-03",
                "2024-01-04",
                "2024-01-05",
            ],
            "temperature": [10.0, 11.5, 9.8, 12.1, 13.0],
            "pressure": [101.0, 100.5, 102.3, 99.8, 101.2],
        }
    )
    with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False) as f:
        data.to_csv(f.name, index=False)
        yield f.name
    os.unlink(f.name)


@pytest.fixture
def epoch_ms_csv():
    """CSV whose x column holds epoch-millisecond integers."""
    base_ms = 1_704_067_200_000  # 2024-01-01T00:00:00Z in ms
    data = pd.DataFrame(
        {
            "ts": [base_ms + i * 86_400_000 for i in range(5)],
            "signal": [1.0, 2.0, 3.0, 4.0, 5.0],
        }
    )
    with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False) as f:
        data.to_csv(f.name, index=False)
        yield f.name
    os.unlink(f.name)


@pytest.fixture
def categorical_csv():
    """CSV whose x column is non-temporal text (categorical fallback)."""
    data = pd.DataFrame(
        {
            "label": ["alpha", "beta", "gamma", "delta", "epsilon"],
            "count": [3, 7, 2, 9, 5],
        }
    )
    with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False) as f:
        data.to_csv(f.name, index=False)
        yield f.name
    os.unlink(f.name)


# --------------------------------------------------------------------------- #
# Helper-level unit tests
# --------------------------------------------------------------------------- #


def test_to_float_handles_blanks_and_text():
    assert _to_float("3.5") == 3.5
    assert _to_float("  -2 ") == -2.0
    assert _to_float("") is None
    assert _to_float("abc") is None
    assert _to_float("NaN") is None
    assert _to_float(None) is None


def test_parse_datetime_text_variants():
    assert _parse_datetime_text("2024-01-01") is not None
    assert _parse_datetime_text("2024-01-01T12:00:00Z") is not None
    assert _parse_datetime_text("01/02/2024") is not None
    assert _parse_datetime_text("") is None
    assert _parse_datetime_text("not-a-date") is None


def test_infer_x_axis_datetime():
    axis = _infer_x_axis(["2024-01-01", "2024-01-02", "2024-01-03"])
    assert axis["kind"] == "datetime"
    assert axis["parse_success_ratio"] == 1.0


def test_infer_x_axis_epoch_milliseconds():
    axis = _infer_x_axis(["1704067200000", "1704153600000", "1704240000000"])
    assert axis["kind"] == "epoch_milliseconds"


def test_infer_x_axis_epoch_seconds():
    axis = _infer_x_axis(["1704067200", "1704153600", "1704240000"])
    assert axis["kind"] == "epoch_seconds"


def test_infer_x_axis_numeric():
    axis = _infer_x_axis(["1", "2", "3", "4"])
    assert axis["kind"] == "numeric"
    assert axis["values"] == [1.0, 2.0, 3.0, 4.0]


def test_infer_x_axis_categorical():
    axis = _infer_x_axis(["a", "b", "c"])
    assert axis["kind"] == "categorical"
    assert axis["values"] == [0, 1, 2]
    assert axis["labels"] == ["a", "b", "c"]


def test_infer_x_axis_empty():
    axis = _infer_x_axis([])
    assert axis["kind"] == "row_index"
    assert axis["values"] == []


# --------------------------------------------------------------------------- #
# create_timeseries_plot tests
# --------------------------------------------------------------------------- #


def test_create_timeseries_datetime_single_series(datetime_csv):
    with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as f:
        result = create_timeseries_plot(
            datetime_csv, "timestamp", "temperature", "Temp over time", f.name
        )
        assert result["status"] == "success"
        assert result["plot_type"] == "timeseries"
        assert result["x_axis"]["kind"] == "datetime"
        assert result["y_columns"] == ["temperature"]
        assert result["data_points"] == 5
        assert os.path.exists(f.name)
        assert os.path.getsize(f.name) > 0
    os.unlink(f.name)


def test_create_timeseries_multiple_series_list(datetime_csv):
    with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as f:
        result = create_timeseries_plot(
            datetime_csv,
            "timestamp",
            ["temperature", "pressure"],
            None,
            f.name,
        )
        assert result["status"] == "success"
        assert result["y_columns"] == ["pressure", "temperature"]
        assert os.path.exists(f.name)
    os.unlink(f.name)


def test_create_timeseries_multiple_series_comma_string(datetime_csv):
    with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as f:
        result = create_timeseries_plot(
            datetime_csv,
            "timestamp",
            "temperature, pressure",
            None,
            f.name,
        )
        assert result["status"] == "success"
        assert result["y_columns"] == ["pressure", "temperature"]
    os.unlink(f.name)


def test_create_timeseries_epoch_ms(epoch_ms_csv):
    with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as f:
        result = create_timeseries_plot(epoch_ms_csv, "ts", "signal", None, f.name)
        assert result["status"] == "success"
        assert result["x_axis"]["kind"] == "epoch_milliseconds"
        assert os.path.exists(f.name)
    os.unlink(f.name)


def test_create_timeseries_categorical(categorical_csv):
    with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as f:
        result = create_timeseries_plot(categorical_csv, "label", "count", None, f.name)
        assert result["status"] == "success"
        assert result["x_axis"]["kind"] == "categorical"
        assert os.path.exists(f.name)
    os.unlink(f.name)


def test_create_timeseries_default_title_is_filename(datetime_csv):
    with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as f:
        result = create_timeseries_plot(
            datetime_csv, "timestamp", "temperature", None, f.name
        )
        assert result["title"] == os.path.basename(datetime_csv)
    os.unlink(f.name)


def test_create_timeseries_max_rows_limits_points(datetime_csv):
    with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as f:
        result = create_timeseries_plot(
            datetime_csv, "timestamp", "temperature", None, f.name, max_rows=3
        )
        assert result["status"] == "success"
        assert result["data_points"] == 3
    os.unlink(f.name)


def test_create_timeseries_missing_column(datetime_csv):
    result = create_timeseries_plot(
        datetime_csv, "timestamp", "does_not_exist", None, "out.png"
    )
    assert result["status"] == "error"
    assert "not found in data" in result["error"]


def test_create_timeseries_missing_x_column(datetime_csv):
    result = create_timeseries_plot(
        datetime_csv, "nope", "temperature", None, "out.png"
    )
    assert result["status"] == "error"
    assert "not found in data" in result["error"]


def test_create_timeseries_empty_y_columns(datetime_csv):
    result = create_timeseries_plot(datetime_csv, "timestamp", "", None, "out.png")
    assert result["status"] == "error"
    assert "at least one y column" in result["error"].lower()


def test_create_timeseries_non_numeric_y(categorical_csv):
    # 'label' is textual; using it as y yields no numeric values.
    result = create_timeseries_plot(categorical_csv, "count", "label", None, "out.png")
    assert result["status"] == "error"
    assert "numeric" in result["error"].lower()


def test_create_timeseries_file_not_found():
    result = create_timeseries_plot("/nonexistent/file.csv", "x", "y", None, "out.png")
    assert result["status"] == "error"
    assert "error" in result


def test_create_timeseries_excel_input():
    data = pd.DataFrame(
        {
            "day": ["2024-03-01", "2024-03-02", "2024-03-03"],
            "metric": [1.0, 2.0, 1.5],
        }
    )
    with tempfile.NamedTemporaryFile(suffix=".xlsx", delete=False) as src:
        data.to_excel(src.name, index=False)
        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as out:
            result = create_timeseries_plot(src.name, "day", "metric", None, out.name)
            assert result["status"] == "success"
            assert os.path.exists(out.name)
        os.unlink(out.name)
    os.unlink(src.name)


# --------------------------------------------------------------------------- #
# MCP tool wrapper tests
# --------------------------------------------------------------------------- #


@pytest.mark.asyncio
async def test_plot_timeseries_tool_success(datetime_csv):
    with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as f:
        result = await server.plot_timeseries(
            data_path=datetime_csv,
            x_column="timestamp",
            y_columns=["temperature", "pressure"],
            output_path=f.name,
            title="MCP Timeseries",
        )
        assert isinstance(result, ToolResult)
        structured = result.structured_content
        assert structured is not None
        assert structured["status"] == "success"
        assert structured["y_columns"] == ["pressure", "temperature"]
        image_blocks = [c for c in result.content if c.type == "image"]
        assert image_blocks, "expected an image content block"
        assert image_blocks[0].mime_type == "image/png"
        assert os.path.exists(f.name)
    os.unlink(f.name)


@pytest.mark.asyncio
async def test_plot_timeseries_tool_comma_string(datetime_csv):
    with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as f:
        result = await server.plot_timeseries(
            data_path=datetime_csv,
            x_column="timestamp",
            y_columns="temperature,pressure",
            output_path=f.name,
        )
        assert result.structured_content is not None
        assert result.structured_content["status"] == "success"
    os.unlink(f.name)


@pytest.mark.asyncio
async def test_plot_timeseries_tool_raises_on_missing_column(datetime_csv):
    with pytest.raises(ToolError):
        await server.plot_timeseries(
            data_path=datetime_csv,
            x_column="timestamp",
            y_columns="missing",
            output_path="out.png",
        )


@pytest.mark.asyncio
async def test_plot_timeseries_tool_raises_on_missing_file():
    with pytest.raises(ToolError):
        await server.plot_timeseries(
            data_path="/nonexistent/file.csv",
            x_column="x",
            y_columns="y",
            output_path="out.png",
        )


def test_plot_timeseries_tool_registered():
    assert hasattr(server, "plot_timeseries")
    assert callable(server.plot_timeseries)
    assert hasattr(server, "create_timeseries_plot")
