"""Scientific parsing utilities for structure-aware chunking and normalization."""

from __future__ import annotations

import hashlib
import math
import re
from dataclasses import dataclass, field

from clio_agentic_search.models.contracts import ChunkRecord

_HEADING_PATTERN = re.compile(r"(?m)^(#{1,6})\s+(.+)$")
_CAPTION_PATTERN = re.compile(r"(?mi)^(figure|fig\.?|table)\s*([0-9A-Za-z-]*)\s*[:.-]\s*(.+)$")
_BLOCK_EQUATION_PATTERN = re.compile(r"\$\$(.+?)\$\$", flags=re.DOTALL)
_INLINE_EQUATION_PATTERN = re.compile(r"(?<!\$)\$(?!\$)(.+?)(?<!\$)\$(?!\$)", flags=re.DOTALL)
_TABLE_LINE_PATTERN = re.compile(r"^\s*\|.*\|\s*$")
_FACTOR_PATTERN = re.compile(r"(\\[a-z]+|[a-z])(\^\d+)?")

# Plain-text equation: <short_var(s)> = <expression ending at } or ^digits>.
# Catches e.g. ``k = A e^{-E_a/RT}`` or ``E = mc^2`` without $ delimiters.
# Uses lazy quantifier so the match stops at the *first* valid math endpoint.
_PLAIN_EQUATION_PATTERN = re.compile(
    r"(?<!\$)\b"
    r"([a-zA-Z_]{1,3}(?:\s+[a-zA-Z_]{1,3})*"
    r"\s*=\s*"
    r"[^\n,;$|]*?"
    r"(?:\}|\^\d+))"
    r"(?=[,.\s;:!?]|$)",
)
_MATH_INDICATOR_RE = re.compile(r"[\^{\\]")

_MEASUREMENT_PATTERN = re.compile(
    r"(?P<value>[+-]?\d+(?:\.\d+)?)\s*"
    r"(?P<unit>"
    r"km/h|m/s|rad/s|m/s2|"  # compound velocity/acceleration
    r"degf|degc|°f|°c|kelvin|"  # temperature
    r"km|cm|mm|nm|m|"  # length
    r"kg|mg|g|"  # mass
    r"hz|khz|mhz|ghz|"  # frequency
    r"bq|ci|"  # radioactivity
    r"ha|"  # area
    r"ev|kev|mev|gev|"  # energy
    r"kj|mj|gj|"  # energy (joule family)
    r"kw|mw|gw|w|"  # power
    r"kn|"  # force (kilonewton)
    r"bar|atm|psi|hpa|mpa|kpa|pa|"  # pressure
    r"h|min|s"  # time
    r")\b",
    flags=re.IGNORECASE,
)

# ---------------------------------------------------------------------------
# Composable unit registry based on dimensional analysis.
#
# Every physical unit is represented as:
#   - dim_vector: exponents of the 7 SI base dimensions [M, L, T, I, Θ, N, J]
#     (mass, length, time, electric current, temperature, amount, luminous intensity)
#   - scale: multiplicative factor relative to the SI base unit for that dimension
#   - offset: additive offset (non-zero only for temperature scales)
#   - domain: semantic grouping for disambiguation (e.g., Hz vs Bq are both T⁻¹)
#
# Compatibility check: dimension vectors must match.
# Conversion: canonical_value = raw_value * scale + offset.
# Adding a new unit = adding a single row. No code changes required.
# ---------------------------------------------------------------------------

# Dimension vector indices: M=0, L=1, T=2, I=3, Θ=4, N=5, J=6
# We use tuples for hashability and fast comparison.

