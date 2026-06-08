"""Generic geospatial map rendering.

Renders one or more vector layers (polygons, lines, points) onto a single
matplotlib figure with an optional web-tile basemap, and writes a PNG. The
input layers are plain GeoJSON, so any tool that returns GeoJSON features
(catalog feature queries, file inspection, analysis output) can be visualized
without a format-specific plotter.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import geopandas as gpd
import matplotlib

matplotlib.use("Agg")
import contextily as cx  # noqa: E402
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.patches import Patch  # noqa: E402
from shapely.geometry import shape  # noqa: E402

WGS84 = 4326
WEB_MERCATOR = 3857

# EPA AQI category breakpoints -> color. Used when a layer requests
# ``"scale": "epa_aqi"`` for a numeric Air Quality Index field.
_EPA_AQI_BANDS: list[tuple[float, str, str]] = [
    (50, "#00e400", "Good (0-50)"),
    (100, "#ffff00", "Moderate (51-100)"),
    (150, "#ff7e00", "Unhealthy for Sensitive (101-150)"),
    (200, "#ff0000", "Unhealthy (151-200)"),
    (300, "#8f3f97", "Very Unhealthy (201-300)"),
    (float("inf"), "#7e0023", "Hazardous (301+)"),
]
_AQI_FALLBACK = "#999999"


class MapRenderError(ValueError):
    """Raised when layers cannot be rendered into a map."""


def _epa_aqi_color(value: Any) -> str:
    """Map a numeric AQI value to its EPA category color."""
    try:
        v = float(value)
    except (TypeError, ValueError):
        return _AQI_FALLBACK
    for upper, color, _label in _EPA_AQI_BANDS:
        if v <= upper:
            return color
    return _AQI_FALLBACK


def _coerce_feature_collection(geojson: Any) -> list[dict[str, Any]]:
    """Normalize assorted GeoJSON shapes into a list of Feature dicts.

    Accepts a FeatureCollection dict, a bare geometry dict, a single Feature, a
    list of Features/geometries, a JSON string of any of those, or a path to a
    ``.geojson`` file.
    """
    if isinstance(geojson, str):
        text = geojson.strip()
        if not text:
            raise MapRenderError("Layer geojson string is empty.")
        if text[0] not in "{[":
            path = Path(geojson).expanduser()
            if not path.is_file():
                raise MapRenderError(f"Layer geojson path not found: {geojson}")
            text = path.read_text(encoding="utf-8")
        try:
            geojson = json.loads(text)
        except json.JSONDecodeError as exc:
            raise MapRenderError(f"Layer geojson is not valid JSON: {exc}") from exc

    if isinstance(geojson, list):
        items = geojson
    elif isinstance(geojson, dict):
        gtype = geojson.get("type")
        if gtype == "FeatureCollection":
            items = geojson.get("features", []) or []
        elif gtype == "Feature":
            items = [geojson]
        elif gtype in {
            "Point",
            "MultiPoint",
            "LineString",
            "MultiLineString",
            "Polygon",
            "MultiPolygon",
            "GeometryCollection",
        }:
            items = [{"type": "Feature", "geometry": geojson, "properties": {}}]
        else:
            raise MapRenderError(f"Unsupported geojson object type: {gtype!r}")
    else:
        raise MapRenderError("Layer geojson must be a dict, list, JSON string, or path.")

    features: list[dict[str, Any]] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        if item.get("type") == "Feature":
            if item.get("geometry"):
                features.append(item)
        elif "geometry" in item:
            if item.get("geometry"):
                features.append(
                    {
                        "type": "Feature",
                        "geometry": item["geometry"],
                        "properties": item.get("properties", {}),
                    }
                )
        elif item.get("type") in {
            "Point",
            "Polygon",
            "LineString",
            "MultiPolygon",
            "MultiPoint",
            "MultiLineString",
        }:
            features.append({"type": "Feature", "geometry": item, "properties": {}})
    return features


def _layer_geodataframe(features: list[dict[str, Any]]) -> gpd.GeoDataFrame:
    """Build a WGS84 GeoDataFrame from GeoJSON Feature dicts."""
    geoms = []
    rows: list[dict[str, Any]] = []
    for feat in features:
        try:
            geom = shape(feat["geometry"])
        except (KeyError, TypeError, ValueError, AttributeError):
            continue
        if geom.is_empty:
            continue
        geoms.append(geom)
        props = feat.get("properties") or {}
        rows.append(props if isinstance(props, dict) else {})
    if not geoms:
        raise MapRenderError("Layer has no usable geometries.")
    return gpd.GeoDataFrame(rows, geometry=geoms, crs=WGS84)


def _legend_handles(legend_entries: list[tuple[str, str]]) -> list[Patch]:
    seen: set[tuple[str, str]] = set()
    handles: list[Patch] = []
    for color, label in legend_entries:
        key = (color, label)
        if key in seen or not label:
            continue
        seen.add(key)
        handles.append(Patch(facecolor=color, edgecolor="black", label=label))
    return handles


def render_map(
    layers: list[dict[str, Any]],
    output_path: str,
    *,
    title: str = "",
    basemap: bool = True,
    bbox: list[float] | None = None,
    figsize: tuple[float, float] = (12.0, 12.0),
    dpi: int = 130,
) -> dict[str, Any]:
    """Render vector ``layers`` to a PNG map and return a result summary.

    Each layer is a dict with:
      - ``geojson``: FeatureCollection / Feature / geometry / list / JSON / path.
      - ``name`` (optional): label used in logging and the legend.
      - ``style`` (optional): dict with any of ``facecolor``, ``edgecolor``,
        ``alpha``, ``linewidth``, ``color``, ``markersize``, ``zorder``,
        ``color_by`` (property name), ``scale`` (``"epa_aqi"`` or a matplotlib
        colormap name), ``category_colors`` (value->color), and ``legend``
        (bool, default True).

    Args:
        layers: Ordered layers; later layers draw on top.
        output_path: Destination PNG path.
        title: Figure title.
        basemap: Add a CartoDB Positron web-tile basemap (needs network).
        bbox: Optional ``[min_lon, min_lat, max_lon, max_lat]`` view window.
        figsize: Figure size in inches.
        dpi: Output resolution.

    Returns:
        Dict with ``status``, ``output_path``, ``bounds`` (WGS84), ``layers``
        (per-layer feature counts), and ``basemap`` (whether tiles were added).

    Raises:
        MapRenderError: If no layers are usable or rendering fails.
    """
    if not layers:
        raise MapRenderError("At least one layer is required.")

    out = Path(output_path).expanduser()
    out.parent.mkdir(parents=True, exist_ok=True)
    target_crs = WEB_MERCATOR if basemap else WGS84

    fig, ax = plt.subplots(figsize=figsize)
    legend_entries: list[tuple[str, str]] = []
    layer_summaries: list[dict[str, Any]] = []
    all_bounds: list[tuple[float, float, float, float]] = []

    for index, layer in enumerate(layers):
        if not isinstance(layer, dict):
            raise MapRenderError(f"Layer {index} is not an object.")
        name = str(layer.get("name") or f"layer_{index}")
        style = layer.get("style") or {}
        features = _coerce_feature_collection(layer.get("geojson"))
        if not features:
            layer_summaries.append({"name": name, "features": 0, "skipped": "no features"})
            continue
        gdf = _layer_geodataframe(features)
        all_bounds.append(tuple(gdf.total_bounds))  # type: ignore[arg-type]
        draw = gdf.to_crs(target_crs)

        geom_types = set(draw.geom_type.str.replace("Multi", "", regex=False))
        is_point = geom_types <= {"Point"}
        zorder = int(style.get("zorder", 5 + index))
        alpha = float(style.get("alpha", 0.6))
        color_by = style.get("color_by")
        want_legend = style.get("legend", True)

        if color_by and color_by in draw.columns:
            scale = str(style.get("scale", "")).lower()
            category_colors = style.get("category_colors")
            if isinstance(category_colors, dict):
                colors = [category_colors.get(str(v), _AQI_FALLBACK) for v in draw[color_by]]
                if want_legend:
                    legend_entries.extend((c, f"{name}: {k}") for k, c in category_colors.items())
                _plot_colored(ax, draw, colors, is_point, style, alpha, zorder)
            elif scale == "epa_aqi":
                colors = [_epa_aqi_color(v) for v in draw[color_by]]
                if want_legend:
                    legend_entries.extend((c, lbl) for _u, c, lbl in _EPA_AQI_BANDS)
                _plot_colored(ax, draw, colors, is_point, style, alpha, zorder)
            else:
                cmap = scale or "viridis"
                draw.plot(
                    ax=ax,
                    column=color_by,
                    cmap=cmap,
                    alpha=alpha,
                    zorder=zorder,
                    markersize=float(style.get("markersize", 40)) if is_point else None,
                    legend=bool(want_legend),
                )
        else:
            color = style.get("color") or style.get("facecolor") or _default_color(index)
            if is_point:
                draw.plot(
                    ax=ax,
                    color=color,
                    edgecolor=style.get("edgecolor", "black"),
                    markersize=float(style.get("markersize", 45)),
                    alpha=alpha,
                    zorder=zorder,
                )
            else:
                draw.plot(
                    ax=ax,
                    facecolor=color,
                    edgecolor=style.get("edgecolor", color),
                    linewidth=float(style.get("linewidth", 1.0)),
                    alpha=alpha,
                    zorder=zorder,
                )
            if want_legend:
                legend_entries.append((color, name))

        layer_summaries.append(
            {"name": name, "features": int(len(draw)), "geometry": sorted(geom_types)}
        )

    if not all_bounds:
        plt.close(fig)
        raise MapRenderError("No layer produced renderable geometry.")

    if bbox:
        _apply_bbox(ax, bbox, target_crs)

    if basemap:
        try:
            cx.add_basemap(ax, source=cx.providers.CartoDB.Positron, attribution_size=6)
            basemap_added = True
        except Exception as exc:  # noqa: BLE001 - network/tile failures must not abort the render
            basemap_added = False
            ax.set_facecolor("#f5f5f5")
            print(f"[geo] basemap unavailable, rendering without tiles: {exc}")
    else:
        basemap_added = False

    ax.set_axis_off()
    if title:
        ax.set_title(title, fontsize=12)
    handles = _legend_handles(legend_entries)
    if handles:
        ax.legend(handles=handles, loc="lower left", fontsize=8, framealpha=0.9)

    fig.savefig(out, dpi=dpi, bbox_inches="tight")
    plt.close(fig)

    if not out.is_file() or out.stat().st_size == 0:
        raise MapRenderError("Render produced no output file.")

    merged = _merge_bounds(all_bounds)
    return {
        "status": "success",
        "output_path": str(out),
        "size_bytes": out.stat().st_size,
        "bounds": {
            "min_lon": merged[0],
            "min_lat": merged[1],
            "max_lon": merged[2],
            "max_lat": merged[3],
        },
        "basemap": basemap_added,
        "layers": layer_summaries,
    }


_PALETTE = ["#1f77b4", "#ff7f0e", "#2ca02c", "#d62728", "#9467bd", "#8c564b"]


def _default_color(index: int) -> str:
    return _PALETTE[index % len(_PALETTE)]


def _plot_colored(
    ax: Any,
    draw: gpd.GeoDataFrame,
    colors: list[str],
    is_point: bool,
    style: dict[str, Any],
    alpha: float,
    zorder: int,
) -> None:
    if is_point:
        draw.plot(
            ax=ax,
            color=colors,
            edgecolor=style.get("edgecolor", "black"),
            markersize=float(style.get("markersize", 45)),
            alpha=alpha,
            zorder=zorder,
        )
    else:
        draw.plot(
            ax=ax,
            color=colors,
            edgecolor=style.get("edgecolor", "none"),
            linewidth=float(style.get("linewidth", 0.0)),
            alpha=alpha,
            zorder=zorder,
        )


def _apply_bbox(ax: Any, bbox: list[float], crs: int) -> None:
    if len(bbox) != 4:
        raise MapRenderError("bbox must be [min_lon, min_lat, max_lon, max_lat].")
    minx, miny, maxx, maxy = (float(v) for v in bbox)
    pts = gpd.GeoSeries(gpd.points_from_xy([minx, maxx], [miny, maxy]), crs=WGS84).to_crs(crs)
    ax.set_xlim(pts.x.min(), pts.x.max())
    ax.set_ylim(pts.y.min(), pts.y.max())


def _merge_bounds(
    bounds: list[tuple[float, float, float, float]],
) -> tuple[float, float, float, float]:
    minx = min(b[0] for b in bounds)
    miny = min(b[1] for b in bounds)
    maxx = max(b[2] for b in bounds)
    maxy = max(b[3] for b in bounds)
    return (minx, miny, maxx, maxy)
