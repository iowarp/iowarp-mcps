"""Scientific retrieval evaluation metrics."""

from __future__ import annotations

from clio_agentic_search.indexing.scientific import Measurement, measurements_close


def precision_at_k(retrieved: list[str], relevant: set[str], k: int) -> float:
    if k <= 0:
        return 0.0
    top_items = retrieved[:k]
    if not top_items:
        return 0.0
    hits = sum(1 for item in top_items if item in relevant)
    return hits / len(top_items)


def numeric_exactness(
    measurements: list[Measurement],
    expected: list[tuple[float, str]],
    *,
    tolerance: float = 1e-9,
) -> float:
    if not expected:
        return 1.0

    matched = 0
    remaining = list(measurements)
    for expected_value, expected_unit in expected:
        index = _find_measurement(remaining, expected_value, expected_unit, tolerance=tolerance)
        if index is None:
            continue
        matched += 1
        del remaining[index]

    return matched / len(expected)


def unit_consistency(measurements: list[Measurement]) -> float:
    if not measurements:
        return 1.0
    consistent = sum(1 for measurement in measurements if bool(measurement.canonical_unit))
    return consistent / len(measurements)


def _find_measurement(
    measurements: list[Measurement],
    expected_value: float,
    expected_unit: str,
    *,
    tolerance: float,
) -> int | None:
    for index, measurement in enumerate(measurements):
        if measurement.canonical_unit != expected_unit:
            continue
        if measurements_close(measurement.canonical_value, expected_value, tolerance=tolerance):
            return index
    return None
