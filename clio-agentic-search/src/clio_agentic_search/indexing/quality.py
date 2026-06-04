"""Data quality layer: QC flags, quality scoring, and validity checks.

This module implements the third search target from the research program:
filtering and ranking retrieval results by the *quality* of the underlying
measurements, alongside unit conversion (Cap. 1) and metadata adaptivity
(Cap. 2).

Quality is captured as a :class:`QualityFlag` attached to each
:class:`Measurement`. Flags follow widely-used conventions from NOAA GHCN,
CIMIS, CF-conventions, and similar scientific data catalogs:

    GOOD            — passed all validity checks (default)
    QUESTIONABLE    — out of expected range but not impossible
    BAD             — failed validation / flagged erroneous
    MISSING         — value was absent or sentinel
    ESTIMATED       — imputed / interpolated, not directly measured
    UNKNOWN         — quality information unavailable

The module is deliberately self-contained: it does not import any retrieval
or storage code. Downstream modules (storage, coordinator, connectors)
attach to this module by calling :func:`parse_qc_token` or by constructing
:class:`QualityFlag` directly from whatever native representation the
source data uses.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class QualityFlag(StrEnum):
    """Normalized data-quality flag values.

    Stored as short lowercase strings so they serialise cleanly through
    DuckDB columns and the ``encode_measurements``/``decode_measurements``
    pipe format. The string form is the authoritative representation;
    downstream code uses ``QualityFlag(raw_string)`` to parse.
    """

    GOOD = "good"
    QUESTIONABLE = "questionable"
    BAD = "bad"
    MISSING = "missing"
    ESTIMATED = "estimated"
    UNKNOWN = "unknown"

    @classmethod
    def from_string(cls, value: str | None) -> QualityFlag:
        if not value:
            return cls.UNKNOWN
        try:
            return cls(value.strip().lower())
        except ValueError:
            return cls.UNKNOWN

    @property
    def is_acceptable(self) -> bool:
        """Whether the flag is considered acceptable under default filtering.

        Default filtering accepts GOOD and ESTIMATED (interpolated values are
        usable for most scientific questions) and rejects the rest.
        """
        return self in _ACCEPTABLE_FLAGS

    @property
    def numeric_score(self) -> float:
        """Map the flag to a 0.0–1.0 confidence score.

        Used by the retrieval layer to rank matching measurements so that
        higher-quality rows surface first.
        """
        return _FLAG_SCORES[self]


_ACCEPTABLE_FLAGS: frozenset[QualityFlag] = frozenset(
    {QualityFlag.GOOD, QualityFlag.ESTIMATED},
)

_FLAG_SCORES: dict[QualityFlag, float] = {
    QualityFlag.GOOD: 1.0,
    QualityFlag.ESTIMATED: 0.75,
    QualityFlag.UNKNOWN: 0.5,
    QualityFlag.QUESTIONABLE: 0.25,
    QualityFlag.BAD: 0.0,
    QualityFlag.MISSING: 0.0,
}


# ---------------------------------------------------------------------------
# QC token parsing
# ---------------------------------------------------------------------------
#
# Scientific CSVs and metadata typically report quality as a single-letter
# flag adjacent to the measurement value. The exact vocabulary varies by
# source, so we normalise the common conventions into QualityFlag.

# Mapping from raw lowercase tokens to normalised flags. We support the
# overlapping conventions from:
#   * NOAA GHCN-Daily       (M=missing, empty=good, various QFLAG letters)
#   * CIMIS                  (Y=questionable, R=rejected, M=missing, blank=good)
#   * NetCDF/CF ancillary   ("flag_meanings" strings)
#   * Ad-hoc human flags    (good/bad/ok/fail)
_TOKEN_MAP: dict[str, QualityFlag] = {
    # Explicit good
    "": QualityFlag.GOOD,
    "ok": QualityFlag.GOOD,
    "good": QualityFlag.GOOD,
    "g": QualityFlag.GOOD,
    "0": QualityFlag.GOOD,
    "valid": QualityFlag.GOOD,
    "pass": QualityFlag.GOOD,
    # Questionable
    "q": QualityFlag.QUESTIONABLE,
    "y": QualityFlag.QUESTIONABLE,  # CIMIS "questionable"
    "s": QualityFlag.QUESTIONABLE,  # CIMIS "suspect"
    "?": QualityFlag.QUESTIONABLE,
    "questionable": QualityFlag.QUESTIONABLE,
    "suspect": QualityFlag.QUESTIONABLE,
    "warn": QualityFlag.QUESTIONABLE,
    # Bad
    "b": QualityFlag.BAD,
    "r": QualityFlag.BAD,  # CIMIS "rejected"
    "n": QualityFlag.BAD,  # "no" / "not valid"
    "bad": QualityFlag.BAD,
    "fail": QualityFlag.BAD,
    "rejected": QualityFlag.BAD,
    "invalid": QualityFlag.BAD,
    # Missing
    "m": QualityFlag.MISSING,
    "missing": QualityFlag.MISSING,
    "na": QualityFlag.MISSING,
    "n/a": QualityFlag.MISSING,
    "null": QualityFlag.MISSING,
    "nan": QualityFlag.MISSING,
    "-9999": QualityFlag.MISSING,
    # Estimated / interpolated
    "e": QualityFlag.ESTIMATED,
    "i": QualityFlag.ESTIMATED,
    "estimated": QualityFlag.ESTIMATED,
    "interpolated": QualityFlag.ESTIMATED,
}


def parse_qc_token(token: str | None) -> QualityFlag:
    """Parse a single QC/quality token into a normalised :class:`QualityFlag`.

    Args:
        token: The raw token from a data source. May be ``None``, empty,
            whitespace, or a single-letter flag like ``"M"`` or ``"Y"``,
            or a word like ``"good"`` / ``"bad"``.

    Returns:
        The normalised flag. Unknown / unrecognised tokens become
        :attr:`QualityFlag.UNKNOWN` rather than raising, so downstream
        code can always classify a measurement.
    """
    if token is None:
        return QualityFlag.UNKNOWN
    stripped = token.strip().lower()
    return _TOKEN_MAP.get(stripped, QualityFlag.UNKNOWN)


# ---------------------------------------------------------------------------
# Quality summary — aggregated view over many measurements
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class QualitySummary:
    """Aggregate quality statistics over a collection of measurements.

    Used by corpus profiling and retrieval ranking to report "how clean is
    this corpus". All counts are absolute; ``acceptable_ratio`` and
    ``average_score`` are derived for convenience.
    """

    total: int
    good: int
    questionable: int
    bad: int
    missing: int
    estimated: int
    unknown: int

    @property
    def acceptable_count(self) -> int:
        return self.good + self.estimated

    @property
    def acceptable_ratio(self) -> float:
        if self.total == 0:
            return 0.0
        return self.acceptable_count / self.total

    @property
    def average_score(self) -> float:
        """Mean numeric quality score across all flags."""
        if self.total == 0:
            return 0.0
        weighted = (
            self.good * _FLAG_SCORES[QualityFlag.GOOD]
            + self.estimated * _FLAG_SCORES[QualityFlag.ESTIMATED]
            + self.unknown * _FLAG_SCORES[QualityFlag.UNKNOWN]
            + self.questionable * _FLAG_SCORES[QualityFlag.QUESTIONABLE]
            + self.bad * _FLAG_SCORES[QualityFlag.BAD]
            + self.missing * _FLAG_SCORES[QualityFlag.MISSING]
        )
        return weighted / self.total


def summarise_quality(flags: list[QualityFlag]) -> QualitySummary:
    """Aggregate a list of flags into a :class:`QualitySummary`."""
    counts = {flag: 0 for flag in QualityFlag}
    for flag in flags:
        counts[flag] += 1
    return QualitySummary(
        total=len(flags),
        good=counts[QualityFlag.GOOD],
        questionable=counts[QualityFlag.QUESTIONABLE],
        bad=counts[QualityFlag.BAD],
        missing=counts[QualityFlag.MISSING],
        estimated=counts[QualityFlag.ESTIMATED],
        unknown=counts[QualityFlag.UNKNOWN],
    )


# ---------------------------------------------------------------------------
# Range validators — physical-plausibility checks
# ---------------------------------------------------------------------------
#
# Even when a source marks a value "good", it can still be outside the
# physically plausible range (a 500°C air-temperature reading from a weather
# station, for example). These validators apply on the *canonical* (SI) value
# so a single table covers all units in a dimension.

# Keyed by canonical dim-key. Values are (min, max) in SI base units.
_PHYSICAL_RANGES: dict[str, tuple[float, float]] = {
    # Temperature (K). Allow deep-cryo lab data to 50 K; reject near absolute
    # zero or anything above typical plasma physics at ~3000 K for weather/
    # chemistry use cases. Users with extreme-science data can bypass via
    # accept_all=True.
    "0,0,0,0,1,0,0": (50.0, 3000.0),
    # Pressure (Pa). Near-vacuum ~1 Pa (lab) to 10^9 Pa (~10 GPa, high-pressure
    # diamond-anvil experiments).
    "1,-1,-2,0,0,0,0": (1.0, 1.0e9),
    # Velocity (m/s). -1 to +3e8 (speed of light). Negative rejected.
    "0,1,-1,0,0,0,0": (0.0, 3.0e8),
}


def is_physically_plausible(
    canonical_unit: str,
    canonical_value: float,
) -> bool:
    """Check if a canonical (SI) value falls within a sanity range.

    If the dimension isn't in the table, returns True (no constraint).
    """
    bounds = _PHYSICAL_RANGES.get(canonical_unit)
    if bounds is None:
        return True
    lo, hi = bounds
    return lo <= canonical_value <= hi


def derive_flag_from_value(
    canonical_unit: str,
    canonical_value: float,
    source_flag: QualityFlag = QualityFlag.UNKNOWN,
) -> QualityFlag:
    """Combine a source-provided flag with physical-plausibility check.

    If the source flag is BAD or MISSING we trust it and return as-is.
    Otherwise we additionally check plausibility: if the value is outside
    the physical range, downgrade to QUESTIONABLE.
    """
    if source_flag in (QualityFlag.BAD, QualityFlag.MISSING):
        return source_flag
    if not is_physically_plausible(canonical_unit, canonical_value):
        return QualityFlag.QUESTIONABLE
    return source_flag
