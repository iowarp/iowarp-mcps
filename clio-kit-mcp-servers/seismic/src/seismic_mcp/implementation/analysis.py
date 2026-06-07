"""Earthquake-sequence descriptive statistics.

Computes the standard numbers a seismologist reads off a catalog - completeness
magnitude (Mc), the Gutenberg-Richter b-value, the Bath-law magnitude gap, and
Omori-style post-mainshock rate decay - from a saved catalog.

Design rule (do not break): these functions produce *data*. They compute the
statistics; they do NOT decide whether the activity is an aftershock sequence, a
swarm, or background, and they do NOT declare which event is "the mainshock".
That classification is the agent's judgment, made by reasoning over the
statistics returned here.
"""

from __future__ import annotations

import math
from typing import Any

import numpy as np

from .catalog_io import load_catalog

_DEFAULT_MAG_BIN = 0.1


def _magnitude_of_completeness(
    mags: list[float], dm: float = _DEFAULT_MAG_BIN
) -> float | None:
    """Maximum-curvature Mc: most-populated magnitude bin, nudged up by 0.2."""
    if len(mags) < 5:
        return None
    counts: dict[float, int] = {}
    for m in mags:
        b = round(round(m / dm) * dm, 1)
        counts[b] = counts.get(b, 0) + 1
    mode_bin = max(counts, key=lambda k: counts[k])
    return round(mode_bin + 0.2, 1)


def _b_value(
    mags: list[float], mc: float, dm: float = _DEFAULT_MAG_BIN
) -> dict[str, Any]:
    """Aki (1965) MLE b-value with Shi & Bolt (1982) uncertainty."""
    sample = [m for m in mags if m >= mc - dm / 2]
    n = len(sample)
    if n < 10:
        return {
            "b_value": None,
            "b_uncertainty": None,
            "n_above_mc": n,
            "a_value": None,
        }
    mean_m = sum(sample) / n
    denom = mean_m - (mc - dm / 2)
    if denom <= 0:
        return {
            "b_value": None,
            "b_uncertainty": None,
            "n_above_mc": n,
            "a_value": None,
        }
    b = math.log10(math.e) / denom
    var = sum((m - mean_m) ** 2 for m in sample) / (n * (n - 1))
    sigma = 2.30 * b**2 * math.sqrt(var)
    a = math.log10(n) + b * mc
    return {
        "b_value": round(b, 3),
        "b_uncertainty": round(sigma, 3),
        "n_above_mc": n,
        "a_value": round(a, 3),
    }


def _omori_decay(events: list[dict[str, Any]], t0_ms: int) -> dict[str, Any]:
    """Event-rate decay after the largest event. Returns rate buckets + a fitted
    Omori-Utsu p exponent (modified Omori, c fixed small) when fittable. Data only."""
    day_ms = 86_400_000
    after = [e for e in events if e["time_ms"] >= t0_ms]
    buckets = [(0, 1), (1, 2), (2, 4), (4, 8), (8, 16), (16, 32)]
    rate_per_day: list[dict[str, Any]] = []
    for lo, hi in buckets:
        c = sum(1 for e in after if lo * day_ms <= e["time_ms"] - t0_ms < hi * day_ms)
        rate_per_day.append(
            {
                "day_start": lo,
                "day_end": hi,
                "count": c,
                "rate_per_day": round(c / (hi - lo), 3),
            }
        )
    # Crude p-fit: log(rate) vs log(t_mid) least squares over non-empty buckets.
    pts = [
        (math.log((b["day_start"] + b["day_end"]) / 2), math.log(b["rate_per_day"]))
        for b in rate_per_day
        if b["rate_per_day"] > 0
    ]
    p = None
    if len(pts) >= 3:
        xs = np.array([x for x, _ in pts])
        ys = np.array([y for _, y in pts])
        slope = float(np.polyfit(xs, ys, 1)[0])
        p = round(-slope, 3)  # rate ~ t^-p
    first = rate_per_day[0]["rate_per_day"]
    last = next(
        (b["rate_per_day"] for b in reversed(rate_per_day) if b["rate_per_day"] > 0),
        0.0,
    )
    return {
        "rate_buckets": rate_per_day,
        "omori_p_estimate": p,
        "first_window_rate_per_day": first,
        "decay_ratio_first_to_last": round(first / last, 2) if last > 0 else None,
    }