# Base dimension vectors for common physical quantities
_DIM_LENGTH = (0, 1, 0, 0, 0, 0, 0)  # L
_DIM_MASS = (1, 0, 0, 0, 0, 0, 0)  # M
_DIM_TIME = (0, 0, 1, 0, 0, 0, 0)  # T
_DIM_TEMPERATURE = (0, 0, 0, 0, 1, 0, 0)  # Θ
_DIM_VELOCITY = (0, 1, -1, 0, 0, 0, 0)  # L·T⁻¹
_DIM_ACCEL = (0, 1, -2, 0, 0, 0, 0)  # L·T⁻²
_DIM_PRESSURE = (1, -1, -2, 0, 0, 0, 0)  # M·L⁻¹·T⁻²
_DIM_FORCE = (1, 1, -2, 0, 0, 0, 0)  # M·L·T⁻²
_DIM_ENERGY = (1, 2, -2, 0, 0, 0, 0)  # M·L²·T⁻²
_DIM_POWER = (1, 2, -3, 0, 0, 0, 0)  # M·L²·T⁻³
_DIM_FREQUENCY = (0, 0, -1, 0, 0, 0, 0)  # T⁻¹
_DIM_AREA = (0, 2, 0, 0, 0, 0, 0)  # L²
_DIM_RADIOACT = (0, 0, -1, 0, 0, 0, 0)  # T⁻¹ (same as frequency, different domain)


@dataclass(frozen=True, slots=True)
class UnitEntry:
    """One row in the composable unit registry."""

    dim_vector: tuple[int, ...]  # exponents of [M, L, T, I, Θ, N, J]
    scale: float  # multiplicative factor to SI base
    offset: float = 0.0  # additive offset (temperature only)
    domain: str = ""  # semantic grouping (pressure, temperature, etc.)


