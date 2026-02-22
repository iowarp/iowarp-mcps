"""Scientific query operators and metadata scoring."""

from __future__ import annotations

from dataclasses import dataclass

from clio_agentic_search.indexing.scientific import (
    Measurement,
    canonicalize_measurement,
    decode_measurements,
    measurements_close,
    normalize_formula,
)


@dataclass(frozen=True, slots=True)
class NumericRangeOperator:
    unit: str
    minimum: float | None = None
    maximum: float | None = None


@dataclass(frozen=True, slots=True)
class UnitMatchOperator:
    unit: str
    value: float | None = None
    tolerance: float = 1e-9


@dataclass(frozen=True, slots=True)
class ScientificQueryOperators:
    numeric_range: NumericRangeOperator | None = None
    unit_match: UnitMatchOperator | None = None
    formula: str | None = None

    def is_active(self) -> bool:
        return self.numeric_range is not None or self.unit_match is not None or bool(self.formula)


def score_scientific_metadata(
    metadata: dict[str, str],
    operators: ScientificQueryOperators,
) -> float:
    if not operators.is_active():
        return 0.0

    measurements = decode_measurements(metadata.get("scientific.measurements", ""))
    formulas = _decode_formulas(metadata.get("scientific.formulas", ""))

    score = 0.0
    if operators.numeric_range is not None:
        if not _matches_numeric_range(measurements, operators.numeric_range):
            return 0.0
        score += 1.2

    if operators.unit_match is not None:
        if not _matches_unit(measurements, operators.unit_match):
            return 0.0
        score += 1.0

    if operators.formula:
        if not _matches_formula(formulas, operators.formula):
            return 0.0
        score += 1.4

    return score


def _matches_numeric_range(
    measurements: list[Measurement],
    operator: NumericRangeOperator,
) -> bool:
    minimum = operator.minimum
    maximum = operator.maximum

    try:
        if minimum is not None:
            minimum, minimum_unit = canonicalize_measurement(minimum, operator.unit)
        else:
            minimum_unit = canonicalize_measurement(0.0, operator.unit)[1]

        if maximum is not None:
            maximum, maximum_unit = canonicalize_measurement(maximum, operator.unit)
        else:
            maximum_unit = minimum_unit
    except ValueError:
        return False

    if minimum_unit != maximum_unit:
        return False

    for measurement in measurements:
        if measurement.canonical_unit != minimum_unit:
            continue
        if minimum is not None and measurement.canonical_value < minimum:
            continue
        if maximum is not None and measurement.canonical_value > maximum:
            continue
        return True
    return False


def _matches_unit(
    measurements: list[Measurement],
    operator: UnitMatchOperator,
) -> bool:
    try:
        if operator.value is None:
            target_value = None
            target_unit = canonicalize_measurement(0.0, operator.unit)[1]
        else:
            target_value, target_unit = canonicalize_measurement(operator.value, operator.unit)
    except ValueError:
        return False

    for measurement in measurements:
        if measurement.canonical_unit != target_unit:
            continue
        if target_value is None:
            return True
        if measurements_close(
            measurement.canonical_value,
            target_value,
            tolerance=operator.tolerance,
        ):
            return True
    return False


def _matches_formula(formulas: list[str], formula_query: str) -> bool:
    normalized_query = normalize_formula(formula_query)
    if not normalized_query:
        return False
    return normalized_query in formulas


def _decode_formulas(value: str) -> list[str]:
    if not value:
        return []
    return [item for item in value.split(";") if item]
