"""Science-aware CSV parser with unit inference and QC flag extraction.

This module provides a single entry point, :func:`parse_scientific_csv`,
used by connectors that ingest tabular scientific data (CIMIS, NOAA GHCN,
DOE data portal CSVs, and similar). It is deliberately self-contained and
connector-agnostic — connectors wrap it, pass a URL or text, and receive
structured :class:`ParsedCsv` objects that plug straight into CLIO's
measurement + metadata pipeline.

What it does:

1. Parses the CSV header and detects columns that look like measurements
   via unit patterns in the header (``"Air Temp (C)"``, ``"Wind Speed
   (m/s)"``, ``"Pressure [kPa]"``).
2. Detects adjacent quality-control columns using the convention
   ``measurement_col, qc`` (CIMIS), ``column_Q`` (NOAA), or ``<col>_qflag``
   (CF conventions).
3. For each matched measurement column, parses each row, canonicalises to
   SI base units, and attaches the parsed quality flag.
4. Returns the rows as :class:`Measurement` objects alongside a
   :class:`CsvSchema` describing the detected columns.

The module does **not** touch DuckDB or any connector — it's pure Python
so it's trivially testable and reusable.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

from clio_agentic_search.indexing.quality import (
    QualityFlag,
    derive_flag_from_value,
    parse_qc_token,
)
from clio_agentic_search.indexing.scientific import Measurement, canonicalize_measurement
from clio_agentic_search.retrieval.metadata_schema import align_field

# ---------------------------------------------------------------------------
# Header parsing: find columns that contain measurements
# ---------------------------------------------------------------------------

# Regex: capture a unit suffix in parentheses or square brackets at the end
# of a header name. Examples:
#   "Air Temp (C)"          -> unit="C"
#   "Wind Speed (m/s)"      -> unit="m/s"
#   "Pressure [kPa]"        -> unit="kPa"
#   "Rel Hum (%)"           -> unit="%"
_UNIT_SUFFIX_RE = re.compile(
    r"""
    .*?                       # column label (non-greedy)
    [\(\[]                    # opening bracket
    ([^)\]]+)                 # unit content (no brackets inside)
    [\)\]]                    # closing bracket
    \s*$                      # end of string
    """,
    re.VERBOSE,
)

# Common single-letter → canonical unit aliases used in CSV headers.
# (Full dimensional analysis happens downstream via canonicalize_measurement.)
_HEADER_UNIT_ALIASES: dict[str, str] = {
    "C": "degC",
    "°C": "degC",
    "degC": "degC",
    "F": "degF",
    "°F": "degF",
    "degF": "degF",
    "K": "kelvin",
    "%": "percent",  # sentinel — %  is dimensionless; treated as "no canonicalization"
}


def _parse_header_unit(header: str) -> tuple[str, str | None]:
    """Return ``(display_name, unit_string_or_None)``.

    ``display_name`` is the header with any trailing ``(unit)`` stripped.
    """
    match = _UNIT_SUFFIX_RE.match(header)
    if not match:
        return header.strip(), None
    raw_unit = match.group(1).strip()
    # Trim the bracketed portion off the display name
    display = re.sub(r"\s*[\(\[].*?[\)\]]\s*$", "", header).strip()
    return display, raw_unit


def _canonicalise_unit_for_registry(raw_unit: str) -> str:
    """Apply header-specific aliases then return the string to feed to
    :func:`canonicalize_measurement`."""
    return _HEADER_UNIT_ALIASES.get(raw_unit, raw_unit)


# ---------------------------------------------------------------------------
# QC column detection
# ---------------------------------------------------------------------------


def _find_qc_column_index(
    headers: list[str],
    measurement_idx: int,
) -> int | None:
    """Return the index of a QC column associated with ``measurement_idx``.

    Conventions tried (in order):
    1. **CIMIS**: the immediately-following column named ``"qc"``
       (case-insensitive, optional whitespace).
    2. **Column suffix**: a later column named
       ``<measurement>_qflag``/``<measurement>_quality``/``<measurement>_q``.

    Returns ``None`` if no QC column is found.
    """
    # CIMIS: qc column directly follows the measurement
    if measurement_idx + 1 < len(headers):
        nxt = headers[measurement_idx + 1].strip().lower()
        if nxt in ("qc", "q", "qflag", "quality"):
            return measurement_idx + 1

    # Suffix convention
    meas_name = headers[measurement_idx].strip().lower()
    # Strip unit suffix for matching
    base = re.sub(r"\s*[\(\[].*?[\)\]]\s*$", "", meas_name).strip()
    base_normalised = re.sub(r"[\s\-\.]+", "_", base)
    for idx, h in enumerate(headers):
        h_lower = h.strip().lower()
        if h_lower in (
            f"{base}_qflag",
            f"{base}_quality",
            f"{base}_q",
            f"{base_normalised}_qflag",
            f"{base_normalised}_quality",
            f"{base_normalised}_q",
        ):
            return idx
    return None


# ---------------------------------------------------------------------------
# Data classes describing the parsed schema + rows
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class CsvColumn:
    """One column in a parsed CSV."""

    index: int
    header: str
    display_name: str
    raw_unit: str | None
    canonical_unit_for_registry: str | None
    qc_column_index: int | None
    canonical_concept: str | None  # e.g. "temperature" — from metadata_schema


@dataclass(frozen=True, slots=True)
class CsvSchema:
    """The result of analysing a CSV header."""

    columns: tuple[CsvColumn, ...]
    header: tuple[str, ...]

    @property
    def measurement_columns(self) -> tuple[CsvColumn, ...]:
        """All columns we were able to interpret as measurements."""
        return tuple(c for c in self.columns if c.canonical_unit_for_registry)


@dataclass(frozen=True, slots=True)
class ParsedRow:
    """A single parsed row with measurements and contextual fields."""

    row_index: int
    measurements: tuple[Measurement, ...]
    context: dict[str, str] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class ParsedCsv:
    """Full result of :func:`parse_scientific_csv`."""

    schema: CsvSchema
    rows: tuple[ParsedRow, ...]
    total_rows: int
    parse_errors: int


# ---------------------------------------------------------------------------
# Main parser
# ---------------------------------------------------------------------------


def analyse_header(headers: list[str]) -> CsvSchema:
    """Analyse headers only — find measurement columns and their QC pairs.

    Returns a :class:`CsvSchema` describing each column, marking those that
    look like measurements (have a recognised unit in their header) and
    noting any adjacent QC columns.
    """
    columns: list[CsvColumn] = []
    for idx, raw in enumerate(headers):
        display, raw_unit = _parse_header_unit(raw)
        canonical_unit_for_registry: str | None = None
        if raw_unit is not None:
            candidate = _canonicalise_unit_for_registry(raw_unit)
            # Verify the unit is actually in the registry by attempting a trial
            # canonicalisation. ``percent`` isn't in the registry; we keep it
            # as a known display unit but skip it for SI conversion.
            try:
                canonicalize_measurement(0.0, candidate)
                canonical_unit_for_registry = candidate
            except (ValueError, KeyError):
                canonical_unit_for_registry = None

        qc_idx = None
        if canonical_unit_for_registry is not None:
            qc_idx = _find_qc_column_index(headers, idx)

        # Map to a canonical concept using the metadata-schema aligner
        concept = align_field(raw)

        columns.append(
            CsvColumn(
                index=idx,
                header=raw,
                display_name=display,
                raw_unit=raw_unit,
                canonical_unit_for_registry=canonical_unit_for_registry,
                qc_column_index=qc_idx,
                canonical_concept=concept,
            )
        )
    return CsvSchema(columns=tuple(columns), header=tuple(headers))


def parse_scientific_csv(
    text: str,
    *,
    max_rows: int | None = None,
    context_columns: tuple[str, ...] = (
        "stn name",
        "station name",
        "site name",
        "name",
        "date",
        "datetime",
        "time",
    ),
    delimiter: str = ",",
) -> ParsedCsv:
    """Parse a CSV text into measurements with quality flags.

    Args:
        text: Raw CSV content including header.
        max_rows: Optional row cap (for bounded memory in tests).
        context_columns: Substrings to look for in header names to capture
            as ``context`` dict on each row (e.g. station name, date).
        delimiter: Field delimiter. Default comma.

    Returns:
        :class:`ParsedCsv` with the inferred schema, per-row measurements,
        and parse error count.
    """
    lines = text.splitlines()
    if not lines:
        return ParsedCsv(
            schema=CsvSchema(columns=(), header=()),
            rows=(),
            total_rows=0,
            parse_errors=0,
        )

    header_row = [h.strip() for h in lines[0].split(delimiter)]
    schema = analyse_header(header_row)

    # Resolve context column indices
    header_lower = [h.lower() for h in header_row]
    context_indices: dict[str, int] = {}
    for ctx in context_columns:
        for i, h in enumerate(header_lower):
            if ctx in h and i not in context_indices.values():
                context_indices[header_row[i]] = i
                break

    rows: list[ParsedRow] = []
    parse_errors = 0
    data_lines = lines[1:]
    if max_rows is not None:
        data_lines = data_lines[:max_rows]

    for row_idx, line in enumerate(data_lines):
        if not line.strip():
            continue
        cells = line.split(delimiter)
        if len(cells) < len(header_row):
            # Allow rows shorter than the header (trailing empty cells)
            cells.extend([""] * (len(header_row) - len(cells)))

        row_measurements: list[Measurement] = []
        row_has_error = False
        for col in schema.measurement_columns:
            if col.canonical_unit_for_registry is None:
                continue
            raw_cell = cells[col.index].strip() if col.index < len(cells) else ""
            if not raw_cell:
                # Treat empty cell as missing; don't emit a measurement.
                continue
            try:
                raw_value = float(raw_cell)
            except ValueError:
                row_has_error = True
                continue

            # Read QC token (if any)
            if col.qc_column_index is not None and col.qc_column_index < len(cells):
                qc_token = cells[col.qc_column_index].strip()
                source_flag = parse_qc_token(qc_token)
            else:
                source_flag = QualityFlag.GOOD  # no QC column = assume good

            try:
                canonical_value, canonical_unit = canonicalize_measurement(
                    raw_value,
                    col.canonical_unit_for_registry,
                )
            except (ValueError, KeyError):
                row_has_error = True
                continue

            # Combine source flag with physical-plausibility check
            final_flag = derive_flag_from_value(
                canonical_unit,
                canonical_value,
                source_flag,
            )

            row_measurements.append(
                Measurement(
                    raw_value=raw_value,
                    raw_unit=(col.raw_unit or "").lower(),
                    canonical_value=canonical_value,
                    canonical_unit=canonical_unit,
                    quality=final_flag.value,
                )
            )

        if row_has_error:
            parse_errors += 1

        context = {
            col_name: cells[idx].strip() if idx < len(cells) else ""
            for col_name, idx in context_indices.items()
        }

        rows.append(
            ParsedRow(
                row_index=row_idx,
                measurements=tuple(row_measurements),
                context=context,
            )
        )

    return ParsedCsv(
        schema=schema,
        rows=tuple(rows),
        total_rows=len(data_lines),
        parse_errors=parse_errors,
    )


# ---------------------------------------------------------------------------
# Convenience aggregates — used by the evaluation code
# ---------------------------------------------------------------------------


def filter_rows_by_concept(
    parsed: ParsedCsv,
    concept: str,
    min_value_canonical: float | None = None,
    max_value_canonical: float | None = None,
    acceptable_quality: frozenset[QualityFlag] | None = None,
) -> list[dict[str, Any]]:
    """Filter parsed rows to those matching a canonical concept + threshold.

    Args:
        parsed: Output of :func:`parse_scientific_csv`.
        concept: Canonical concept name from :mod:`metadata_schema`
            (e.g. ``"temperature"``).
        min_value_canonical, max_value_canonical: Optional range bounds in
            canonical (SI) units.
        acceptable_quality: Optional set of acceptable flags. Default
            is ``{GOOD, ESTIMATED}``.

    Returns:
        List of dicts containing ``{raw_value, raw_unit, canonical_value,
        quality, context}``.
    """
    if acceptable_quality is None:
        acceptable_quality = frozenset({QualityFlag.GOOD, QualityFlag.ESTIMATED})

    # Find measurement columns matching the concept
    concept_cols = [c for c in parsed.schema.columns if c.canonical_concept == concept]
    concept_col_indices = {c.index for c in concept_cols}
    if not concept_cols:
        return []

    # Build a map from column index → the canonical unit the column
    # produced. We need this because a row has one Measurement per
    # matched column; we only want rows from columns matching the concept.
    results: list[dict[str, Any]] = []
    for row in parsed.rows:
        # Walk the row's measurements alongside the schema columns
        # (measurements are emitted in the same order as measurement_columns).
        meas_iter = iter(row.measurements)
        for col in parsed.schema.measurement_columns:
            try:
                m = next(meas_iter)
            except StopIteration:
                break
            if col.index not in concept_col_indices:
                continue
            flag = QualityFlag.from_string(m.quality)
            if flag not in acceptable_quality:
                continue
            if min_value_canonical is not None and m.canonical_value < min_value_canonical:
                continue
            if max_value_canonical is not None and m.canonical_value > max_value_canonical:
                continue
            results.append(
                {
                    "raw_value": m.raw_value,
                    "raw_unit": m.raw_unit,
                    "canonical_value": m.canonical_value,
                    "canonical_unit": m.canonical_unit,
                    "quality": m.quality,
                    "context": dict(row.context),
                    "column": col.header,
                }
            )
    return results