# The registry: unit_name → UnitEntry.
# Adding a new unit = adding a single line here.
_UNIT_REGISTRY: dict[str, UnitEntry] = {
    # --- Length (L) ---
    "nm": UnitEntry(_DIM_LENGTH, 1e-9, domain="length"),
    "mm": UnitEntry(_DIM_LENGTH, 1e-3, domain="length"),
    "cm": UnitEntry(_DIM_LENGTH, 1e-2, domain="length"),
    "m": UnitEntry(_DIM_LENGTH, 1.0, domain="length"),
    "km": UnitEntry(_DIM_LENGTH, 1e3, domain="length"),
    # --- Mass (M) ---
    "mg": UnitEntry(_DIM_MASS, 1e-6, domain="mass"),
    "g": UnitEntry(_DIM_MASS, 1e-3, domain="mass"),
    "kg": UnitEntry(_DIM_MASS, 1.0, domain="mass"),
    # --- Time (T) ---
    "s": UnitEntry(_DIM_TIME, 1.0, domain="time"),
    "min": UnitEntry(_DIM_TIME, 60.0, domain="time"),
    "h": UnitEntry(_DIM_TIME, 3600.0, domain="time"),
    # --- Temperature (Θ) ---
    "kelvin": UnitEntry(_DIM_TEMPERATURE, 1.0, 0.0, domain="temperature"),
    "k": UnitEntry(_DIM_TEMPERATURE, 1.0, 0.0, domain="temperature"),
    "degc": UnitEntry(_DIM_TEMPERATURE, 1.0, 273.15, domain="temperature"),
    "°c": UnitEntry(_DIM_TEMPERATURE, 1.0, 273.15, domain="temperature"),
    "c": UnitEntry(_DIM_TEMPERATURE, 1.0, 273.15, domain="temperature"),
    "celsius": UnitEntry(_DIM_TEMPERATURE, 1.0, 273.15, domain="temperature"),
    "centigrade": UnitEntry(_DIM_TEMPERATURE, 1.0, 273.15, domain="temperature"),
    "degf": UnitEntry(_DIM_TEMPERATURE, 5.0 / 9.0, 255.372, domain="temperature"),
    "°f": UnitEntry(_DIM_TEMPERATURE, 5.0 / 9.0, 255.372, domain="temperature"),
    "f": UnitEntry(_DIM_TEMPERATURE, 5.0 / 9.0, 255.372, domain="temperature"),
    "fahrenheit": UnitEntry(_DIM_TEMPERATURE, 5.0 / 9.0, 255.372, domain="temperature"),
    # --- Pressure (M·L⁻¹·T⁻²) ---
    "pa": UnitEntry(_DIM_PRESSURE, 1.0, domain="pressure"),
    "pascal": UnitEntry(_DIM_PRESSURE, 1.0, domain="pressure"),
    "pascals": UnitEntry(_DIM_PRESSURE, 1.0, domain="pressure"),
    "hpa": UnitEntry(_DIM_PRESSURE, 1e2, domain="pressure"),
    "hectopascal": UnitEntry(_DIM_PRESSURE, 1e2, domain="pressure"),
    "kpa": UnitEntry(_DIM_PRESSURE, 1e3, domain="pressure"),
    "kilopascal": UnitEntry(_DIM_PRESSURE, 1e3, domain="pressure"),
    "mpa": UnitEntry(_DIM_PRESSURE, 1e6, domain="pressure"),
    "megapascal": UnitEntry(_DIM_PRESSURE, 1e6, domain="pressure"),
    "bar": UnitEntry(_DIM_PRESSURE, 1e5, domain="pressure"),
    "atm": UnitEntry(_DIM_PRESSURE, 101325.0, domain="pressure"),
    "atmosphere": UnitEntry(_DIM_PRESSURE, 101325.0, domain="pressure"),
    "psi": UnitEntry(_DIM_PRESSURE, 6894.757, domain="pressure"),
    # --- Velocity (L·T⁻¹) ---
    "m/s": UnitEntry(_DIM_VELOCITY, 1.0, domain="velocity"),
    "km/h": UnitEntry(_DIM_VELOCITY, 1000.0 / 3600.0, domain="velocity"),
    "kn": UnitEntry(_DIM_VELOCITY, 0.514444, domain="velocity"),  # knots
    # --- Acceleration (L·T⁻²) ---
    "m/s2": UnitEntry(_DIM_ACCEL, 1.0, domain="acceleration"),
    # --- Frequency (T⁻¹) ---
    "hz": UnitEntry(_DIM_FREQUENCY, 1.0, domain="frequency"),
    "khz": UnitEntry(_DIM_FREQUENCY, 1e3, domain="frequency"),
    "mhz": UnitEntry(_DIM_FREQUENCY, 1e6, domain="frequency"),
    "ghz": UnitEntry(_DIM_FREQUENCY, 1e9, domain="frequency"),
    "rad/s": UnitEntry(_DIM_FREQUENCY, 1.0 / (2 * 3.14159265), domain="frequency"),
    # --- Radioactivity (T⁻¹, different domain from frequency) ---
    "bq": UnitEntry(_DIM_RADIOACT, 1.0, domain="radioactivity"),
    "ci": UnitEntry(_DIM_RADIOACT, 3.7e10, domain="radioactivity"),
    # --- Energy (M·L²·T⁻²) ---
    "ev": UnitEntry(_DIM_ENERGY, 1.602176634e-19, domain="energy"),
    "kev": UnitEntry(_DIM_ENERGY, 1.602176634e-16, domain="energy"),
    "mev": UnitEntry(_DIM_ENERGY, 1.602176634e-13, domain="energy"),
    "gev": UnitEntry(_DIM_ENERGY, 1.602176634e-10, domain="energy"),
    "kj": UnitEntry(_DIM_ENERGY, 1e3, domain="energy"),
    "mj": UnitEntry(_DIM_ENERGY, 1e6, domain="energy"),
    "gj": UnitEntry(_DIM_ENERGY, 1e9, domain="energy"),
    # --- Power (M·L²·T⁻³) ---
    "w": UnitEntry(_DIM_POWER, 1.0, domain="power"),
    "kw": UnitEntry(_DIM_POWER, 1e3, domain="power"),
    "mw": UnitEntry(_DIM_POWER, 1e6, domain="power"),
    "gw": UnitEntry(_DIM_POWER, 1e9, domain="power"),
    # --- Area (L²) ---
    "ha": UnitEntry(_DIM_AREA, 1e4, domain="area"),
    # --- Force (M·L·T⁻²) ---
    # "n" omitted — collides with amount-of-substance "N" and generic variables.
    # Users can add it if their corpus doesn't use "N" as a variable.
}

