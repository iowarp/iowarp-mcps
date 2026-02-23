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
    r"(?P<value>[+-]?\d+(?:\.\d+)?)\s*(?P<unit>km/h|m/s|km|cm|mm|m|kg|mg|g|h|min|s|mpa|kpa|pa)\b",
    flags=re.IGNORECASE,
)

_UNIT_CANONICALIZATION: dict[str, tuple[str, float]] = {
    "mm": ("m", 1e-3),
    "cm": ("m", 1e-2),
    "m": ("m", 1.0),
    "km": ("m", 1e3),
    "mg": ("kg", 1e-6),
    "g": ("kg", 1e-3),
    "kg": ("kg", 1.0),
    "s": ("s", 1.0),
    "min": ("s", 60.0),
    "h": ("s", 3600.0),
    "pa": ("pa", 1.0),
    "kpa": ("pa", 1e3),
    "mpa": ("pa", 1e6),
    "m/s": ("m/s", 1.0),
    "km/h": ("m/s", 1000.0 / 3600.0),
}


@dataclass(frozen=True, slots=True)
class Measurement:
    raw_value: float
    raw_unit: str
    canonical_value: float
    canonical_unit: str


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
    canonical_unit, multiplier = canonical
    return value * multiplier, canonical_unit


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
    measurements: list[Measurement] = []
    for match in _MEASUREMENT_PATTERN.finditer(text):
        raw_value = float(match.group("value"))
        raw_unit = match.group("unit")
        try:
            canonical_value, canonical_unit = canonicalize_measurement(raw_value, raw_unit)
        except ValueError:
            continue
        measurements.append(
            Measurement(
                raw_value=raw_value,
                raw_unit=raw_unit.lower(),
                canonical_value=canonical_value,
                canonical_unit=canonical_unit,
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
    if not measurements:
        return ""
    return ";".join(
        f"{item.canonical_unit}|{item.canonical_value:.12g}|{item.raw_unit}|{item.raw_value:.12g}"
        for item in measurements
    )


def decode_measurements(value: str) -> list[Measurement]:
    decoded: list[Measurement] = []
    if not value:
        return decoded

    for item in value.split(";"):
        parts = item.split("|")
        if len(parts) != 4:
            continue
        canonical_unit, canonical_value, raw_unit, raw_value = parts
        try:
            decoded.append(
                Measurement(
                    raw_value=float(raw_value),
                    raw_unit=raw_unit,
                    canonical_value=float(canonical_value),
                    canonical_unit=canonical_unit,
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
