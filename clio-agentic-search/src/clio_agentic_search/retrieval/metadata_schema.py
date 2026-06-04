"""Metadata schema inference and field alignment.

This module implements the second search target from the research program:
*heterogeneous metadata*. Different scientific datasets describe the same
real-world concept under different field names — ``"temperature"``,
``"temp"``, ``"air_temp"``, ``"Air Temp (C)"``, ``"T_air"``, ``"T2M"``.
A retrieval layer that only does substring match on field names misses
most of these.

Two separate concerns live here:

1. :class:`MetadataSchema` — a per-namespace description of *what fields
   exist and how often they appear*. Built from the ``metadata`` table in
   DuckDB via :func:`build_metadata_schema`.

2. :func:`align_field` — map a raw field name to a *canonical concept*
   from a small, hand-curated taxonomy. This is the dictionary-based
   "best match" that lets the retrieval layer say "field X in dataset A
   and field Y in dataset B both represent temperature".

A richer version of this layer would use embeddings to infer concepts,
but the dictionary approach is deterministic, fast, and covers the
most common scientific fields. It's the real version — not a stub.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

# ---------------------------------------------------------------------------
# Canonical concept taxonomy
# ---------------------------------------------------------------------------
#
# After normalisation each field name becomes a sequence of ``_``-separated
# tokens (``"Air Temp (C)"`` → ``["air", "temp"]``). We match by checking
# whether any ``include_tokens`` entry is a **set subset** of the field's
# tokens (AND semantics for multi-token patterns), and whether none of the
# ``exclude_tokens`` words appear as tokens (OR semantics for exclusions).
#
# Order matters: the first concept whose include set matches wins.

_CANONICAL_CONCEPTS: list[tuple[str, list[frozenset[str]], frozenset[str]]] = [
    # (canonical_name, [set_of_required_tokens, ...], {disqualifying_tokens})
    (
        "temperature",
        [
            frozenset({"temp"}),
            frozenset({"temperature"}),
            frozenset({"air", "temp"}),
            frozenset({"surface", "temp"}),
            frozenset({"t", "air"}),
            frozenset({"t2m"}),
        ],
        frozenset({"id", "sensor", "scale", "unit", "station", "site"}),
    ),
    (
        "station_id",
        [
            frozenset({"stn", "id"}),
            frozenset({"station", "id"}),
            frozenset({"site", "id"}),
            frozenset({"station", "number"}),
            frozenset({"sid"}),
        ],
        frozenset(),
    ),
    (
        "pressure",
        [
            frozenset({"pressure"}),
            frozenset({"press"}),
            frozenset({"pres"}),
            frozenset({"baro"}),
            frozenset({"barometric"}),
            frozenset({"barometric", "pressure"}),
            frozenset({"atm", "pressure"}),
            frozenset({"mslp"}),
            frozenset({"slp"}),
            frozenset({"vap", "pres"}),
        ],
        frozenset({"id", "sensor"}),
    ),
    (
        "humidity",
        [
            frozenset({"humidity"}),
            frozenset({"humid"}),
            frozenset({"rel", "hum"}),
            frozenset({"relative", "humidity"}),
            frozenset({"rh"}),
            frozenset({"dew", "point"}),
        ],
        frozenset({"sensor"}),
    ),
    (
        "wind_direction",
        [
            frozenset({"wind", "direction"}),
            frozenset({"wind", "dir"}),
            frozenset({"wnd", "dir"}),
            frozenset({"wd"}),
        ],
        frozenset({"id"}),
    ),
    (
        "wind_speed",
        [
            frozenset({"wind", "speed"}),
            frozenset({"wind", "spd"}),
            frozenset({"wnd", "spd"}),
            frozenset({"wnd", "speed"}),
            frozenset({"ws"}),
            frozenset({"wind", "vel"}),
            frozenset({"wind", "velocity"}),
        ],
        frozenset({"id", "direction", "dir"}),
    ),
    (
        "precipitation",
        [
            frozenset({"precip"}),
            frozenset({"precipitation"}),
            frozenset({"rain"}),
            frozenset({"rainfall"}),
            frozenset({"pcp"}),
            frozenset({"snow"}),
            frozenset({"snowfall"}),
        ],
        frozenset({"id"}),
    ),
    (
        "solar_radiation",
        [
            frozenset({"sol", "rad"}),
            frozenset({"solar"}),
            frozenset({"solar", "radiation"}),
            frozenset({"irradiance"}),
            frozenset({"short", "wave"}),
            frozenset({"sw", "down"}),
        ],
        frozenset({"id"}),
    ),
    (
        "soil_moisture",
        [
            frozenset({"soil", "moisture"}),
            frozenset({"soil", "moist"}),
            frozenset({"vwc"}),
        ],
        frozenset({"id"}),
    ),
    (
        "time",
        [
            frozenset({"time"}),
            frozenset({"timestamp"}),
            frozenset({"date"}),
            frozenset({"datetime"}),
            frozenset({"epoch"}),
            frozenset({"hour"}),
            frozenset({"obs", "time"}),
        ],
        frozenset({"zone"}),
    ),
    (
        "latitude",
        [
            frozenset({"lat"}),
            frozenset({"latitude"}),
        ],
        frozenset({"id", "err", "limit", "plat", "flat"}),
    ),
    (
        "longitude",
        [
            frozenset({"lon"}),
            frozenset({"lng"}),
            frozenset({"longitude"}),
        ],
        frozenset({"id", "err", "limit"}),
    ),
    (
        "elevation",
        [
            frozenset({"elevation"}),
            frozenset({"elev"}),
            frozenset({"altitude"}),
            frozenset({"alt"}),
            frozenset({"height"}),
        ],
        frozenset({"id", "ref"}),
    ),
    (
        "measurement_quality",
        [
            frozenset({"qc"}),
            frozenset({"quality"}),
            frozenset({"qflag"}),
            frozenset({"qa"}),
            frozenset({"flag"}),
        ],
        frozenset(),
    ),
]


_WHITESPACE_RE = re.compile(r"[\s\-\.]+")
_UNIT_SUFFIX_RE = re.compile(r"\s*\([^)]*\)\s*$")
_PUNCT_RE = re.compile(r"[^\w_]")


def _normalise_field_name(name: str) -> str:
    """Normalise a field name for matching.

    - Strip trailing ``(unit)`` suffixes.
    - Lowercase.
    - Collapse whitespace/dots/hyphens to underscores.
    - Drop other punctuation.
    """
    cleaned = _UNIT_SUFFIX_RE.sub("", name.strip()).lower()
    cleaned = _WHITESPACE_RE.sub("_", cleaned)
    cleaned = _PUNCT_RE.sub("", cleaned)
    return cleaned


def _tokenise(normalised: str) -> set[str]:
    """Split a normalised field name into its token set."""
    return {t for t in normalised.split("_") if t}


def align_field(field_name: str) -> str | None:
    """Map a raw field name to a canonical concept, or ``None`` if unknown.

    Matching is token-based on the normalised form of the field name:
    the field is split on underscores (after stripping ``(unit)`` suffixes
    and lowercasing) and each concept's include patterns are treated as
    required-token sets. Exclude tokens disqualify a match if they appear.

    Examples:
        >>> align_field("Air Temp (C)")
        'temperature'
        >>> align_field("temperature_sensor_id")  # "id" disqualifies
        >>> align_field("Rel Hum (%)")
        'humidity'
    """
    normalised = _normalise_field_name(field_name)
    if not normalised:
        return None

    tokens = _tokenise(normalised)
    if not tokens:
        return None

    for concept, include_sets, excludes in _CANONICAL_CONCEPTS:
        if tokens & excludes:
            continue
        for required in include_sets:
            if required.issubset(tokens):
                return concept
    return None


# ---------------------------------------------------------------------------
# MetadataSchema — per-namespace description of indexed fields
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class FieldInfo:
    """Description of a single metadata field found in a namespace."""

    key: str
    scope: str  # "document" or "chunk"
    occurrences: int
    canonical_concept: str | None


@dataclass(frozen=True, slots=True)
class MetadataSchema:
    """Per-namespace metadata schema.

    Attributes:
        namespace: The namespace this schema describes.
        fields: All distinct metadata keys found, with occurrence counts.
        total_documents: Total documents in the namespace.
        total_chunks: Total chunks in the namespace.
        concepts: Set of canonical concepts detected (e.g. ``{"temperature",
            "humidity"}``).
        richness_score: Heuristic 0-1 score of how metadata-rich this
            namespace is. 0 = almost no structured metadata, 1 = every
            chunk has rich structured metadata with recognised concepts.
    """

    namespace: str
    fields: tuple[FieldInfo, ...]
    total_documents: int
    total_chunks: int
    concepts: frozenset[str]
    richness_score: float

    @property
    def has_temperature_field(self) -> bool:
        return "temperature" in self.concepts

    @property
    def has_pressure_field(self) -> bool:
        return "pressure" in self.concepts

    @property
    def has_location_fields(self) -> bool:
        return "latitude" in self.concepts and "longitude" in self.concepts

    @property
    def has_quality_field(self) -> bool:
        return "measurement_quality" in self.concepts

    def fields_for_concept(self, concept: str) -> tuple[FieldInfo, ...]:
        """Return all fields that map to the given canonical concept."""
        return tuple(f for f in self.fields if f.canonical_concept == concept)


def build_metadata_schema(
    namespace: str,
    metadata_rows: list[tuple[str, str, str, int]],
    total_documents: int,
    total_chunks: int,
) -> MetadataSchema:
    """Build a :class:`MetadataSchema` from raw metadata rows.

    Args:
        namespace: Namespace name.
        metadata_rows: Each entry is ``(key, scope, sample_value, count)``
            — the count of how many distinct record_ids in this namespace
            have that ``(key, scope)`` pair. Typically produced by a
            ``GROUP BY`` query on the ``metadata`` table.
        total_documents, total_chunks: Totals for richness-score computation.
    """
    fields: list[FieldInfo] = []
    concepts: set[str] = set()
    for key, scope, _sample, count in metadata_rows:
        concept = align_field(key)
        if concept:
            concepts.add(concept)
        fields.append(
            FieldInfo(
                key=key,
                scope=scope,
                occurrences=count,
                canonical_concept=concept,
            )
        )

    richness = _compute_richness(fields, concepts, total_documents, total_chunks)

    return MetadataSchema(
        namespace=namespace,
        fields=tuple(fields),
        total_documents=total_documents,
        total_chunks=total_chunks,
        concepts=frozenset(concepts),
        richness_score=richness,
    )


def _compute_richness(
    fields: list[FieldInfo],
    concepts: set[str],
    total_docs: int,
    total_chunks: int,
) -> float:
    """Compute a 0-1 richness score.

    Combines three signals, each weighted:
      - Coverage: how many chunks have ANY metadata key (0-0.4)
      - Field count: how many distinct keys exist (saturates at 10) (0-0.3)
      - Concept recognition: how many canonical concepts were detected
        (saturates at 5) (0-0.3)
    """
    if total_chunks == 0:
        return 0.0

    # Coverage
    chunk_scope_fields = [f for f in fields if f.scope == "chunk"]
    chunks_with_metadata = max(
        (f.occurrences for f in chunk_scope_fields),
        default=0,
    )
    coverage = min(chunks_with_metadata / total_chunks, 1.0) if total_chunks > 0 else 0.0
    coverage_score = 0.4 * coverage

    # Field variety
    variety_score = 0.3 * min(len(fields) / 10.0, 1.0)

    # Concept recognition
    concept_score = 0.3 * min(len(concepts) / 5.0, 1.0)

    return round(coverage_score + variety_score + concept_score, 4)


# ---------------------------------------------------------------------------
# Convenience: describe schema as plain dict for JSON / trace output
# ---------------------------------------------------------------------------


def describe_schema(schema: MetadataSchema) -> dict[str, Any]:
    """Return a JSON-serialisable description of a schema."""
    return {
        "namespace": schema.namespace,
        "total_documents": schema.total_documents,
        "total_chunks": schema.total_chunks,
        "richness_score": schema.richness_score,
        "distinct_field_count": len(schema.fields),
        "concepts": sorted(schema.concepts),
        "top_fields": [
            {
                "key": f.key,
                "scope": f.scope,
                "occurrences": f.occurrences,
                "concept": f.canonical_concept,
            }
            for f in sorted(schema.fields, key=lambda x: -x.occurrences)[:20]
        ],
    }