# Backward-compatible flat dict for query_rewriter.py (_expand_unit_variants).
# Maps unit_name → (canonical_dim_key, scale, offset).
# The canonical_dim_key is a string representation of the dimension vector
# so that existing code comparing canonical_unit strings still works.
_DIM_KEY_CACHE: dict[tuple[int, ...], str] = {}


def _dim_key(dim_vector: tuple[int, ...]) -> str:
    """Return a stable string key for a dimension vector.

    Uses comma separator to avoid conflict with the pipe-delimited
    measurement encoding format used by encode_measurements().
    """
    if dim_vector not in _DIM_KEY_CACHE:
        _DIM_KEY_CACHE[dim_vector] = ",".join(str(d) for d in dim_vector)
    return _DIM_KEY_CACHE[dim_vector]


# Build backward-compatible _UNIT_CANONICALIZATION from the registry.
_UNIT_CANONICALIZATION: dict[str, tuple[str, float, float]] = {
    name: (_dim_key(entry.dim_vector), entry.scale, entry.offset)
    for name, entry in _UNIT_REGISTRY.items()
}


@dataclass(frozen=True, slots=True)
class Measurement:
    raw_value: float
    raw_unit: str
    canonical_value: float
    canonical_unit: str  # dimension key string (e.g., "1|-1|-2|0|0|0|0" for pressure)
    quality: str = "unknown"  # QualityFlag string form; see indexing.quality


@dataclass(frozen=True, slots=True)
class ScientificChunk:
    kind: str
    text: str
    start_offset: int
    end_offset: int
    metadata: dict[str, str] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class ScientificChunkPlan:
    chunks: list[ChunkRecord]
    metadata_by_chunk_id: dict[str, dict[str, str]]


def canonicalize_measurement(value: float, unit: str) -> tuple[float, str]:
    normalized_unit = unit.strip().lower()
    canonical = _UNIT_CANONICALIZATION.get(normalized_unit)
    if canonical is None:
        raise ValueError(f"Unsupported unit '{unit}'")
    canonical_unit, scale, offset = canonical
    return value * scale + offset, canonical_unit


def normalize_formula(formula: str) -> str:
    stripped = formula.strip().lower()
    normalized = re.sub(r"\s+", "", stripped)
    # Superscript normalization: ^{2} → ^2, **2 → ^2
    normalized = re.sub(r"\^\{(\d+)\}", r"^\1", normalized)
    normalized = re.sub(r"\*\*(\d+)", r"^\1", normalized)
    # Split on = and normalize each side independently
    sides = normalized.split("=")
    sides = [_normalize_formula_side(side) for side in sides]
    sides.sort()
    return "=".join(sides)


def _normalize_formula_side(side: str) -> str:
    """Normalize one side of a formula equation for canonical comparison."""
    if not side:
        return side
    if "/" in side or "+" in side or "-" in side:
        return side
    factors = [match.group(0) for match in _FACTOR_PATTERN.finditer(side)]
    if not factors:
        return side
    if "".join(factors) != side:
        return side
    factors.sort()
    return "".join(factors)


def extract_measurements(text: str) -> list[Measurement]:
    """Extract numeric measurements with units from free text.

    Each match is canonicalised to SI base units. Quality is set to
    ``"good"`` by default since the value was successfully parsed and
    canonicalised — downstream connectors can override this when the
    source provides explicit QC flags (e.g. CSV qc columns).
    """
    # Import locally to avoid a top-level circular import (quality depends
    # on nothing, but indexing.scientific is imported widely).
    from clio_agentic_search.indexing.quality import (
        QualityFlag,
        derive_flag_from_value,
    )

    measurements: list[Measurement] = []
    for match in _MEASUREMENT_PATTERN.finditer(text):
        raw_value = float(match.group("value"))
        raw_unit = match.group("unit")
        try:
            canonical_value, canonical_unit = canonicalize_measurement(raw_value, raw_unit)
        except ValueError:
            continue
        # Default to GOOD, then let the physical-plausibility check
        # potentially downgrade to QUESTIONABLE for out-of-range values.
        flag = derive_flag_from_value(
            canonical_unit,
            canonical_value,
            QualityFlag.GOOD,
        )
        measurements.append(
            Measurement(
                raw_value=raw_value,
                raw_unit=raw_unit.lower(),
                canonical_value=canonical_value,
                canonical_unit=canonical_unit,
                quality=flag.value,
            )
        )
    return measurements