def _haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    r = 6371.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlmb = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dlmb / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


def analyze_sequence(
    catalog_path: str, mag_bin: float = _DEFAULT_MAG_BIN
) -> dict[str, Any]:
    """Compute the descriptive statistics of a saved earthquake catalog so the
    agent can classify the sequence.

    After staging a catalog, call this to get the numbers a seismologist reads -
    completeness magnitude (Mc), the Gutenberg-Richter b-value (with
    uncertainty), the largest event and its depth/time, the magnitude gap to the
    second-largest (Bath's law), the share of events before vs after the largest,
    and the post-event rate decay (Omori). It returns statistics ONLY; it does
    not label the sequence. The agent decides, from these numbers, whether this
    is a mainshock-aftershock sequence (one dominant event, large Bath gap, most
    activity after it, a decaying Omori rate, b near 1), an earthquake swarm
    (co-equal magnitudes, small/zero Bath gap, flat rate, often b>1), or
    background (too few events, no clustering).

    Args:
        catalog_path: Path to a saved GeoJSON or CSV earthquake catalog.
        mag_bin: Magnitude bin width for Mc and the b-value MLE (default 0.1).

    Returns:
        A dict with ``ok``, ``event_count``, ``catalog_path``, and (when the
        catalog is non-empty) a ``statistics`` block.

    Raises:
        CatalogError: If the catalog cannot be read or parsed.
    """
    path, events = load_catalog(catalog_path)

    n = len(events)
    result: dict[str, Any] = {"ok": True, "event_count": n, "catalog_path": str(path)}
    if n == 0:
        result["finding_inputs"] = {
            "note": "Empty catalog - no sequence to characterize (background/quiet)."
        }
        return result

    mags = [e["mag"] for e in events]
    largest = max(events, key=lambda e: e["mag"])
    others = sorted((e["mag"] for e in events if e is not largest), reverse=True)
    second = others[0] if others else None
    before = [e for e in events if e["time_ms"] < largest["time_ms"]]
    after = [e for e in events if e["time_ms"] >= largest["time_ms"]]

    mc = _magnitude_of_completeness(mags, mag_bin)
    bstats = (
        _b_value(mags, mc, mag_bin)
        if mc is not None
        else {
            "b_value": None,
            "b_uncertainty": None,
            "n_above_mc": None,
            "a_value": None,
        }
    )

    # Spatial extent (max pairwise distance is O(n^2); sample-cap for safety).
    locs = [
        (e["lat"], e["lon"])
        for e in events
        if e["lat"] is not None and e["lon"] is not None
    ]
    extent_km = None
    if len(locs) >= 2:
        sample = locs[:: max(1, len(locs) // 200)]
        extent_km = (
            round(
                max(
                    _haversine_km(a[0], a[1], b[0], b[1])
                    for i, a in enumerate(sample)
                    for b in sample[i + 1 :]
                ),
                1,
            )
            if len(sample) >= 2
            else None
        )

    decay = _omori_decay(events, largest["time_ms"])

    result["statistics"] = {
        "completeness_mc": mc,
        **bstats,
        "largest_event": {
            "magnitude": largest["mag"],
            "depth_km": largest["depth_km"],
            "time_ms": largest["time_ms"],
            "place": largest["place"],
            "lat": largest["lat"],
            "lon": largest["lon"],
        },
        "second_largest_magnitude": second,
        "bath_gap": round(largest["mag"] - second, 2) if second is not None else None,
        "events_before_largest": len(before),
        "events_after_largest": len(after),
        "fraction_after_largest": round(len(after) / n, 3),
        "spatial_extent_km": extent_km,
        "magnitude_min": round(min(mags), 2),
        "magnitude_max": round(max(mags), 2),
        "temporal_decay": decay,
    }
    return result
