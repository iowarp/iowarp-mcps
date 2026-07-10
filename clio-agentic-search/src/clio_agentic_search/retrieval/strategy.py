"""Rule-based branch selection for intelligent retrieval orchestration.

The :class:`BranchPlan` answers three questions the coordinator asks before
dispatching a query:

1. Which retrieval branches should run? (lexical / vector / graph / scientific)
2. Should the quality filter be applied (is the corpus known to carry
   quality flags)?
3. What concepts in the corpus schema is the agent implicitly targeting?

The plan's ``reasoning`` field records the *why* in human-readable form so
the whole decision is auditable from the trace log.
"""

from __future__ import annotations

from dataclasses import dataclass

from clio_agentic_search.retrieval.corpus_profile import CorpusProfile
from clio_agentic_search.retrieval.scientific import ScientificQueryOperators


@dataclass(frozen=True, slots=True)
class BranchPlan:
    """Which retrieval branches to activate for a query.

    Also records the strategic choices the planner made based on the
    metadata schema and quality information in the corpus profile.
    """

    use_lexical: bool
    use_vector: bool
    use_graph: bool
    use_scientific: bool
    reasoning: str
    # Richer context for the agent and the trace log
    apply_quality_filter: bool = False
    targeted_concepts: tuple[str, ...] = ()
    schema_richness: float = 0.0
    average_quality: float = 1.0


def select_branches(
    query: str,
    operators: ScientificQueryOperators,
    profile: CorpusProfile | None,
    *,
    connector_has_lexical: bool = False,
    connector_has_vector: bool = False,
    connector_has_graph: bool = False,
    connector_has_scientific: bool = False,
) -> BranchPlan:
    """Decide which retrieval branches to activate.

    When *profile* is ``None`` (connector does not support profiling),
    every branch that the connector declares is used — identical to the
    original behaviour, with all schema/quality fields zeroed.
    """
    if profile is None:
        return BranchPlan(
            use_lexical=connector_has_lexical,
            use_vector=connector_has_vector,
            use_graph=connector_has_graph,
            use_scientific=connector_has_scientific and operators.is_active(),
            reasoning="no corpus profile available; using all declared branches",
        )

    reasons: list[str] = []

    # --- Branch 1: lexical ---
    use_lexical = connector_has_lexical and profile.has_lexical
    if connector_has_lexical and not profile.has_lexical:
        reasons.append("lexical skipped (no postings)")

    # --- Branch 2: vector ---
    use_vector = connector_has_vector and profile.has_embeddings
    if connector_has_vector and not profile.has_embeddings:
        reasons.append("vector skipped (no embeddings)")

    # --- Branch 3: graph (always run if supported, cheap) ---
    use_graph = connector_has_graph

    # --- Branch 4: scientific ---
    use_scientific = False
    if connector_has_scientific and operators.is_active():
        has_relevant = False
        if operators.numeric_range is not None and profile.has_measurements:
            has_relevant = True
        if operators.formula is not None and profile.has_formulas:
            has_relevant = True
        if operators.unit_match is not None and profile.has_measurements:
            has_relevant = True
        if operators.quality_filter is not None and profile.has_measurements:
            has_relevant = True
        use_scientific = has_relevant
        if not has_relevant:
            reasons.append("scientific skipped (operators active but corpus lacks matching data)")
    elif connector_has_scientific and not operators.is_active():
        reasons.append("scientific skipped (no operators in query)")

    # --- Quality filter decision ---
    # Apply the quality filter whenever the corpus actually carries quality
    # information AND the scientific branch is about to run. This hides
    # BAD/MISSING rows by default without requiring the user to specify
    # the filter manually.
    apply_quality_filter = False
    if use_scientific and profile.has_quality_info:
        # Only auto-apply if the corpus has at least some non-good flags;
        # if everything is already GOOD there's no work for the filter to do.
        q = profile.quality_summary
        if q is not None and q.acceptable_ratio < 1.0:
            apply_quality_filter = True
            reasons.append(
                f"quality filter enabled (corpus has "
                f"{q.total - q.acceptable_count} non-acceptable rows)"
            )

    # --- Targeted concepts from schema ---
    targeted: list[str] = []
    if profile.has_metadata_schema:
        schema = profile.metadata_schema
        assert schema is not None  # for type checker
        # If the query mentions a recognised scientific concept, prioritise it.
        q_lower = query.lower()
        concept_keywords = {
            "temperature": ("temperature", "temp ", "celsius", "fahrenheit", "kelvin"),
            "pressure": ("pressure", "kpa", "hpa", "atm", "bar"),
            "humidity": ("humidity", "humid", "dew point"),
            "wind_speed": ("wind speed", "wind velocity", "km/h", "m/s"),
            "precipitation": ("precipitation", "rain", "snow"),
        }
        for concept, keywords in concept_keywords.items():
            if concept in schema.concepts and any(k in q_lower for k in keywords):
                targeted.append(concept)
        if targeted:
            reasons.append(f"targeting schema concepts: {', '.join(targeted)}")

    if not reasons:
        reasons.append("all applicable branches activated")

    return BranchPlan(
        use_lexical=use_lexical,
        use_vector=use_vector,
        use_graph=use_graph,
        use_scientific=use_scientific,
        reasoning="; ".join(reasons),
        apply_quality_filter=apply_quality_filter,
        targeted_concepts=tuple(targeted),
        schema_richness=profile.richness_score,
        average_quality=profile.average_quality_score,
    )