def extract_formula_signatures(text: str) -> list[str]:
    signatures: list[str] = []
    seen: set[str] = set()
    for expression in _extract_equation_expressions(text):
        signature = normalize_formula(expression)
        if not signature or signature in seen:
            continue
        signatures.append(signature)
        seen.add(signature)
    return signatures


def encode_measurements(measurements: list[Measurement]) -> str:
    """Encode a list of :class:`Measurement` objects to a string.

    Format: semicolon-separated entries; each entry pipe-separated as:
        canonical_unit|canonical_value|raw_unit|raw_value[|quality]

    The optional ``quality`` field is a :class:`~indexing.quality.QualityFlag`
    string (``"good"``, ``"bad"``, etc). When absent (legacy rows), decoding
    yields ``quality="unknown"``.
    """
    if not measurements:
        return ""
    return ";".join(
        f"{item.canonical_unit}|{item.canonical_value:.12g}|"
        f"{item.raw_unit}|{item.raw_value:.12g}|{item.quality}"
        for item in measurements
    )


def decode_measurements(value: str) -> list[Measurement]:
    """Decode a string produced by :func:`encode_measurements`.

    Accepts both the 4-field legacy format (no quality) and the 5-field
    format (with quality) for backward compatibility. Malformed entries
    are skipped silently.
    """
    decoded: list[Measurement] = []
    if not value:
        return decoded

    for item in value.split(";"):
        parts = item.split("|")
        if len(parts) < 4:
            continue
        canonical_unit = parts[0]
        canonical_value = parts[1]
        raw_unit = parts[2]
        raw_value = parts[3]
        quality = parts[4] if len(parts) >= 5 else "unknown"
        try:
            decoded.append(
                Measurement(
                    raw_value=float(raw_value),
                    raw_unit=raw_unit,
                    canonical_value=float(canonical_value),
                    canonical_unit=canonical_unit,
                    quality=quality,
                )
            )
        except ValueError:
            continue
    return decoded


def build_structure_aware_chunk_plan(
    *,
    namespace: str,
    document_id: str,
    text: str,
    chunk_size: int,
) -> ScientificChunkPlan:
    if not text:
        return ScientificChunkPlan(chunks=[], metadata_by_chunk_id={})

    scientific_chunks: list[ScientificChunk] = []
    scientific_chunks.extend(_build_section_chunks(text))
    scientific_chunks.extend(_build_caption_chunks(text))
    scientific_chunks.extend(_build_equation_chunks(text))
    scientific_chunks.extend(_build_table_chunks(text))

    if not scientific_chunks:
        scientific_chunks.extend(_build_plain_chunks(text=text, chunk_size=chunk_size))

    scientific_chunks.sort(key=lambda item: (item.start_offset, item.end_offset, item.kind))

    chunk_records: list[ChunkRecord] = []
    metadata_by_chunk_id: dict[str, dict[str, str]] = {}
    for index, item in enumerate(scientific_chunks):
        chunk_id = hashlib.sha1(
            f"{namespace}:{document_id}:{item.kind}:{index}:{item.start_offset}:{item.end_offset}".encode()
        ).hexdigest()

        measurements = extract_measurements(item.text)
        formulas = extract_formula_signatures(item.text)
        if item.kind == "equation" and not formulas:
            normalized = normalize_formula(item.text)
            if normalized:
                formulas = [normalized]
        chunk_metadata = dict(item.metadata)
        chunk_metadata["structure.kind"] = item.kind
        if measurements:
            chunk_metadata["scientific.measurements"] = encode_measurements(measurements)
        if formulas:
            chunk_metadata["scientific.formulas"] = ";".join(formulas)

        chunk_records.append(
            ChunkRecord(
                namespace=namespace,
                chunk_id=chunk_id,
                document_id=document_id,
                chunk_index=index,
                text=item.text,
                start_offset=item.start_offset,
                end_offset=item.end_offset,
            )
        )
        metadata_by_chunk_id[chunk_id] = chunk_metadata

    return ScientificChunkPlan(chunks=chunk_records, metadata_by_chunk_id=metadata_by_chunk_id)


