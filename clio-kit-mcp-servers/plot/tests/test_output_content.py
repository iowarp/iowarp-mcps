"""Verify plot tools declare real MCP output semantics (2026-07-28 protocol).

Every image-producing plot tool must return a proper MCP ``ImageContent``
block (base64 PNG) alongside its structured dict, and every plot tool's
registration must advertise a real ``outputSchema`` — not just the generic
``{"type": "object"}`` a bare ``-> dict`` annotation would produce.

These tests drive the server through an in-memory ``fastmcp.Client``, so they
exercise exactly what a real MCP client sees on the wire.
"""

import base64
import os
import tempfile

import pandas as pd
import pytest
from fastmcp import Client

from plot_mcp.server import mcp

IMAGE_TOOL_NAMES = {
    "line_plot",
    "bar_plot",
    "scatter_plot",
    "histogram_plot",
    "heatmap_plot",
    "plot_timeseries",
}

# Every plot tool -- including data_info, which has no image -- must declare
# a real, field-level output schema (not a bare {"type": "object"}).
ALL_TOOL_NAMES = IMAGE_TOOL_NAMES | {"data_info"}


@pytest.fixture
def sample_csv_file():
    """A small CSV with numeric and categorical columns for every plot kind."""
    data = pd.DataFrame(
        {
            "x": [1, 2, 3, 4, 5],
            "y": [2, 4, 6, 8, 10],
            "category": ["A", "B", "A", "B", "A"],
            "value": [10, 20, 15, 25, 30],
        }
    )
    with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False) as f:
        data.to_csv(f.name, index=False)
        yield f.name
    os.unlink(f.name)


@pytest.mark.asyncio
async def test_tools_list_advertises_real_output_schemas() -> None:
    """tools/list must show a field-level outputSchema for every plot tool."""
    async with Client(mcp) as client:
        tools = {tool.name: tool for tool in await client.list_tools()}

    missing = ALL_TOOL_NAMES - set(tools)
    assert not missing, f"tools missing from tools/list: {missing}"

    for name in ALL_TOOL_NAMES:
        schema = tools[name].output_schema
        assert schema is not None, f"{name} has no outputSchema"
        assert schema.get("type") == "object", f"{name} outputSchema is not an object"
        properties = schema.get("properties")
        assert properties, f"{name} outputSchema has no real field properties: {schema}"
        # "status" is common to every structured plot/data result.
        assert "status" in properties, f"{name} outputSchema missing 'status' field"


@pytest.mark.asyncio
async def test_line_plot_returns_image_content_and_structured_dict(
    sample_csv_file,
) -> None:
    """A plot tool call returns both an image/png content block and intact
    structuredContent (with output_path still pointing at the full-res file)."""
    with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as f:
        output_path = f.name

    async with Client(mcp) as client:
        result = await client.call_tool_mcp(
            "line_plot",
            {
                "file_path": sample_csv_file,
                "x_column": "x",
                "y_column": "y",
                "title": "Content Test",
                "output_path": output_path,
            },
        )

    try:
        assert not result.is_error

        image_blocks = [c for c in result.content if c.type == "image"]
        assert image_blocks, "expected an ImageContent block in the response"
        image = image_blocks[0]
        assert image.mime_type == "image/png"
        # The data must be valid, non-trivial base64-encoded PNG bytes.
        decoded = base64.b64decode(image.data)
        assert decoded.startswith(b"\x89PNG\r\n\x1a\n")
        assert len(decoded) > 0

        structured = result.structured_content
        assert structured is not None
        assert structured["status"] == "success"
        assert structured["plot_type"] == "line"
        assert structured["output_path"] == output_path
        assert structured["data_points"] == 5

        # The full-resolution file on disk is untouched and independent
        # of the (possibly downscaled) embedded preview.
        assert os.path.exists(output_path)
        with open(output_path, "rb") as full_res:
            full_res_bytes = full_res.read()
        assert len(full_res_bytes) > 0
    finally:
        os.unlink(output_path)


@pytest.mark.asyncio
async def test_preview_is_bounded_even_when_full_res_is_large(
    sample_csv_file,
) -> None:
    """The embedded preview must stay small regardless of the on-disk size."""
    with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as f:
        output_path = f.name

    async with Client(mcp) as client:
        result = await client.call_tool_mcp(
            "heatmap_plot",
            {
                "file_path": sample_csv_file,
                "title": "Bounded Preview Test",
                "output_path": output_path,
            },
        )

    try:
        image = next(c for c in result.content if c.type == "image")
        decoded = base64.b64decode(image.data)

        from PIL import Image as PILImage
        import io

        with PILImage.open(io.BytesIO(decoded)) as preview:
            assert preview.width <= 800

        # A downscaled, optimized PNG preview of a simple chart should
        # comfortably stay well under a megabyte on the wire.
        assert len(decoded) < 1_000_000
    finally:
        os.unlink(output_path)


@pytest.mark.asyncio
async def test_data_info_has_no_image_but_has_structured_content(
    sample_csv_file,
) -> None:
    """data_info produces no plot, so it carries no image content block, but
    it still returns intact structured content matching its output schema."""
    async with Client(mcp) as client:
        result = await client.call_tool_mcp("data_info", {"file_path": sample_csv_file})

    assert not result.is_error
    image_blocks = [c for c in result.content if c.type == "image"]
    assert not image_blocks, "data_info should not carry an image content block"

    structured = result.structured_content
    assert structured is not None
    assert structured["status"] == "success"
    assert structured["columns"] == ["x", "y", "category", "value"]
