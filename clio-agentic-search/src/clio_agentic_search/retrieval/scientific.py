"""Scientific query operators and metadata scoring."""

from __future__ import annotations

from dataclasses import dataclass

from clio_agentic_search.indexing.quality import QualityFlag
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
class QualityFilterOperator:
    """Filter measurements by data-quality flags.

    ``acceptable`` is the whitelist of :class:`QualityFlag` values that
    should match. The default accepts GOOD and ESTIMATED only. Set
    ``minimum_score`` to a value in [0, 1] to additionally require each
    measurement's numeric quality score (see
    :attr:`QualityFlag.numeric_score`) to exceed that threshold.
    """

    acceptable: tuple[QualityFlag, ...] = (
        QualityFlag.GOOD,
        QualityFlag.ESTIMATED,
    )
    minimum_score: float = 0.0

    def accepts(self, flag_string: str | QualityFlag) -> bool:
        flag = (
            flag_string
            if isinstance(flag_string, QualityFlag)
            else QualityFlag.from_string(flag_string)
        )
        if flag not in self.acceptable:
            return False
        if flag.numeric_score < self.minimum_score:
            return False
        return True

    def acceptable_strings(self) -> tuple[str, ...]:
        """Return the whitelist as raw strings (for SQL parameter binding)."""
        return tuple(flag.value for flag in self.acceptable)


@dataclass(frozen=True, slots=True)
class ScientificQueryOperators:
    numeric_range: NumericRangeOperator | None = None
    unit_match: UnitMatchOperator | None = None
    formula: str | None = None
    quality_filter: QualityFilterOperator | None = None

    def is_active(self) -> bool:
        return (
            self.numeric_range is not None
            or self.unit_match is not None
            or bool(self.formula)
            or self.quality_filter is not None
        )


def score_scientific_metadata(
    metadata: dict[str, str],
    operators: ScientificQueryOperators,
) -> float:
    """Score a chunk's scientific metadata against a set of query operators.

    Returns ``0.0`` if any operator's hard constraint fails, otherwise a
    sum of weighted contributions. The :class:`QualityFilterOperator` (if
    present) is applied as a pre-filter to the measurement list — bad or
    missing measurements are dropped before the other operators see them.
    Additionally, the *mean* quality score of remaining measurements is
    folded into the returned score as a soft boost, so chunks with
    better-quality data rank higher.
    """
    if not operators.is_active():
        return 0.0

    measurements = decode_measurements(metadata.get("scientific.measurements", ""))
    formulas = _decode_formulas(metadata.get("scientific.formulas", ""))

    # Quality pre-filter: drop unacceptable measurements entirely so the
    # downstream range/unit operators only ever see clean rows.
    if operators.quality_filter is not None:
        measurements = [m for m in measurements if operators.quality_filter.accepts(m.quality)]
        if not measurements and (
            operators.numeric_range is not None or operators.unit_match is not None
        ):
            # Quality filter removed everything this chunk could match on.
            return 0.0

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

    # Quality boost: if the quality operator is active and there are
    # surviving measurements, reward chunks whose average measurement
    # quality is higher. Max boost = 0.3 for all-GOOD rows.
    if operators.quality_filter is not None and measurements:
        avg_quality = sum(
            QualityFlag.from_string(m.quality).numeric_score for m in measurements
        ) / len(measurements)
        score += 0.3 * avg_quality

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