def measurements_close(left: float, right: float, *, tolerance: float = 1e-9) -> bool:
    if tolerance < 0:
        return False
    return math.isclose(left, right, abs_tol=tolerance)


def _build_plain_chunks(*, text: str, chunk_size: int) -> list[ScientificChunk]:
    chunks: list[ScientificChunk] = []
    for start in range(0, len(text), chunk_size):
        end = min(start + chunk_size, len(text))
        chunk_text = text[start:end].strip()
        if not chunk_text:
            continue
        chunks.append(
            ScientificChunk(
                kind="text",
                text=chunk_text,
                start_offset=start,
                end_offset=end,
            )
        )
    return chunks


def _build_section_chunks(text: str) -> list[ScientificChunk]:
    matches = list(_HEADING_PATTERN.finditer(text))
    if not matches:
        return []

    chunks: list[ScientificChunk] = []
    for index, match in enumerate(matches):
        start = match.start()
        end = matches[index + 1].start() if index + 1 < len(matches) else len(text)
        section_text = text[start:end].strip()
        if not section_text:
            continue
        chunks.append(
            ScientificChunk(
                kind="section",
                text=section_text,
                start_offset=start,
                end_offset=end,
                metadata={
                    "structure.section": match.group(2).strip(),
                    "structure.section_level": str(len(match.group(1))),
                },
            )
        )
    return chunks


def _build_caption_chunks(text: str) -> list[ScientificChunk]:
    chunks: list[ScientificChunk] = []
    for index, match in enumerate(_CAPTION_PATTERN.finditer(text), start=1):
        caption_text = match.group(0).strip()
        if not caption_text:
            continue
        chunks.append(
            ScientificChunk(
                kind="caption",
                text=caption_text,
                start_offset=match.start(),
                end_offset=match.end(),
                metadata={
                    "caption.label": match.group(1).lower().rstrip("."),
                    "caption.index": match.group(2).strip() or str(index),
                    "caption.body": match.group(3).strip(),
                },
            )
        )
    return chunks


def _build_equation_chunks(text: str) -> list[ScientificChunk]:
    chunks: list[ScientificChunk] = []
    blocked_ranges: list[tuple[int, int]] = []

    for match in _BLOCK_EQUATION_PATTERN.finditer(text):
        expression = match.group(1).strip()
        if not expression:
            continue
        blocked_ranges.append((match.start(), match.end()))
        chunks.append(
            ScientificChunk(
                kind="equation",
                text=expression,
                start_offset=match.start(),
                end_offset=match.end(),
                metadata={"equation.block": "true"},
            )
        )

    for match in _INLINE_EQUATION_PATTERN.finditer(text):
        if _is_in_blocked_range(match.start(), blocked_ranges):
            continue
        expression = match.group(1).strip()
        if not expression:
            continue
        chunks.append(
            ScientificChunk(
                kind="equation",
                text=expression,
                start_offset=match.start(),
                end_offset=match.end(),
                metadata={"equation.block": "false"},
            )
        )

    return chunks


