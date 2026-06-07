"""Three-panel earthquake-sequence figure renderer.

Draws (1) an epicenter map sized by magnitude and coloured by time, (2) the
Gutenberg-Richter magnitude-frequency distribution with an optional b-value fit
line, and (3) the cumulative count over time, from a saved catalog. Writes a PNG
and returns its path. Like the analysis code, this produces a *figure*, not a
verdict about what the sequence is.
"""

from __future__ import annotations

import math
from pathlib import Path
from typing import Any

import numpy as np

from .catalog_io import CatalogError, load_catalog, resolve_write_path


def plot_sequence(
    catalog_path: str,
    title: str | None = None,
    mc: float | None = None,
    b_value: float | None = None,
    output_path: str = "",
) -> dict[str, Any]:
    """Render the three-panel sequence figure from a saved catalog.

    Panels: (1) epicenter map sized by magnitude and coloured by time, (2)
    Gutenberg-Richter magnitude-frequency with the b-value fit line, (3)
    cumulative count and rate over time.

    Once the agent has classified the sequence, render this figure to make the
    behaviour legible - the spatial cluster, the magnitude distribution, and the
    decay (or lack of it). Pass the catalog path and, if available, ``mc`` /
    ``b_value`` so the G-R fit line is drawn.

    Args:
        catalog_path: Path to a saved GeoJSON or CSV earthquake catalog.
        title: Optional figure title.
        mc: Optional completeness magnitude for the G-R fit line.
        b_value: Optional Gutenberg-Richter b-value for the G-R fit line.
        output_path: Destination PNG path; a default under the current working
            directory is used when empty.

    Returns:
        A dict with the figure path, the event count, and the panel names.

    Raises:
        CatalogError: If the catalog is unreadable, empty, or rendering fails.
    """
    path, events = load_catalog(catalog_path)
    if not events:
        raise CatalogError(
            "No events to plot. An empty catalog is a background finding; "
            "skip the figure."
        )

    if not output_path:
        default_dir = Path.cwd() / "seismic-artifacts" / "charts"
        output_path = str(default_dir / f"earthquake_sequence_{path.stem}.png")
    out = resolve_write_path(output_path)

    try:
        import matplotlib

        matplotlib.use("Agg")
        import matplotlib.pyplot as plt  # noqa: PLC0415

        mags = np.array([e["mag"] for e in events])
        lons = np.array([e["lon"] for e in events], dtype=float)
        lats = np.array([e["lat"] for e in events], dtype=float)
        times = np.array([e["time_ms"] for e in events], dtype=float)
        t_days = (times - times.min()) / 86_400_000
        largest_i = int(np.argmax(mags))

        fig, axes = plt.subplots(1, 3, figsize=(18, 5.5))

        # Panel 1: epicenter map
        ax = axes[0]
        sizes = 8 * (10 ** (0.4 * (mags - mags.min())))
        sc = ax.scatter(
            lons,
            lats,
            s=sizes,
            c=t_days,
            cmap="viridis",
            alpha=0.75,
            edgecolor="k",
            linewidth=0.3,
        )
        ax.scatter(
            lons[largest_i],
            lats[largest_i],
            marker="*",
            s=600,
            facecolor="red",
            edgecolor="k",
            linewidth=0.8,
            label=f"largest M{mags[largest_i]:.1f}",
            zorder=5,
        )
        ax.set_xlabel("longitude")
        ax.set_ylabel("latitude")
        ax.set_title("epicenters (size~magnitude, colour~time)")
        ax.legend(loc="best", fontsize=8)
        ax.grid(True, alpha=0.3)
        fig.colorbar(sc, ax=ax, label="days from first event", fraction=0.046, pad=0.04)

        # Panel 2: Gutenberg-Richter magnitude-frequency
        ax = axes[1]
        edges = np.arange(math.floor(mags.min() * 10) / 10, mags.max() + 0.1, 0.1)
        cum = [np.sum(mags >= e) for e in edges]
        ax.semilogy(edges, cum, "o", ms=4, color="navy", label="cumulative N(>=M)")
        if mc is not None and b_value is not None:
            n_mc = float(np.sum(mags >= mc - 0.05))
            a = math.log10(n_mc) + b_value * mc
            line_m = np.array([mc, mags.max()])
            ax.semilogy(
                line_m,
                10 ** (a - b_value * line_m),
                "r--",
                label=f"b={b_value:.2f} fit",
            )
            ax.axvline(mc, color="gray", ls=":", alpha=0.7, label=f"Mc={mc}")
        ax.set_xlabel("magnitude")
        ax.set_ylabel("count >= M")
        ax.set_title("Gutenberg-Richter")
        ax.legend(fontsize=8)
        ax.grid(True, which="both", alpha=0.3)

        # Panel 3: cumulative count + rate over time
        ax = axes[2]
        order = np.argsort(t_days)
        ax.plot(
            t_days[order],
            np.arange(1, len(t_days) + 1),
            "-",
            color="darkgreen",
            label="cumulative count",
        )
        ax.axvline(
            t_days[largest_i],
            color="red",
            ls="--",
            alpha=0.8,
            label=f"largest M{mags[largest_i]:.1f}",
        )
        ax.set_xlabel("days from first event")
        ax.set_ylabel("cumulative events")
        ax.set_title("temporal evolution")
        ax.legend(fontsize=8)
        ax.grid(True, alpha=0.3)

        fig.suptitle(title or "Earthquake sequence", fontsize=14, y=1.02)
        fig.tight_layout()
        fig.savefig(out, dpi=140, bbox_inches="tight")
        plt.close(fig)
    except CatalogError:
        raise
    except Exception as exc:  # noqa: BLE001 - surface render failures uniformly
        raise CatalogError(
            f"Could not render figure: {exc}. Check the catalog has valid coordinates."
        ) from exc

    return {
        "ok": True,
        "figure_path": str(out),
        "event_count": len(events),
        "panels": ["epicenter_map", "gutenberg_richter", "temporal_evolution"],
    }