def _build_table_chunks(text: str) -> list[ScientificChunk]:
    lines = text.splitlines(keepends=True)
    if not lines:
        return []

    offsets: list[int] = []
    total = 0
    for line in lines:
        offsets.append(total)
        total += len(line)

    chunks: list[ScientificChunk] = []
    line_index = 0
    table_index = 0
    while line_index < len(lines):
        if not _TABLE_LINE_PATTERN.match(lines[line_index]):
            line_index += 1
            continue

        start_line = line_index
        block_lines: list[str] = []
        while line_index < len(lines) and _TABLE_LINE_PATTERN.match(lines[line_index]):
            block_lines.append(lines[line_index])
            line_index += 1

        if len(block_lines) < 2 or not _is_table_separator(block_lines[1]):
            continue

        table_index += 1
        start_offset = offsets[start_line]
        end_offset = offsets[start_line] + sum(len(line) for line in block_lines)
        table_text = "".join(block_lines).strip()
        if table_text:
            chunks.append(
                ScientificChunk(
                    kind="table",
                    text=table_text,
                    start_offset=start_offset,
                    end_offset=end_offset,
                    metadata={"table.index": str(table_index)},
                )
            )

        headers = _split_table_row(block_lines[0])
        data_rows = block_lines[2:]
        for row_idx, row_line in enumerate(data_rows, start=1):
            values = _split_table_row(row_line)
            for col_idx, value in enumerate(values, start=1):
                normalized_value = value.strip()
                if not normalized_value:
                    continue
                header = headers[col_idx - 1].strip() if col_idx - 1 < len(headers) else ""
                header_label = header or f"column_{col_idx}"
                cell_text = f"{header_label}: {normalized_value}"
                maybe_unit = _extract_unit_from_header(header_label)
                if maybe_unit and _is_number(normalized_value):
                    cell_text = f"{header_label}: {normalized_value} {maybe_unit}"
                chunks.append(
                    ScientificChunk(
                        kind="table_cell",
                        text=cell_text,
                        start_offset=start_offset,
                        end_offset=end_offset,
                        metadata={
                            "table.index": str(table_index),
                            "table.row": str(row_idx),
                            "table.column": str(col_idx),
                            "table.column_name": header_label,
                            "citation.fragment": (
                                f"table={table_index}&row={row_idx}&column={col_idx}"
                            ),
                        },
                    )
                )

    return chunks


def _extract_equation_expressions(text: str) -> list[str]:
    expressions: list[str] = []
    blocked_ranges: list[tuple[int, int]] = []

    for match in _BLOCK_EQUATION_PATTERN.finditer(text):
        expression = match.group(1).strip()
        if expression:
            expressions.append(expression)
            blocked_ranges.append((match.start(), match.end()))

    for match in _INLINE_EQUATION_PATTERN.finditer(text):
        if _is_in_blocked_range(match.start(), blocked_ranges):
            continue
        expression = match.group(1).strip()
        if expression:
            expressions.append(expression)
            blocked_ranges.append((match.start(), match.end()))

    # Third pass: plain-text equations without $ delimiters.
    # Matches patterns like ``k = A e^{-E_a/RT}`` or ``E = mc^2``.
    for match in _PLAIN_EQUATION_PATTERN.finditer(text):
        if _is_in_blocked_range(match.start(), blocked_ranges):
            continue
        expression = match.group(1).strip()
        if not expression or not _MATH_INDICATOR_RE.search(expression):
            continue
        # Skip matches on table lines
        line_start = text.rfind("\n", 0, match.start()) + 1
        if text[line_start:].lstrip().startswith("|"):
            continue
        expressions.append(expression)

    return expressions


def _is_in_blocked_range(position: int, ranges: list[tuple[int, int]]) -> bool:
    return any(start <= position < end for start, end in ranges)


def _is_table_separator(line: str) -> bool:
    cells = [cell.strip() for cell in _split_table_row(line)]
    if not cells:
        return False
    return all(cell and all(character in "-:" for character in cell) for cell in cells)


def _split_table_row(line: str) -> list[str]:
    stripped = line.strip()
    if stripped.startswith("|"):
        stripped = stripped[1:]
    if stripped.endswith("|"):
        stripped = stripped[:-1]
    return [cell.strip() for cell in stripped.split("|")]


def _extract_unit_from_header(header: str) -> str | None:
    match = re.search(r"\(([^)]+)\)", header)
    if match is None:
        return None
    return match.group(1).strip().lower() or None


def _is_number(value: str) -> bool:
    try:
        float(value)
    except ValueError:
        return False
    return True
